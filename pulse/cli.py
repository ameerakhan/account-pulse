"""Command line: `python -m pulse.cli {data,build,freshness}`."""

from __future__ import annotations

import argparse
import sys

from . import config, freshness, materialize, synth


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pulse", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    gen = sub.add_parser("data", help="generate synthetic raw data")
    gen.add_argument("--seed", type=int, default=synth.SynthSpec.seed)
    gen.add_argument("--accounts", type=int, default=synth.SynthSpec.n_accounts)
    sub.add_parser("build", help="materialize marts from raw (atomic)")
    sub.add_parser("freshness", help="report whether marts are current; exit 1 if not")
    args = parser.parse_args(argv)

    if args.cmd == "data":
        tables = synth.generate(synth.SynthSpec(seed=args.seed, n_accounts=args.accounts))
        synth.write_raw(tables)
        for name, df in tables.items():
            print(f"{name:14} {len(df):>8,} rows")
        print(f"-> {config.RAW_DB}")
    elif args.cmd == "build":
        result = materialize.build()
        for name, n in result.row_counts.items():
            print(f"{name:20} {n:>8,} rows")
        print(f"-> {result.path} in {result.seconds:.2f}s")
    elif args.cmd == "freshness":
        f = freshness.check()
        print(f.summary())
        return 0 if f.ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
