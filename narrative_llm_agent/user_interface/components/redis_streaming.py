import os
import redis
from dash import DiskcacheManager
import sys
import time

def get_background_callback_manager(celery_app=None):
    """Factory function to get appropriate background callback manager."""

    if 'REDIS_URL' in os.environ:
        # Use Redis & Celery if REDIS_URL set as an env variable
        from dash import CeleryManager
        background_callback_manager = CeleryManager(celery_app)

    else:
        # Diskcache for non-production apps when developing locally
        import diskcache
        cache = diskcache.Cache("./cache")
        background_callback_manager = DiskcacheManager(cache)
    
    return background_callback_manager

def get_redis_client():
    """Get Redis client if available"""
    return redis.from_url(os.environ['REDIS_URL']) if 'REDIS_URL' in os.environ else None


class RedisStreamRedirector:
    def __init__(self, session_id: str, redis_client):
        self.session_id = session_id
        self.redis_client = redis_client
        self.original_stdout = None
        self.original_stderr = None
        self.key = f"analysis_log:{session_id}"
    def __enter__(self):
        # Store original streams
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        # Redirect to this instance
        sys.stdout = self
        sys.stderr = self
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original streams
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        if exc_type:
            # Log exception to Redis
            self._write_to_redis(f"💥 Exception: {exc_type.__name__}: {exc_val}")

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

redis_client = get_redis_client()

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