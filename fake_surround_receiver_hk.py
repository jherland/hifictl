#!/usr/bin/env python3

import asyncio
import logging
import serial_asyncio

import avr_command
import avr_dgram
from avr_status import AVR_Status


class Fake_HK_AVR:
    """Impersonate a Harman/Kardon AVR 430 surround receiver's serial port.

    Receive remote commands, update internal state and provide plausible
    AVR_Status messages.
    """
    description = 'Fake Harman/Kardon AVR 430'
    in_spec = avr_dgram.PC_AVR_Command
    out_spec = avr_dgram.AVR_PC_Status

    empty_icons = bytes([0x00] * 14)
    default_icons = bytes(
        [0xC0, 0x00, 0x00, 0x00, 0xFD, 0xFB, 0x7A, 0x00, 0xC0] + [0x00] * 5
    )

    status_map = {
        'standby': ('              ', '              ', empty_icons),
        'default': ('FAKE AVR      ', 'DOLBY DIGITAL ', default_icons),
        'mute': ('     MUTE     ', '              ', default_icons),
        'volume': ('FAKE AVR      ', '  VOL {volume:3d} dB  ', default_icons),
    }

    @classmethod
    async def create(cls, url, baudrate=38400, *args, **kwargs):
        reader, writer = await serial_asyncio.open_serial_connection(
            url=url, baudrate=baudrate, *args, **kwargs)
        return cls(reader, writer)

    def __init__(self, rstream, wstream):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rstream = rstream
        self.wstream = wstream
        self.state = 'standby'
        self.volume = -35  # dB
        self.volume_canceler = None

    def __str__(self):
        return f'{self.description} on {self.wstream.transport.serial.name}'

    def _status(self):
        '''Return current status.'''
        line1, line2, icons = self.status_map[self.state]
        return AVR_Status(
            line1.format(volume=self.volume),
            line2.format(volume=self.volume),
            icons)

    async def _write_status(self):
        while True:
            dgram = avr_dgram.encode(self._status().data, self.out_spec)
            self.logger.debug(f'Writing {dgram}')
            self.wstream.write(dgram)
            await self.wstream.drain()
            await asyncio.sleep(0.2)

    async def _read_commands(self):
        read_len = avr_dgram.dgram_len(self.in_spec)
        while True:
            try:
                dgram = await self.rstream.readexactly(read_len)
            except asyncio.IncompleteReadError:
                self.logger.warning('Incomplete read!')
                break
            self.logger.debug(f'Read {dgram}')
            cmd = avr_command.decode(avr_dgram.decode(dgram, self.in_spec))
            # TODO??? await asyncio.sleep(0.2)
            self._handle_command(cmd)

    def _handle_command(self, cmd):
        if self.state == 'standby':
            if cmd == 'POWER ON':
                self.state = 'default'
                self.volume = -35  # dB
            else:
                self.logger.warning(
                    f'Cannot handle {cmd} in state {self.state}')
                return
        else:
            if cmd == 'POWER OFF':
                self.state = 'standby'
            elif cmd == 'MUTE':
                self.state = 'default' if self.state == 'mute' else 'mute'
            elif cmd in {'VOL DOWN', 'VOL UP'}:
                if self.state == 'volume':
                    self.volume += 1 if cmd == 'VOL UP' else -1
                self.state = 'volume'
                if self.volume_canceler is not None:
                    self.volume_canceler.cancel()

                def return_to_default():
                    if self.state == 'volume':
                        self.state = 'default'

                self.volume_canceler = asyncio.get_event_loop().call_later(
                    3, return_to_default)
            else:
                self.logger.warning(
                    f'Cannot handle {cmd} in state {self.state}')
                return
        self.logger.info(f'Handled {cmd}, state is now {self.state}')

    async def run(self):
        self.logger.debug(f'Running {self}...')
        await asyncio.gather(
            self._write_status(),
            self._read_commands(),
        )


async def main(serial_port):
    hk = await Fake_HK_AVR.create(serial_port)
    print(f'Starting {hk}...')
    print('Press Ctrl+C to abort')
    await hk.run()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=Fake_HK_AVR.__doc__)
    parser.add_argument(
        'device',
        help='Serial port for surround receiver')
    parser.add_argument(
        '--verbose', '-v', action='count', default=0,
        help='Increase log level')
    parser.add_argument(
        '--quiet', '-q', action='count', default=0,
        help='Decrease log level')
    args = parser.parse_args()

    loglevel = logging.WARNING + 10 * (args.quiet - args.verbose)
    logging.basicConfig(level=loglevel)

    try:
        asyncio.run(main(args.device))
    except KeyboardInterrupt:
        print('Bye!')
