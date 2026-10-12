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
from app.evidence import make_evidence, validate_references
from app.main import load_demo_documents
from app.output_validation import output_schema
from app.workflow import AGENTS, run_workflow, supply_metrics


def baseline():
    docs = load_demo_documents()
    metrics = supply_metrics(docs)
    run = {'id': 'reviewer-test', 'mode': 'replay', 'status': 'queued', 'question': 'Review suppliers',
           'evidence': make_evidence(docs, metrics), 'metrics': metrics,
           'review': {'decision': 'pending', 'findings': [], 'metric_issues': []},
           'agents': [{**a, 'status': 'queued', 'output': ''} for a in AGENTS]}
    return run, docs


class MetricIssueTests(unittest.TestCase):
    def check(self, values, refs):
        evidence = [{'evidence_id': 'M-spend', 'kind': 'computed', 'related_claim': [],
                     'supporting_excerpt': {'value': 900000}}]
        issues = []
        result = {'claims': [{'text': 'Test cost', 'kind': 'computed', 'metric_values': values, 'evidence_ids': refs}]}
        findings = validate_references(result, evidence, issues)
        return findings, issues

    def test_unknown_metric_is_not_called_value_mismatch(self):
        findings, issues = self.check({'top3_spend': 588000}, ['M-spend'])
        self.assertEqual([i['type'] for i in issues], ['unknown_metric'])
        self.assertIsNone(issues[0]['expected_value'])
        self.assertIn('数值冲突', findings[0])
        self.assertTrue(issues[0]['blocking'])

    def test_missing_reference_even_with_correct_value(self):
        _, issues = self.check({'spend': 900000}, [])
        self.assertEqual([i['type'] for i in issues], ['missing_reference'])
        self.assertEqual(issues[0]['observed_value'], issues[0]['expected_value'])

    def test_value_mismatch_with_valid_reference(self):
        findings, issues = self.check({'spend': 142000}, ['M-spend'])
        self.assertEqual([i['type'] for i in issues], ['value_mismatch'])
        self.assertEqual(issues[0]['expected_value'], 900000)
        self.assertIn('[value_mismatch]', findings[0])

    def test_both_missing_reference_and_value_mismatch_retained(self):
        _, issues = self.check({'spend': 142000}, [])
        self.assertEqual({i['type'] for i in issues}, {'missing_reference', 'value_mismatch'})

    def test_valid_metric_has_no_issue(self):
        findings, issues = self.check({'spend': 900000}, ['M-spend'])
        self.assertEqual(findings, [])
        self.assertEqual(issues, [])


class ReviewerContextTests(unittest.TestCase):
    def test_keeps_basis_and_does_not_mutate_inputs(self):
        run, docs = baseline()
        outputs = {a['id']: demo_structure(a['id'], run, docs) for a in AGENTS[:3]}
        for evidence in run['evidence']:
            evidence['related_claim'] = ['Repeated narrative' * 100]
        run['review']['findings'] = ['Metric conflict', 'Metric conflict']
        run['review']['metric_issues'] = [{'type': 'unknown_metric', 'metric': 'derived', 'expected_evidence_id': 'M-derived', 'blocking': True}]
        before = copy.deepcopy((run, outputs))
        data = json.loads(context_for(run, 'risk', outputs))
        self.assertEqual((run, outputs), before)
        self.assertEqual(len(data['untrusted_evidence']), len(run['evidence']))
        for original, compact in zip(run['evidence'], data['untrusted_evidence']):
            for key in ('evidence_id', 'source_file', 'source_location', 'supporting_excerpt', 'kind', 'verification_status'):
                self.assertEqual(compact[key], original[key])
            self.assertNotIn('related_claim', compact)
            self.assertNotIn('document_id', compact)
        for stage in outputs:
            self.assertEqual(data['previous_outputs'][stage]['summary'], outputs[stage]['summary'])
            for key in ('claims', 'risks', 'acceptance_conditions', 'unresolved'):
                if outputs[stage][key]:
                    self.assertEqual(data['previous_outputs'][stage][key], outputs[stage][key])
        self.assertEqual(data['metric_issues'], run['review']['metric_issues'])
        self.assertEqual(data['validation_findings'], ['Metric conflict'])
        self.assertEqual(data['required_output_schema'], output_schema('risk'))
        self.assertLess(len(context_for(run, 'risk', outputs)), len(context_for(run, 'analyst', outputs)))

    def test_unreferenced_source_and_long_excerpt_are_not_dropped(self):
        run, docs = baseline()
        run['evidence'][0]['supporting_excerpt'] = 'Important source' * 500
        data = json.loads(context_for(run, 'risk', {}))
        self.assertEqual(data['untrusted_evidence'][0]['supporting_excerpt'], run['evidence'][0]['supporting_excerpt'])
        self.assertEqual({e['evidence_id'] for e in data['untrusted_evidence']}, {e['evidence_id'] for e in run['evidence']})

    def test_other_contexts_unchanged(self):
        run, _ = baseline()
        outputs = {'planner': {'summary': 'Full upstream', 'claims': []}}
        for stage in ('planner', 'analyst', 'action'):
            data = json.loads(context_for(run, stage, outputs))
            self.assertEqual(data['previous_outputs'], outputs)
            self.assertEqual(data['untrusted_evidence'], run['evidence'])


