#!/usr/bin/env python3

import logging
from pathlib import Path
import subprocess
import time

from virtual_serial_port import virtual_serial_port


host_tty = Path('./ttyTestHK')
device_tty = Path('./ttyFakeHK')

logging.basicConfig(level=logging.DEBUG)

with virtual_serial_port(host_tty, device_tty):
    device = subprocess.Popen(
        ['./fake_surround_receiver_hk.py', '-v', str(device_tty)])
    print(f'Connect the surround_receiver to {host_tty}')
    print('Press Ctrl+C to abort')
    try:
        while True:
            time.sleep(60 * 60)
    except KeyboardInterrupt:
        print('Quitting...')
    finally:
        device.terminate()
        device.wait()
