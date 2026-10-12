import json
import re

from pydantic import ValidationError

from .contracts import StageOutput


class OutputValidationError(ValueError):
    def __init__(self, reason: str, issues: list[dict] | None = None):
        # Never attach model content, validation inputs or the raw exception.
        super().__init__(reason)
        self.reason = reason
        self.issues = issues or []


def output_schema(stage: str) -> dict:
    schema = StageOutput.model_json_schema()
    if stage == 'planner':
        conditions = schema['properties']['acceptance_conditions']
        conditions.pop('default', None)
        conditions['minItems'] = 1
        conditions['items']['minLength'] = 1
        schema['required'] = [*schema['required'], 'acceptance_conditions']
    return schema


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OutputValidationError('duplicate_json_field')
        result[key] = value
    return result


def _reject_constant(value):
    raise OutputValidationError('nonfinite_json_number')


def parse_output(raw, stage: str, finish_reason: str | None = None) -> dict:
    if finish_reason == 'length':
        raise OutputValidationError('truncated_response')
    if finish_reason in ('content_filter', 'function_calls'):
        raise OutputValidationError('unsupported_completion')
    if not isinstance(raw, str):
        raise OutputValidationError('nontext_response')
    text = raw.strip()
    if not text:
        raise OutputValidationError('empty_response')
    # Only unwrap a complete single fence. Never search for a JSON fragment in prose.
    fenced = re.fullmatch(r'```(?:json)?[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```', text, re.IGNORECASE)
    if fenced:
        text = fenced.group('body').strip()
    try:
        decoded = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except json.JSONDecodeError:
        raise OutputValidationError('invalid_json') from None
    if not isinstance(decoded, dict):
        raise OutputValidationError('nonobject_json')
    try:
        data = StageOutput.model_validate_json(text).model_dump()
    except ValidationError as exc:
        allowed = set(StageOutput.model_fields) | {'text', 'kind', 'evidence_ids', 'metric_values',
                    'supplier', 'level', 'reason', 'title', 'owner', 'deadline', 'impact', 'requires_approval'}
        issues = [
            {'type': error['type'], 'path': [part if isinstance(part, int) or part in allowed else '<unknown_field>'
                                           for part in error['loc']]}
            for error in exc.errors(include_input=False, include_context=False, include_url=False)[:10]
        ]
        raise OutputValidationError('schema_mismatch', issues) from None
    if stage == 'planner' and (not data['acceptance_conditions'] or any(not item.strip() for item in data['acceptance_conditions'])):
        raise OutputValidationError('missing_planner_conditions', [{'type': 'nonempty_required', 'path': ['acceptance_conditions']}])
    return data


class CompletionObserver:
    """Delegate the model API and retain only non-content completion metadata."""

    def __init__(self, client, agent: dict, request_timeout: int | None = None):
        self.client = client
        self.agent = agent
        self.request_timeout = request_timeout

    def __getattr__(self, name):
        return getattr(self.client, name)

    async def create(self, *args, **kwargs):
        if self.request_timeout is not None:
            kwargs['extra_create_args'] = {**kwargs.get('extra_create_args', {}), 'timeout': self.request_timeout}
        result = await self.client.create(*args, **kwargs)
        reason = getattr(result, 'finish_reason', None)
        known = {'stop', 'length', 'content_filter', 'function_calls', 'unknown'}
        self.agent['response_metadata'] = {'finish_reason': reason if reason in known else 'unknown'}
        return result
