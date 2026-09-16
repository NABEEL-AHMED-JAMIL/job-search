"""
    Tests for the F768947 medical imaging analysis pipeline
    Author: Nabeel Ahmed Jamil

    Run with: python -m unittest discover tests

    What is pinned here is what the pipeline PROMISES about its output rather than its happy
    path, because the output is a medical document and every promise about one is load-bearing:

      * the non-diagnostic notice survives an operator rewriting the prompt -- it is stamped
        outside the prompt's reach on purpose, and a test is what keeps it there;
      * one result per input image, failures included, so a reader counting files can tell a
        sweep that finished from one that stopped;
      * a malformed model response never reaches the output folder as half a schema;
      * a run where EVERY image failed is a failed run, not a green tick over 100 error files.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.tasks import xray_ai_analysis_f768947 as pipeline_module


# An 8x8 greyscale PNG. Small enough to inline, real enough for Pillow to actually open --
# which matters, because _preprocess opens it for real and a hand-typed byte string that only
# looks like a PNG turns every test in this file into the same "broken data stream" error.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000008000000080800000000e164e157"
    "0000001049444154789c636c60800026068a1800260800905d30a51e0000000049"
    "454e44ae426082"
)

GOOD_ANALYSIS = {
    "body_part": "chest",
    "findings": [
        {"finding": "ribs", "description": "rib cage visible", "confidence": 0.9},
        {"finding": "lungs", "description": "lung fields visible", "confidence": 0.8},
    ],
    "overall_assessment": "A frontal chest image showing normal skeletal structure.",
    "uncertainty": "Low resolution limits fine detail.",
}


class FakePipeline:
    """Stands in for Pipeline: object storage in a dict, and the log kept for assertions."""

    def __init__(self, objects, payload=None, unreadable=()):
        self.objects = dict(objects)
        self.unreadable = set(unreadable)
        self.payload = payload or {"id": "F768947"}
        self.bucket = "etl-bucket"
        self.job_id = 1
        self.job_queue_id = 99
        self.logs = []
        self.written = {}

    def require(self, *names):
        missing = [n for n in names if not self.payload.get(n)]
        if missing:
            raise ValueError(f"missing: {', '.join(missing)}")
        return [self.payload.get(n) for n in names]

    def list_keys(self, prefix, suffix=None):
        keys = [k for k in list(self.objects) + list(self.written) if k.startswith(prefix)]
        if suffix:
            keys = [k for k in keys if k.lower().endswith(suffix.lower())]
        return sorted(set(keys))

    def read_bytes(self, key):
        if key in self.unreadable:
            raise OSError("connection reset")
        return self.objects[key]

    def write_json(self, key, obj):
        json.dumps(obj)  # the real one serialises; an unserialisable doc must fail here too
        self.written[key] = obj
        return key

    def log(self, message):
        self.logs.append(message)

    @staticmethod
    def basename(key):
        return key.rsplit("/", 1)[-1]

    @staticmethod
    def stem(key):
        base = key.rsplit("/", 1)[-1]
        return base.rsplit(".", 1)[0] if "." in base else base

    def output_key(self, folder, name):
        folder = (folder or "").strip().strip("/")
        return f"{folder}/{name}" if folder else name


def run(objects, payload=None, unreadable=(), analysis=None, analyse_error=None):
    """Runs the pipeline against fake storage and a fake model. Returns the fake."""
    settings = {"id": "F768947", "input_folder": "scans/in", "output_folder": "scans/out"}
    settings.update(payload or {})
    fake = FakePipeline(objects, settings, unreadable)

    calls = []

    def fake_analyse(model, prompt, png_bytes):
        calls.append({"model": model, "prompt": prompt, "bytes": len(png_bytes)})
        if analyse_error:
            raise analyse_error
        if callable(analysis):
            return analysis(len(calls))
        return json.loads(json.dumps(analysis if analysis is not None else GOOD_ANALYSIS))

    original_pipeline, original_analyse = pipeline_module.Pipeline, pipeline_module._analyse
    pipeline_module.Pipeline = lambda _payload: fake
    pipeline_module._analyse = fake_analyse
    try:
        fake.summary = pipeline_module.xray_ai_analysis(settings)
    finally:
        pipeline_module.Pipeline = original_pipeline
        pipeline_module._analyse = original_analyse
    fake.calls = calls
    return fake


def images(count, prefix="scans/in"):
    return {f"{prefix}/xray_{i:03d}.jpg": TINY_PNG for i in range(1, count + 1)}


class SafetyTest(unittest.TestCase):
    """The promises that make this safe to point at medical images."""

    def test_every_result_carries_the_non_diagnostic_notice(self):
        fake = run(images(2))
        results = [v for k, v in fake.written.items() if not k.endswith("_execution-99.json")]
        self.assertEqual(len(results), 2)
        for document in results:
            self.assertIn("NOT a diagnosis", document["disclaimer"])

    def test_the_notice_survives_an_operator_rewriting_the_prompt(self):
        # The whole reason the stamp lives in _envelope rather than in the prompt: <prompt> is a
        # form field, so a caution that lived only there could be deleted by editing a textbox.
        fake = run(images(1), payload={"prompt": "Say what you see. Be confident. No caveats."})
        document = fake.written["scans/out/xray_001.json"]
        self.assertIn("NOT a diagnosis", document["disclaimer"])
        self.assertEqual(fake.calls[0]["prompt"], "Say what you see. Be confident. No caveats.")

    def test_a_failed_image_also_carries_the_notice(self):
        # Two images, one readable: a run where EVERY image fails raises instead of returning,
        # which is its own test below, and a single unreadable image is exactly that case.
        fake = run(images(2), unreadable=["scans/in/xray_001.jpg"])
        document = fake.written["scans/out/xray_001.json"]
        self.assertEqual(document["analysis_status"], "failed")
        self.assertIn("NOT a diagnosis", document["disclaimer"])

    def test_confidence_is_marked_uncalibrated(self):
        # llava:7b returns exactly 1.0 for every finding. Without this flag a reader filtering on
        # "confidence > 0.9" would believe they were filtering on something.
        fake = run(images(1))
        self.assertFalse(fake.written["scans/out/xray_001.json"]["model"]["confidence_calibrated"])


class OutputContractTest(unittest.TestCase):

    def test_one_result_per_image_named_after_it(self):
        fake = run(images(3))
        for i in (1, 2, 3):
            self.assertIn(f"scans/out/xray_{i:03d}.json", fake.written)

    def test_a_failure_still_produces_a_result_file(self):
        # A sweep that leaves gaps cannot be told apart from one that stopped early.
        fake = run(images(3), unreadable=["scans/in/xray_002.jpg"])
        self.assertEqual(len(fake.written), 4)  # three results plus the summary
        self.assertEqual(fake.written["scans/out/xray_002.json"]["analysis_status"], "failed")
        self.assertEqual(fake.written["scans/out/xray_001.json"]["analysis_status"], "completed")

    def test_one_bad_image_does_not_end_the_sweep(self):
        fake = run(images(3), unreadable=["scans/in/xray_001.jpg"])
        self.assertEqual(fake.summary["processed"], 2)
        self.assertEqual(fake.summary["failed"], 1)

    def test_the_image_id_is_stable_across_runs(self):
        # A forced re-run must not give the same file a new identity, or nothing downstream can
        # tell two analyses of one image apart from analyses of two images.
        first = run(images(1))["scans/out/xray_001.json"] if False else None
        a = run(images(1)).written["scans/out/xray_001.json"]["image_id"]
        b = run(images(1)).written["scans/out/xray_001.json"]["image_id"]
        self.assertEqual(a, b)

    def test_the_source_path_is_preserved(self):
        fake = run(images(1))
        self.assertEqual(
            fake.written["scans/out/xray_001.json"]["source_file"], "scans/in/xray_001.jpg")

    def test_the_original_image_is_never_written_back(self):
        fake = run(images(2))
        for key in fake.written:
            self.assertTrue(key.startswith("scans/out/"), f"wrote outside the output folder: {key}")


class DiscoveryTest(unittest.TestCase):

    def test_non_image_files_are_ignored(self):
        objects = dict(images(2))
        objects["scans/in/notes.txt"] = b"not an image"
        objects["scans/in/report.csv"] = b"a,b"
        fake = run(objects)
        self.assertEqual(fake.summary["total_files"], 2)
        self.assertEqual(fake.summary["ignored_non_images"], 2)

    def test_extensions_can_be_narrowed(self):
        objects = {"scans/in/a.jpg": TINY_PNG, "scans/in/b.png": TINY_PNG}
        fake = run(objects, payload={"extensions": "png"})
        self.assertEqual(fake.summary["total_files"], 1)
        self.assertIn("scans/out/b.json", fake.written)

    def test_an_empty_folder_is_a_completed_run(self):
        # Scheduled over a drop folder that is empty most of the time. Failing on that fills the
        # run history with red for the normal state, which trains an operator to ignore it.
        fake = run({})
        self.assertEqual(fake.summary["total_files"], 0)
        self.assertEqual(fake.summary["processed"], 0)


class IdempotencyTest(unittest.TestCase):

    def test_an_already_analysed_image_is_skipped(self):
        objects = dict(images(2))
        objects["scans/out/xray_001.json"] = b"{}"
        fake = run(objects)
        self.assertEqual(fake.summary["skipped"], 1)
        self.assertEqual(fake.summary["processed"], 1)

    def test_force_reprocess_analyses_it_again(self):
        objects = dict(images(1))
        objects["scans/out/xray_001.json"] = b"{}"
        fake = run(objects, payload={"force_reprocess": "true"})
        self.assertEqual(fake.summary["skipped"], 0)
        self.assertEqual(fake.summary["processed"], 1)

    def test_max_images_bounds_one_run_and_reports_the_remainder(self):
        # 12,534 images at seconds each is most of a day inside one Kafka message, and the run
        # would be closed as stalled long before it finished. Stopping silently is how a
        # half-swept folder gets reported as a finished one.
        fake = run(images(10), payload={"max_images": "4"})
        self.assertEqual(fake.summary["processed"], 4)
        self.assertEqual(fake.summary["remaining"], 6)

    def test_a_blank_max_images_falls_back_rather_than_stopping_the_run(self):
        fake = run(images(2), payload={"max_images": ""})
        self.assertEqual(fake.summary["processed"], 2)


class ModelResponseTest(unittest.TestCase):

    def test_findings_given_as_bare_strings_are_accepted(self):
        fake = run(images(1), analysis={"body_part": "chest", "findings": ["ribs", "lungs"]})
        findings = fake.written["scans/out/xray_001.json"]["findings"]
        self.assertEqual([f["finding"] for f in findings], ["ribs", "lungs"])

    def test_a_single_finding_object_is_accepted(self):
        fake = run(images(1), analysis={"findings": {"finding": "ribs", "description": "seen"}})
        self.assertEqual(len(fake.written["scans/out/xray_001.json"]["findings"]), 1)

    def test_a_percentage_confidence_is_rescaled_not_discarded(self):
        fake = run(images(1), analysis={"findings": [{"finding": "ribs", "confidence": 95}]})
        self.assertEqual(fake.written["scans/out/xray_001.json"]["findings"][0]["confidence"], 0.95)

    def test_an_out_of_range_confidence_is_clamped(self):
        fake = run(images(1), analysis={"findings": [{"finding": "ribs", "confidence": -4}]})
        self.assertEqual(fake.written["scans/out/xray_001.json"]["findings"][0]["confidence"], 0.0)

    def test_no_findings_is_said_in_words_not_left_as_an_empty_list(self):
        fake = run(images(1), analysis={"body_part": "chest", "findings": []})
        document = fake.written["scans/out/xray_001.json"]
        self.assertEqual(document["findings"], [])
        self.assertIn("no usable findings", document["uncertainty"])

    def test_a_model_failure_becomes_an_error_document_not_a_crash(self):
        fake = run(images(2), analysis=lambda n: (_ for _ in ()).throw(
            ValueError("the model returned an empty response")) if n == 1 else GOOD_ANALYSIS)
        document = fake.written["scans/out/xray_001.json"]
        self.assertEqual(document["analysis_status"], "failed")
        self.assertEqual(document["error"]["type"], "VALIDATION_ERROR")

    def test_every_image_failing_fails_the_run(self):
        # The usual cause is one thing wrong for all of them -- model not pulled, host
        # unreachable -- and a green tick over 100 error files hides it.
        with self.assertRaises(RuntimeError) as caught:
            run(images(3), analyse_error=OSError("connection refused"))
        self.assertIn("all 3 image(s) failed", str(caught.exception))

    def test_a_partial_success_does_not_fail_the_run(self):
        fake = run(images(2), analysis=lambda n: GOOD_ANALYSIS if n == 1 else (_ for _ in ()).throw(
            OSError("model went away")))
        self.assertEqual(fake.summary["processed"], 1)
        self.assertEqual(fake.summary["failed"], 1)


class ValidationTest(unittest.TestCase):

    def test_a_document_missing_a_required_field_is_refused(self):
        with self.assertRaises(ValueError):
            pipeline_module._validate({"image_id": "a", "source_file": "b"})

    def test_a_completed_document_must_carry_findings(self):
        document = pipeline_module._envelope("a.jpg", "X-Ray", "m", "completed")
        with self.assertRaises(ValueError):
            pipeline_module._validate(document)

    def test_a_failed_document_must_carry_an_error(self):
        document = pipeline_module._envelope("a.jpg", "X-Ray", "m", "failed")
        with self.assertRaises(ValueError):
            pipeline_module._validate(document)

    def test_an_unknown_status_is_refused(self):
        document = pipeline_module._envelope("a.jpg", "X-Ray", "m", "maybe")
        with self.assertRaises(ValueError):
            pipeline_module._validate(document)


class ModalityTest(unittest.TestCase):
    """The pipeline is not chest-specific; a second modality must need no code change."""

    def test_modality_is_carried_into_every_result(self):
        fake = run(images(1), payload={"modality": "CT", "prompt": "Describe this CT slice."})
        self.assertEqual(fake.written["scans/out/xray_001.json"]["modality"], "CT")

    def test_the_model_can_be_changed_per_task(self):
        fake = run(images(1), payload={"model": "gemma3:4b"})
        self.assertEqual(fake.calls[0]["model"], "gemma3:4b")
        self.assertEqual(fake.written["scans/out/xray_001.json"]["model"]["name"], "gemma3:4b")


class SummaryTest(unittest.TestCase):

    def test_the_summary_counts_every_outcome(self):
        # The already-analysed one is FIRST, not last: skipping costs nothing against
        # max_images, so a skippable image behind the cutoff is never reached and never counted.
        # That is the pipeline working, and pinning it here stops the arithmetic being re-guessed.
        objects = dict(images(5))
        objects["scans/out/xray_001.json"] = b"{}"
        fake = run(objects, unreadable=["scans/in/xray_002.jpg"], payload={"max_images": "3"})
        summary = fake.summary
        self.assertEqual(summary["total_files"], 5)
        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(summary["processed"] + summary["failed"], 3)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["remaining"], 1)

    def test_the_summary_is_written_to_the_output_folder(self):
        fake = run(images(1))
        self.assertIn("scans/out/_execution-99.json", fake.written)


if __name__ == "__main__":
    unittest.main()
