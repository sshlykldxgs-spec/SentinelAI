import asyncio
import json
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import openai._base_client as sdk_transport
from fastapi.testclient import TestClient
from openai import AuthenticationError, NotFoundError
from autogen_ext.models.replay import ReplayChatCompletionClient

from app import config as config_module
from app.config import ModelConfig, safe_text
from app.main import app, connection_response_diagnostics, observe_connection_response, runs
from app.contracts import StageOutput
from app.engine import demo_structure
from app.evidence import make_evidence
from app.main import load_demo_documents
from app.workflow import AGENTS, supply_metrics

ORIGIN = {'Origin': 'http://127.0.0.1:5173'}
CANARY = 'offline-ui-secret-canary'


class ModelConfigUITests(unittest.TestCase):
    def setUp(self):
        self.saved_runtime = dict(config_module._runtime_model)
        config_module._runtime_model.clear()
        self.saved_runs = dict(runs)
        runs.clear()
        self.env = patch.dict(os.environ, {'OPENAI_API_KEY': '', 'MODEL_MAX_RETRIES': '0', 'MODEL_SDK_MAX_RETRIES': '0'})
        self.env.start()

    def tearDown(self):
        config_module._runtime_model.clear()
        config_module._runtime_model.update(self.saved_runtime)
        runs.clear()
        runs.update(self.saved_runs)
        self.env.stop()

    def payload(self, **changes):
        return {'service_type': 'openai_compatible', 'base_url': 'https://api.deepseek.com/v1',
                'api_key': CANARY, 'model': 'offline-model', 'max_output_tokens': 0, **changes}

    def authorize(self, client):
        self.assertEqual(client.post('/api/session', headers=ORIGIN).status_code, 200)

    def test_configuration_requires_local_session_and_no_active_task(self):
        with TestClient(app) as client:
            self.assertEqual(client.post('/api/model/config', json=self.payload(), headers=ORIGIN).status_code, 403)
            self.authorize(client)
            runs['active'] = {'status': 'running'}
            self.assertEqual(client.post('/api/model/config', json=self.payload(), headers=ORIGIN).status_code, 409)
            self.assertFalse(ModelConfig.load().ready)

    def test_save_does_not_touch_environment_or_echo_key(self):
        original = os.environ['OPENAI_API_KEY']
        before = ModelConfig.load()
        with TestClient(app) as client, patch('app.config.ModelConfig.client') as factory:
            self.authorize(client)
            response = client.post('/api/model/config', json=self.payload(), headers=ORIGIN)
            self.assertEqual(response.status_code, 200)
            factory.assert_not_called()
            self.assertNotIn(CANARY, response.text)
            self.assertNotIn(CANARY, client.get('/api/bootstrap').text)
            self.assertEqual(client.get('/api/model/config').json()['configuration_source'], 'process_memory')
        self.assertEqual(os.environ['OPENAI_API_KEY'], original)
        after = ModelConfig.load()
        self.assertEqual(after.api_key, CANARY)
        for field in ('timeout', 'retries', 'sdk_retries', 'task_timeout', 'planner_timeout', 'research_timeout', 'reviewer_timeout', 'action_timeout'):
            self.assertEqual(getattr(before, field), getattr(after, field))
        self.assertNotIn(CANARY, safe_text('canary=' + CANARY))

    def test_endpoint_change_requires_reentering_key(self):
        with TestClient(app) as client:
            self.authorize(client)
            client.post('/api/model/config', json=self.payload(), headers=ORIGIN)
            same = client.post('/api/model/config', json=self.payload(api_key=''), headers=ORIGIN)
            self.assertEqual(same.status_code, 200)
            different = client.post('/api/model/config', json=self.payload(api_key='', base_url='https://other.invalid/v1'), headers=ORIGIN)
            self.assertEqual(different.status_code, 422)
            self.assertEqual(ModelConfig.load().base_url, 'https://api.deepseek.com/v1')

    def test_invalid_fields_and_url_do_not_echo_inputs(self):
        with TestClient(app) as client:
            self.authorize(client)
            for payload in [self.payload(api_key={'private': CANARY}), self.payload(extra_secret=CANARY),
                            self.payload(base_url='https://user:' + CANARY + '@invalid.test'),
                            self.payload(base_url='https://invalid.test/v1?token=' + CANARY),
                            self.payload(base_url='https://invalid.test/chat/completions'),
                            self.payload(api_key='replace-with-your-own-key')]:
                response = client.post('/api/model/config', json=payload, headers=ORIGIN)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn(CANARY, response.text)

    def test_previous_runtime_key_still_redacted_after_replacement(self):
        with TestClient(app) as client:
            self.authorize(client)
            client.post('/api/model/config', json=self.payload(), headers=ORIGIN)
            client.post('/api/model/config', json=self.payload(api_key='offline-replacement-canary'), headers=ORIGIN)
        self.assertNotIn(CANARY, safe_text('past-key=' + CANARY))

    def test_minimum_test_success_and_failure_are_explicit(self):
        from autogen_core.models import CreateResult, RequestUsage
        with TestClient(app) as client:
            self.authorize(client)
            client.post('/api/model/config', json=self.payload(), headers=ORIGIN)
            completion = CreateResult(content='OK', finish_reason='stop',
                                      usage=RequestUsage(prompt_tokens=1, completion_tokens=1), cached=False)
            replay = ReplayChatCompletionClient([completion])
            with patch('app.config.ModelConfig.client', return_value=replay):
                response = client.post('/api/model/test', headers=ORIGIN).json()
                self.assertTrue(response['ok'])
                self.assertEqual(response['model'], 'offline-model')
                self.assertIn('模型连接成功', response['message'])
                self.assertIn('需另行验收', response['response_summary'])
                self.assertIsInstance(response['elapsed_seconds'], float)
                self.assertEqual(len(replay.create_calls), 1)
            fake = SimpleNamespace(close=AsyncMock())
            for cls, status, code in [(AuthenticationError, 401, 'API_KEY_ERROR'), (NotFoundError, 404, 'MODEL_OR_BASE_URL_ERROR')]:
                error = cls('private request ' + CANARY, response=httpx.Response(status, request=httpx.Request('POST', 'https://invalid.test')), body=None)
                with patch('app.config.ModelConfig.client', return_value=fake), patch('autogen_agentchat.agents.AssistantAgent.run', new=AsyncMock(side_effect=error)) as worker:
                    response = client.post('/api/model/test', headers=ORIGIN)
                    self.assertFalse(response.json()['ok'])
                    self.assertEqual(response.json()['error']['code'], code)
                    self.assertNotIn(CANARY, response.text)
                    self.assertEqual(worker.await_count, 1)

    def test_connection_test_accepts_normal_text_without_marker(self):
        from autogen_core.models import CreateResult, RequestUsage
        with TestClient(app) as client:
            self.authorize(client)
            client.post('/api/model/config', json=self.payload(), headers=ORIGIN)
            completion = CreateResult(content='Connected to the model.', finish_reason='stop',
                                      usage=RequestUsage(prompt_tokens=1, completion_tokens=1), cached=False)
            replay = ReplayChatCompletionClient([completion])
            configs = []
            def factory(config):
                configs.append(config)
                return replay
            with patch.object(ModelConfig, 'client', factory):
                response = client.post('/api/model/test', headers=ORIGIN)
            self.assertTrue(response.json()['ok'])
            self.assertNotIn('Connected to the model.', response.text)
            self.assertIn('非空文本响应', response.json()['response_summary'])
            self.assertEqual(len(replay.create_calls), 1)
            self.assertEqual(configs[0].sdk_retries, 0)
            self.assertEqual(configs[0].max_output_tokens, 64)

    def test_connection_test_rejects_empty_truncated_or_filtered_text(self):
        from autogen_core.models import CreateResult, RequestUsage
        with TestClient(app) as client:
            self.authorize(client)
            client.post('/api/model/config', json=self.payload(), headers=ORIGIN)
            for content, reason in [('  ', 'stop'), ('OK', 'length'), ('OK', 'content_filter'), ('OK', 'function_calls'), ('OK', 'unknown')]:
                with self.subTest(content=content, reason=reason):
                    completion = CreateResult(content=content, finish_reason=reason,
                                              usage=RequestUsage(prompt_tokens=1, completion_tokens=1), cached=False)
                    replay = ReplayChatCompletionClient([completion])
                    with patch.object(ModelConfig, 'client', return_value=replay):
                        response = client.post('/api/model/test', headers=ORIGIN).json()
                    self.assertFalse(response['ok'])
                    self.assertEqual(response['error']['code'], 'UNEXPECTED_RESPONSE')
                    self.assertEqual(len(replay.create_calls), 1)

    def test_connection_diagnostics_observe_response_without_exposing_content(self):
        from autogen_core.models import CreateResult, RequestUsage
        raw = {'id': 'private-id', 'object': 'chat.completion', 'model': 'offline-model',
               'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': CANARY},
                            'finish_reason': 'stop', CANARY: CANARY}], CANARY: CANARY}
        diagnostic = connection_response_diagnostics(raw, 200)
        self.assertEqual(diagnostic['upstream_http_status'], 200)
        self.assertEqual(diagnostic['top_level_keys'], ['choices', 'id', 'model', 'object'])
        self.assertEqual(diagnostic['other_top_level_key_count'], 1)
        self.assertEqual(diagnostic['choices_count'], 1)
        self.assertEqual(diagnostic['choice_keys'], ['finish_reason', 'index', 'message'])
        self.assertEqual(diagnostic['other_choice_key_count'], 1)
        self.assertEqual(diagnostic['finish_reason_actual'], 'stop')
        self.assertTrue(diagnostic['message_present'])
        self.assertTrue(diagnostic['content_present'])
        self.assertEqual(diagnostic['content_length'], len(CANARY))
        self.assertNotIn(CANARY, json.dumps(diagnostic))

        with TestClient(app) as client:
            self.authorize(client)
            client.post('/api/model/config', json=self.payload(), headers=ORIGIN)
            completion = CreateResult(content='  ', finish_reason='stop',
                                      usage=RequestUsage(prompt_tokens=1, completion_tokens=1), cached=False)
            replay = ReplayChatCompletionClient([completion])
            hooks = SimpleNamespace(event_hooks={'response': []})
            replay._client = SimpleNamespace(_client=hooks)
            original_create = replay.create

            async def observed_create(*args, **kwargs):
                await hooks.event_hooks['response'][0](httpx.Response(200, json=raw))
                return await original_create(*args, **kwargs)

            with patch.object(replay, 'create', observed_create), patch.object(ModelConfig, 'client', return_value=replay):
                response = client.post('/api/model/test', headers=ORIGIN).json()
            self.assertFalse(response['ok'])
            self.assertEqual(response['error']['code'], 'UNEXPECTED_RESPONSE')
            self.assertEqual(response['diagnostic']['parsed_finish_reason'], 'stop')
            self.assertTrue(response['diagnostic']['parsed_text_empty'])
            self.assertEqual(response['diagnostic']['content_length'], len(CANARY))
            self.assertNotIn(CANARY, json.dumps(response))
            self.assertEqual(len(replay.create_calls), 1)

    def test_connection_diagnostics_limit_unknown_fields_and_reasons(self):
        raw = {CANARY: CANARY, 'output': [CANARY], 'choices': [{'finish_reason': CANARY,
               'message': {'content': None, CANARY: CANARY}, CANARY: CANARY}]}
        diagnostic = connection_response_diagnostics(raw, 200)
        self.assertEqual(diagnostic['top_level_keys'], ['choices', 'output'])
        self.assertEqual(diagnostic['finish_reason_actual'], 'other')
        self.assertTrue(diagnostic['content_present'])
        self.assertIsNone(diagnostic['content_length'])
        self.assertNotIn(CANARY, json.dumps(diagnostic))

    def test_connection_diagnostics_capture_real_sdk_transport(self):
        transport = getattr(sdk_transport, 'httpx2', None) or getattr(sdk_transport, 'httpx')
        response_body = {'id': 'offline', 'object': 'chat.completion', 'created': 0,
                         'model': 'offline-model', 'choices': [{'index': 0,
                         'message': {'role': 'assistant', 'content': ''}, 'finish_reason': 'stop'}],
                         'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
        requests = []
        old_clients = []

        async def handler(request):
            requests.append(request.url.path)
            return transport.Response(200, json=response_body)

        real_factory = ModelConfig.client

        def factory(config):
            model_client = real_factory(config)
            old_clients.append(model_client._client._client)
            model_client._client._client = transport.AsyncClient(transport=transport.MockTransport(handler))
            return model_client

        try:
            with TestClient(app) as client:
                self.authorize(client)
                client.post('/api/model/config', json=self.payload(), headers=ORIGIN)
                with patch.object(ModelConfig, 'client', factory):
                    response = client.post('/api/model/test', headers=ORIGIN).json()
            self.assertFalse(response['ok'])
            self.assertEqual(requests, ['/v1/chat/completions'])
            diagnostic = response['diagnostic']
            self.assertEqual(diagnostic['upstream_http_status'], 200)
            self.assertEqual(diagnostic['choices_count'], 1)
            self.assertEqual(diagnostic['finish_reason_actual'], 'stop')
            self.assertTrue(diagnostic['content_present'])
            self.assertEqual(diagnostic['content_length'], 0)
            self.assertTrue(diagnostic['parsed_text_empty'])
            self.assertEqual(diagnostic['parsed_finish_reason'], 'stop')
            self.assertNotIn(CANARY, json.dumps(response))
        finally:
            for http_client in old_clients:
                asyncio.run(http_client.aclose())

    def test_five_stage_after_ui_config_uses_original_executor(self):
        docs = load_demo_documents()
        m = supply_metrics(docs)
        baseline = {'question': 'Review risk', 'metrics': m, 'evidence': make_evidence(docs, m)}
        replies = [StageOutput.model_validate(demo_structure(a['id'], baseline, docs)).model_dump_json() for a in AGENTS]
        replay = ReplayChatCompletionClient(replies)
        with TestClient(app) as client:
            data = client.get('/api/bootstrap').json()
            self.authorize(client)
            client.post('/api/model/config', json=self.payload(), headers=ORIGIN)
            with patch('app.config.ModelConfig.client', return_value=replay):
                created = client.post('/api/runs', json={'question': data['default_question'], 'mode': 'live', 'document_ids': data['demo_document_ids']}).json()
                for _ in range(100):
                    run = client.get('/api/runs/' + created['id']).json()
                    if run['status'] not in ('running', 'queued'): break
                    time.sleep(.02)
            self.assertEqual(run['mode'], 'live')
            self.assertEqual(len(replay.create_calls), 5)
            self.assertTrue(run['report'])
            self.assertEqual(run['agents'][3]['status'], 'completed')
            self.assertNotIn(CANARY, json.dumps(run))


if __name__ == '__main__':
    unittest.main()
