from enum import IntEnum

BATTERY_PCB16_BOOT_MODE_VID = "16d0"
BATTERY_PCB16_BOOT_MODE_PID = "0557"

BATTERY_FIRMWARE_URL = "https://duckietown-public-storage.s3.amazonaws.com/assets/battery/" \
                       "PCBv{pcb_version}/firmware/{resource}"


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
