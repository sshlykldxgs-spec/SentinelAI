import asyncio
import hashlib
import json
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from urllib.parse import urlparse
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .documents import extract_document, read_upload
from .workflow import AGENTS, now, run_workflow, supply_metrics
from .config import ModelConfig, configure_runtime_model, error_info, public_data
from .evidence import source_units
from .events import emit

ORIGINS = {'http://localhost:5173', 'http://127.0.0.1:5173'}

ROOT = Path(__file__).resolve().parents[2]
DEMO_FILES = [ROOT / "demo" / "suppliers.csv", ROOT / "demo" / "brief.txt"]
DEFAULT_QUESTION = "未来 30 天如何降低关键供应商的交付风险，同时控制采购成本？"

@asynccontextmanager
async def lifespan(app):
    app.state.model_config_status = ModelConfig.load().public()
    yield
    for task in list(tasks):
        task.cancel()
    if tasks:
        await asyncio.gather(*list(tasks), return_exceptions=True)


app = FastAPI(title="SentinelAI Intelligent Operations Cockpit", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

documents: dict[str, dict] = {}
runs: dict[str, dict] = {}
tasks: set[asyncio.Task] = set()
sessions: dict[str, dict] = {}
idempotency: dict[str, str] = {}
MAX_CONCURRENT_RUNS = 3


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError):
    if request.url.path.startswith('/api/model/'):
        # FastAPI's default errors can echo submitted secret inputs.
        return JSONResponse(status_code=422, content={'detail': '模型配置格式无效，请检查服务类型、地址、模型名称和Token上限。'})
    from fastapi.exception_handlers import request_validation_exception_handler
    return await request_validation_exception_handler(request, exc)


def launch(run: dict, selected: list[dict]):
    task = asyncio.create_task(run_workflow(run, selected))
    tasks.add(task)
    task.add_done_callback(tasks.discard)


def check_origin(request: Request):
    if request.headers.get('origin') not in ORIGINS:
        raise HTTPException(403, '仅允许受信任的本机工作台发起此操作')


def reviewer(request: Request):
    check_origin(request)
    session = sessions.get(request.cookies.get('sentinel_session', ''))
    if not session or session['expires_at'] < time.time() or session['role'] != 'reviewer':
        raise HTTPException(403, '需要有效的本机审批会话')
    return session


def model_admin(request: Request):
    reviewer(request)
    if request.client.host not in ('127.0.0.1', '::1', 'testclient'):
        raise HTTPException(403, '模型配置只允许本机操作')


class RunRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1000)
    document_ids: list[str] = Field(default_factory=list, max_length=12)
    mode: str = "demo"


def public_document(doc: dict) -> dict:
    return public_data({key: doc[key] for key in ("id", "name", "type", "size", "created_at", "demo")})


def internal_run(run_id: str):
    if run_id not in runs:
        raise HTTPException(404, "运行记录不存在")
    return runs[run_id]


def load_demo_documents() -> list[dict]:
    loaded = []
    for path in DEMO_FILES:
        existing = next((doc for doc in documents.values() if doc["name"] == path.name and doc["demo"]), None)
        if existing:
            loaded.append(existing)
            continue
        data = path.read_bytes()
        text, rows = extract_document(path.name, data)
        doc = {
            "id": str(uuid4()), "name": path.name, "type": path.suffix[1:],
            "size": len(data), "created_at": now(), "demo": True,
            "text": text, "rows": rows,
            "units": source_units(path.name, data, text, rows),
        }
        documents[doc["id"]] = doc
        loaded.append(doc)
    return loaded


@app.get("/api/health")
def health():
    return public_data({"status": "ok", "autogen_available": ModelConfig.load().ready, 'model': ModelConfig.load().public()})


@app.get("/api/bootstrap")
def bootstrap():
    demo_docs = load_demo_documents()
    return public_data({
        "documents": [public_document(doc) for doc in documents.values()],
        "runs": list(reversed(list(runs.values()))),
        "demo_document_ids": [doc["id"] for doc in demo_docs],
        "default_question": DEFAULT_QUESTION,
        "metrics": supply_metrics(demo_docs),
        "live_available": ModelConfig.load().ready,
        'model_config': ModelConfig.load().public(),
        'approvals': [a for r in runs.values() for a in r.get('approvals', [])],
    })


