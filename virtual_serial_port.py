#!/usr/bin/env python3
"""Setup both ends of a virtual serial port.

Use socat to create two symlinks to pseudo-terminal devices that function like
either end of a serial port connection.

This is useful to test a program that communicate with a serial device, as you
can point it to one of these symlinks (instead of a regular serial port like
/dev/ttyS1), and then connect another program that fakes the behavior of the
serial device to the other symlink.
"""
import argparse
from contextlib import contextmanager
import logging
from pathlib import Path
import subprocess
import time


DEFAULT_PATH1 = Path('./ttyFake1')
DEFAULT_PATH2 = Path('./ttyFake2')
SOCAT = 'socat'

logger = logging.getLogger(__name__)


@contextmanager
def virtual_serial_port(path1, path2, debug=False):
    argv = [SOCAT, '-d']
    if debug:
        argv.extend(['-d', '-x'])
    address = 'pty,rawer,link={}'
    argv.extend([address.format(path1), address.format(path2)])
    logger.debug(f'Starting {argv}...')
    proc = subprocess.Popen(argv)
    try:
        yield
    finally:
        logger.debug(f'Terminating {SOCAT}...')
        proc.terminate()
        proc.wait()
        logger.debug(f'Terminated {SOCAT}')


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'path1', type=Path, nargs='?', default=DEFAULT_PATH1, metavar='PATH',
        help=f'Fake serial device #1 (default: {DEFAULT_PATH1})')
    parser.add_argument(
        'path2', type=Path, nargs='?', default=DEFAULT_PATH2, metavar='PATH',
        help=f'Fake serial device #2 (default: {DEFAULT_PATH2})')
    parser.add_argument(
        "--verbose", "-v", action="count", default=0,
        help="Increase log level")
    parser.add_argument(
        "--quiet", "-q", action="count", default=0,
        help="Decrease log level")

    args = parser.parse_args()

    loglevel = logging.WARNING + 10 * (args.quiet - args.verbose)
    logging.basicConfig(level=loglevel)

    try:
        logger.info(
            f'Creating virtual serial ports at {args.path1} and {args.path2}')
        debug = args.verbose > 0
        with virtual_serial_port(args.path1, args.path2, debug=debug):
            logger.info(f'Press Ctrl+C to quit')
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        logger.info('Quitting')


if __name__ == '__main__':
    main()
