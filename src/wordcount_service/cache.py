"""Redis cache access for word-count results."""

from __future__ import annotations

import os
from typing import Any

import redis


class WordCountCache:
    """Store word-count results and request-frequency statistics in Redis."""

    def __init__(self) -> None:
        self._client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
        )

    def get_count(self, file_id: str, keyword: str) -> int | None:
        value = self._client.get(self._count_key(file_id, keyword))
        return None if value is None else int(value)

    def set_count(self, file_id: str, keyword: str, count: int) -> None:
        self._client.set(self._count_key(file_id, keyword), count)

    def record_request(self, keyword: str) -> None:
        self._client.zincrby("hot_keywords", 1, keyword)

    def hot_keywords(self, limit: int = 10) -> list[tuple[str, float]]:
        values: list[Any] = self._client.zrevrange(
            "hot_keywords", 0, limit - 1, withscores=True
        )
        return [(str(keyword), float(score)) for keyword, score in values]

    @staticmethod
    def _count_key(file_id: str, keyword: str) -> str:
        return f"wordcount:{file_id}:{keyword.casefold()}"