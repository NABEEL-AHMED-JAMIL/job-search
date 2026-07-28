import uuid
import redis
import os

def redis_client():
    host = os.environ['REDIS_HOST'] = 'localhost'
    port = os.environ['REDIS_PORT'] = '6379'
    password = os.environ['REDIS_PASSWORD'] = 'redis123'
    redis_client = redis.Redis(
        host=host,
        port=port,
        password=password,
        decode_responses=True)
    return redis_client

def add_item(redis_client,key, value):
    """
        Add an item to Redis.
    """
    redis_client.hset(key, mapping=value)

def delete_item(redis_client, key):
    """
        Delete an item from Redis.
    """
    redis_client.delete(key)

def get_item(redis_client ,key):
    """
        Get an item from Redis.
    """
    return redis_client.hgetall(key)

def get_item_filed(redis_client, key, filed):
    """
        Projection on key
        key: afd16ba1-ca87-48b6-8886-1c0e01313cdb
        value: {'uuui': 'afd16ba1-ca87-48b6-8886-1c0e01313cdb', 'username': 'admin', 'email': 'nabeel.amd82@gmail.com', 'password': 'aw#234'}
        filed: ['uuui', 'username', 'email', 'password']
        want to fetch the target filed from the redis client
    """
    return redis_client.hget(key, filed)

def update_item(redis_client, key, value):
    """
        Update an item from Redis.
    """
    redis_client.hset(key, mapping=value)

if __name__ == '__main__':
    redis_client = redis_client()
    user_id = str(uuid.uuid4())
    user = {
        'uuui': user_id,
        'username': 'admin',
        'email': 'nabeel.amd82@gmail.com',
        'password': 'aw#234'
    }
    add_item(redis_client, user_id, user)
    print(get_item(redis_client, key=user_id))
    user = {
        'uuui': user_id,
        'username': 'admin',
        'password': 'nabeel ahmed',
        'email': 'nabeel.amd82@gmail.com',
    }
    update_item(redis_client, user_id, user)
    print(get_item_filed(redis_client, key=user_id, filed='username'))