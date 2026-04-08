from __future__ import annotations

import argparse
from dataclasses import asdict
from pprint import pprint

from promo.admin_cli.bootstrap import create_first_admin, seed_reference_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="promo-cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("seed-reference-data")

    admin_parser = subparsers.add_parser("create-first-admin")
    admin_parser.add_argument("--username", required=True)
    admin_parser.add_argument("--password", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "seed-reference-data":
        outcome = seed_reference_data()
        pprint(asdict(outcome))
        return 0

    if args.command == "create-first-admin":
        outcome = create_first_admin(args.username, args.password)
        pprint(asdict(outcome))
        return 1 if outcome.status == "validation_failed" else 0

    parser.error("Unsupported command")
    return 2
