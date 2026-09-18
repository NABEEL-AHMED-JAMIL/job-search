"""
    Tests for the AI steps a pipeline hands to the worker, and the per-run callback token.
    Author: Nabeel Ahmed Jamil

    Run with: python -m unittest discover tests
"""
import json
import os
import sys
import threading
import unittest
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.util.ai_steps import AiStepError, resolve_ai_steps
from etl.util.job_state_client import JobStateClient

DOCUMENT = (
    '<pipeline>\n'
    '  <claim_id>CLM-1</claim_id>\n'
    '  <document>claims/in/CLM-1.txt</document>\n'
    '  <ai_step prompt="uuid-9" version="3" output="summary" on_error="fail">\n'
    '    <var name="claim_id" from="claim_id" as="text"/>\n'
    '    <var name="document_text" from="document" as="file"/>\n'
    '  </ai_step>\n'
    '</pipeline>'
)


class FakeConsole(BaseHTTPRequestHandler):
    """Answers /aiPrompt.json/run the way the console does, and records what it was sent."""
    calls = []
    answer = {"status": "SUCCESS", "message": "Answered in 0.5 s.", "data": {"status": "ok", "output": "Fracture; billed 412 & <flagged>"}}
    code = 200

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        FakeConsole.calls.append({"path": self.path, "token": self.headers.get("X-Worker-Token"), "body": body})
        payload = json.dumps(FakeConsole.answer).encode()
        self.send_response(FakeConsole.code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class AiStepsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeConsole)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        os.environ["ETL_EVENT_URL"] = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeConsole.calls = []
        FakeConsole.code = 200
        FakeConsole.answer = {"status": "SUCCESS", "message": "ok", "data": {"status": "ok", "output": "Fracture; billed 412 & <flagged>"}}

    def test_a_document_without_a_step_is_returned_untouched(self):
        xml = "<pipeline><claim_id>CLM-1</claim_id></pipeline>"
        self.assertIs(resolve_ai_steps(xml, 1, 2, "tok"), xml)
        self.assertEqual(FakeConsole.calls, [])

    def test_the_step_reads_a_tag_and_a_file_asks_the_console_and_writes_the_answer(self):
        reads = []

        def read_object(bucket, key):
            reads.append((bucket, key))
            return b"PATIENT J. Alvarez ... total 412.00"

        # The task names its bucket the way every object-storage pipeline does.
        with_bucket = DOCUMENT.replace("<claim_id>", "<bucket>medaxis</bucket>\n  <claim_id>", 1)
        out = resolve_ai_steps(with_bucket, 2425, 5715, "cbt_1.5715.secret", read_object=read_object)

        # The file was read from the task's bucket by the worker, not sent as a key.
        self.assertEqual(reads, [("medaxis", "claims/in/CLM-1.txt")])
        call = FakeConsole.calls[0]
        self.assertEqual(call["path"], "/aiPrompt.json/run")
        self.assertEqual(call["token"], "cbt_1.5715.secret")
        self.assertEqual(call["body"]["promptUuid"], "uuid-9")
        self.assertEqual(call["body"]["version"], 3)
        self.assertEqual(call["body"]["stepTag"], "summary")
        self.assertEqual(call["body"]["jobQueueId"], 5715)
        self.assertEqual(call["body"]["variables"], {"claim_id": "CLM-1", "document_text": "PATIENT J. Alvarez ... total 412.00"})
        # The answer is a tag, escaped by the writer; the instruction is gone.
        root = ET.fromstring(out)
        self.assertEqual(root.find("summary").text, "Fracture; billed 412 & <flagged>")
        self.assertIsNone(root.find("ai_step"))
        self.assertEqual(root.find("claim_id").text, "CLM-1")

    def test_a_refusal_fails_the_run_or_continues_empty_as_the_step_says(self):
        FakeConsole.answer = {"status": "ERROR", "message": "Daily token budget reached"}
        with self.assertRaises(AiStepError) as failed:
            resolve_ai_steps(DOCUMENT, 1, 2, "tok", read_object=lambda b, k: b"x")
        self.assertIn("budget", str(failed.exception))

        lenient = DOCUMENT.replace('on_error="fail"', 'on_error="continue"')
        out = resolve_ai_steps(lenient, 1, 2, "tok", read_object=lambda b, k: b"x")
        root = ET.fromstring(out)
        self.assertEqual(root.find("summary").text or "", "")
        self.assertIsNone(root.find("ai_step"))

    def test_a_rejected_token_is_named_as_such(self):
        FakeConsole.code = 401
        FakeConsole.answer = {"status": "ERROR", "message": "Unauthorized worker callback."}
        with self.assertRaises(AiStepError) as failed:
            resolve_ai_steps(DOCUMENT, 1, 2, "stale", read_object=lambda b, k: b"x")
        self.assertIn("token", str(failed.exception))


class RunTokenTest(unittest.TestCase):

    def test_the_runs_own_token_is_sent_and_the_shared_secret_is_only_the_fallback(self):
        client = JobStateClient("http://console")
        os.environ["WORKER_CALLBACK_TOKEN"] = "shared-secret"
        try:
            client.remember_run_token(2425, 5715, "cbt_1.5715.secret")
            self.assertEqual(client._auth_headers(2425, 5715), {"X-Worker-Token": "cbt_1.5715.secret"})
            # A run this worker was not handed a token for: the shared secret, as before.
            self.assertEqual(client._auth_headers(2425, 9999), {"X-Worker-Token": "shared-secret"})
            client.forget_run_token(2425, 5715)
            self.assertEqual(client._auth_headers(2425, 5715), {"X-Worker-Token": "shared-secret"})
        finally:
            del os.environ["WORKER_CALLBACK_TOKEN"]


if __name__ == "__main__":
    unittest.main()
