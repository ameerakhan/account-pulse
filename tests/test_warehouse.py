import threading
import time

import pandas as pd
import pytest

from pulse.warehouse import DuckDBRunner, SharedStore

STATEMENTS = {f"q{i}": f"SELECT {i}" for i in range(6)}


class SlowRunner:
    def __init__(self, latency=0.2):
        self.latency = latency
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, sql):
        with self.lock:
            self.calls.append(sql)
        time.sleep(self.latency)
        return pd.DataFrame({"v": [sql]})


def test_bundle_runs_in_parallel():
    runner = SlowRunner(0.2)
    store = SharedStore(STATEMENTS, runner, max_workers=8)
    t0 = time.perf_counter()
    out = store.bundle(STATEMENTS)
    elapsed = time.perf_counter() - t0
    assert set(out) == set(STATEMENTS)
    assert elapsed < 0.2 * len(STATEMENTS) / 2  # well under the serial sum (1.2s)


def test_single_flight_under_concurrency():
    runner = SlowRunner(0.2)
    store = SharedStore(STATEMENTS, runner, max_workers=8)
    results = []
    threads = [threading.Thread(target=lambda: results.append(store.get("q1"))) for _ in range(25)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(runner.calls) == 1
    assert all(r is results[0] for r in results)  # one shared frame, not 25 copies
    assert store.stats.waits + store.stats.hits == 24


def test_errors_are_not_cached():
    attempts = {"n": 0}

    def flaky(sql):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("warehouse hiccup")
        return pd.DataFrame({"ok": [1]})

    store = SharedStore({"q": "SELECT 1"}, flaky)
    with pytest.raises(RuntimeError):
        store.get("q")
    assert store.get("q")["ok"].iloc[0] == 1
    assert store.stats.errors == 1


def test_version_change_triggers_refetch():
    runner = SlowRunner(0)
    version = {"v": 1}
    store = SharedStore(STATEMENTS, runner, version=lambda: version["v"])
    store.get("q0")
    store.get("q0")
    assert len(runner.calls) == 1
    version["v"] = 2
    store.get("q0")
    assert len(runner.calls) == 2


def test_ttl_expiry():
    runner = SlowRunner(0)
    now = {"t": 0.0}
    store = SharedStore(STATEMENTS, runner, ttl_seconds=60, clock=lambda: now["t"])
    store.get("q0")
    now["t"] = 59
    store.get("q0")
    now["t"] = 61
    store.get("q0")
    assert len(runner.calls) == 2


def test_unknown_statement():
    store = SharedStore(STATEMENTS, SlowRunner(0))
    with pytest.raises(KeyError):
        store.get("nope")


def test_shared_frame_is_protected_by_copy_on_write():
    store = SharedStore({"q": "x"}, lambda sql: pd.DataFrame({"a": [1, 2, 3]}))
    shared = store.get("q")
    derived = shared[shared["a"] > 1]
    derived.loc[:, "a"] = 99
    assert store.get("q")["a"].tolist() == [1, 2, 3]


def test_duckdb_runner_picks_up_rebuilt_file(built, tmp_path):
    import shutil

    _, marts, _ = built
    live = tmp_path / "live.duckdb"
    shutil.copy(marts, live)
    runner = DuckDBRunner(live, simulated_latency_s=0)
    store = SharedStore({"n": "SELECT count(*) AS n FROM account_scores"}, runner, version=runner.version)
    n1 = store.get("n")["n"].iloc[0]

    import duckdb

    staging = tmp_path / "staging.duckdb"
    shutil.copy(marts, staging)
    with duckdb.connect(str(staging)) as con:
        con.execute("DELETE FROM account_scores WHERE ehi < 50")
    time.sleep(0.01)
    import os

    os.replace(staging, live)
    n2 = store.get("n")["n"].iloc[0]
    assert n2 < n1


def test_many_concurrent_warm_calls_do_not_deadlock():
    """More simultaneous page loads than fetch workers must still complete."""
    runner = SlowRunner(0.05)
    store = SharedStore(STATEMENTS, runner, max_workers=2)
    futures = [store.warm(list(STATEMENTS)) for _ in range(20)]
    for f in futures:
        assert set(f.result(timeout=5)) == set(STATEMENTS)
    assert len(runner.calls) == len(STATEMENTS)
