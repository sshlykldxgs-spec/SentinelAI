import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env', override=False)
load_dotenv(ROOT / 'backend' / '.env', override=False)

# UI overrides are local to this process; never written to environment or disk.
_runtime_model: dict = {}
_runtime_redactions: set[str] = set()


def configure_runtime_model(model: str, base_url: str, api_key: str, max_output_tokens: int | None):
    if api_key:
        _runtime_redactions.add(api_key)
    _runtime_model.clear()
    _runtime_model.update(model=model, base_url=base_url, api_key=api_key, max_output_tokens=max_output_tokens)


def bounded(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def token_limit(name: str) -> int | None:
    value = os.getenv(name, '0').strip()
    try:
        limit = int(value)
    except ValueError:
        raise ValueError(f'{name} must be an integer; use 0 to disable') from None
    if limit < 0:
        raise ValueError(f'{name} must be nonnegative')
    return limit or None


def stage_timeout(name: str, default: int) -> int:
    if name in os.environ:
        return bounded(name, default, 1, 120)
    if 'MODEL_TIMEOUT_SECONDS' in os.environ:
        return bounded('MODEL_TIMEOUT_SECONDS', default, 1, 120)
    return default


@dataclass(frozen=True)
class ModelConfig:
    model: str
    base_url: str
    api_key: str
    timeout: int
    retries: int
    max_output_tokens: int | None
    task_timeout: int
    token_budget: int | None
    reviewer_timeout: int | None = None
    research_timeout: int | None = None
    planner_timeout: int | None = None
    analyst_timeout: int | None = None
    action_timeout: int | None = None
    sdk_retries: int = 0

    @classmethod
    def load(cls):
        config = cls(
            os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
            os.getenv('OPENAI_API_KEY', '').strip(),
            bounded('MODEL_TIMEOUT_SECONDS', 45, 1, 120),
            bounded('MODEL_MAX_RETRIES', 1, 0, 1),
            token_limit('MODEL_MAX_OUTPUT_TOKENS'),
            bounded('TASK_TIMEOUT_SECONDS', 300, 5, 600),
            token_limit('TASK_TOKEN_BUDGET'),
            stage_timeout('REVIEWER_TIMEOUT_SECONDS', 120),
            stage_timeout('RESEARCH_TIMEOUT_SECONDS', 120),
            stage_timeout('PLANNER_TIMEOUT_SECONDS', 60),
            stage_timeout('ANALYST_TIMEOUT_SECONDS', 90),
            stage_timeout('ACTION_TIMEOUT_SECONDS', 120),
            bounded('MODEL_SDK_MAX_RETRIES', bounded('MODEL_MAX_RETRIES', 1, 0, 1), 0, 1),
        )
        return replace(config, **_runtime_model) if _runtime_model else config

    @property
    def ready(self):
        parsed = urlparse(self.base_url)
        return bool(self.model and self.api_key and not self.api_key.lower().startswith(('your-', 'sk-test', 'replace', 'test-key')) and parsed.scheme in ('https', 'http') and parsed.hostname and not parsed.username and not parsed.password and not parsed.query)

    def public(self):
        parsed = urlparse(self.base_url)
        return {'model': self.model, 'provider': parsed.hostname or 'invalid', 'configured': self.ready,
                'base_url': self.base_url if parsed.scheme in ('http', 'https') and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment else '',
                'configuration_source': 'process_memory' if _runtime_model else 'environment',
                'timeout_seconds': self.timeout, 'max_retries': min(max(self.retries, 0), 1),
                'sdk_max_retries': min(max(self.sdk_retries, 0), 1),
                'max_output_tokens': self.max_output_tokens, 'task_timeout_seconds': self.task_timeout,
                'token_budget': self.token_budget,
                'planner_timeout_seconds': self.timeout_for('planner'),
                'research_timeout_seconds': self.timeout_for('research'),
                'analyst_timeout_seconds': self.timeout_for('analyst'),
                'reviewer_timeout_seconds': self.timeout_for('risk'),
                'action_timeout_seconds': self.timeout_for('action'),
                'protocol': 'OpenAI Chat Completions'}

    def timeout_for(self, stage: str) -> int:
        limits = {'planner': self.planner_timeout, 'research': self.research_timeout,
                  'analyst': self.analyst_timeout, 'risk': self.reviewer_timeout,
                  'action': self.action_timeout}
        limit = limits.get(stage)
        return limit if limit is not None else self.timeout

    def client(self):
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        output_options = {'max_tokens': self.max_output_tokens} if self.max_output_tokens is not None else {}
        return OpenAIChatCompletionClient(
            model=self.model, api_key=self.api_key, base_url=self.base_url,
            timeout=self.timeout, max_retries=min(max(self.sdk_retries, 0), 1), **output_options,
            model_info={'vision': False, 'function_calling': False, 'json_output': False,
                        'family': 'unknown', 'structured_output': False},
        )


def safe_text(value: str) -> str:
    for secret in (os.getenv('OPENAI_API_KEY', ''), *_runtime_redactions, _runtime_model.get('api_key', '')):
        if secret:
            value = value.replace(secret, '[REDACTED]')
    value = re.sub(r'(?i)(bearer\s+|authorization\s*[:=]\s*)\S+', '[REDACTED]', value)
    value = re.sub(r'\bsk-[A-Za-z0-9_-]{8,}', '[REDACTED]', value)
    return value


def public_data(value):
    if isinstance(value, str):
        return safe_text(value)
    if isinstance(value, dict):
        return {safe_text(str(key)): public_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [public_data(item) for item in value]
    return value


def error_info(exc: Exception) -> dict:
    from .output_validation import OutputValidationError

    if isinstance(exc, OutputValidationError):
        return {'code': 'INVALID_OUTPUT', 'message': '模型输出未通过结构或证据校验。',
                'retryable': exc.reason not in ('truncated_response', 'unsupported_completion', 'nontext_response'),
                'reason': exc.reason, 'schema_issues': exc.issues}
    name = type(exc).__name__
    status = getattr(exc, 'status_code', None)
    if isinstance(exc, TimeoutError) or 'Timeout' in name:
        return {'code': 'MODEL_TIMEOUT', 'message': '模型请求或任务预算超时。', 'retryable': True}
    if status in (401, 403) or 'Authentication' in name:
        return {'code': 'MODEL_AUTH', 'message': '模型服务认证失败，请检查后端凭据。', 'retryable': False}
    if status == 429 or 'RateLimit' in name:
        return {'code': 'MODEL_RATE_LIMIT', 'message': '模型服务限流。', 'retryable': True, 'http_status': status}
    if status and status >= 500:
        return {'code': 'MODEL_SERVER', 'message': '模型服务暂不可用。', 'retryable': status in (502, 503, 504), 'http_status': status}
    if status and 400 <= status < 500:
        return {'code': 'MODEL_REQUEST', 'message': '模型请求参数或服务条件不满足。', 'retryable': False, 'http_status': status}
    if isinstance(exc, ConnectionError) or 'Connection' in name or 'ConnectError' in name:
        return {'code': 'MODEL_CONNECTION', 'message': '模型连接中断。', 'retryable': True}
    if isinstance(exc, ValueError):
        return {'code': 'INVALID_OUTPUT', 'message': '模型输出未通过结构或证据校验。', 'retryable': True}
    return {'code': 'MODEL_ERROR', 'message': '模型执行失败；未回退到演示模式。', 'retryable': False}
