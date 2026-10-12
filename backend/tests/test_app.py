import asyncio
import io
import json
import os
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.documents import extract_document
from app.main import app
from app.workflow import AGENTS, demo_output, run_workflow


class DocumentTests(unittest.TestCase):
    def test_pdf_extracts_text(self):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=200)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
        })
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 20 100 Td (Supplier evidence) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        buffer = io.BytesIO()
        writer.write(buffer)
        text, rows = extract_document("evidence.pdf", buffer.getvalue())
        self.assertIn("Supplier evidence", text)
        self.assertEqual(rows, [])

    def test_csv_extracts_structured_rows(self):
        text, rows = extract_document("sample.csv", b"supplier,on_time_rate\nA,91\n")
        self.assertIn("supplier", text)
        self.assertEqual(rows[0]["on_time_rate"], "91")

    def test_rejects_unsupported_extension(self):
        with self.assertRaises(Exception):
            extract_document("binary.exe", b"payload")

    def test_demo_metrics_have_traceable_total(self):
        with TestClient(app) as client:
            data = client.get("/api/bootstrap").json()
        self.assertEqual(data["metrics"]["count"], 6)
        self.assertEqual(data["metrics"]["spend"], 900000)
        self.assertEqual(data["metrics"]["on_time"], 91.3)

    def test_demo_analyst_uses_supplied_data(self):
        with TestClient(app) as client:
            data = client.get("/api/bootstrap").json()
        from app.main import documents
        selected = [documents[doc_id] for doc_id in data["demo_document_ids"]]
        output = demo_output("analyst", {"question": data["default_question"]}, selected)
        self.assertIn("Meridian Electronics", output)
        self.assertIn("$228,000", output)
        self.assertIn("25.3%", output)

    def test_zero_spend_does_not_divide_by_zero(self):
        doc = {"name": "zero.csv", "rows": [{"supplier": "A", "on_time_rate": "98", "defect_rate": "1", "monthly_spend_usd": "0"}]}
        output = demo_output("analyst", {"question": "Review spend"}, [doc])
        self.assertIn("无法计算支出占比", output)


class AutoGenTests(unittest.TestCase):
    def make_run(self):
        return {
            "question": "Review the evidence and suggest next steps", "mode": "live",
            "report": None, "agents": [{**agent, "status": "pending", "output": ""} for agent in AGENTS],
        }

    def test_real_assistant_agents_pass_previous_output(self):
        from autogen_ext.models.replay import ReplayChatCompletionClient

        from app.contracts import StageOutput
        responses = [StageOutput(summary=s, acceptance_conditions=['check evidence'] if i == 0 else [],
                    claims=[{'text': s, 'kind': 'hypothesis'}] if i == 2 else [{'text': s, 'kind': 'fact', 'evidence_ids': []}] if i == 1 else [],
                    review_decision='pass' if i == 3 else 'not_applicable',
                    actions=[{'title': 'ACTIONS', 'reason': 'review evidence', 'owner': 'owner', 'deadline': 'tomorrow', 'impact': 'review only'}] if i == 4 else []).model_dump_json()
                    for i, s in enumerate(["PLAN", "EVIDENCE", "ANALYSIS", "REVIEW", "ACTIONS"])]
        replay = ReplayChatCompletionClient(responses)
        run = self.make_run()
        docs = [{"name": "notes.txt", "type": "txt", "text": "Business evidence."}]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-fixture"}), patch(
            "autogen_ext.models.openai.OpenAIChatCompletionClient", return_value=replay
        ):
            asyncio.run(run_workflow(run, docs))
        self.assertEqual(run["status"], "waiting_approval")
        self.assertEqual(len(replay.create_calls), 5)
        second_prompt = replay.create_calls[1]["messages"][-1].content
        final_prompt = replay.create_calls[4]["messages"][-1].content
        self.assertIn("PLAN", second_prompt)
        self.assertIn("REVIEW", final_prompt)
        self.assertIn("ACTIONS", run["report"])

    def test_model_failure_stops_downstream_agents(self):
        from autogen_ext.models.replay import ReplayChatCompletionClient

        run = self.make_run()
        replay = ReplayChatCompletionClient([])
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-fixture"}), patch(
            "autogen_ext.models.openai.OpenAIChatCompletionClient", return_value=replay
        ):
            asyncio.run(run_workflow(run, []))
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["agents"][0]["status"], "failed")
        self.assertEqual(run["agents"][1]["status"], "blocked")
        self.assertEqual(run["agents"][1]["blocked_by"], "planner")
        self.assertIsNone(run["report"])


class WorkflowTests(unittest.TestCase):
    def test_upload_and_run_to_markdown(self):
        with TestClient(app) as client:
            upload = client.post(
                "/api/files",
                files={"files": ("notes.txt", b"Check alternatives before committing.", "text/plain")},
            )
            self.assertEqual(upload.status_code, 201)
            doc_id = upload.json()["documents"][0]["id"]
            created = client.post(
                "/api/runs",
                json={"question": "What are the next steps?", "document_ids": [doc_id], "mode": "demo"},
            )
            self.assertEqual(created.status_code, 201)
            run_id = created.json()["id"]
            for _ in range(70):
                run = client.get(f"/api/runs/{run_id}").json()
                if run["status"] in ("completed", "failed", 'waiting_approval'):
                    break
                time.sleep(0.1)
            self.assertEqual(run["status"], "waiting_approval", run.get("error"))
            self.assertEqual([agent["status"] for agent in run["agents"]], ["completed"] * 4 + ['waiting_approval'])
            report = client.get(f"/api/runs/{run_id}/report")
            self.assertEqual(report.status_code, 200)
            self.assertIn("规则演示 / 非 AI 推理", report.text)
            self.assertIn("Risk Reviewer Agent", report.text)

    def test_missing_file_and_live_without_key(self):
        with TestClient(app) as client:
            invalid = client.post("/api/runs", json={"question": "Review supply chain", "document_ids": ["missing"]})
            self.assertEqual(invalid.status_code, 404)


if __name__ == "__main__":
    unittest.main()
