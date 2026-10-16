"""RPyC word-count server."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import rpyc
from rpyc.utils.server import ThreadedServer

from wordcount_service.cache import WordCountCache


class WordCountService(rpyc.Service):
    """Expose word counting over RPyC."""

    def __init__(self, files_dir: Path, cache: WordCountCache) -> None:
        self._files_dir = files_dir.resolve()
        self._cache = cache

    def exposed_count(self, file_id: str, keyword: str) -> str:
        if not file_id or not keyword:
            raise ValueError("file_id and keyword must not be empty")

        started = time.perf_counter()
        safe_file = self._resolve_file(file_id)
        normalized_keyword = keyword.casefold()
        self._cache.record_request(normalized_keyword)
        cached_count = self._cache.get_count(file_id, normalized_keyword)

        if cached_count is None:
            text = safe_file.read_text(encoding="utf-8")
            count = len(
                re.findall(
                    rf"(?<!\w){re.escape(normalized_keyword)}(?!\w)",
                    text.casefold(),
                )
            )
            self._cache.set_count(file_id, normalized_keyword, count)
            cached = False
        else:
            count = cached_count
            cached = True

        result = {
            "file_id": file_id,
            "keyword": keyword,
            "count": count,
            "cached": cached,
            "latency_ms": (time.perf_counter() - started) * 1000,
        }
        return json.dumps(result)

    def exposed_hot_keywords(self, limit: int = 10) -> str:
        return json.dumps(
            [[keyword, score] for keyword, score in self._cache.hot_keywords(limit)]
        )

    def exposed_health(self) -> bool:
        return True

    def _resolve_file(self, file_id: str) -> Path:
        candidate = (self._files_dir / file_id).resolve()
        if candidate.parent != self._files_dir or not candidate.is_file():
            raise FileNotFoundError(f"Unknown text file: {file_id}")
        return candidate


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the word-count RPyC server")
    parser.add_argument("--host", default=os.getenv("SERVER_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("SERVER_PORT", "18812"))
    )
    parser.add_argument(
        "--files-dir",
        type=Path,
        default=Path(
            os.getenv("WORDCOUNT_FILES_DIR", "/app/src/wordcount_service/files")
        ),
    )
    args = parser.parse_args()
    service = WordCountService(args.files_dir, WordCountCache())
    ThreadedServer(service, hostname=args.host, port=args.port).start()