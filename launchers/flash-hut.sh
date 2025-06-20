#!/bin/bash

source /environment.sh

# YOUR CODE BELOW THIS LINE
# ----------------------------------------------------------------------------
cd fw-device-hut
echo Copying configuration file...
if [ "${ROBOT_HARDWARE}" == "jetson_nano" ]; then
    sudo cp _avrdudeconfig_jetson_nano/avrdude.conf /etc/avrdude.conf
    echo Jetson Nano configuration file copied.
else
    sudo cp _avrdudeconfig_raspberry_pi/avrdude.conf /etc/avrdude.conf
    echo Raspberry Pi configuration file copied.
fi
echo Running 'make fuses'...
if ! make fuses; then
    exit 1
fi
echo Running 'make clean && make'...
make clean
if ! make; then
    exit 1
fi
# ----------------------------------------------------------------------------
# YOUR CODE ABOVE THIS LINE
