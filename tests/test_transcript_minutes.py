"""
    MIG-104 (the owner's decision, 2026-09-23): ai.transcript.minutes has producers. A transcription bills
    the minutes of audio it transcribed -- the input's own length, as a speech-to-text API bills -- from
    both places audio is transcribed:
      - a pipeline run, on the run's own meter (task_payload["meter"]), once per file transcribed;
      - the ad-hoc worker endpoint, which answers durationSeconds beside the transcript so media-service,
        the caller that knows the workspace, can meter it.
    A file that failed validation was not transcribed and bills nothing.
"""
import unittest
import warnings
from unittest import mock

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from fastapi.testclient import TestClient
    from etl.service import audio_extract_service as service
    from etl.tasks import mp3_noise_processing_extract_txt_f768927 as task


def output(minutes, text="hello there"):
    return task.AudioTranscriptOutput(cleaned_text=text, segments=[], duration_ms=minutes * 60_000)


class FakeMeter:
    def __init__(self):
        self.events = []

    def event(self, meter, quantity, unit=None, subject=None, note=None):
        self.events.append((meter, quantity, unit, subject))


class WorkerEndpointTest(unittest.TestCase):

    def test_an_upload_answers_the_audio_length_beside_the_transcript(self):
        with mock.patch.object(service, "process_one_audio_file", return_value=output(2.5)):
            r = TestClient(service.app).post("/extract/upload", files={"file": ("call.mp3", b"ID3...", "audio/mpeg")})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"transcript": "hello there", "durationSeconds": 150.0})

    def test_timestamps_do_not_lose_the_length(self):
        with mock.patch.object(service, "process_one_audio_file", return_value=output(1)):
            r = TestClient(service.app).post("/extract/upload", files={"file": ("call.m4a", b"....", "audio/mp4")}, data={"timestamps": "true"})
        self.assertEqual(r.json()["durationSeconds"], 60.0)


class PipelineRunTest(unittest.TestCase):

    def run_task(self, outputs):
        meter = FakeMeter()
        payload = {"input_folder": "calls/", "output_folder": "out", "job_id": 1, "job_queue_id": 2, "meter": meter}
        names = [f"calls/{n}.mp3" for n in outputs]
        with mock.patch.object(task, "minio_client") as minio, \
                mock.patch.object(task, "process_one_audio_file", side_effect=list(outputs.values())), \
                mock.patch.object(task, "job_audit_log"):
            minio.list_objects.return_value = names
            minio.get_object_bytes.return_value = b"audio"
            minio.upload_bytes.return_value = True
            task.mp3_noise_processing_extract_txt(payload)
        return meter.events

    def test_every_transcribed_file_bills_its_minutes_on_the_runs_meter(self):
        events = self.run_task({"a": output(3), "b": output(0.5)})
        self.assertEqual(events, [("ai.transcript.minutes", 3.0, "minute", ("object", "a.mp3")),
                                  ("ai.transcript.minutes", 0.5, "minute", ("object", "b.mp3"))])

    def test_a_file_that_failed_validation_bills_nothing(self):
        self.assertEqual(self.run_task({"a": None, "b": output(1)}), [("ai.transcript.minutes", 1.0, "minute", ("object", "b.mp3"))])

    def test_a_run_without_a_meter_still_transcribes(self):
        with mock.patch.object(task, "minio_client") as minio, \
                mock.patch.object(task, "process_one_audio_file", return_value=output(1)), \
                mock.patch.object(task, "job_audit_log"):
            minio.list_objects.return_value = ["calls/a.mp3"]
            minio.get_object_bytes.return_value = b"audio"
            minio.upload_bytes.return_value = True
            task.mp3_noise_processing_extract_txt({"input_folder": "calls/", "output_folder": "out", "job_id": 1, "job_queue_id": 2})
            minio.upload_bytes.assert_called_once()


if __name__ == "__main__":
    unittest.main()
