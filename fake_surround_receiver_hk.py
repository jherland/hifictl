#!/usr/bin/env python

import asyncio
import logging
import serial_asyncio

from avr_command import AVR_Command
import avr_dgram
from avr_status import AVR_Status


logger = logging.getLogger(__name__)


class Fake_HK_AVR:
    """Impersonate a Harman/Kardon AVR 430 surround receiver.

    Receive remote commands, update internal state and provide plausible
    AVR_Status messages.
    """

    in_spec = avr_dgram.PC_AVR_Command
    out_spec = avr_dgram.AVR_PC_Status

    description = "Fake Harman/Kardon AVR 430"

    empty_icons = bytes([0x00] * 14)
    default_icons = bytes(
        [0xC0, 0x00, 0x00, 0x00, 0xFD, 0xFB, 0x7A, 0x00, 0xC0] + [0x00] * 5
    )

    status_map = {
        "standby": ("              ", "              ", empty_icons),
        "default": ("FAKE AVR      ", "DOLBY DIGITAL ", default_icons),
        "mute": ("     MUTE     ", "              ", default_icons),
        "volume": ("FAKE AVR      ", "  VOL {volume:3d} dB  ", default_icons),
    }

    @classmethod
    async def create(cls, url, baudrate=38400, *args, **kwargs):
        reader, writer = await serial_asyncio.open_serial_connection(
            url=url, baudrate=baudrate, *args, **kwargs
        )
        return cls(reader, writer)

    def __init__(self, incoming, outgoing):
        self.incoming = incoming
        self.outgoing = outgoing
        self.pending = asyncio.Queue(maxsize=1)  # Command in-progress
        self.state = "standby"
        self.volume = -35  # dB
        self.volume_canceler = None

    def __str__(self):
        return f"{self.description} on {self.outgoing.transport.serial.name}"

    def status(self):
        '''Return current status.'''
        line1, line2, icons = self.status_map[self.state]
        return AVR_Status(
            line1.format(volume=self.volume),
            line2.format(volume=self.volume),
            icons)

    async def write_status(self):
        while True:
            dgram = avr_dgram.build(self.status().data, self.out_spec)
            self.outgoing.write(dgram)
            await self.outgoing.drain()
            await asyncio.sleep(0.2)

    async def read_commands(self):
        read_len = avr_dgram.dgram_len(self.in_spec)
        while True:
            try:
                dgram = await self.incoming.readexactly(read_len)
            except asyncio.IncompleteReadError:
                logger.warning("Incomplete read!")
                break
            cmd = AVR_Command.parse_dgram(avr_dgram.parse(dgram, self.in_spec))
            self.handle_command(cmd)

    def handle_command(self, cmd):
        if self.state == "standby":
            if cmd.keyword == "POWER ON":
                self.state = "default"
                self.volume = -35  # dB
            else:
                logger.warning(f"Cannot handle {cmd} in state {self.state}")
                return
        else:
            if cmd.keyword == "POWER OFF":
                self.state = "standby"
            elif cmd.keyword == "MUTE":
                self.state = "default" if self.state == "mute" else "mute"
            elif cmd.keyword in ["VOL DOWN", "VOL UP"]:
                self.volume += 1 if cmd.keyword == "VOL UP" else -1
                self.state = "volume"
                if self.volume_canceler is not None:
                    self.volume_canceler.cancel()

                def return_to_default():
                    if self.state == "volume":
                        self.state = "default"

                self.volume_canceler = asyncio.get_event_loop().call_later(
                    3, return_to_default)
            else:
                logger.warning(f"Cannot handle {cmd} in state {self.state}")
                return
        logger.info(f"Handled {cmd}, state is now {self.state}")

    async def run(self):
        await asyncio.gather(
            self.write_status(),
            self.read_commands(),
        )


async def main(serial_port):
    hk = await Fake_HK_AVR.create(serial_port)
    print(f"Started {hk}. Press Ctrl+C to abort")
    await hk.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=Fake_HK_AVR.__doc__)
    parser.add_argument("device", help="Serial port for surround receiver")
    parser.add_argument(
        "--verbose", "-v", action="count", default=0, help="Increase log level"
    )
    parser.add_argument(
        "--quiet", "-q", action="count", default=0, help="Decrease log level"
    )
    args = parser.parse_args()

    loglevel = logging.WARNING + 10 * (args.quiet - args.verbose)
    logging.basicConfig(level=loglevel)

    try:
        asyncio.run(main(args.device))
    except KeyboardInterrupt:
        print("Bye!")
