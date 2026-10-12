#!/bin/sh
# Read CC Switch without persisting credentials; keep existing application processes intact.
set -eu
SENTINEL_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$SENTINEL_ROOT"
exec .venv/bin/python - "$@" <<'PY'
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import time
import tomllib
from urllib.parse import urlparse
from uuid import uuid4

parser = argparse.ArgumentParser(description='SentinelAI: read-only CC Switch Deepseek bridge')
parser.add_argument('command', choices=['check', 'probe', 'workflow', 'serve'])
parser.add_argument('--port', type=int, default=8001)
args = parser.parse_args()
sys.path.insert(0, str(Path('backend').resolve()))
logging.disable(logging.CRITICAL)


def output(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


def configure():
    from app.config import ModelConfig
    db = Path.home() / '.cc-switch' / 'cc-switch.db'
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as connection:
        matches = connection.execute('SELECT settings_config FROM providers WHERE lower(name)=?', ('deepseek',)).fetchall()
    if len(matches) != 1:
        raise ValueError('Expected exactly one Deepseek provider')
    settings = json.loads(matches[0][0])
    config = tomllib.loads(settings['config'])
    provider = config['model_providers'][config['model_provider']]
    key = settings['auth']['OPENAI_API_KEY']
    base = provider['base_url'].rstrip('/')
    parsed = urlparse(base)
    model = config['model']
    if not key or not model or parsed.scheme != 'https' or parsed.hostname != 'api.deepseek.com' or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/v1'):
        raise ValueError('Provider requires manual endpoint validation')
    values = {'OPENAI_API_KEY': key, 'OPENAI_BASE_URL': base, 'OPENAI_MODEL': model}
    # Import above loads project dotenv files without overriding the environment.
    for name, value in values.items():
        if os.getenv(name) and os.environ[name] != value:
            raise ValueError('Existing project model configuration conflicts; nothing overwritten')
    for name, value in values.items():
        os.environ.setdefault(name, value)
    return ModelConfig.load(), provider.get('wire_api', 'unspecified')


async def probe(config):
    import httpx
    started = time.monotonic()
    result = {'step': 'minimum_request', 'mode': 'live', 'configured_model': config.model,
              'http_status': None, 'response_model': None, 'usage': None, 'passed': False, 'retries': 0}
    try:
        payload = {'model': config.model, 'messages': [{'role': 'user', 'content': '仅返回 SENTINELAI_DEEPSEEK_OK，不要添加其他内容。'}],
                   'stream': False}
        if config.max_output_tokens is not None:
            payload['max_tokens'] = config.max_output_tokens
        async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=10), follow_redirects=False) as client:
            response = await client.post(config.base_url.rstrip('/') + '/chat/completions',
                headers={'Authorization': 'Bearer ' + config.api_key},
                json=payload)
        result['http_status'] = response.status_code
        data = response.json()
        if response.is_success:
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            result.update(response_model=data.get('model'), usage=data.get('usage'),
                          marker_matches=isinstance(content, str) and content.strip() == 'SENTINELAI_DEEPSEEK_OK',
                          finish_reason=data.get('choices', [{}])[0].get('finish_reason'))
            result['passed'] = result['marker_matches'] and result['finish_reason'] != 'length'
        else:
            result['error'] = {'code': 'HTTP_' + str(response.status_code), 'message': 'Provider rejected request; response text omitted'}
    except Exception as exc:
        from app.config import error_info
        result['error'] = error_info(exc)
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    output(result)
    return result['passed']


