from enum import IntEnum, Enum

BATTERY_FIRMWARE_URL = (
    "https://duckietown-public-storage.s3.amazonaws.com"
    "/assets/battery/PCBv{pcb_version}/firmware/{resource}"
) 

# in the helper, these env variables help configure some options
ENV_KEY_FORCE_FW_VERSION = "FORCE_BATTERY_FW_VERSION"
ENV_KEY_PCB_VERSION = "PCB_VERSION"

# see README file, section "Testing Local Firmware"
LOCAL_FIRMWARE_BIN_PATH = "assets/firmware/fw.bin"

class ExitCode(IntEnum):
    # This APP communicates the outcome of its actions using these exit codes.
    NOTHING_TO_DO = 255
    SUCCESS = 1
    HARDWARE_NOT_FOUND = 2
    HARDWARE_BUSY = 3
    HARDWARE_WRONG_MODE = 4
    FIRMWARE_UP_TO_DATE = 5
    FIRMWARE_NEEDS_UPDATE = 6
    GENERIC_ERROR = 9

# when running main.py with `--find-pcbid`, either return
#   this: meaning failed to obtain a valid PCB version
#   other int: the pcb version (e.g. PCBv1.6 => 16, PCBv2.1 => 21)
PCB_VERSION_ID_EXIT_CODE_NONE = 0

class BatteryMode(Enum):
    READY = "ready"  # referred to as ready/normal mode
    BOOT = "boot"
