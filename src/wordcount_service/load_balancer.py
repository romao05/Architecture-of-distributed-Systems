"""TCP load balancer that pipes raw bytes between RPyC clients and servers."""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from dataclasses import dataclass

CHUNK_SIZE = 64 * 1024
TOTALS_INTERVAL_SECONDS = 5
DEFAULT_AGING_FACTOR = 0.98
LOOPBACK_ADDRESSES = ("127.0.0.1", "::1")


@dataclass
class Backend:
    """One word-count server and the statistics the balancer keeps for it."""

    name: str
    host: str
    port: int
    active: int = 0
    total: int = 0
    ewma_ms: float | None = None
    healthy: bool = True  # Phase 4: Track health status


class Strategy:
    """Pick the backend with the lowest (score, active, rotation) key."""

    name = "base"

    def __init__(self) -> None:
        self._choices_made = 0

    def score(self, backend: Backend) -> float:
        raise NotImplementedError

    def choose(self, backends: list[Backend]) -> Backend:
        # Phase 4: Filter out failed replicas before routing
        healthy_backends = [b for b in backends if b.healthy]
        
        if not healthy_backends:
            raise RuntimeError("All backend servers are currently offline!")

        # Ties are broken by "rotation": the backend at position
        # (choices_made mod n) wins first, so equal idle servers get
        # requests 1 -> 2 -> 3 instead of always server1.
        start = self._choices_made % len(healthy_backends)
        self._choices_made += 1

        def key(index: int) -> tuple[float, int, int]:
            backend = healthy_backends[index]
            rotation = (index - start) % len(healthy_backends)
            return (self.score(backend), backend.active, rotation)

        return healthy_backends[min(range(len(healthy_backends)), key=key)]


class LeastConnections(Strategy):
    """Send the request to the server with the fewest open connections."""

    name = "least_connections"

    def score(self, backend: Backend) -> float:
        return backend.active


class LeastResponseTime(Strategy):
    """Send the request to the server with the lowest expected wait."""

    name = "least_response_time"

    def __init__(self, aging_factor: float = DEFAULT_AGING_FACTOR) -> None:
        super().__init__()
        self._aging_factor = aging_factor

    def score(self, backend: Backend) -> float:
        if backend.ewma_ms is None:
            return 0.0  # no sample yet: probe every server once
        return (backend.active + 1) * backend.ewma_ms

    def choose(self, backends: list[Backend]) -> Backend:
        winner = super().choose(backends)
        # LRT only learns a server's speed from requests sent to it, so an
        # idle server that is never chosen keeps a stale estimate forever.
        # Each time an idle server is passed over its estimate drops a little,
        # so it is eventually re-probed and gets a fresh sample.
        healthy_backends = [b for b in backends if b.healthy]
        for backend in healthy_backends:
            if backend is not winner and backend.active == 0 and backend.ewma_ms:
                backend.ewma_ms *= self._aging_factor
        return winner


def make_strategy(algorithm: str, aging_factor: float) -> Strategy:
    if algorithm == LeastResponseTime.name:
        return LeastResponseTime(aging_factor)
    return LeastConnections()


def parse_backends(text: str) -> list[Backend]:
    """Parse 'host:port,host:port' into backends named after the host."""
    backends = []
    for item in text.split(","):
        host, _, port = item.strip().rpartition(":")
        backends.append(Backend(name=host, host=host, port=int(port)))
    return backends


