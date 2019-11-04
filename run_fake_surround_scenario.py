#!/usr/bin/env python3

import logging
from pathlib import Path
import subprocess

from virtual_serial_port import virtual_serial_port

host_tty = Path('./ttyTestHK')
device_tty = Path('./ttyFakeHK')

logging.basicConfig(level=logging.DEBUG)

with virtual_serial_port(host_tty, device_tty):
    device = subprocess.Popen(
        ['./fake_surround_receiver_hk.py', '-v', str(device_tty)])
    host = subprocess.Popen(
        ['./surround_receiver_hk.py', '-v', f'--device={host_tty}'])
    host.wait()
    device.terminate()
    device.wait()
