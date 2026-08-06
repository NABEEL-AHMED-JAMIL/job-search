"""
    MinIO Client
    @author: Nabeel Ahmed Jamil
"""
import io
import os
from datetime import timedelta

from dotenv import load_dotenv
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error
from etl.util.logging_config import get_logger

# ------------------------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------------------------
load_dotenv()
# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logger = get_logger(__name__)


class MinioClient:

    def __init__(self, endpoint=None, access_key=None, secret_key=None, secure=None):
        """
            endpoint: host:port, e.g. localhost:9000 (no http:// prefix)
            secure: True for https, False for http
        """
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin123")
        if secure is None:
            secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=secure
        )

    # ------------------------------------------------------------------
    # Bucket operations
    # ------------------------------------------------------------------
    def create_bucket(self, bucket_name):
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info("SUCCESS: bucket created bucket=%s", bucket_name)
            else:
                logger.info("SKIPPED: bucket already exists bucket=%s", bucket_name)
            return True
        except S3Error as e:
            logger.error("ERROR creating bucket=%s: %s", bucket_name, e)
            return False

    def delete_bucket(self, bucket_name):
        """Bucket must be empty before it can be removed."""
        try:
            self.client.remove_bucket(bucket_name)
            logger.info("SUCCESS: bucket removed bucket=%s", bucket_name)
            return True
        except S3Error as e:
            logger.error("ERROR removing bucket=%s: %s", bucket_name, e)
            return False

    def bucket_exists(self, bucket_name):
        try:
            return self.client.bucket_exists(bucket_name)
        except S3Error as e:
            logger.error("ERROR checking bucket=%s: %s", bucket_name, e)
            return False

    def list_buckets(self):
        try:
            buckets = [b.name for b in self.client.list_buckets()]
            logger.info("SUCCESS: listed %d bucket(s)", len(buckets))
            return buckets
        except S3Error as e:
            logger.error("ERROR listing buckets: %s", e)
            return []

    # ------------------------------------------------------------------
    # Object operations
    # ------------------------------------------------------------------

    def upload_file(self, bucket_name, object_name, file_path, content_type="application/octet-stream"):
        """Upload a local file to bucket_name/object_name."""
        try:
            self.client.fput_object(bucket_name, object_name, file_path, content_type=content_type)
            logger.info("SUCCESS: uploaded file=%s bucket=%s object=%s", file_path, bucket_name, object_name)
            return True
        except (S3Error, OSError) as e:
            logger.error("ERROR uploading file=%s bucket=%s object=%s: %s", file_path, bucket_name, object_name, e)
            return False

    def upload_bytes(self, bucket_name, object_name, data, content_type="application/octet-stream"):
        """Upload raw bytes to bucket_name/object_name."""
        try:
            data_stream = io.BytesIO(data)
            self.client.put_object(bucket_name, object_name, data_stream, length=len(data), content_type=content_type)
            logger.info("SUCCESS: uploaded bytes bucket=%s object=%s size=%d", bucket_name, object_name, len(data))
            return True
        except S3Error as e:
            logger.error("ERROR uploading bytes bucket=%s object=%s: %s", bucket_name, object_name, e)
            return False

    def download_file(self, bucket_name, object_name, file_path):
        """Download bucket_name/object_name to a local file_path."""
        try:
            self.client.fget_object(bucket_name, object_name, file_path)
            logger.info("SUCCESS: downloaded bucket=%s object=%s to file=%s", bucket_name, object_name, file_path)
            return True
        except (S3Error, OSError) as e:
            logger.error("ERROR downloading bucket=%s object=%s: %s", bucket_name, object_name, e)
            return False

    def get_object_bytes(self, bucket_name, object_name):
        """Fetch bucket_name/object_name and return its raw bytes."""
        response = None
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            logger.info("SUCCESS: fetched bucket=%s object=%s size=%d", bucket_name, object_name, len(data))
            return data
        except S3Error as e:
            logger.error("ERROR fetching bucket=%s object=%s: %s", bucket_name, object_name, e)
            return None
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def list_objects(self, bucket_name, prefix=None, recursive=True):
        """List object names in bucket_name, optionally filtered by prefix."""
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=recursive)
            names = [obj.object_name for obj in objects]
            logger.info("SUCCESS: listed %d object(s) bucket=%s prefix=%s", len(names), bucket_name, prefix)
            return names
        except S3Error as e:
            logger.error("ERROR listing objects bucket=%s prefix=%s: %s", bucket_name, prefix, e)
            return []

    def object_exists(self, bucket_name, object_name):
        try:
            self.client.stat_object(bucket_name, object_name)
            return True
        except S3Error:
            return False

    def delete_object(self, bucket_name, object_name):
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info("SUCCESS: deleted bucket=%s object=%s", bucket_name, object_name)
            return True
        except S3Error as e:
            logger.error("ERROR deleting bucket=%s object=%s: %s", bucket_name, object_name, e)
            return False

    def delete_objects(self, bucket_name, object_names):
        """Bulk delete a list of object names from bucket_name."""
        try:
            errors = self.client.remove_objects(
                bucket_name, [DeleteObject(name) for name in object_names]
            )
            error_count = 0
            for error in errors:
                error_count += 1
                logger.error("ERROR deleting bucket=%s object=%s: %s", bucket_name, error.name, error)
            deleted_count = len(object_names) - error_count
            logger.info("SUCCESS: deleted %d/%d object(s) bucket=%s", deleted_count, len(object_names), bucket_name)
            return error_count == 0
        except S3Error as e:
            logger.error("ERROR bulk deleting bucket=%s: %s", bucket_name, e)
            return False

    def get_presigned_url(self, bucket_name, object_name, expires_hours=1):
        """Temporary shareable download URL for bucket_name/object_name."""
        try:
            url = self.client.presigned_get_object(
                bucket_name, object_name, expires=timedelta(hours=expires_hours)
            )
            logger.info("SUCCESS: presigned url bucket=%s object=%s expires_hours=%d", bucket_name, object_name, expires_hours)
            return url
        except S3Error as e:
            logger.error("ERROR presigning bucket=%s object=%s: %s", bucket_name, object_name, e)
            return None

if __name__ == '__main__':
    # Example usage of MinioClient
    minio_client = MinioClient()
    # Create a bucket
    minio_client.create_bucket("test-bucket")
    # Upload a file
    minio_client.upload_file("test-bucket", "example.txt", "example.txt")
    # List objects in the bucket
    objects = minio_client.list_objects("test-bucket")
    print("Objects in bucket:", objects)
    # Download the file
    minio_client.download_file("test-bucket", "example.txt", "downloaded_example.txt")
    # Get presigned URL
    url = minio_client.get_presigned_url("test-bucket", "example.txt")
    print("Presigned URL:", url)
    # Delete the object
    minio_client.delete_object("test-bucket", "example.txt")
    # Delete the bucket
    minio_client.delete_bucket("test-bucket")
