import asyncio
import os
import unittest
from dataclasses import replace
from unittest.mock import patch

from app.config import ModelConfig
from app.main import load_demo_documents
from app.workflow import AGENTS, run_workflow


class TokenLimitTests(unittest.TestCase):
    def test_zero_disables_both_limits(self):
        with patch.dict(os.environ, {'MODEL_MAX_OUTPUT_TOKENS': '0', 'TASK_TOKEN_BUDGET': '0'}):
            config = ModelConfig.load()
        self.assertIsNone(config.max_output_tokens)
        self.assertIsNone(config.token_budget)
        self.assertIsNone(config.public()['max_output_tokens'])

    def test_unset_defaults_disable_limits(self):
        with patch.dict(os.environ, {}, clear=True):
            config = ModelConfig.load()
        self.assertIsNone(config.max_output_tokens)
        self.assertIsNone(config.token_budget)

    def test_explicit_limits_are_not_clamped(self):
        with patch.dict(os.environ, {'MODEL_MAX_OUTPUT_TOKENS': '16000', 'TASK_TOKEN_BUDGET': '600000'}):
            config = ModelConfig.load()
        self.assertEqual(config.max_output_tokens, 16000)
        self.assertEqual(config.token_budget, 600000)

    def test_invalid_values_fail_without_echoing_input(self):
        for name in ('MODEL_MAX_OUTPUT_TOKENS', 'TASK_TOKEN_BUDGET'):
            for value in ('invalid-canary', '-1'):
                with patch.dict(os.environ, {name: value}):
                    with self.assertRaises(ValueError) as cm:
                        ModelConfig.load()
                self.assertNotIn(value, str(cm.exception))

    def test_unlimited_client_omits_max_tokens(self):
        config = replace(ModelConfig.load(), max_output_tokens=None)
        with patch('autogen_ext.models.openai.OpenAIChatCompletionClient') as factory:
            config.client()
        self.assertNotIn('max_tokens', factory.call_args.kwargs)
        self.assertEqual(factory.call_args.kwargs['max_retries'], config.sdk_retries)

    def test_explicit_output_limit_is_sent(self):
        config = replace(ModelConfig.load(), max_output_tokens=16000)
        with patch('autogen_ext.models.openai.OpenAIChatCompletionClient') as factory:
            config.client()
        self.assertEqual(factory.call_args.kwargs['max_tokens'], 16000)

    def test_unlimited_replay_completes_with_usage_tracking(self):
        run = {'id': 'unlimited-test', 'question': 'Review supplier risk', 'mode': 'replay', 'status': 'queued',
               'events': [], 'report': None, 'agents': [{**a, 'status': 'queued', 'output': ''} for a in AGENTS]}
        with patch.dict(os.environ, {'MODEL_MAX_OUTPUT_TOKENS': '0', 'TASK_TOKEN_BUDGET': '0'}):
            asyncio.run(run_workflow(run, load_demo_documents()))
        self.assertEqual(run['status'], 'waiting_approval')
        self.assertIsNone(run['budget']['limit'])
        self.assertGreater(run['budget']['reserved_tokens'], 0)
        self.assertTrue(run['report'])
        self.assertEqual(run['agents'][3]['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
