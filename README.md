# dt-firmware-upgrade

## Testing Local Firmware
The steps to test a firmware binary available locally are stated here.

### Why we need this
Previously, the firmware always has to be downloaded from S3 storage, which makes testing new firmware files built locally difficult and slow. This mode avoids having to upload the firmware binaries to S3 and creating indexes for them, before they could be tested with this repo.

### Steps
1. Clone this repo to your laptop; Navigate to the repo
1. Build the repo on the Duckiebot with `dts devel build -f --pull -H [DUCKIEBOT_HOSTNAME]` from your laptop
1. On your laptop, copy the firmware `xxx.bin` file to `assets/firmware` of the cloned repo, and rename the copied file to `fw.bin`.
1. To start a container with the local files mounted on the Duckiebot, run the firmware upgrade container with `dts devel run -M -s -f -c bash -H autobot33 -- --privileged -it`
1. Then, in the shell from the previous step, run the upgrade module with the extra argument `--use-local-firmware`

```
# Example (in the shell inside the container)

$ python3 -m upgrade_helper.main --battery --use-local-firmware
```

### Expected logs on terminal

#### A successful run
```
root@autobot33:/code/dt-firmware-upgrade# python3 -m upgrade_helper.main --battery --use-local-firmware
INFO:UpgradeHelper:App status changed [INITIALIZING] -> [RUNNING]

Duckietown Battery Firmware Upgrade Utility.
Version 0.0.2

INFO:UpgradeHelper:In local firmware testing mode, will NOT download firmware from server.
INFO:UpgradeHelper:Using firmware file: /code/dt-firmware-upgrade/assets/firmware/fw.bin
INFO:UpgradeHelper:Flashing firmware to device ttyACM0...
Atmel SMART device 0x10030000 found
Erase flash
done in 0.201 seconds

Write 12204 bytes to flash (191 pages)
[==============================] 100% (191/191 pages)
done in 2.388 seconds

Verify 12204 bytes of flash
[==============================] 100% (191/191 pages)
Verify successful
done in 0.070 seconds
CPU reset.
INFO:UpgradeHelper:Done!
```

#### The binary file wrongly put/named, or not found
```
root@autobot33:/code/dt-firmware-upgrade# python3 -m upgrade_helper.main --battery --use-local-firmware
INFO:UpgradeHelper:App status changed [INITIALIZING] -> [RUNNING]

Duckietown Battery Firmware Upgrade Utility.
Version 0.0.2

INFO:UpgradeHelper:In local firmware testing mode, will NOT download firmware from server.
INFO:UpgradeHelper:Error! Local firmware binary NOT FOUND at: /code/dt-firmware-upgrade/assets/firmware/fw.bin
```