class ReviewerTimeoutTests(unittest.TestCase):
    def test_independent_default_bounds_and_other_stages(self):
        with patch.dict(os.environ, {}, clear=True):
            config = ModelConfig.load()
        self.assertEqual(config.timeout_for('risk'), 120)
        self.assertEqual(config.timeout_for('analyst'), 90)
        for value, expected in [('0', 1), ('1000', 120), ('invalid', 120), ('75', 75)]:
            with patch.dict(os.environ, {'REVIEWER_TIMEOUT_SECONDS': value, 'MODEL_TIMEOUT_SECONDS': '30'}):
                config = ModelConfig.load()
            self.assertEqual(config.timeout_for('risk'), expected)
            self.assertEqual(config.timeout_for('planner'), 30)
            self.assertEqual(config.public()['reviewer_timeout_seconds'], expected)

    def test_sdk_and_agent_deadline_both_use_reviewer_setting(self):
        run, docs = baseline()
        responses = [json.dumps(demo_structure(a['id'], run, docs)) for a in AGENTS]
        client = ReplayChatCompletionClient(responses)
        real_wait_for = asyncio.wait_for
        deadlines = []

        async def track_wait_for(coro, timeout):
            deadlines.append(timeout)
            return await real_wait_for(coro, timeout)

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture', 'MODEL_TIMEOUT_SECONDS': '30', 'REVIEWER_TIMEOUT_SECONDS': '75', 'MODEL_MAX_RETRIES': '0'}), patch('app.config.ModelConfig.client', return_value=client), patch('app.engine.asyncio.wait_for', side_effect=track_wait_for):
            run['mode'] = 'live'
            asyncio.run(run_workflow(run, docs))
        self.assertEqual(deadlines, [30, 30, 30, 75, 30])
        self.assertEqual(client.create_calls[1]['extra_create_args']['timeout'], 30)
        self.assertEqual(client.create_calls[3]['extra_create_args']['timeout'], 75)
        for index in (0, 2, 4):
            self.assertEqual(client.create_calls[index]['extra_create_args']['timeout'], 30)
        self.assertEqual(run['agents'][3]['request_timeout_seconds'], 75)
        self.assertFalse(run['agents'][3]['review_context_stats']['excerpts_truncated'])
        self.assertTrue(run['report'])

    def test_reviewer_timeout_still_stops_action(self):
        run, docs = baseline()
        replies = [json.dumps(demo_structure(a['id'], run, docs)) for a in AGENTS[:3]]

        class SlowReviewer(ReplayChatCompletionClient):
            async def create(self, messages, **kwargs):
                if kwargs.get('extra_create_args', {}).get('timeout') == .01:
                    await asyncio.sleep(10)
                return await super().create(messages, **kwargs)

        config = replace(ModelConfig.load(), reviewer_timeout=.01, retries=0, api_key='offline-fixture')
        with patch('app.engine.ModelConfig.load', return_value=config), patch('app.config.ModelConfig.client', return_value=SlowReviewer(replies)):
            run['mode'] = 'live'
            asyncio.run(run_workflow(run, docs))
        self.assertEqual(run['status'], 'failed')
        self.assertEqual(run['error_details']['code'], 'MODEL_TIMEOUT')
        self.assertEqual(run['agents'][3]['status'], 'failed')
        self.assertEqual(run['agents'][4]['status'], 'blocked')
        self.assertEqual(run['agents'][4]['blocked_by'], 'risk')
        self.assertIsNone(run['report'])

    def test_metric_issue_cannot_be_overridden_by_reviewer_pass(self):
        run, docs = baseline()
        data = [demo_structure(a['id'], run, docs) for a in AGENTS]
        data[2]['claims'][0]['metric_values']['unknown_derived'] = 100
        data[3]['review_decision'] = 'pass'
        client = ReplayChatCompletionClient([json.dumps(d) for d in data])
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture', 'MODEL_MAX_RETRIES': '0'}), patch('app.config.ModelConfig.client', return_value=client):
            run['mode'] = 'live'
            asyncio.run(run_workflow(run, docs))
        self.assertEqual(run['review']['decision'], 'needs_evidence')
        self.assertEqual(run['review']['metric_issues'][0]['type'], 'unknown_metric')
        reviewer_input = json.loads(client.create_calls[3]['messages'][-1].content)
        self.assertEqual(reviewer_input['metric_issues'][0]['metric'], 'unknown_derived')
        self.assertTrue(all(a['status'] == 'needs_evidence' for a in run['approvals']))


if __name__ == '__main__':
    unittest.main()
