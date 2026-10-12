import ast
import asyncio
import os
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.config import ModelConfig


class ProbeTests(unittest.TestCase):
    def invoke(self, data=None, status=200, exception=None, limit='0'):
        # Load only the real probe function: never execute the credential bridge or CLI.
        script = Path(__file__).resolve().parents[2] / 'scripts' / 'deepseek.sh'
        source = script.read_text().split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        function = next(n for n in ast.parse(source).body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'probe')
        outputs = []
        namespace = {'time': time, 'output': outputs.append}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(script), 'exec'), namespace)
        env = {'MODEL_MAX_OUTPUT_TOKENS': limit} if limit is not None else {}
        with patch.dict(os.environ, env, clear=True):
            config = replace(ModelConfig.load(), api_key='offline-fixture', model='deepseek-flash', base_url='https://api.deepseek.com')
        if data is None:
            data = {'model': 'deepseek-flash', 'choices': [{'message': {'content': 'SENTINELAI_DEEPSEEK_OK'}, 'finish_reason': 'stop'}]}
        response = httpx.Response(status, json=data)
        client = MagicMock()
        client.post = AsyncMock(return_value=response, side_effect=exception)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        with patch('httpx.AsyncClient', return_value=client) as factory:
            passed = asyncio.run(namespace['probe'](config))
        self.assertEqual(client.post.await_count, 1)
        self.assertFalse(factory.call_args.kwargs['follow_redirects'])
        return passed, outputs[0], client.post.call_args.kwargs['json']

    def test_positive_limit_sent(self):
        passed, _, payload = self.invoke(limit='8192')
        self.assertTrue(passed)
        self.assertEqual(payload['max_tokens'], 8192)

    def test_zero_omits_max_tokens(self):
        passed, _, payload = self.invoke(limit='0')
        self.assertTrue(passed)
        self.assertNotIn('max_tokens', payload)

    def test_unset_omits_max_tokens(self):
        passed, _, payload = self.invoke(limit=None)
        self.assertTrue(passed)
        self.assertNotIn('max_tokens', payload)

    def test_length_fails_even_if_marker_matches(self):
        data = {'choices': [{'message': {'content': 'SENTINELAI_DEEPSEEK_OK'}, 'finish_reason': 'length'}]}
        passed, result, _ = self.invoke(data)
        self.assertFalse(passed)
        self.assertTrue(result['marker_matches'])
        self.assertEqual(result['finish_reason'], 'length')

    def test_marker_mismatch_fails(self):
        data = {'choices': [{'message': {'content': 'wrong marker'}, 'finish_reason': 'stop'}]}
        passed, result, _ = self.invoke(data)
        self.assertFalse(passed)
        self.assertFalse(result['marker_matches'])

    def test_http_error_not_retried(self):
        passed, result, _ = self.invoke(status=429)
        self.assertFalse(passed)
        self.assertEqual(result['http_status'], 429)
        self.assertEqual(result['retries'], 0)

    def test_connection_error_not_retried_or_exposed(self):
        passed, result, _ = self.invoke(exception=httpx.ConnectError('private request canary'))
        self.assertFalse(passed)
        self.assertNotIn('canary', str(result))
        self.assertEqual(result['retries'], 0)


if __name__ == '__main__':
    unittest.main()
