import os
import redis

# Redis client setup
if 'REDIS_URL' in os.environ:
    redis_client = redis.from_url(os.environ['REDIS_URL'])
else:
    redis_client = None

class RedisStreamRedirector:
    """Stream redirector that writes to Redis for distributed logging"""
    
    def __init__(self, session_id, redis_client, log_type="default"):
        self.session_id = session_id
        self.redis_client = redis_client
        self.key = f"{log_type}_log:{session_id}"
        
    def write(self, text):
        if self.redis_client:
            # Append to Redis list
            self.redis_client.lpush(self.key, text)
            # Keep only last 1000 entries
            self.redis_client.ltrim(self.key, 0, 999)
            # Set expiration (24 hours)
            self.redis_client.expire(self.key, 86400)
        else:
            print(text, end='')
    
    def flush(self):
        pass

def get_logs_from_redis(session_id, log_type="default"):
    """Retrieve logs from Redis for a given session and log type"""
    if not redis_client:
        return ""
    
    try:
        key = f"{log_type}_log:{session_id}"
        logs = redis_client.lrange(key, 0, -1)
        if logs:
            # Reverse to get chronological order
            return "".join(log.decode('utf-8') for log in reversed(logs))
    except Exception as e:
        print(f"Error reading from Redis: {e}")
        return f"Error reading logs: {e}"
    
    return ""