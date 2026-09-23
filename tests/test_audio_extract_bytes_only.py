"""
MIG-49: transcription is fed bytes, never a bucket and a key.

The ad-hoc audio service once had an endpoint that took a bucket and a key from the caller and
fetched them with this worker's own MinIO credentials: anyone who could reach the port could read
any object in any bucket, and the console's storage permissions stopped at the JVM boundary. The
backend now resolves the object through its own authorisation and posts the bytes to
/extract/upload. Splitting Media & Documents into its own service is exactly when that endpoint
is most likely to come back "for convenience" -- this makes it fail a build instead.
"""
import ast
import inspect
import unittest
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from etl.service import audio_extract_service as service


class TranscriptionIsFedBytesOnly(unittest.TestCase):

    def _api_routes(self):
        return {
            route.path: route for route in service.app.routes
            if getattr(route, "methods", None) and route.path not in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc")
        }

    def test_the_service_answers_exactly_three_endpoints(self):
        self.assertEqual(sorted(self._api_routes()), ["/extract/image", "/extract/upload", "/health"])

    def test_no_endpoint_takes_a_bucket_or_a_key(self):
        for path, route in self._api_routes().items():
            names = {param.name.lower() for param in inspect.signature(route.endpoint).parameters.values()}
            self.assertFalse(names & {"bucket", "bucket_name", "key", "object_key", "storage_key"},
                             "%s takes %s from the caller" % (path, sorted(names)))
            self.assertNotIn("bucket", path.lower())

    def test_extraction_takes_uploaded_bytes(self):
        upload = self._api_routes()["/extract/upload"]
        annotations = [str(p.annotation) for p in inspect.signature(upload.endpoint).parameters.values()]
        self.assertTrue(any("UploadFile" in a for a in annotations), annotations)

    def test_the_module_holds_no_storage_client(self):
        tree = ast.parse(inspect.getsource(service))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported & {"minio", "boto3", "botocore", "azure"}, sorted(imported))


if __name__ == "__main__":
    unittest.main()
