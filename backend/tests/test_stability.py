import asyncio
import json
import os
import unittest
from dataclasses import replace
from unittest.mock import patch

import httpx
from openai import APIConnectionError, AuthenticationError, BadRequestError, InternalServerError, RateLimitError
from autogen_ext.models.replay import ReplayChatCompletionClient

from app.config import ModelConfig
from app.engine import demo_structure
from app.evidence import make_evidence
from app.main import load_demo_documents
from app.workflow import AGENTS, run_workflow, supply_metrics


def http_error(status):
    cls = AuthenticationError if status == 401 else BadRequestError if status == 400 else RateLimitError if status == 429 else InternalServerError
    return cls('private-error-canary', response=httpx.Response(status, request=httpx.Request('POST', 'https://invalid.test')), body=None)


class RecoveryClient(ReplayChatCompletionClient):
    def __init__(self, responses, target='planner', failures=None):
        super().__init__(responses)
        self.target = target
        self.failures = list(failures or [TimeoutError('private-error-canary')])
        self.invocations = []

    async def create(self, messages, **kwargs):
        stage = json.loads(messages[-1].content)['stage']
        self.invocations.append(stage)
        if stage == self.target and self.failures:
            raise self.failures.pop(0)
        return await super().create(messages, **kwargs)


class StabilityTests(unittest.TestCase):
    def run_case(self, failures=None, target='planner', retries=1, edit=None, config=None):
        docs = load_demo_documents()
        m = supply_metrics(docs)
        baseline = {'question': 'Review supplier risk', 'metrics': m, 'evidence': make_evidence(docs, m)}
        outputs = [demo_structure(a['id'], baseline, docs) for a in AGENTS]
        if edit:
            edit(outputs)
        replies = [json.dumps(o) for o in outputs]
        client = RecoveryClient(replies, target, failures)
        run = {'id': 'recovery-test', 'mode': 'live', 'question': baseline['question'], 'status': 'queued', 'events': [],
               'report': None, 'agents': [{**a, 'status': 'queued', 'output': ''} for a in AGENTS]}
        env = {'OPENAI_API_KEY': 'offline-fixture', 'MODEL_MAX_RETRIES': str(retries), 'MODEL_SDK_MAX_RETRIES': '0'}
        with patch.dict(os.environ, env), patch('app.config.ModelConfig.client', return_value=client), patch('app.engine.RETRY_DELAY_SECONDS', .01):
            if config:
                with patch('app.engine.ModelConfig.load', return_value=config):
                    asyncio.run(run_workflow(run, docs))
            else:
                asyncio.run(run_workflow(run, docs))
        return run, client

    def test_timeout_once_then_success_preserves_first_failure(self):
        run, client = self.run_case()
        self.assertTrue(run['report'])
        agent = run['agents'][0]
        self.assertEqual(agent['status'], 'completed')
        self.assertEqual(agent['attempts'], 2)
        self.assertEqual(agent['retry_attempt'], 1)
        self.assertEqual(agent['first_failure']['code'], 'MODEL_TIMEOUT')
        self.assertEqual([a['status'] for a in agent['attempt_history']], ['failed', 'completed'])
        self.assertEqual(client.invocations, ['planner', 'planner', 'research', 'analyst', 'risk', 'action'])
        events = [e for e in run['events'] if e['type'] == 'agent.retrying']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['payload']['retry_attempt'], 1)
        self.assertNotIn('private-error-canary', json.dumps(run))

    def test_second_timeout_fails_no_third_request(self):
        run, client = self.run_case([TimeoutError('one'), TimeoutError('two')], retries=99)
        self.assertEqual(client.invocations, ['planner', 'planner'])
        self.assertEqual(run['status'], 'failed')
        self.assertIsNone(run['report'])
        self.assertEqual(run['agents'][0]['attempts'], 2)
        self.assertTrue(all(a['status'] == 'blocked' for a in run['agents'][1:]))
        self.assertEqual(len(run['agents'][0]['attempt_history']), 2)

    def test_connection_and_only_allowed_http_statuses_recover(self):
        failures = [APIConnectionError(request=httpx.Request('POST', 'https://invalid.test')),
                    httpx.ConnectError('private-error-canary'), ConnectionError('private-error-canary')]
        failures.extend(http_error(status) for status in (429, 502, 503, 504))
        for error in failures:
            with self.subTest(type=type(error).__name__, status=getattr(error, 'status_code', None)):
                run, client = self.run_case([error])
                self.assertTrue(run['report'])
                self.assertEqual(client.invocations.count('planner'), 2)

    def test_auth_parameter_and_other_5xx_not_retried_by_executor(self):
        for status in (400, 401, 500, 501, 505):
            with self.subTest(status=status):
                run, client = self.run_case([http_error(status)])
                self.assertEqual(client.invocations, ['planner'])
                self.assertEqual(run['status'], 'failed')
                self.assertFalse(run['agents'][0]['first_failure']['retryable'])

    def test_schema_error_corrected_once(self):
        run, client = self.run_case([ValueError('private-error-canary')])
        self.assertEqual(client.invocations.count('planner'), 2)
        self.assertTrue(run['report'])
        self.assertEqual(run['agents'][0]['first_failure']['code'], 'INVALID_OUTPUT')

    def test_schema_correction_is_bounded_and_truncation_not_retried(self):
        from autogen_core.models import CreateResult, RequestUsage
        docs = load_demo_documents()
        for content, reason in [('not-json', 'stop'), ('{"summary":42}', 'stop'), ('{"summary":"partial"}', 'length')]:
            completion = CreateResult(content=content, finish_reason=reason, usage=RequestUsage(prompt_tokens=1, completion_tokens=1), cached=False)
            client = ReplayChatCompletionClient([completion, completion])
            run = {'id': 'bad-output', 'mode': 'live', 'question': 'Review', 'status': 'queued', 'events': [],
                   'report': None, 'agents': [{**a, 'status': 'queued', 'output': ''} for a in AGENTS]}
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture', 'MODEL_MAX_RETRIES': '1', 'MODEL_SDK_MAX_RETRIES': '0'}), patch('app.config.ModelConfig.client', return_value=client):
                asyncio.run(run_workflow(run, docs))
            self.assertEqual(len(client.create_calls), 1 if reason == 'length' else 2)
            self.assertEqual(run['status'], 'failed')
            self.assertEqual(run['error_details']['retryable'], reason != 'length')
            self.assertIsNone(run['report'])

    def test_business_needs_evidence_does_not_retry_reviewer(self):
        def refuse(outputs):
            outputs[3]['review_decision'] = 'needs_evidence'
        run, client = self.run_case(target='action', edit=refuse)
        self.assertEqual(client.invocations.count('risk'), 1)
        self.assertEqual(run['review']['decision'], 'needs_evidence')
        self.assertEqual(run['status'], 'waiting_approval')
        self.assertTrue(all(a['status'] == 'needs_evidence' for a in run['approvals']))

    def test_action_recovery_creates_approval_once_and_no_external_tools(self):
        run, client = self.run_case(target='action')
        action = run['agents'][4]
        self.assertEqual(client.invocations.count('action'), 2)
        self.assertEqual(action['retry_attempt'], 1)
        self.assertEqual(action['first_failure']['code'], 'MODEL_TIMEOUT')
        self.assertEqual(action['status'], 'waiting_approval')
        self.assertEqual(len(run['approvals']), 2)
        self.assertTrue(all(a['requires_approval'] and a['status'] == 'pending' and not a['audit'] for a in run['approvals']))
        self.assertTrue(all(not call['tools'] for call in client.create_calls))

    def test_action_second_failure_has_no_approvals_or_report(self):
        run, client = self.run_case([TimeoutError('one'), TimeoutError('two')], target='action')
        self.assertEqual(run['status'], 'failed')
        self.assertEqual(run['agents'][4]['attempts'], 2)
        self.assertEqual(run['approvals'], [])
        self.assertIsNone(run['report'])

    def test_recovery_disabled_keeps_single_request(self):
        run, client = self.run_case(retries=0)
        self.assertEqual(client.invocations, ['planner'])
        self.assertEqual(run['agents'][0]['retry_attempt'], 0)
        self.assertFalse(any(e['type'] == 'agent.retrying' for e in run['events']))

    def test_total_task_deadline_interrupts_delay_without_extra_request(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture'}):
            config = replace(ModelConfig.load(), task_timeout=.005, retries=1)
        run, client = self.run_case(config=config)
        self.assertEqual(client.invocations, ['planner'])
        self.assertEqual(run['status'], 'failed')
        self.assertIsNone(run['report'])
        self.assertEqual(run['agents'][0]['attempt_history'][0]['status'], 'failed')

    def test_stage_defaults_legacy_and_overrides(self):
        with patch.dict(os.environ, {}, clear=True):
            config = ModelConfig.load()
        self.assertEqual([config.timeout_for(a['id']) for a in AGENTS], [60, 120, 90, 120, 120])
        with patch.dict(os.environ, {'MODEL_TIMEOUT_SECONDS': '35', 'ACTION_TIMEOUT_SECONDS': '100'}, clear=True):
            config = ModelConfig.load()
        self.assertEqual([config.timeout_for(a['id']) for a in AGENTS], [35, 35, 35, 35, 100])
        with patch.dict(os.environ, {'MODEL_MAX_RETRIES': '100'}, clear=True):
            self.assertEqual(ModelConfig.load().retries, 1)


if __name__ == '__main__':
    unittest.main()
