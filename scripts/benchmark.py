"""Run Phase 2 latency measurements and generate tables and figures."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import rpyc
from rpyc.core.vinegar import GenericException

matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass(frozen=True)
class RequestResult:
    latency_ms: float
    cached: bool
    failed: bool


@dataclass(frozen=True)
class RateResult:
    rate: int
    requests: int
    average_ms: float
    p99_ms: float
    minimum_ms: float
    maximum_ms: float
    cached_requests: int
    failed_requests: int


def request(host: str, port: int, file_id: str, keyword: str) -> RequestResult:
    started = time.perf_counter()
    connection = None
    try:
        connection = rpyc.connect(
            host, port, config={"sync_request_timeout": 10}
        )
        response = json.loads(connection.root.count(file_id, keyword))
        cached = bool(response["cached"])
    except (
        TimeoutError,
        EOFError,
        OSError,
        socket.timeout,
        GenericException,
    ):
        return RequestResult(
            latency_ms=(time.perf_counter() - started) * 1000,
            cached=False,
            failed=True,
        )
    finally:
        if connection is not None:
            connection.close()
    return RequestResult(
        latency_ms=(time.perf_counter() - started) * 1000,
        cached=cached,
        failed=False,
    )


def measure_rate(
    rate: int,
    duration: float,
    host: str,
    port: int,
    file_id: str,
    keywords: list[str],
) -> RateResult:
    request_count = max(1, round(rate * duration))
    interval = 1 / rate
    results: list[RequestResult] = []

    with ThreadPoolExecutor(max_workers=request_count) as executor:
        futures = []
        started = time.perf_counter()
        for request_number in range(request_count):
            target = started + request_number * interval
            remaining = target - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
            futures.append(
                executor.submit(
                    request, host, port, file_id, keywords[request_number]
                )
            )
        results = [future.result() for future in futures]

    successful_results = [result for result in results if not result.failed]
    latencies = sorted(result.latency_ms for result in successful_results)
    failed_requests = sum(result.failed for result in results)
    if latencies:
        p99_index = math.ceil(len(latencies) * 0.99) - 1
        average_ms = sum(latencies) / len(latencies)
        p99_ms = latencies[p99_index]
        minimum_ms = latencies[0]
        maximum_ms = latencies[-1]
    else:
        average_ms = 0.0
        p99_ms = 0.0
        minimum_ms = 0.0
        maximum_ms = 0.0
    return RateResult(
        rate=rate,
        requests=len(results),
        average_ms=average_ms,
        p99_ms=p99_ms,
        minimum_ms=minimum_ms,
        maximum_ms=maximum_ms,
        cached_requests=sum(result.cached for result in results),
        failed_requests=failed_requests,
    )


def write_results(results: list[RateResult], output_dir: Path, mode: str) -> None:
    figures_dir = output_dir / "figures"
    tables_dir = output_dir / "tables"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    csv_path = tables_dir / f"phase2_latency_{mode}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "request_rate_per_second",
                "requests",
                "average_latency_ms",
                "p99_latency_ms",
                "minimum_latency_ms",
                "maximum_latency_ms",
                "cached_requests",
                "failed_requests",
            ]
        )
        for result in results:
            writer.writerow(
                [
                    result.rate,
                    result.requests,
                    f"{result.average_ms:.3f}",
                    f"{result.p99_ms:.3f}",
                    f"{result.minimum_ms:.3f}",
                    f"{result.maximum_ms:.3f}",
                    result.cached_requests,
                    result.failed_requests,
                ]
            )

    markdown_path = tables_dir / f"phase2_latency_{mode}.md"
    with markdown_path.open("w", encoding="utf-8") as file:
        file.write(
            "| Request rate (req/s) | Requests | Average (ms) | "
            "P99 (ms) | Minimum (ms) | Maximum (ms) | Cached requests | "
            "Failed requests |\n"
        )
        file.write(
            "|---:|---:|---:|---:|---:|---:|---:|---:|\n"
        )
        for result in results:
            file.write(
                f"| {result.rate} | {result.requests} | {result.average_ms:.3f} | "
                f"{result.p99_ms:.3f} | {result.minimum_ms:.3f} | "
                f"{result.maximum_ms:.3f} | {result.cached_requests} | "
                f"{result.failed_requests} |\n"
            )

    rates = [result.rate for result in results]
    average = [result.average_ms for result in results]
    p99 = [result.p99_ms for result in results]
    for filename, title, values in (
        (
            f"average_latency_{mode}.png",
            f"Average execution latency ({mode})",
            average,
        ),
        (
            f"p99_latency_{mode}.png",
            f"99th-percentile execution latency ({mode})",
            p99,
        ),
    ):
        figure, axis = plt.subplots(figsize=(8, 5))
        axis.plot(rates, values, marker="o")
        axis.set(
            title=title,
            xlabel="Keyword requests per second",
            ylabel="Request execution latency (ms)",
        )
        axis.grid(True, alpha=0.3)
        figure.tight_layout()
        figure.savefig(figures_dir / filename, dpi=160)
        plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18812)
    parser.add_argument("--file", default="twilight-annette-lyster.txt")
    parser.add_argument("--keyword", default="Christie")
    parser.add_argument("--duration", type=float, default=5)
    parser.add_argument("--rates", default="10,40,70,100,130")
    parser.add_argument("--mode", choices=("warm", "cold"), default="warm")
    parser.add_argument("--files-dir", type=Path, default=Path("src/wordcount_service/files"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rates = [int(rate.strip()) for rate in args.rates.split(",") if rate.strip()]
    if len(rates) != 5:
        raise ValueError("Exactly five request rates are required")
    if min(rates) < 10:
        raise ValueError("The lowest request rate must be at least 10 requests/second")
    if any(right - left < 10 for left, right in zip(rates, rates[1:])):
        raise ValueError("Request-rate intervals must be at least 10 requests/second")
    if args.duration <= 0:
        raise ValueError("Duration must be greater than zero")

    request_counts = [max(1, round(rate * args.duration)) for rate in rates]
    keywords: list[str] | None = None
    if args.mode == "cold":
        text = (args.files_dir / args.file).read_text(encoding="utf-8")
        vocabulary = list(dict.fromkeys(re.findall(r"\w+", text.casefold())))
        largest_request_count = max(request_counts)
        if len(vocabulary) < largest_request_count:
            raise ValueError(
                f"Text file vocabulary has {len(vocabulary)} distinct words, "
                f"but {largest_request_count} are needed for the largest request rate"
            )
        keywords = vocabulary

    results = []
    for rate, request_count in zip(rates, request_counts):
        subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "redis",
                "redis-cli",
                "FLUSHALL",
            ],
            check=True,
        )
        if args.mode == "warm":
            request(args.host, args.port, args.file, args.keyword)
            rate_keywords = [args.keyword] * request_count
            expected_cached = request_count
        else:
            rate_keywords = keywords[:request_count]
            expected_cached = 0
        result = measure_rate(
            rate,
            args.duration,
            args.host,
            args.port,
            args.file,
            rate_keywords,
        )
        if result.cached_requests != expected_cached:
            print(
                f"WARNING: expected {expected_cached} cached requests at "
                f"{rate} req/s, got {result.cached_requests}"
            )
        results.append(result)
    write_results(results, args.output_dir, args.mode)
    for result in results:
        print(
            f"{result.rate:>4} req/s: average={result.average_ms:.3f} ms, "
            f"p99={result.p99_ms:.3f} ms, cached={result.cached_requests}/"
            f"{result.requests}, failed={result.failed_requests}/{result.requests}"
        )


if __name__ == "__main__":
    main()
