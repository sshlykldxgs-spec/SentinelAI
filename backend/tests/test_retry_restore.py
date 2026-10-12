import asyncio
import json
import os
import unittest
from unittest.mock import patch

import httpx
import openai._base_client as sdk_transport
from autogen_ext.models.replay import ReplayChatCompletionClient

from app.config import ModelConfig
from app.contracts import StageOutput
from app.engine import demo_structure
from app.evidence import make_evidence
from app.main import load_demo_documents
from app.workflow import AGENTS, run_workflow, supply_metrics


class RetryRestoreTests(unittest.TestCase):
    def setup_run(self):
        docs = load_demo_documents()
        metrics = supply_metrics(docs)
        run = {'id': 'restore-retry', 'question': 'Review risk', 'mode': 'live', 'status': 'queued', 'events': [],
               'report': None, 'agents': [{**a, 'status': 'queued', 'output': ''} for a in AGENTS]}
        baseline = {'question': run['question'], 'metrics': metrics, 'evidence': make_evidence(docs, metrics)}
        replies = [StageOutput.model_validate(demo_structure(a['id'], baseline, docs)).model_dump_json() for a in AGENTS]
        return run, docs, replies

    def test_sdk_default_enabled_and_disable_compatible(self):
        with patch.dict(os.environ, {}, clear=True):
            c = ModelConfig.load()
        self.assertEqual(c.sdk_retries, 1)
        self.assertEqual(c.retries, 1)
        with patch.dict(os.environ, {'MODEL_MAX_RETRIES': '0'}, clear=True):
            self.assertEqual(ModelConfig.load().sdk_retries, 0)
        with patch.dict(os.environ, {'MODEL_MAX_RETRIES': '0', 'MODEL_SDK_MAX_RETRIES': '9'}, clear=True):
            self.assertEqual(ModelConfig.load().sdk_retries, 1)

    def test_sdk_recovers_429_with_real_client_mock_transport(self):
        transport = getattr(sdk_transport, 'httpx2', None) or getattr(sdk_transport, 'httpx')
        count = 0
        async def handler(request):
            nonlocal count
            count += 1
            if count == 1:
                return transport.Response(429, json={'error': {'message': 'offline limited', 'type': 'rate_limit'}}, headers={'retry-after-ms': '1'})
            return transport.Response(200, json={'id': 'offline-chat', 'object': 'chat.completion', 'created': 0,
                'model': 'offline-model', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'OK'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})

        async def check():
            from autogen_core.models import UserMessage
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture', 'OPENAI_MODEL': 'offline-model',
                'OPENAI_BASE_URL': 'https://offline.invalid/v1', 'MODEL_SDK_MAX_RETRIES': '1'}):
                client = ModelConfig.load().client()
            original_http = client._client._client
            client._client._client = transport.AsyncClient(transport=transport.MockTransport(handler))
            try:
                result = await client.create([UserMessage(content='Offline request', source='user')])
                self.assertEqual(result.content, 'OK')
            finally:
                await client.close()
                await original_http.aclose()
        asyncio.run(check())
        self.assertEqual(count, 2)

    def test_sdk_exhaustion_does_not_cascade_executor_retry(self):
        from openai import RateLimitError
        class Exhausted(ReplayChatCompletionClient):
            calls = 0
            async def create(self, *args, **kwargs):
                self.calls += 1
                raise RateLimitError('private canary', response=httpx.Response(429, request=httpx.Request('POST', 'https://invalid.test')), body=None)
        run, docs, _ = self.setup_run()
        client = Exhausted([])
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture', 'MODEL_MAX_RETRIES': '1', 'MODEL_SDK_MAX_RETRIES': '1'}), patch('app.config.ModelConfig.client', return_value=client):
            asyncio.run(run_workflow(run, docs))
        self.assertEqual(client.calls, 1)
        self.assertEqual(run['agents'][0]['attempts'], 1)
        self.assertTrue(run['error_details']['executor_retry_suppressed'])
        self.assertIsNone(run['report'])

    def test_invalid_schema_then_valid_output_without_relaxing_schema(self):
        run, docs, replies = self.setup_run()
        client = ReplayChatCompletionClient(['{"summary":42}', *replies])
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture', 'MODEL_MAX_RETRIES': '1', 'MODEL_SDK_MAX_RETRIES': '1'}), patch('app.config.ModelConfig.client', return_value=client), patch('app.engine.RETRY_DELAY_SECONDS', .01):
            asyncio.run(run_workflow(run, docs))
        self.assertTrue(run['report'])
        self.assertEqual(run['agents'][0]['attempts'], 2)
        self.assertEqual(run['agents'][0]['first_failure']['reason'], 'schema_mismatch')
        self.assertEqual(run['agents'][3]['status'], 'completed')
        self.assertIn('完整JSON', client.create_calls[1]['messages'][-1].content)
        self.assertNotIn('42', json.dumps(run['agents'][0]['first_failure']))


if __name__ == '__main__':
    unittest.main()