async def workflow(config):
    # Observe the transport actually used by the installed SDK, without request logging.
    import openai._base_client as sdk_transport
    transport = getattr(sdk_transport, 'httpx2', None) or getattr(sdk_transport, 'httpx')
    from unittest.mock import patch
    from app import engine
    from app.main import load_demo_documents
    from app.workflow import AGENTS, run_workflow
    # Acceptance performs at most one request per stage; preserve user's persistent settings.
    os.environ['MODEL_MAX_RETRIES'] = '0'
    run = {'id': str(uuid4()), 'question': '未来 30 天如何降低关键供应商的交付风险，同时控制采购成本？',
           'mode': 'live', 'status': 'queued', 'events': [], 'report': None,
           'agents': [{**a, 'status': 'queued', 'output': ''} for a in AGENTS]}
    http_records, contexts = [], []
    original_send = transport.AsyncClient.send
    original_context = engine.context_for

    def record_context(current, stage, previous):
        text = original_context(current, stage, previous)
        parsed = json.loads(text)
        expected_previous = previous
        if stage == 'risk':
            from app.reviewer_context import review_inputs
            expected_previous = review_inputs(current, previous)['previous_outputs']
        elif stage == 'research':
            from app.research_context import research_inputs
            expected_previous = research_inputs(current, previous)['previous_outputs']
        contexts.append({'stage': stage, 'upstream_stages': list(previous),
                         'context_equal': parsed['previous_outputs'] == expected_previous,
                         'context_projection': 'reviewer_compact' if stage == 'risk' else 'research_compact' if stage == 'research' else 'full',
                         'evidence_count': len(parsed['untrusted_evidence'])})
        return text

    async def record_send(client, request, *positional, **kwargs):
        stage = next((a['id'] for a in run['agents'] if a['status'] in ('running', 'retrying')), None)
        start = time.monotonic()
        record = {'stage': stage, 'http_status': None}
        try:
            response = await original_send(client, request, *positional, **kwargs)
            record['http_status'] = response.status_code
            await response.aread()
            if response.is_success:
                body = response.json()
                record.update(response_model=body.get('model'), usage=body.get('usage'),
                              finish_reason=body.get('choices', [{}])[0].get('finish_reason'))
            return response
        finally:
            record['elapsed_seconds'] = round(time.monotonic() - start, 3)
            http_records.append(record)
            output({'step': 'workflow_http', **record})

    with patch.object(transport.AsyncClient, 'send', record_send), patch.object(engine, 'context_for', record_context):
        await run_workflow(run, load_demo_documents())
    result = {'step': 'workflow_result', 'mode': run['mode'], 'run_id': run['id'],
              'configured_model': config.model, 'status': run['status'], 'elapsed_seconds': run.get('elapsed_seconds'),
              'error': run.get('error_details'), 'report_generated': bool(run.get('report')),
              'evidence_count': len(run.get('evidence', [])), 'review': run.get('review'),
              'budget': run.get('budget'), 'contexts': contexts,
              'agents': [{k: a.get(k) for k in ('id', 'status', 'model', 'attempts', 'retry_attempt', 'first_failure', 'attempt_history', 'elapsed_seconds', 'tokens', 'response_metadata', 'request_timeout_seconds', 'review_context_stats', 'research_context_stats', 'error_details')} for a in run['agents']],
              'actual_http_calls': http_records, 'approval_operations': 0,
              'passed': bool(run.get('report')) and run['status'] in ('completed', 'waiting_approval')}
    from app.config import public_data
    output(public_data(result))
    return result['passed']


try:
    config, source_protocol = configure()
except Exception as exc:
    output({'step': 'configuration', 'configured': False, 'error_type': type(exc).__name__,
            'message': 'Could not safely load unique Deepseek service, or existing config conflicts. No credentials persisted.'})
    sys.exit(2)

output({'step': 'configuration', 'configured': config.ready, 'source': 'CC Switch / Deepseek',
        'source_protocol': source_protocol, 'project_protocol': 'Chat Completions',
        'model': config.model, 'provider_host': urlparse(config.base_url).hostname, 'credential_persisted': False})
if args.command == 'probe':
    sys.exit(0 if asyncio.run(probe(config)) else 1)
elif args.command == 'workflow':
    sys.exit(0 if asyncio.run(workflow(config)) else 1)
elif args.command == 'serve':
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=args.port, access_log=False)
PY
