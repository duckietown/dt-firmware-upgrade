import os
import re
import subprocess
import sys
import time
import traceback
from threading import Thread
from typing import List, Optional, Tuple, Union, Dict

import requests
import serial
from serial.tools.list_ports import grep as serial_grep

from battery_drivers import Battery
from dt_class_utils import DTProcess
from battery_drivers.constants import (
    BATTERY_PCB_BOOT_VID,
    BATTERY_PCB_BOOT_PID,
    BATTERY_PCB_READY_VID,
    BATTERY_PCB_READY_PID,
    BATTERY_PCB_BAUD_RATE,
)

from . import __version__
from .constants import (
    ExitCode,
    BatteryMode,
    BATTERY_FIRMWARE_URL,
    LOCAL_FIRMWARE_BIN_PATH,
    PCB_VERSION_ID_EXIT_CODE_NONE,
    ENV_KEY_FORCE_FW_VERSION,
    ENV_KEY_PCB_VERSION,
)

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
        self._battery_info = None

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
            if parsed.find_pcbid:
                return self.battery_find_pcb_version()
            if parsed.check:
                return self.battery_check_firmware_up_to_date()
            # try to flash firmware
            return self.upgrade_battery(
                parsed.find_pcbid,
                parsed.check,
                parsed.dry_run,
                parsed.use_local_firmware,
            )
        # upgrade hut
        if parsed.hut:
            return self.upgrade_hut(parsed.check, parsed.dry_run)

    def _battery_device_mode_detect(self,
                                   mode_required: BatteryMode,
                                   ) -> Union[int, str]:
        """Detect battery device address

        battery needs to be:
          * in ready mode for info/version reading
          * in boot mode for firmware flashing

        Args:
            mode_required (BatteryMode): the battery is expected in READY or BOOT mode

        Returns:
            Union[int, str]: If success, the device port, e.g. "/dev/ttyUSB0".
                             Otherwise, return an int defined in ExitCode class.
        """

        ready_devs = self._find_device(BATTERY_PCB_READY_VID, BATTERY_PCB_READY_PID)
        boot_devs = self._find_device(BATTERY_PCB_BOOT_VID, BATTERY_PCB_BOOT_PID)
        # no battery at all?
        if len(boot_devs) + len(ready_devs) <= 0:
            self.logger.error((
                "Battery not detected. "
                "Please check the connection to the battery and retry."
            ))
            return ExitCode.HARDWARE_NOT_FOUND

        # check if mode correct
        if mode_required == BatteryMode.READY:
            if len(ready_devs) < 1:
                # battery found but NOT in NORMAL/READY mode
                self.logger.error("Battery detected in 'Boot Mode', but it needs to be in "
                                  "'Normal Mode'. You can switch mode by pressing the button "
                                  "on the battery ONCE.")
                return ExitCode.HARDWARE_WRONG_MODE
            return ready_devs[0]
        elif mode_required == BatteryMode.BOOT:
            if len(boot_devs) < 1:
                # battery found but NOT in BOOT mode
                self.logger.error("Battery detected in 'Normal Mode', but it needs to be in "
                                "'Boot Mode'. You can switch mode by DOUBLE pressing the button "
                                "on the battery.")
                return ExitCode.HARDWARE_WRONG_MODE
            return boot_devs[0]
        else:
            self.logger.error(f"Invalid mode given: {mode_required}. This is most likely a bug in the code.")
            return ExitCode.GENERIC_ERROR

    def _battery_obtain_info(self) -> int:
        """Obtain battery related information

        If successful, put battery info (e.g. PCB version and firmware version)
        in the class attribute self._battery_info.

        Returns:
            int: If success, ExitCode.SUCCESS. Otherwise, other ExitCodes.
        """

        # if info already read successfully, just return success
        if self._battery_info is not None:
            return ExitCode.SUCCESS

        # battery needs to be in READY mode for info/version reading
        res = self._battery_device_mode_detect(mode_required=BatteryMode.READY)
        if isinstance(res, int):  # if an ExitCode is returned
            return res
        # else, res is the ready mode device address

        # battery READY. spin battery drivers and wait for info to be read
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
            self.logger.debug(f"Trying to communicate with {res}...")
            battery.start(block=True, quiet=False)
        except (OSError, serial.serialutil.SerialException) as e:
            if "multiple access" in str(e):
                # battery is busy
                self.logger.error((
                    "Battery detected but another process is using it. "
                    "Make sure no other process communicates with the battery."
                ))
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

        # store info in class attribute
        self._battery_info = battery.info
        return ExitCode.SUCCESS

    def battery_find_pcb_version(self) -> int:
        """Find PCB version of the battery

        Returns:
            int: If success, the pcb version (int) is returned, e.g. version "1.6" => 16.
                 Otherwise, return 0 (PCB_VERSION_ID_EXIT_CODE_NONE).
        """

        res = self._battery_obtain_info()
        if res != ExitCode.SUCCESS:
            return PCB_VERSION_ID_EXIT_CODE_NONE

        pcb_version = int(self._battery_info['boot']['pcb_version'])
        self.logger.info(f"Fetched battery PCB version: {pcb_version}")

        return pcb_version

    def _battery_get_latest_firmware_version(self) -> Union[int, Tuple[int, str]]:
        """Get latest firmware version

        Two ways to obtain the "latest firmware"
        1. supply a known firmware version
            * with env variable FORCE_BATTERY_FW_VERSION
        2. supply a PCB version, and use our API to check
            a) with env variable PCB_VERSION
            b) query the battery info for pcb version, with self.battery_find_pcb_version(...)

        Among 2.a and 2.b, the reason to not always go with 2.b is:
        In our duckietown-shell-commands duckiebot/battery/upgrade,
        we use program exit/return codes to pass information along several steps.
        Ideally:
        - Step 1: find pcb version -> PCB version
        - Step 2: check if firmware update is needed -> ExitCode.FIRMWARE_UP_TO_DATE or ExitCode.FIRMWARE_NEEDS_UPDATE
        - Step 3: download and flash new firmware -> ExitCode.SUCCESS

        And in Step 3, we need to download the latest firmware. For that,
        we need to know the PCB version. (see constants.py/BATTERY_FIRMWARE_URL)

        Since Step 3 also requires the BOOT mode, we cannot read the battery info.
        So we need to pass the PCB_VERSION in somehow anyways.

        In conclusion, 2.a is needed when upgrading battery with `dts`, and always works.
        2.b just helps make calling the `--check` option easier (no need to do 2 separate things)

        Returns:
            Union[int, Tuple[int, str]]: If success, return (latest_fw_ver_int, latest_fw_ver_str).
                                         Otherwise, non-SUCCESS ExitCodes.
        """

        # method 1
        if os.environ.get(ENV_KEY_FORCE_FW_VERSION, default=None) is not None:
            latest_str = os.environ.get(ENV_KEY_FORCE_FW_VERSION, default=None)
            try:
                latest_int = int(re.sub("[^0-9]+", "", latest_str))
                self.logger.info(f"Firmware version forced to {latest_str}")
                return latest_int, latest_str
            except ValueError:
                # something went wrong
                self.logger.error("Error parsing the given version string. Exiting.")
                return ExitCode.GENERIC_ERROR

        def fetch_lateset_fw(pcb_version: int):
            # get latest version available for a particular pcb version
            latest_int, latest_str = self._get_latest_battery_firmware_available_for_pcb(pcb_version=pcb_version)
            if latest_int is None:
                # something went wrong
                self.logger.error("Error fetching the latest firmware version available "
                                "from the internet. Exiting.")
                return ExitCode.GENERIC_ERROR
            self.logger.debug(f"Latest version fetched from the cloud is {latest_str}")
            return latest_int, latest_str

        # method 2.a
        if os.environ.get(ENV_KEY_PCB_VERSION) is not None:
            pcb_ver = int(os.environ.get(ENV_KEY_PCB_VERSION))
            self.logger.info(f"PCB version supplied: {pcb_ver}")
            return fetch_lateset_fw(pcb_version=pcb_ver)

        # method 2.b
        res = self.battery_find_pcb_version()
        if res == PCB_VERSION_ID_EXIT_CODE_NONE:
            self.logger.error("Cannot read battery PCB version")
            return ExitCode.GENERIC_ERROR
        self.logger.info(f"PCB version read: {res}")
        return fetch_lateset_fw(pcb_version=res)

    def battery_check_firmware_up_to_date(self) -> int:
        """Check if battery firmware is up-to-date

        Returns:
            int: ExitCodes
        """

        # get current firmware info
        res = self._battery_obtain_info()
        if res != ExitCode.SUCCESS:
            return res
        # now the self._battery_info contains the firmware version
        current_str = self._battery_info['version']
        current_int = int(re.sub("[^0-9]+", "", current_str))

        # get latest firmware for this version of PCB
        res = self._battery_get_latest_firmware_version()
        if isinstance(res, int):  # failed
            return res
        latest_int, latest_str = res

        # print info and compare versions
        print(BATTERY_INFO.format(current=f"v{current_str}", latest=latest_str))
        if latest_int > current_int:
            return ExitCode.FIRMWARE_NEEDS_UPDATE
        else:
            return ExitCode.FIRMWARE_UP_TO_DATE

    def upgrade_battery(self,
                        dryrun: bool = False,
                        use_local_firmware: bool = False,
                        ) -> int:

        res = self._battery_device_mode_detect(mode_required=BatteryMode.BOOT)
        if isinstance(res, int):  # failed with ExitCode
            return res
        # res contains the boot mode device addr
        dev_addr = res

        # try opening connection to it
        try:
            with serial.Serial(dev_addr, BATTERY_PCB_BAUD_RATE) as _:
                pass
        except (OSError, serial.serialutil.SerialException):
            # battery is busy
            self.logger.error("Battery detected but another process is using it. This should not "
                              "have happened. Contact the administrator.")
            return ExitCode.HARDWARE_BUSY

        if use_local_firmware:
            self.logger.info(f"In local firmware testing mode, will NOT download firmware from server.")
            # mounted repo path / preset firmware bin path
            fw_fpath = os.path.join(os.environ.get("DT_REPO_PATH"), LOCAL_FIRMWARE_BIN_PATH)
            if not (os.path.exists(fw_fpath) and os.path.isfile(fw_fpath)):
                self.logger.info(f"Error! Local firmware binary NOT FOUND at: {fw_fpath}")
                return ExitCode.GENERIC_ERROR
        else:  # download latest firmware
            # the env variable PCB_VERSION has to be set
            if os.environ.get(ENV_KEY_PCB_VERSION) is None:
                self.logger.error(f"{ENV_KEY_PCB_VERSION} env variable not given. Abort.")
                return ExitCode.GENERIC_ERROR

            res = self._battery_get_latest_firmware_version()
            if isinstance(res, int):  # failed
                return res
            latest_int, latest_str = res

            pcb_ver = int(os.environ.get(ENV_KEY_PCB_VERSION))
            fw_filename = f"battery_pcb{pcb_ver}_fw_v{latest_int}.bin"
            fw_fpath = f"/tmp/{fw_filename}"
            url = BATTERY_FIRMWARE_URL.format(pcb_version=pcb_ver, resource=fw_filename)
            self.logger.info(f"Downloading firmware version {latest_str}...")
            try:
                with open(fw_fpath, "wb") as fout:
                    # noinspection PyBroadException
                    try:
                        fout.write(requests.get(url).content)
                    except BaseException as e:
                        self.logger.error(f"ERROR: {str(e)}")
                        return ExitCode.GENERIC_ERROR
                self.logger.info("Firmware downloaded!")
            except Exception:
                self.logger.error(f"Failed to download firmware. Error: {traceback.format_exc()}")
                return ExitCode.GENERIC_ERROR

        self.logger.info(f"Using firmware file: {fw_fpath}")
        # everything should be ready to go
        device = dev_addr.split('/')[-1]
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
    def _get_latest_battery_firmware_available_for_pcb(
        pcb_version: int,
    ) -> Tuple[Optional[int], Optional[str]]:
        url = BATTERY_FIRMWARE_URL.format(pcb_version=pcb_version, resource="latest")
        # noinspection PyBroadException
        try:
            latest = requests.get(url).text
        except BaseException:
            traceback.print_exc()
            return None, None
        # ---
        major, minor, patch, *_ = latest + "000"
        return int(latest), f"v{major}.{minor}.{patch}"
