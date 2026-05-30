#!/bin/bash
# Bluetooth module reset script
# Fixes Bluetooth adapter power-on issues on Raspberry Pi

/sbin/modprobe -r btusb
sleep 1
/sbin/modprobe btusb
sleep 2
/usr/bin/hciconfig hci0 up
sleep 1
# Ensure Bluetooth service is restarted after module reload
/bin/systemctl restart bluetooth
sleep 3