@app.post("/api/files", status_code=201)
async def upload_files(files: list[UploadFile] = File(...)):
    if len(files) > 12:
        raise HTTPException(400, "每次最多上传 12 个文件")
    created = []
    staged = []
    for upload in files:
        text, rows, size = await read_upload(upload)
        await upload.seek(0)
        data = await upload.read()
        doc = {
            "id": str(uuid4()), "name": Path(upload.filename or "unknown").name,
            "type": Path(upload.filename or "").suffix.lower().lstrip("."),
            "size": size, "created_at": now(), "demo": False,
            "text": text, "rows": rows,
            'units': source_units(upload.filename or '', data, text, rows),
        }
        staged.append(doc)
        created.append(public_document(doc))
        await upload.close()
    for doc in staged:
        documents[doc['id']] = doc
    return {"documents": created}


@app.post("/api/runs", status_code=201)
async def create_run(request: RunRequest, http_request: Request):
    from .config import safe_text
    if len(request.question.strip()) < 5:
        raise HTTPException(422, "决策问题至少需要 5 个非空字符")
    if request.mode not in ("demo", "live", 'replay'):
        raise HTTPException(400, "模式仅支持 demo、live、replay")
    if request.mode == "live" and not ModelConfig.load().ready:
        raise HTTPException(400, "请先配置 OPENAI_API_KEY 再启用 AutoGen 模式")
    if not request.document_ids:
        raise HTTPException(400, "请选择至少一份资料")
    selected = []
    for doc_id in dict.fromkeys(request.document_ids):
        if doc_id not in documents:
            raise HTTPException(404, f"资料不存在：{doc_id}")
        selected.append(documents[doc_id])
    key = http_request.headers.get('idempotency-key')
    if key:
        key = hashlib.sha256(f"{key}:{request.model_dump_json()}".encode('utf-8')).hexdigest()
        if key in idempotency:
            return public_data(runs[idempotency[key]])
    if sum(r['status'] in ('queued', 'running') for r in runs.values()) >= MAX_CONCURRENT_RUNS:
        raise HTTPException(429, '最多同时执行 3 个任务，请稍后重试')
    run = {
        "id": str(uuid4()), "question": safe_text(request.question.strip()), "mode": request.mode,
        "document_ids": [doc["id"] for doc in selected],
        "status": "queued", "created_at": now(), "started_at": None,
        "completed_at": None, "error": None, "report": None,
        'events': [], 'approvals': [], 'model': ModelConfig.load().model if request.mode == 'live' else 'rules-v2' if request.mode == 'demo' else 'autogen-replay',
        "agents": [{**agent, "status": "queued", "output": "", "started_at": None, "completed_at": None} for agent in AGENTS],
    }
    runs[run["id"]] = run
    if key:
        idempotency[key] = run['id']
    emit(run, 'task.created', payload={'mode': run['mode']})
    launch(run, selected)
    return public_data(run)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return public_data(internal_run(run_id))


@app.get("/api/runs/{run_id}/report", response_class=PlainTextResponse)
def download_report(run_id: str):
    run = runs.get(run_id)
    if not run or not run["report"]:
        raise HTTPException(404, "报告尚未生成")
    return PlainTextResponse(
        public_data(run["report"]), media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sentinelai-report.md"'},
    )


