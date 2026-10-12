import asyncio
import json
import os
import unittest
from unittest.mock import patch

from autogen_core.models import CreateResult, RequestUsage
from autogen_ext.models.replay import ReplayChatCompletionClient

from app.config import error_info
from app.engine import context_for
from app.main import load_demo_documents
from app.output_validation import OutputValidationError, output_schema, parse_output
from app.workflow import AGENTS, run_workflow


VALID_PLANNER = json.dumps({'summary': 'Review supplier evidence', 'acceptance_conditions': ['Every metric cites evidence']})


class ParsingTests(unittest.TestCase):
    def test_plain_and_single_fenced_json(self):
        for raw in (VALID_PLANNER, f'```json\n{VALID_PLANNER}\n```', f'```\n{VALID_PLANNER}\n```'):
            self.assertEqual(parse_output(raw, 'planner')['summary'], 'Review supplier evidence')

    def test_invalid_json_not_repaired(self):
        for raw in ('broken', '{"summary":"incomplete",', f'Explanation\n{VALID_PLANNER}',
                    f'```json\n{VALID_PLANNER}', f'{VALID_PLANNER}\n{VALID_PLANNER}',
                    f'```json\n{VALID_PLANNER}\n```\nextra'):
            with self.assertRaises(OutputValidationError) as cm:
                parse_output(raw, 'planner')
            self.assertEqual(cm.exception.reason, 'invalid_json')

    def test_schema_and_role_requirement_still_enforced(self):
        for raw, reason in (
            ('{"summary":42,"acceptance_conditions":["valid"]}', 'schema_mismatch'),
            ('{"acceptance_conditions":["valid"]}', 'schema_mismatch'),
            ('{"summary":"text","acceptance_conditions":"invalid"}', 'schema_mismatch'),
            ('{"summary":"text","acceptance_conditions":[]}', 'missing_planner_conditions'),
            ('{"summary":"text"}', 'missing_planner_conditions'),
            ('{"summary":"text","acceptance_conditions":["   "]}', 'missing_planner_conditions'),
            ('{"summary":"text","acceptance_conditions":["valid"],"unexpected":"value"}', 'schema_mismatch'),
            ('{"summary":"text","acceptance_conditions":[{"nested":"invalid"}]}', 'schema_mismatch'),
        ):
            with self.assertRaises(OutputValidationError) as cm:
                parse_output(raw, 'planner')
            self.assertEqual(cm.exception.reason, reason)

    def test_root_type_duplicate_fields_and_nonfinite_rejected(self):
        for raw, reason in (('[1,2]', 'nonobject_json'), ('{"summary":"first","summary":"second"}', 'duplicate_json_field'),
                            ('{"summary":"text","metric":NaN}', 'nonfinite_json_number')):
            with self.assertRaises(OutputValidationError) as cm:
                parse_output(raw, 'planner')
            self.assertEqual(cm.exception.reason, reason)

    def test_length_completion_rejected_even_if_json_looks_complete(self):
        with self.assertRaises(OutputValidationError) as cm:
            parse_output(VALID_PLANNER, 'planner', 'length')
        self.assertEqual(cm.exception.reason, 'truncated_response')

    def test_nontext_or_empty_response_rejected(self):
        for value, reason in (([], 'nontext_response'), ({}, 'nontext_response'), (None, 'nontext_response'), ('', 'empty_response')):
            with self.assertRaises(OutputValidationError) as cm:
                parse_output(value, 'planner')
            self.assertEqual(cm.exception.reason, reason)

    def test_schema_error_does_not_expose_unknown_field_or_input(self):
        raw = json.dumps({'summary': 'safe', 'acceptance_conditions': ['valid'], 'private-canary-field': 'private-canary-value'})
        with self.assertRaises(OutputValidationError) as cm:
            parse_output(raw, 'planner')
        diagnostic = json.dumps(error_info(cm.exception))
        self.assertNotIn('private-canary-field', diagnostic)
        self.assertNotIn('private-canary-value', diagnostic)
        self.assertIn('<unknown_field>', diagnostic)

    def test_prompt_schema_matches_planner_requirement(self):
        run = {'question': 'review', 'evidence': [], 'metrics': None, 'review': {'findings': []}}
        context = json.loads(context_for(run, 'planner', {}))
        schema = context['required_output_schema']
        self.assertIn('acceptance_conditions', schema['required'])
        self.assertEqual(schema['properties']['acceptance_conditions']['minItems'], 1)
        self.assertEqual(schema['properties']['acceptance_conditions']['items']['minLength'], 1)
        self.assertIn('Planner', context['stage_output_scope'])
        self.assertNotIn('acceptance_conditions', output_schema('research')['required'])


