import re
import subprocess
import sys
import time
import traceback
from threading import Thread
from typing import List, Optional, Tuple

import requests
import serial
from serial.tools.list_ports import grep as serial_grep

from battery_drivers import Battery
from dt_class_utils import DTProcess
from battery_drivers.constants import BATTERY_PCB16_BOOT_VID, BATTERY_PCB16_BOOT_PID, \
    BATTERY_PCB16_READY_VID, BATTERY_PCB16_READY_PID, BATTERY_PCB16_BAUD_RATE

from . import __version__
from .constants import ExitCode, BATTERY_FIRMWARE_URL

INFO = """
Duckietown {hardware} Firmware Upgrade Utility.
Version {version}

"""

BATTERY_INFO = """
Duckietown Battery:
    - Current version:   {current}
    - Available version: {latest}
"""


class UpgradeHelper(DTProcess):

    def __init__(self):
        super(UpgradeHelper, self).__init__("UpgradeHelper")

    def start(self, parsed) -> int:
        # nothing to do?
        if not parsed.battery and not parsed.hut:
            return ExitCode.NOTHING_TO_DO
        # print some info
        sys.stdout.write(INFO.format(
            hardware="Battery" if parsed.battery else "HUT",
            version=__version__
        ))
        sys.stdout.flush()
        # upgrade battery
        if parsed.battery:
            return self.upgrade_battery(parsed.check, parsed.dry_run)
        # upgrade hut
        if parsed.hut:
            return self.upgrade_hut(parsed.check, parsed.dry_run)

    def upgrade_battery(self, check: bool = False, dryrun: bool = False) -> int:
        # battery needs to be in boot mode
        ready_devs = self._find_device(BATTERY_PCB16_READY_VID, BATTERY_PCB16_READY_PID)
        boot_devs = self._find_device(BATTERY_PCB16_BOOT_VID, BATTERY_PCB16_BOOT_PID)
        # no battery at all?
        if len(boot_devs) + len(ready_devs) <= 0:
            # no battery found
            self.logger.error("Battery not detected. Please, check the connection to the battery "
                              "and retry.")
            return ExitCode.HARDWARE_NOT_FOUND
        # get latest version available
        latest_int, latest_str = self._get_latest_battery_firmware_available()
        if latest_int is None:
            # something went wrong
            self.logger.error("Error fetching the latest firmware version available "
                              "from the internet. Exiting.")
            return ExitCode.GENERIC_ERROR
        self.logger.debug(f"Latest version fetched from the cloud is {latest_str}")
        # two cases:
        # - check = True: we want a battery in normal mode so that we can read the current version
        # - check = False: we want a battery in boot mode so that we can flash it
        if check:
            # normal mode enabled?
            if len(ready_devs) <= 0:
                # battery found but not in normal mode
                self.logger.error("Battery detected in 'Boot Mode', but it needs to be in "
                                  "'Normal Mode'. You can switch mode by pressing the button "
                                  "on the battery ONCE.")
                return ExitCode.HARDWARE_WRONG_MODE

            # we have a device in normal mode, spin battery drivers and wait for info to be read
            battery = Battery(lambda _: None, logger=self.logger)
            self.register_shutdown_callback(battery.shutdown)

            def watchdog_fcn():
                timeout, elapsed, step = 10, 0, 0.5
                while not (self.is_shutdown() or battery.is_shutdown()) and battery.info is None:
                    if elapsed > timeout:
                        break
                    time.sleep(step)
                    elapsed += step
                battery.shutdown()

            watchdog = Thread(target=watchdog_fcn)
            watchdog.start()

            try:
                self.logger.debug(f"Trying to communicate with {ready_devs[0]}...")
                battery.start(block=True, quiet=False)
            except (OSError, serial.serialutil.SerialException) as e:
                if "multiple access" in str(e):
                    # battery is busy
                    self.logger.error(
                        "Battery detected but another process is using it. Make sure no other "
                        "processes are communicating with the battery.")
                    battery.shutdown()
                    return ExitCode.HARDWARE_BUSY
                # ---
                self.logger.error(
                    "An error occurred while talking to the battery, make sure "
                    "no other processes are communicating with the battery.")
                battery.shutdown()
                return ExitCode.GENERIC_ERROR

            # if we are here, either we got the info or we timed out
            battery.shutdown()
            watchdog.join()
            if battery.info is None:
                self.logger.error(
                    "An error occurred while talking to the battery, make sure "
                    "no other processes are communicating with the battery.")
                return ExitCode.GENERIC_ERROR

            # info is here
            current_str = battery.info['firmware_version']
            current_int = int(re.sub("[^0-9]+", "", current_str))
            # print info and compare versions
            print(BATTERY_INFO.format(current=current_str, latest=latest_str))
            return ExitCode.FIRMWARE_NEEDS_UPDATE if latest_int > current_int else \
                ExitCode.FIRMWARE_UP_TO_DATE

        # boot mode enabled?
        if len(boot_devs) <= 0:
            # battery found but not in boot mode
            self.logger.error("Battery detected in 'Normal Mode', but it needs to be in "
                              "'Boot Mode'. You can switch mode by DOUBLE pressing the button "
                              "on the battery.")
            return ExitCode.HARDWARE_WRONG_MODE
        # we have a device in boot mode, try opening connection to it
        try:
            with serial.Serial(boot_devs[0], BATTERY_PCB16_BAUD_RATE) as _:
                pass
        except (OSError, serial.serialutil.SerialException):
            # battery is busy
            self.logger.error("Battery detected but another process is using it. This should not "
                              "have happened. Contact the administrator.")
            return ExitCode.HARDWARE_BUSY
        # download latest firmware
        fw_filename = f"battery_pcb16_fw_v{latest_int}.bin"
        fw_fpath = f"/tmp/{fw_filename}"
        url = BATTERY_FIRMWARE_URL.format(pcb_version=16, resource=fw_filename)
        self.logger.info(f"Downloading firmware version {latest_str}...")
        with open(fw_fpath, "wb") as fout:
            # noinspection PyBroadException
            try:
                fout.write(requests.get(url).content)
            except BaseException as e:
                self.logger.error(f"ERROR: {str(e)}")
                return ExitCode.GENERIC_ERROR
        self.logger.info(f"Firmware downloaded!")
        # everything should be ready to go
        device = boot_devs[0].split('/')[-1]
        self.logger.info(f"Flashing firmware to device {device}...")
        # compile command
        cmd = ["bossac",
               f"--port={device}",
               "--force_usb_port=true"]
        if dryrun:
            cmd += ["--info"]
        else:
            cmd += ["--erase", "--write", "--verify", "--reset", fw_fpath]
        # execute
        self.logger.debug(f"$ {' '.join(cmd)}")
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError:
            self.logger.info("An error occurred while flashing the battery.")
            return ExitCode.GENERIC_ERROR
        # ---
        self.logger.info(f"Done!")
        return ExitCode.SUCCESS

    def upgrade_hut(self, check: bool = False, dryrun: bool = False) -> int:
        self.logger.info("HUT upgrade not supported at this time.")
        return ExitCode.NOTHING_TO_DO

    @staticmethod
    def _find_device(vid: str, pid: str) -> List[str]:
        vid_pid_match = "VID:PID={}:{}".format(vid, pid)
        ports = serial_grep(vid_pid_match)
        return [p.device for p in ports]  # ['/dev/ttyACM0', ...]

    @staticmethod
    def _get_latest_battery_firmware_available() -> Tuple[Optional[int], Optional[str]]:
        url = BATTERY_FIRMWARE_URL.format(pcb_version=16, resource="latest")
        # noinspection PyBroadException
        try:
            latest = requests.get(url).text
        except BaseException:
            traceback.print_exc()
            return None, None
        # ---
        major, minor, patch, *_ = latest + "000"
        return int(latest), f"v{major}.{minor}.{patch}"
