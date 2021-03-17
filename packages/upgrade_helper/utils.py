import re
import subprocess
from typing import List, Dict

LSUSB_REGEX = r"Bus\s+(?P<bus>\d+)\s+Device\s+(?P<device>\d+).+ID\s(?P<id>\w+:\w+)\s(?P<tag>.+)$"


def get_usb_devices() -> List[Dict[str, str]]:
    device_re = re.compile(LSUSB_REGEX, re.I)
    df = subprocess.check_output("lsusb").decode('utf-8')
    devices = []
    for i in df.split('\n'):
        if i:
            info = device_re.match(i)
            if info:
                dinfo = info.groupdict()
                dinfo['device'] = '/dev/bus/usb/%s/%s' % (dinfo.pop('bus'), dinfo.pop('device'))
                devices.append(dinfo)
    return devices
