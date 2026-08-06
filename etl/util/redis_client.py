"""
    Redis client
    @author: Nabeel Ahmed Jamil
"""
import os
import uuid
from time import sleep

import redis
from etl.util.logging_config import get_logger

# Configure colored logging
logger = get_logger(__name__)

class RedisClient:

    def __init__(self, host=None, port=None, db=None, password=None):
        self.host = host or os.environ.get('REDIS_HOST', 'localhost')
        self.port = port or os.environ.get('REDIS_PORT', 6379)
        self.db = db or os.environ.get('REDIS_DB', 0)
        self.password = db or os.environ.get('REDIS_PASSWORD', "redis123")
        logger.info("Connecting to Redis at %s:%s, db=%s", self.host, self.port, self.db)
        self.client = redis.Redis(host=self.host, port=self.port, password=self.password, decode_responses=True)
        logger.info("Ping client statsu=%s", self.client.ping())

    # ------------------------------------------------------------------
    # Bucket operations
    # ------------------------------------------------------------------
    def add_object(self, key, value):
        """
            Add an object to Redis.
            Returns True if the object was added successfully, otherwise returns False.
        """
        try:
            self.client.hset(key, mapping=value)
            logger.info("SUCCESS: object added key=%s", key)
            return True
        except Exception as e:
            logger.error("ERROR: failed to add object key=%s error=%s", key, str(e))
            return False

    def get_object_field(self, key, field):
        """
            Get an object from Redis by key.
            Returns the object if found, otherwise returns None.
        """
        try:
            obj = self.client.hget(key, field)
            if obj is not None:
                logger.info("SUCCESS: object retrieved key=%s", key)
                return obj
            else:
                logger.warning("WARNING: object not found key=%s", key)
                return None
        except Exception as e:
            logger.error("ERROR: failed to retrieve object key=%s error=%s", key, str(e))
            return None

    def get_object_fields(self, key, fields):
        """
            Get multiple fields from a hash in Redis by key.
            Returns a dictionary of field-value pairs if found, otherwise returns None.
        """
        try:
            obj = self.client.hmget(key, fields)
            if obj is not None:
                logger.info("SUCCESS: object retrieved key=%s", key)
                return dict(zip(fields, obj))
            else:
                logger.warning("WARNING: object not found key=%s", key)
                return None
        except Exception as e:
            logger.error("ERROR: failed to retrieve object key=%s error=%s", key, str(e))
            return None

    def get_object(self, key):
        """
            Get all fields from a hash in Redis by key.
            Returns a dictionary of field-value pairs if found, otherwise returns None.
        """
        try:
            obj = self.client.hgetall(key)
            if obj is not None:
                logger.info("SUCCESS: object retrieved key=%s", key)
                return obj
            else:
                logger.warning("WARNING: object not found key=%s", key)
                return None
        except Exception as e:
            logger.error("ERROR: failed to retrieve object key=%s error=%s", key, str(e))
            return None

    def get_object_field_names(self, key):
        """
            Get all field names from a hash in Redis by key.
            Returns a list of field names if found, otherwise returns None.
        """
        try:
            obj = self.client.hkeys(key)
            if obj is not None:
                logger.info("SUCCESS: object retrieved key=%s", key)
                return obj
            else:
                logger.warning("WARNING: object not found key=%s", key)
                return None
        except Exception as e:
            logger.error("ERROR: failed to retrieve object key=%s error=%s", key, str(e))
            return None

    def get_object_field_values(self, key):
        """
            Get all field values from a hash in Redis by key.
            Returns a list of field values if found, otherwise returns None.
        """
        try:
            obj = self.client.hvals(key)
            if obj is not None:
                logger.info("SUCCESS: object retrieved key=%s", key)
                return obj
            else:
                logger.warning("WARNING: object not found key=%s", key)
                return None
        except Exception as e:
            logger.error("ERROR: failed to retrieve object key=%s error=%s", key, str(e))
            return None

    def delete_object(self, key):
        """
            Delete an object from Redis.
            Returns True if the object was deleted successfully, otherwise returns False.
        """
        try:
            self.client.delete(key)
            logger.info("SUCCESS: object deleted key=%s", key)
            return True
        except Exception as e:
            logger.error("ERROR: failed to delete object key=%s", key)
            return False

    def delete_object_field(self, key, *fields):
        """
        Delete multiple fields from a hash in Redis by key.
        """
        try:
            self.client.hdel(key, fields)
            logger.info("SUCCESS: object deleted key=%s", key)
            return True
        except Exception as e:
            logger.error("ERROR: failed to delete object key=%s error=%s", key, str(e))
            return False

    def exists(self, key):
        """
            Check if an object exists in Redis.
            Returns True if the object exists, otherwise returns False.
        """
        try:
            exists = self.client.exists(key)
            logger.info("SUCCESS: object exists key=%s", key)
            return exists
        except Exception as e:
            logger.error("ERROR: failed to check existence of object key=%s error=%s", key, str(e))
            return False

    def set_expire(self, key, seconds):
        """
            Set an expiration time for an object in Redis.
            Returns True if the expiration time was set successfully, otherwise returns False.
        """
        try:
            self.client.expire(key, seconds)
            logger.info("SUCCESS: object expiration set key=%s seconds=%d", key, seconds)
            return True
        except Exception as e:
            logger.error("ERROR: failed to set expiration for object key=%s error=%s", key, str(e))
            return False

    def remaining_expire(self, key):
        """
            Reset an expiration time for an object in Redis.
            Returns True if the expiration time was set successfully, otherwise returns False.
        """
        try:
            return self.client.ttl(key)
        except Exception as e:
            logger.error("ERROR: failed to retrieve expiration for object key=%s error=%s", key, str(e))
            return False


if __name__ == '__main__':
    # Example usage
    redis_client = RedisClient()
    id = str(uuid.uuid4())
    user = {
        "id": id,
        'field1': 'value1',
        'field2': 'value2',
        'field3': 'value3'
    }
    # Add the object to Redis
    redis_client.add_object(id, user)
    print(redis_client.get_object(id))
    print(redis_client.get_object_field_values(id))
    print(redis_client.get_object_field_names(id))
    print(redis_client.get_object_field(id, 'field1'))
    print(redis_client.get_object_fields(id, ['field1', 'field2']))
    print(redis_client.set_expire(id, 60))
    while redis_client.remaining_expire(id) > 0:
        sleep(0.1)
        print(f"Remaining expiration time for object {id}: {redis_client.remaining_expire(id)} seconds")
    print(redis_client.delete_object_field(id, 'field1', 'field2'))