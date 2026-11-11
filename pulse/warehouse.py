"""A process-wide, single-flight, parallel query store for a Streamlit app.

Why not just ``st.cache_data``?

* ``st.cache_data`` pickles the result and hands every caller its own
  deserialized copy. With many sessions reading the same hourly-refreshed
  tables, every session pays to rebuild identical frames.
* A page that loads N tables one after another costs the *sum* of N query
  times. Loading them in parallel costs roughly the *slowest* one.
* If 50 people open the same page in the same second, a naive cache issues
  the same query 50 times before the first result lands.

``SharedStore`` addresses all three:

* One in-memory frame per (statement, data version), shared by every session.
  pandas 3 enables Copy-on-Write by default, so a page that derives from a
  shared frame can never mutate it for anyone else.
* ``bundle()`` fetches a page's statements concurrently on a thread pool.
* Single-flight: the first caller for a key runs the query; everyone else who
  asks while it is in flight waits on the same ``Future``.
* The data version is the marts file's modification time, so a rebuild is
  picked up automatically, with no app restart. A TTL bounds staleness for
  sources that have no cheap version signal.
* Failures are never cached: the next caller retries.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd

from . import config

Runner = Callable[[str], pd.DataFrame]


@dataclass
class _Entry:
    future: Future
    version: object
    created: float


@dataclass
class StoreStats:
    executed: int = 0
    hits: int = 0
    waits: int = 0
    errors: int = 0
    per_statement: dict[str, int] = field(default_factory=dict)


class SharedStore:
    def __init__(
        self,
        statements: Mapping[str, str],
        runner: Runner,
        *,
        version: Callable[[], object] = lambda: None,
        ttl_seconds: float = config.CACHE_TTL_SECONDS,
        max_workers: int = config.FETCH_WORKERS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._statements = dict(statements)
        self._runner = runner
        self._version = version
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}
        # Fetches and orchestration use separate pools. bundle() blocks on
        # fetches, so if warm() ran bundle() on the fetch pool, enough
        # concurrent page loads would occupy every worker waiting on fetches
        # that can never be scheduled: a deadlock.
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pulse-fetch")
        self._orchestrator = ThreadPoolExecutor(
            max_workers=max(4, max_workers * 4), thread_name_prefix="pulse-bundle"
        )
        self.stats = StoreStats()

    # ------------------------------------------------------------------ core
    def _fresh(self, entry: _Entry, version: object) -> bool:
        return entry.version == version and (self._clock() - entry.created) < self._ttl

    def _run(self, name: str) -> pd.DataFrame:
        with self._lock:
            self.stats.executed += 1
            self.stats.per_statement[name] = self.stats.per_statement.get(name, 0) + 1
        return self._runner(self._statements[name])

    def _claim(self, name: str) -> tuple[Future, bool]:
        """Return the future for ``name`` and whether this caller must run it."""
        if name not in self._statements:
            raise KeyError(f"unknown statement {name!r}")
        version = self._version()
        with self._lock:
            entry = self._entries.get(name)
            if entry is not None and self._fresh(entry, version):
                if entry.future.done():
                    self.stats.hits += 1
                else:
                    self.stats.waits += 1
                return entry.future, False
            fut: Future = Future()
            self._entries[name] = _Entry(fut, version, self._clock())
            return fut, True

    def _execute(self, name: str, fut: Future) -> None:
        try:
            fut.set_result(self._run(name))
        except BaseException as exc:  # noqa: BLE001 - propagate to every waiter
            with self._lock:
                self.stats.errors += 1
                entry = self._entries.get(name)
                if entry is not None and entry.future is fut:
                    del self._entries[name]
            fut.set_exception(exc)

    # --------------------------------------------------------------- public
    def get(self, name: str) -> pd.DataFrame:
        """Return the shared frame for ``name``. Treat it as read-only."""
        fut, owner = self._claim(name)
        if owner:
            self._execute(name, fut)
        return fut.result()

    def bundle(self, names: Iterable[str]) -> dict[str, pd.DataFrame]:
        """Fetch several statements concurrently. Costs ~the slowest, not the sum.

        Claims happen in the calling thread and only statements this caller
        owns are submitted, so a pool worker never sits blocked waiting on
        somebody else's query.
        """
        names = list(dict.fromkeys(names))
        futures: dict[str, Future] = {}
        for n in names:
            fut, owner = self._claim(n)
            if owner:
                self._pool.submit(self._execute, n, fut)
            futures[n] = fut
        return {n: f.result() for n, f in futures.items()}

    def warm(self, names: Iterable[str]) -> Future:
        """Start loading in the background; returns immediately."""
        return self._orchestrator.submit(self.bundle, list(names))

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


# ---------------------------------------------------------------- DuckDB glue
class DuckDBRunner:
    """Thread-safe read-only DuckDB runner that reopens when the file is swapped."""

    def __init__(self, path: Path, simulated_latency_s: float = config.SIMULATED_LATENCY_S):
        self._path = Path(path)
        self._latency = simulated_latency_s
        self._lock = threading.Lock()
        self._con: duckdb.DuckDBPyConnection | None = None
        self._opened_version: object = None

    def version(self) -> object:
        try:
            st = self._path.stat()
        except FileNotFoundError:
            return None
        return (st.st_mtime_ns, st.st_ino)

    def _connection(self) -> duckdb.DuckDBPyConnection:
        version = self.version()
        with self._lock:
            if self._con is None or version != self._opened_version:
                if self._con is not None:
                    self._con.close()
                if version is None:
                    raise FileNotFoundError(
                        f"marts database not found at {self._path}; run `make build` first"
                    )
                self._con = duckdb.connect(str(self._path), read_only=True)
                self._opened_version = version
            return self._con

    def __call__(self, sql: str) -> pd.DataFrame:
        if self._latency:
            time.sleep(self._latency)
        cursor = self._connection().cursor()  # one cursor per thread is the safe pattern
        try:
            return cursor.execute(sql).df()
        finally:
            cursor.close()


def duckdb_store(path: Path | None = None, statements: Mapping[str, str] | None = None) -> SharedStore:
    from .queries import STATEMENTS

    runner = DuckDBRunner(Path(path or config.MARTS_DB))
    return SharedStore(statements or STATEMENTS, runner, version=runner.version)
