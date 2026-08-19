#!/usr/bin/env python3
"""Generate one or more human-readable activation codes."""

import secrets
import sys


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(count):
        groups = ["".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(4)]
        print("-".join(groups))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