class ExecutionTests(unittest.TestCase):
    def run_response(self, content, finish_reason='stop'):
        run = {'id': 'output-acceptance', 'mode': 'live', 'question': 'Review supplier risks', 'status': 'queued',
               'events': [], 'report': None, 'agents': [{**a, 'status': 'queued', 'output': ''} for a in AGENTS]}
        docs = load_demo_documents()
        completion = CreateResult(content=content, finish_reason=finish_reason, usage=RequestUsage(prompt_tokens=100, completion_tokens=100), cached=False)
        client = ReplayChatCompletionClient([completion])
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture', 'MODEL_MAX_RETRIES': '0'}), patch('app.config.ModelConfig.client', return_value=client):
            asyncio.run(run_workflow(run, docs))
        return run

    def test_fenced_planner_uses_real_autogen_message_path(self):
        run = self.run_response(f'```json\n{VALID_PLANNER}\n```')
        self.assertEqual(run['agents'][0]['status'], 'completed')
        self.assertEqual(run['agents'][0]['structured_output']['acceptance_conditions'], ['Every metric cites evidence'])
        self.assertEqual(run['agents'][0]['response_metadata']['finish_reason'], 'stop')
        # One Replay response only: downstream failure is expected, not a forged report.
        self.assertEqual(run['agents'][1]['status'], 'failed')
        self.assertIsNone(run['report'])

    def test_truncated_response_preserves_failure_without_demo(self):
        run = self.run_response(VALID_PLANNER, 'length')
        self.assertEqual(run['mode'], 'live')
        self.assertEqual(run['status'], 'failed')
        self.assertEqual(run['agents'][0]['status'], 'failed')
        self.assertEqual(run['agents'][1]['status'], 'blocked')
        self.assertEqual(run['agents'][1]['blocked_by'], 'planner')
        self.assertEqual(run['error_details']['reason'], 'truncated_response')
        self.assertEqual(run['agents'][0]['response_metadata']['finish_reason'], 'length')
        self.assertEqual(run['events'][-1]['type'], 'task.failed')
        self.assertIsNone(run['report'])

    def test_invalid_json_failure_has_safe_specific_reason(self):
        run = self.run_response('private-canary-not-json')
        self.assertEqual(run['error_details']['reason'], 'invalid_json')
        self.assertNotIn('private-canary', json.dumps(run))
        self.assertEqual(run['status'], 'failed')

    def test_fenced_planner_continues_all_stages_without_skipping_reviewer(self):
        from app.engine import demo_structure
        from app.evidence import make_evidence
        from app.workflow import supply_metrics

        docs = load_demo_documents()
        metrics = supply_metrics(docs)
        baseline = {'question': 'Review supplier risks', 'metrics': metrics, 'evidence': make_evidence(docs, metrics)}
        responses = [json.dumps(demo_structure(agent['id'], baseline, docs)) for agent in AGENTS]
        responses[0] = f'```json\n{responses[0]}\n```'
        client = ReplayChatCompletionClient(responses)
        run = {'id': 'fenced-chain', 'mode': 'live', 'question': baseline['question'], 'status': 'queued',
               'events': [], 'report': None, 'agents': [{**a, 'status': 'queued', 'output': ''} for a in AGENTS]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'offline-fixture', 'MODEL_MAX_RETRIES': '0'}), patch('app.config.ModelConfig.client', return_value=client):
            asyncio.run(run_workflow(run, docs))
        self.assertEqual(len(client.create_calls), 5)
        self.assertEqual([a['status'] for a in run['agents']], ['completed'] * 4 + ['waiting_approval'])
        self.assertEqual(run['review']['decision'], 'human_review')
        self.assertIn('human_review', client.create_calls[4]['messages'][-1].content)
        self.assertTrue(run['report'])
        self.assertEqual(run['mode'], 'live')


if __name__ == '__main__':
    unittest.main()
