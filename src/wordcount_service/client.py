"""Command-line client for the word-count service."""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor

import rpyc


def count_once(host: str, port: int, file_id: str, keyword: str) -> str:
    """Open a connection, send one count request and return the output line."""
    connection = rpyc.connect(host, port)
    try:
        result = json.loads(connection.root.count(file_id, keyword))
    finally:
        connection.close()
    return (
        f"{result['keyword']} occurs {result['count']} times in "
        f"{result['file_id']} (cached={result['cached']}, "
        f"latency_ms={result['latency_ms']:.3f}, "
        f"served_by={result.get('server', '?')})"
    )


def print_hot_keywords(host: str, port: int, limit: int) -> None:
    connection = rpyc.connect(host, port)
    try:
        entries = json.loads(connection.root.hot_keywords(limit))
    finally:
        connection.close()
    for keyword, score in entries:
        print(f"{keyword}: {int(score)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the word-count service")
    parser.add_argument("--file", help="Text file name on the server")
    parser.add_argument(
        "--keyword", help="Keyword, or a comma-separated list to cycle through"
    )
    parser.add_argument("--hot", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--host", default=os.getenv("SERVER_HOST", "localhost"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("SERVER_PORT", "18812"))
    )
    parser.add_argument("--repeat", type=int, default=1, help="Number of requests")
    parser.add_argument(
        "--parallel", action="store_true", help="Send the requests concurrently"
    )
    args = parser.parse_args()
    if not args.hot and (args.file is None or args.keyword is None):
        parser.error("--file and --keyword are required unless --hot is used")

    if args.hot:
        print_hot_keywords(args.host, args.port, args.limit)
        return

    keywords = [word.strip() for word in args.keyword.split(",")]
    requested = [keywords[number % len(keywords)] for number in range(args.repeat)]

    def send(keyword: str) -> str:
        return count_once(args.host, args.port, args.file, keyword)

    if args.parallel:
        with ThreadPoolExecutor(max_workers=args.repeat) as executor:
            for line in executor.map(send, requested):
                print(line)
    else:
        for keyword in requested:
            print(send(keyword))
