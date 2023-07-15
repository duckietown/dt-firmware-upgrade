#!/usr/bin/env python3

import argparse

from .helper import UpgradeHelper


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=(
        "When trying to flash the Battery firmware, "
        "first obtain the PCB version with --find-pcbid. "
        "Then set the env variable PCB_VERSION to the above int, "
        "for downloading the correct version of firmware."
    ))
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
        "--find-pcbid",
        action="store_true",
        default=False,
        help="Identify the PCB version"
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
    parser.add_argument(
        "--use-local-firmware",
        action="store_true",
        default=False,
        help="Try to use the firmware at assets/firmware/fw.bin (to help fast testing with local firmware binaries)"
    )
    parsed = parser.parse_args()
    # ---
    # run upgrade helper
    app = UpgradeHelper()
    exit_code = app.start(parsed)
    exit(exit_code)