@app.get('/api/runs/{run_id}/events')
async def stream_events(run_id: str, request: Request, after: int = 0):
    run = internal_run(run_id)
    try:
        cursor = max(after, int(request.headers.get('last-event-id', '0')))
    except ValueError:
        raise HTTPException(400, '事件游标必须为整数')
    if cursor < 0 or cursor > len(run['events']):
        raise HTTPException(400, '事件游标无效')

    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            events = run['events'][cursor:]
            for event in events:
                cursor = event['event_id']
                data = json.dumps(public_data({'event': event, 'run': run}), ensure_ascii=False)
                yield f"id: {cursor}\ndata: {data}\n\n"
            if run['status'] not in ('queued', 'running') and cursor == len(run['events']):
                return
            yield ': heartbeat\n\n'
            await asyncio.sleep(0.4)
    return StreamingResponse(stream(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.post('/api/runs/{run_id}/retry', status_code=201)
async def retry_run(run_id: str, request: Request):
    previous = internal_run(run_id)
    if previous['status'] != 'failed':
        raise HTTPException(409, '仅失败任务可重跑')
    new = await create_run(RunRequest(question=previous['question'], document_ids=previous['document_ids'], mode=previous['mode']), request)
    runs[new['id']]['parent_run_id'] = previous['id']
    return public_data(runs[new['id']])


@app.post('/api/session')
def local_session(request: Request, response: Response):
    check_origin(request)
    if request.client.host not in ('127.0.0.1', '::1', 'testclient'):
        raise HTTPException(403, '审批会话仅用于本机 MVP')
    token = secrets.token_urlsafe(32)
    session = {'role': 'reviewer', 'actor': 'local-reviewer', 'expires_at': time.time() + 3600}
    sessions[token] = session
    response.set_cookie('sentinel_session', token, httponly=True, samesite='strict', max_age=3600)
    return {'role': session['role'], 'scope': 'local-only', 'expires_in': 3600}


class ApprovalDecision(BaseModel):
    decision: str
    note: str = Field(min_length=3, max_length=1000)


@app.get('/api/approvals')
def approvals():
    return public_data([a for run in runs.values() for a in run.get('approvals', [])])


@app.post('/api/approvals/{approval_id}')
def decide(approval_id: str, body: ApprovalDecision, request: Request):
    actor = reviewer(request)
    if len(body.note.strip()) < 3:
        raise HTTPException(422, '审批意见至少 3 个非空字符')
    if body.decision not in ('approved', 'rejected', 'needs_evidence'):
        raise HTTPException(422, '审批操作无效')
    for run in runs.values():
        for action in run.get('approvals', []):
            if action['id'] != approval_id:
                continue
            if action['status'] not in ('pending', 'needs_evidence'):
                raise HTTPException(409, '此事项已经完成审批')
            ids = {e['evidence_id'] for e in run.get('evidence', [])}
            if body.decision == 'approved' and (action['status'] == 'needs_evidence' or not action['evidence_ids'] or any(ref not in ids for ref in action['evidence_ids'])):
                raise HTTPException(409, '证据不足，补充资料并重新分析后方可批准')
            from .config import safe_text
            action['status'] = body.decision
            action['audit'].append({'actor': actor['actor'], 'decision': body.decision, 'note': safe_text(body.note), 'timestamp': now()})
            if all(a['status'] in ('approved', 'rejected') for a in run['approvals']):
                run['status'] = 'completed'
                run['agents'][-1]['status'] = 'completed'
            emit(run, 'review.required', 'action', {'approval_id': approval_id, 'decision': body.decision})
            from .engine import report
            run['report'] = report(run, [documents[i] for i in run['document_ids']])
            return public_data(action)
    raise HTTPException(404, '审批事项不存在')


@app.get('/api/model/config')
def model_config():
    return public_data(ModelConfig.load().public())


class ModelSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    service_type: str = 'openai_compatible'
    base_url: str = Field(min_length=1, max_length=500)
    api_key: SecretStr = SecretStr('')
    model: str = Field(min_length=1, max_length=160)
    max_output_tokens: int = Field(default=0, ge=0, le=1000000)


@app.post('/api/model/config')
def save_model_config(body: ModelSettings, request: Request):
    model_admin(request)
    if any(run['status'] in ('queued', 'running') for run in runs.values()):
        raise HTTPException(409, '任务正在执行，完成后才能更改模型配置')
    if body.service_type != 'openai_compatible':
        raise HTTPException(422, '仅支持OpenAI Compatible Chat Completions')
    base_url = body.base_url.strip().rstrip('/')
    parsed = urlparse(base_url)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or
        parsed.scheme not in ('https', 'http') or
        (parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'))):
        raise HTTPException(422, 'Base URL无效：使用HTTPS服务地址或本机HTTP地址，不得含凭据、查询参数或片段')
    if parsed.path.endswith(('/chat/completions', '/responses')):
        raise HTTPException(422, 'Base URL应为API根地址，例如 https://api.deepseek.com/v1')
    model = body.model.strip()
    if not model or any(ord(char) < 32 for char in model):
        raise HTTPException(422, '模型名称无效')
    key = body.api_key.get_secret_value().strip()
    if len(key) > 8192 or any(ord(char) < 32 for char in key):
        raise HTTPException(422, 'API Key格式无效')
    current = ModelConfig.load()
    if not key:
        if base_url != current.base_url.rstrip('/'):
            raise HTTPException(422, '更换服务地址必须重新输入自己的API Key')
        key = current.api_key
    candidate = replace(current, model=model, base_url=base_url, api_key=key, max_output_tokens=body.max_output_tokens or None)
    if not candidate.ready:
        raise HTTPException(422, '请填写有效的API Key，不要使用示例占位符')
    configure_runtime_model(candidate.model, candidate.base_url, candidate.api_key, candidate.max_output_tokens)
    return {'saved': True, 'storage': 'process_memory', 'config': public_data(ModelConfig.load().public())}


def connection_test_error(exc: Exception) -> dict:
    status = getattr(exc, 'status_code', None)
    if status in (401, 403):
        return {'code': 'API_KEY_ERROR', 'message': 'API Key错误或无权访问该模型，请检查自己的凭据。'}
    if status == 404:
        return {'code': 'MODEL_OR_BASE_URL_ERROR', 'message': '模型不存在或Base URL路径错误，请核对服务文档。'}
    if status in (400, 422):
        return {'code': 'MODEL_REQUEST_ERROR', 'message': '模型名称或接口参数不受支持，请确认Chat Completions兼容性。'}
    info = error_info(exc)
    if info['code'] == 'MODEL_CONNECTION':
        return {'code': 'NETWORK_ERROR', 'message': '网络连接失败，请检查网络及Base URL。'}
    return {'code': info['code'], 'message': info['message']}


def connection_response_diagnostics(body, status_code: int) -> dict:
    diagnostic = {'upstream_http_status': status_code, 'top_level_keys': [], 'other_top_level_key_count': 0,
                  'choices_count': None, 'choice_keys': [], 'other_choice_key_count': 0,
                  'finish_reason_actual': None, 'message_present': False, 'content_present': False,
                  'content_length': None, 'parsed_text_empty': None}
    if not isinstance(body, dict):
        return diagnostic
    top_keys = {'id', 'object', 'created', 'model', 'choices', 'usage', 'system_fingerprint',
                'service_tier', 'error', 'output', 'output_text', 'text'}
    diagnostic['top_level_keys'] = sorted(top_keys.intersection(body))
    diagnostic['other_top_level_key_count'] = len(body.keys() - top_keys)
    choices = body.get('choices')
    if not isinstance(choices, list):
        return diagnostic
    diagnostic['choices_count'] = len(choices)
    if not choices or not isinstance(choices[0], dict):
        return diagnostic
    choice = choices[0]
    choice_keys = {'index', 'message', 'finish_reason', 'logprobs'}
    diagnostic['choice_keys'] = sorted(choice_keys.intersection(choice))
    diagnostic['other_choice_key_count'] = len(choice.keys() - choice_keys)
    reason = choice.get('finish_reason')
    diagnostic['finish_reason_actual'] = reason if reason in ('stop', 'length', 'content_filter', 'tool_calls', 'function_calls', 'end_turn') else 'other'
    diagnostic['message_present'] = 'message' in choice
    message = choice.get('message')
    if isinstance(message, dict):
        diagnostic['content_present'] = 'content' in message
        content = message.get('content')
        diagnostic['content_length'] = len(content) if isinstance(content, str) else None
    return diagnostic


def observe_connection_response(client, diagnostic: dict) -> None:
    # This hook is attached only to the connection-test client, never the Live executor.
    transport = getattr(getattr(client, '_client', None), '_client', None)
    hooks = getattr(transport, 'event_hooks', None)
    if not isinstance(hooks, dict) or not isinstance(hooks.get('response'), list):
        return

    async def observe(response):
        await response.aread()
        try:
            body = response.json()
        except ValueError:
            body = None
        diagnostic.update(connection_response_diagnostics(body, response.status_code))

    hooks['response'].append(observe)


@app.post('/api/model/test')
async def test_model(request: Request):
    model_admin(request)
    config = replace(ModelConfig.load(), sdk_retries=0, max_output_tokens=64)
    if not config.ready:
        raise HTTPException(400, '模型凭据未配置完整')
    client = None
    diagnostic = {}
    started = time.monotonic()
    try:
        client = config.client()
        observe_connection_response(client, diagnostic)
        from autogen_agentchat.agents import AssistantAgent
        from .output_validation import CompletionObserver
        observation = {}
        result = await asyncio.wait_for(AssistantAgent(name='connection_test', model_client=CompletionObserver(client, observation),
                    system_message='只回复 OK。').run(task='连接测试'), config.timeout)
        content = getattr(result.messages[-1], 'content', None) if result.messages else None
        finish_reason = observation.get('response_metadata', {}).get('finish_reason')
        diagnostic['parsed_finish_reason'] = finish_reason
        diagnostic['parsed_text_empty'] = not isinstance(content, str) or not content.strip()
        if not isinstance(content, str) or not content.strip() or finish_reason != 'stop':
            return {'ok': False, 'model': config.model, 'elapsed_seconds': round(time.monotonic() - started, 3),
                    'error': {'code': 'UNEXPECTED_RESPONSE', 'message': '接口未返回正常结束的非空文本响应；请核对模型或接口兼容性。'},
                    'diagnostic': diagnostic}
        return {'ok': True, 'model': config.model, 'elapsed_seconds': round(time.monotonic() - started, 3),
                'message': '模型连接成功。',
                'response_summary': '收到非空文本响应并正常结束；五阶段结构化工作流需另行验收。',
                'diagnostic': diagnostic}
    except Exception as exc:
        return {'ok': False, 'model': config.model, 'elapsed_seconds': round(time.monotonic() - started, 3),
                'error': connection_test_error(exc), 'diagnostic': diagnostic}
    finally:
        if client:
            await client.close()
