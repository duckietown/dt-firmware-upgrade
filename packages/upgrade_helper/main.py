#!/usr/bin/env python3

import argparse

from .helper import UpgradeHelper


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # define parser arguments
    parser.add_argument(
        "--battery",
        action="store_true",
        default=False,
        help="Whether to update the battery's firmware"
    )
    parser.add_argument(
        "--hut",
        action="store_true",
        default=False,
        help="Whether to update the HUT's firmware"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Check if an update is needed"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Pretend you are doing stuff"
    )
    parsed = parser.parse_args()
    # ---
    # run upgrade helper
    app = UpgradeHelper()
    exit_code = app.start(parsed)
    exit(exit_code)
