#!/bin/bash

source /environment.sh

# Ref (manual procedure) current URL
# https://docs.duckietown.com/daffy/opmanual-duckiebot/debugging_and_troubleshooting/reflash_mc/index.html

disp_troubleshoot_info() {
    echo
    echo "=== Operation Aborted =========================================================="
    echo "There might be problems during the procedure."
    echo "Please refer to the following page on the Duckiebot book:"
    echo "    Debug Re-flash Microcontroller"
}

disp_success_info() {
    echo
    echo "=== Operation Succeeded ========================================================"
    echo Please reboot your robot and HUT completely now.
}

# print separator between end of command output and expected output to be printed
util_separator() {
    echo "================================================================================" 
    echo "=== (Above) command output =====================================================" 
    echo
    echo "================================================================================" 
    echo
    echo "=== (Below) expected output ===================================================="
    echo "================================================================================" 
}

# given some command output and an expected output, ask user to compare and confirm they match
ask_compare_and_confirm() {
    read -p "Did the command output match the expected output? (Y/N, default N): " _user_confirm
    if [ "${_user_confirm^^}" != "Y" ]; then
        disp_troubleshoot_info
        exit 1
    fi
}


# install dependencies
sudo apt-get update
sudo apt-get install bison autoconf flex gcc-avr binutils-avr gdb-avr avr-libc avrdude build-essential

# clone repo
git clone --branch main https://github.com/duckietown/fw-device-hut.git $HOME/fw-device-hut
cd $HOME/fw-device-hut

# read robot hardware (JETSON vs. RPI), and copy files
if [ "${ROBOT_HARDWARE}" == "jetson_nano" ]; then
    sudo cp _avrdudeconfig_jetson_nano/avrdude.conf /etc/avrdude.conf
else # RPi
    sudo cp _avrdudeconfig_raspberry_pi/avrdude.conf /etc/avrdude.conf
fi

# test the avrdude and set the low-level configuration
make fuses

# ask verification confirmation
util_separator
echo "
avrdude: verifying …
avrdude: 1 bytes of efuse verified

avrdude: safemode: Fuses OK (E:FF, H:DF, L:E2)

avrdude done.  Thank you.
"
ask_compare_and_confirm

# remove temporary files
make clean

# compile the firmware and flash to the HUT micro-controller
make

# ask verification confirmation
util_separator
echo "
avrdude: verifying ...
avrdude: 2220 bytes of flash verified

avrdude: safemode: Fuses OK (E:FF, H:DF, L:E2)

avrdude done.  Thank you.
"
ask_compare_and_confirm

# print success, ask user to reboot, and exit
disp_success_info