"""Command-line client for the word-count service."""

from __future__ import annotations

import argparse
import json
import os

import rpyc


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the word-count service")
    parser.add_argument("--file", help="Text file name on the server")
    parser.add_argument("--keyword")
    parser.add_argument("--hot", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--host", default=os.getenv("SERVER_HOST", "localhost"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("SERVER_PORT", "18812"))
    )
    args = parser.parse_args()
    if not args.hot and (args.file is None or args.keyword is None):
        parser.error("--file and --keyword are required unless --hot is used")

    connection = rpyc.connect(args.host, args.port)
    try:
        if args.hot:
            entries = json.loads(connection.root.hot_keywords(args.limit))
            for keyword, score in entries:
                print(f"{keyword}: {int(score)}")
            return

        result = json.loads(connection.root.count(args.file, args.keyword))
        print(
            f"{result['keyword']} occurs {result['count']} times in "
            f"{result['file_id']} (cached={result['cached']}, "
            f"latency_ms={result['latency_ms']:.3f})"
        )
    finally:
        connection.close()