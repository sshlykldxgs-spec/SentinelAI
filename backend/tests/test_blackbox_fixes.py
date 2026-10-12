import asyncio
import copy
import json
import os
import unittest
from dataclasses import replace
from unittest.mock import patch

from autogen_ext.models.replay import ReplayChatCompletionClient

from app.config import ModelConfig
from app.engine import context_for, demo_structure
from app.evidence import make_evidence
from app.main import load_demo_documents
from app.output_validation import output_schema
from app.workflow import AGENTS, run_workflow, supply_metrics


def fixture():
    docs = load_demo_documents()
    m = supply_metrics(docs)
    run = {'id': 'blackbox-offline', 'mode': 'live', 'question': 'Review evidence', 'status': 'queued', 'events': [],
           'report': None, 'evidence': make_evidence(docs, m), 'metrics': m, 'review': {'findings': [], 'metric_issues': []},
           'agents': [{**a, 'status': 'pending', 'output': ''} for a in AGENTS]}
    return run, docs


class ResearchTests(unittest.TestCase):
    def test_research_projection_preserves_all_source_and_upstream(self):
        run, docs = fixture()
        outputs = {'planner': demo_structure('planner', run, docs)}
        run['evidence'][0]['supporting_excerpt'] = 'Important source detail ' * 1000
        run['evidence'][0]['related_claim'] = ['duplicate' * 1000]
        before = copy.deepcopy((run, outputs))
        context = json.loads(context_for(run, 'research', outputs))
        self.assertEqual((run, outputs), before)
        self.assertEqual(len(context['untrusted_evidence']), len(run['evidence']))
        for source, compact in zip(run['evidence'], context['untrusted_evidence']):
            for key in ('evidence_id', 'source_file', 'source_location', 'supporting_excerpt', 'kind', 'verification_status'):
                self.assertEqual(compact[key], source[key])
            self.assertNotIn('related_claim', compact)
            self.assertNotIn('document_id', compact)
        self.assertEqual(context['previous_outputs']['planner']['summary'], outputs['planner']['summary'])
        self.assertEqual(context['previous_outputs']['planner']['acceptance_conditions'], outputs['planner']['acceptance_conditions'])
        self.assertEqual(context['required_output_schema'], output_schema('research'))
        self.assertLess(len(context_for(run, 'research', outputs)), len(context_for(run, 'analyst', outputs)))

    def test_timeout_is_independent_and_bounded(self):
        with patch.dict(os.environ, {}, clear=True):
            config = ModelConfig.load()
        self.assertEqual(config.timeout_for('research'), 120)
        self.assertEqual(config.timeout_for('planner'), 60)
        for raw, expected in [('0', 1), ('1000', 120), ('invalid', 120), ('70', 70)]:
            with patch.dict(os.environ, {'MODEL_TIMEOUT_SECONDS': '30', 'RESEARCH_TIMEOUT_SECONDS': raw}):
                config = ModelConfig.load()
            self.assertEqual(config.timeout_for('research'), expected)
            self.assertEqual(config.timeout_for('analyst'), 30)
            self.assertEqual(config.timeout_for('risk'), 30)

    def test_five_stage_sdk_and_deadlines(self):
        run, docs = fixture()
        client = ReplayChatCompletionClient([json.dumps(demo_structure(a['id'], run, docs)) for a in AGENTS])
        real_wait = asyncio.wait_for
        deadlines = []
        async def observe(coro, timeout):
            deadlines.append(timeout)
            return await real_wait(coro, timeout)
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture', 'MODEL_MAX_RETRIES': '0', 'RESEARCH_TIMEOUT_SECONDS': '70'}), patch('app.config.ModelConfig.client', return_value=client), patch('app.engine.asyncio.wait_for', side_effect=observe):
            asyncio.run(run_workflow(run, docs))
        self.assertEqual(deadlines, [60, 70, 90, 120, 120])
        self.assertEqual(client.create_calls[1]['extra_create_args']['timeout'], 70)
        self.assertFalse(run['agents'][1]['research_context_stats']['excerpts_truncated'])
        self.assertTrue(run['report'])


class FailureTests(unittest.TestCase):
    def test_research_failure_blocks_downstream_and_emits_before_terminal(self):
        run, docs = fixture()
        replies = [json.dumps(demo_structure('planner', run, docs))]
        class SlowResearch(ReplayChatCompletionClient):
            async def create(self, messages, **kwargs):
                if kwargs.get('extra_create_args', {}).get('timeout') is not None:
                    await asyncio.sleep(10)
                return await super().create(messages, **kwargs)
        config = replace(ModelConfig.load(), research_timeout=.01, retries=0, api_key='offline-fixture')
        client = SlowResearch(replies)
        with patch('app.engine.ModelConfig.load', return_value=config), patch('app.config.ModelConfig.client', return_value=client):
            asyncio.run(run_workflow(run, docs))
        self.assertEqual([a['status'] for a in run['agents']], ['completed', 'failed', 'blocked', 'blocked', 'blocked'])
        self.assertTrue(all(a['blocked_by'] == 'research' for a in run['agents'][2:]))
        self.assertTrue(all(a.get('started_at') is None for a in run['agents'][2:]))
        self.assertEqual(run['mode'], 'live')
        self.assertIsNone(run['report'])
        self.assertEqual(run['events'][-1]['type'], 'task.failed')
        self.assertEqual(sum(e['type'] == 'agent.blocked' for e in run['events']), 3)

    def test_client_initialization_failure_blocks_all(self):
        run, docs = fixture()
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture'}), patch('app.config.ModelConfig.client', side_effect=RuntimeError('offline initialization fault')):
            asyncio.run(run_workflow(run, docs))
        self.assertEqual(run['status'], 'failed')
        self.assertTrue(all(a['status'] == 'blocked' and a['blocked_by'] == 'task' for a in run['agents']))
        self.assertIsNone(run['report'])


if __name__ == '__main__':
    unittest.main()