class LoadBalancer:
    """Accept client connections and pipe each one to a chosen backend."""

    def __init__(
        self,
        backends: list[Backend],
        strategy: Strategy,
        alpha: float,
        log_connections: bool,
    ) -> None:
        self._backends = backends
        self._strategy = strategy
        self._alpha = alpha
        self._log_connections = log_connections
        self._connection_count = 0

    async def handle_client(
        self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
    ) -> None:
        peer = client_writer.get_extra_info("peername")
        if peer and peer[0] in LOOPBACK_ADDRESSES:
            # Only the container's own healthcheck connects from loopback.
            # Close it here so it does not count as a request or skew timings.
            client_writer.close()
            return

        try:
            backend = self._strategy.choose(self._backends)
        except RuntimeError as e:
            log(f"[lb] Request dropped: {e}")
            client_writer.close()
            return

        # No await between choose() and active += 1: asyncio runs one thread,
        # so no other connection can pick a backend in between.
        backend.active += 1
        backend.total += 1
        self._connection_count += 1
        number = self._connection_count
        self._log_assign(number, peer, backend)

        backend_writer = None
        try:
            started = time.perf_counter()
            try:
                backend_reader, backend_writer = await asyncio.open_connection(
                    backend.host, backend.port
                )
            except OSError as error:
                log(f"[lb] #{number} cannot reach {backend.name}: {error}")
                backend.healthy = False  # Phase 4: Instantly drop from routing pool
                return
            await asyncio.gather(
                pump(client_reader, backend_writer),
                pump(backend_reader, client_writer),
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            self._record_sample(backend, elapsed_ms)
            self._log_done(number, backend, elapsed_ms)
        finally:
            backend.active -= 1
            client_writer.close()
            if backend_writer is not None:
                backend_writer.close()

    def _record_sample(self, backend: Backend, elapsed_ms: float) -> None:
        if backend.ewma_ms is None:
            backend.ewma_ms = elapsed_ms
        else:
            backend.ewma_ms = (
                self._alpha * elapsed_ms + (1 - self._alpha) * backend.ewma_ms
            )

    def _log_assign(self, number: int, peer: object, backend: Backend) -> None:
        if not self._log_connections:
            return
        host, port = peer[:2] if peer else ("?", "?")
        active = " ".join(f"{b.name}={b.active}" for b in self._backends)
        log(
            f"[lb] #{number} {host}:{port} -> {backend.name} "
            f"({self._strategy.name}) active: {active}"
        )

    def _log_done(self, number: int, backend: Backend, elapsed_ms: float) -> None:
        if not self._log_connections:
            return
        line = f"[lb] #{number} {backend.name} done {elapsed_ms:.1f} ms"
        if isinstance(self._strategy, LeastResponseTime):
            ewma = " ".join(
                f"{b.name}={'-' if b.ewma_ms is None else f'{b.ewma_ms:.1f}'}"
                for b in self._backends
            )
            line += f" ewma: {ewma}"
        log(line)

    async def log_totals_forever(self) -> None:
        last_totals = self._format_totals()
        while True:
            await asyncio.sleep(TOTALS_INTERVAL_SECONDS)
            totals = self._format_totals()
            if totals != last_totals:
                log(f"[lb] totals: {totals}")
                last_totals = totals

    def _format_totals(self) -> str:
        return " ".join(f"{b.name}={b.total}" for b in self._backends)

    async def health_check_forever(self, interval_seconds: float = 3.0) -> None:
        """Phase 4: Periodically probe backends to detect failures and recoveries."""
        while True:
            for backend in self._backends:
                try:
                    # Attempt a fast TCP handshake to verify the server is listening
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(backend.host, backend.port),
                        timeout=1.0
                    )
                    writer.close()
                    await writer.wait_closed()
                    
                    if not backend.healthy:
                        log(f"[lb] 🟢 Health check: {backend.name} is back ONLINE")
                        backend.healthy = True
                        
                except (OSError, asyncio.TimeoutError):
                    if backend.healthy:
                        log(f"[lb] 🔴 Health check: {backend.name} FAILED! Marking OFFLINE")
                        backend.healthy = False
                        
            await asyncio.sleep(interval_seconds)


async def pump(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Copy bytes from reader to writer until EOF, then half-close writer."""
    try:
        while data := await reader.read(CHUNK_SIZE):
            writer.write(data)
            await writer.drain()
        if writer.can_write_eof():
            writer.write_eof()
    except OSError:
        writer.close()


def log(message: str) -> None:
    print(message, flush=True)


async def run(args: argparse.Namespace) -> None:
    backends = parse_backends(args.backends)
    strategy = make_strategy(args.algorithm, args.aging_factor)
    balancer = LoadBalancer(backends, strategy, args.alpha, args.log_connections)
    server = await asyncio.start_server(balancer.handle_client, args.host, args.port)
    names = ", ".join(f"{b.name}={b.host}:{b.port}" for b in backends)
    aging = f" aging={args.aging_factor}" if isinstance(strategy, LeastResponseTime) else ""
    log(
        f"[lb] listening on {args.host}:{args.port} "
        f"algorithm={strategy.name}{aging} backends: {names}"
    )
    asyncio.create_task(balancer.log_totals_forever())
    
    # Phase 4: Start the background health monitor
    asyncio.create_task(balancer.health_check_forever()) 
    
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TCP load balancer")
    parser.add_argument("--host", default=os.getenv("LB_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("LB_PORT", "18812")))
    parser.add_argument(
        "--algorithm",
        choices=(LeastConnections.name, LeastResponseTime.name),
        default=os.getenv("LB_ALGORITHM", "least_connections"),
    )
    parser.add_argument(
        "--backends",
        default=os.getenv(
            "LB_BACKENDS", "server1:18812,server2:18812,server3:18812"
        ),
    )
    parser.add_argument(
        "--alpha", type=float, default=float(os.getenv("LB_EWMA_ALPHA", "0.2"))
    )
    parser.add_argument(
        "--aging-factor",
        type=float,
        default=float(os.getenv("LB_AGING_FACTOR", str(DEFAULT_AGING_FACTOR))),
    )
    parser.add_argument(
        "--log-connections",
        type=lambda value: value not in ("0", "false", "False"),
        default=os.getenv("LB_LOG_CONNECTIONS", "1") not in ("0", "false", "False"),
    )
    args = parser.parse_args()
    asyncio.run(run(args))

if __name__ == "__main__":
    main()