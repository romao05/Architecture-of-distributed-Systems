import os
import re
import redis
import rpyc
from rpyc.utils.server import ThreadedServer

# Connect to Redis container on the Docker network host 'redis'
# decode_responses=True ensures strings are returned instead of raw bytes
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)


class WordCountService(rpyc.Service):
    """RPyC Service providing keyword occurrence counts with Redis caching[cite: 1, 3]."""

    def on_connect(self, conn):
        print(f"[SERVER] Client connected: {conn}")

    def on_disconnect(self, conn):
        print(f"[SERVER] Client disconnected: {conn}")

    def exposed_count_keyword(self, filename: str, keyword: str) -> int:
        """
        Calculates the frequency of a keyword in a specified text file.
        Checks Redis cache first before reading from disk[cite: 1, 3].
        """
        # Normalize keys and keywords to ensure case-insensitive matching
        clean_keyword = keyword.strip().lower()
        cache_key = f"{filename}:{clean_keyword}"

        # 1. Cache Lookup[cite: 1]
        try:
            cached_count = redis_client.get(cache_key)
            if cached_count is not None:
                print(f"[CACHE HIT] Key: '{cache_key}' -> Count: {cached_count}")
                return int(cached_count)
        except redis.RedisError as err:
            print(f"[REDIS ERROR] Connection issue during lookup: {err}")

        # 2. Cache Miss[cite: 1]
        print(f"[CACHE MISS] Key: '{cache_key}'. Counting from file...")
        filepath = os.path.join("/data", filename)

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Requested file '{filename}' was not found in /data directory.")

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read().lower()

        # Match exact word occurrences using regex word boundaries (\b)
        pattern = r"\b" + re.escape(clean_keyword) + r"\b"
        count = len(re.findall(pattern, text))

        # Store calculated result in Redis for future requests[cite: 1, 3]
        try:
            redis_client.set(cache_key, count)
        except redis.RedisError as err:
            print(f"[REDIS ERROR] Connection issue during save: {err}")

        return count


if __name__ == "__main__":
    PORT = 18861
    print(f"[SERVER] Starting Threaded RPyC WordCount Server on port {PORT}...")
    server = ThreadedServer(
        WordCountService,
        port=PORT,
        protocol_config={"allow_public_attrs": True}
    )
    server.start()