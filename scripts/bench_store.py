"""Measure what the shared store buys you, isolated from warehouse variance.

Every statement is given a fixed artificial latency (default 0.4 s) to stand in
for a remote SQL warehouse, then three loading strategies are compared:

1. serial      - a page runs its statements one after another
2. bundle      - the page's statements run concurrently
3. N sessions  - N users open the same page at the same moment

Usage: python scripts/bench_store.py [--latency 0.4] [--sessions 20]
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pulse import config  # noqa: E402
from pulse.queries import BUNDLES, STATEMENTS  # noqa: E402
from pulse.warehouse import DuckDBRunner, SharedStore  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latency", type=float, default=0.4)
    ap.add_argument("--sessions", type=int, default=20)
    ap.add_argument("--page", default="hub_lens", choices=sorted(BUNDLES))
    args = ap.parse_args()

    runner = DuckDBRunner(config.MARTS_DB, simulated_latency_s=args.latency)
    names = BUNDLES[args.page]

    t0 = time.perf_counter()
    for n in names:
        runner(STATEMENTS[n])
    serial = time.perf_counter() - t0

    store = SharedStore(STATEMENTS, runner, version=runner.version)
    t0 = time.perf_counter()
    store.bundle(names)
    bundled = time.perf_counter() - t0

    store = SharedStore(STATEMENTS, runner, version=runner.version)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(args.sessions) as pool:
        list(pool.map(lambda _: store.bundle(names), range(args.sessions)))
    crowd = time.perf_counter() - t0

    print(f"page={args.page}  statements={len(names)}  latency={args.latency}s each\n")
    print(f"{'serial, one session':34} {serial:6.2f}s  {len(names)} statements")
    print(f"{'parallel bundle, one session':34} {bundled:6.2f}s  {len(names)} statements")
    print(
        f"{f'{args.sessions} sessions at once':34} {crowd:6.2f}s  "
        f"{store.stats.executed} statements (naive: {len(names) * args.sessions})"
    )


if __name__ == "__main__":
    main()
