from __future__ import annotations

import argparse
from pathlib import Path

from .runner import run_batch


def main() -> None:
    parser = argparse.ArgumentParser(prog="wqbrain-open", description="Batch simulate FASTEXPR formulas and store results in SQLite.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run / resume batch simulations")
    run_p.add_argument("--input", required=True, help="Path to txt file (one formula per line)")
    run_p.add_argument("--db", required=True, help="Path to SQLite db")
    run_p.add_argument("--credentials", required=True, help="Path to credentials.json")

    run_p.add_argument("--concurrency", type=int, default=2)
    run_p.add_argument("--batch-size", type=int, default=10)
    run_p.add_argument("--batch-sleep", type=float, default=5.0)
    run_p.add_argument("--min-request-interval", type=float, default=1.5)
    run_p.add_argument("--poll-seconds", type=float, default=10.0)

    run_p.add_argument("--force", action="store_true", help="Re-run even if status is SUCCESS")

    args = parser.parse_args()

    if args.cmd == "run":
        run_batch(
            input_path=Path(args.input),
            db_path=Path(args.db),
            credentials_path=Path(args.credentials),
            concurrency=max(1, int(args.concurrency)),
            batch_size=max(1, int(args.batch_size)),
            batch_sleep=float(args.batch_sleep),
            min_request_interval=float(args.min_request_interval),
            poll_seconds=float(args.poll_seconds),
            force=bool(args.force),
        )
        return

    raise SystemExit(2)
