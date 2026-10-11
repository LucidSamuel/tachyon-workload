"""Run with python3 -m tachyon_workload --help."""

import argparse
import asyncio
import os
import sys

from .runner import Runner
from .runtime import emit, load_config


def arguments():
    parser = argparse.ArgumentParser(description="Private mock-proof Tachyon workload sidecar (Python 3.11+, Unix)")
    parser.add_argument("--config", required=True)
    parser.add_argument("--accept-test-funds", action="store_true", help="required: keys are unencrypted and proofs mocked")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create missing simulation wallets; reuse and verify the treasury")
    sub.add_parser("status", help="sync and show both pool balances; does not send payments")
    for name in ("bootstrap", "run"):
        command = sub.add_parser(name)
        command.add_argument("--rounds", type=int, default=1, help="bounded by default; 0 explicitly means continuous")
        command.add_argument("--mode", choices=("live", "controlled"), default="live")
        command.add_argument("--sole-miner", action="store_true", help="acknowledge internal/other miners are OFF; required for controlled mode")
        command.add_argument("--seed", type=int, help="scheduler randomness only, never wallet key randomness")
    args = parser.parse_args()
    if not args.accept_test_funds:
        parser.error("--accept-test-funds is required; private networks and disposable funds only")
    if getattr(args, "rounds", 0) < 0:
        parser.error("--rounds cannot be negative")
    if getattr(args, "mode", "live") == "controlled" and not args.sole_miner:
        parser.error("controlled mode requires --sole-miner and a PoW-disabled node without other miners")
    return args


async def main(args):
    os.umask(0o077)
    runner = Runner(load_config(args.config), getattr(args, "seed", None))
    try:
        await runner.initialize(create=args.command == "init")
        if args.command == "status":
            await runner.status()
        elif args.command in ("bootstrap", "run"):
            await runner.run(args.mode, args.rounds, args.command == "bootstrap")
    finally:
        runner.journal.close()


if __name__ == "__main__":
    try:
        asyncio.run(main(arguments()))
    except KeyboardInterrupt:
        emit("stopped", message="journal retained; rerun to recover the same operation IDs")
    except Exception as error:
        emit("error", message=str(error) or type(error).__name__,
             recovery="journal retained; resolve the error and rerun, do not delete wallet data")
        sys.exit(1)
