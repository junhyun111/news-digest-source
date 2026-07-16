from __future__ import annotations

import argparse
import sys

from news_digest.runner import run_digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Naver news daily digest sender")
    parser.add_argument("--dry-run", action="store_true", help="Print the digest without sending email.")
    parser.add_argument(
        "--prepare-output",
        help="Collect and save selected articles to this JSON file without sending email.",
    )
    parser.add_argument(
        "--send-prepared",
        help="Send a digest from a JSON file created by --prepare-output.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(
        run_digest(
            dry_run=args.dry_run,
            prepare_output=args.prepare_output,
            send_prepared=args.send_prepared,
            verbose=args.verbose,
        )
    )
