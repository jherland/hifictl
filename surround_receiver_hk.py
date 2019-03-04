#!/usr/bin/env python3

import asyncio
import logging
from serial_asyncio import open_serial_connection
from time import monotonic as now

import avr_command
import avr_dgram
from avr_status import AVR_Status
from avr_state import AVR_State


logger = logging.getLogger(__name__)


class HarmanKardon_Surround_Receiver:
    """Async communication with a Harman/Kardon AVR 430 surround receiver.

    Encapsulate RS-232 commands and responses to/from the serial port
    connected to this receiver.
    """

    in_spec = avr_dgram.AVR_PC_Status
    out_spec = avr_dgram.PC_AVR_Command

    # Map simple string commands to corresponding H/K serial commands
    commands = {
        "on": avr_command.AVR_Command.Commands["POWER ON"],
        "off": avr_command.AVR_Command.Commands["POWER OFF"],
        #"on_off": _toggle_standby,  # Toggle on/off
        "mute": avr_command.AVR_Command.Commands["MUTE"],
        "vol+": avr_command.AVR_Command.Commands["VOL UP"],
        "vol-": avr_command.AVR_Command.Commands["VOL DOWN"],
        "vol?": avr_command.AVR_Command.Commands["VOL DOWN"],
        "source vid1": avr_command.AVR_Command.Commands["VID1"],
        "source vid2": avr_command.AVR_Command.Commands["VID2"],
        "surround 6ch": avr_command.AVR_Command.Commands["6CH/8CH"],
        "surround dolby": avr_command.AVR_Command.Commands["DOLBY"],
        "surround dts": avr_command.AVR_Command.Commands["DTS"],
        "surround stereo": avr_command.AVR_Command.Commands["STEREO"],
        "dig+": avr_command.AVR_Command.Commands["DIGITAL UP"],
        "dig-": avr_command.AVR_Command.Commands["DIGITAL DOWN"],
        "dig?": avr_command.AVR_Command.Commands["DIGITAL"],
        #"update": lambda self: [],  # We only _emit_ this command
    }

    def __init__(self, serial_port, baudrate=38400, *args, **kwargs):
        self.logger = logger.getChild(self.__class__.__name__)
        kwargs.update({"url": serial_port, "baudrate": baudrate})
        self.serial_args = (args, kwargs)
        self.reader = None
        self.writer = None
        self.state = AVR_State()
        self.command_queue = asyncio.Queue()

    async def connect(self):
        args, kwargs = self.serial_args
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
        self.reader, self.writer = await open_serial_connection(*args, **kwargs)
        self.logger.info("Connected via %s", self.writer.transport.serial.name)

    async def control(self, new_state):
        prev = self.state
        self.state = new_state

        if not self.command_queue.empty():
            return  # Hold off while there are pending commands
        if self.state.off or self.state.standby or self.state.muted:
            return  # Nothing to do

        if self.state.volume is None:
            await self.command_queue.put("vol?")  # Trigger volume display
            await self.command_queue.join()
        # TODO: REMOVE? assert self.state.source is not None
        if self.state.digital is None:
            await self.command_queue.put("dig?")  # Trigger digital display
            await self.command_queue.join()
        assert self.state.line1 is not None
        assert self.state.line2 is not None

        # Trigger wake from standby if we just went from OFF -> STANDBY
        if prev.off and self.state.standby:
            await self.command_queue.put("on")
            await self.command_queue.join()

        # My receiver has "episodes" where volume increases suddenly...
        if self.state.volume is None:
            pass
        elif self.state.volume > -15:
            self.logger.error("*** PANIC: Volume runaway, shutting down!")
            await self.command_queue.put("off")
            await self.command_queue.join()
        elif self.state.volume > -20:
            self.logger.warning("*** WARNING: Volume runaway? decreasing...")
            await self.command_queue.put("vol-")
            await self.command_queue.join()

    async def recv(self, state_queue):
        """Read state updates from surround receiver and put onto state_queue.

        If EOF is received over the serial port, put None as a sentinel onto
        the 'state_queue' and exit immediately.
        """
        logger = self.logger.getChild("recv")
        while True:
            try:
                dgram = await asyncio.wait_for(
                    self.reader.read(avr_dgram.dgram_len(self.in_spec)), 10)
            except asyncio.TimeoutError:
                logger.warning("Nothing incoming. Re-establishing connection.")
                await self.connect()
                continue
            except asyncio.IncompleteReadError as e:
                logger.debug("incomplete read:")
                dgram = e.partial
            logger.debug(f"<<< {dgram!r}")
            try:
                status = AVR_Status.parse(avr_dgram.parse(dgram, self.in_spec))
            except ValueError as e:
                logger.warning(f"Discarding datagram: {e}")
            else:
                logger.debug(f"received {status}")
                new_state = self.state.update(status)
                if new_state != self.state:
                    logger.debug(f"state -> {new_state}")
                    await state_queue.put(new_state)
                    await state_queue.join()
                    await self.control(new_state)
            if self.reader.at_eof():
                await state_queue.put(None)  # EOF
                logger.info("finished")
                break

    async def send(self, command_queue=None):
        """Write receiver commands from 'command_queue' to the serial port.

        Use existing self.command_queue if none given, otherwise replace
        self.command_queue with the one given.
        """
        logger = self.logger.getChild("send")
        if command_queue is not None:
            self.command_queue = command_queue
        last_sent = 0.0

        while True:
            cmd = await self.command_queue.get()
            if cmd is None:  # shutdown
                break
            try:
                data = avr_dgram.build(self.commands[cmd], self.out_spec)
            except KeyError:
                if cmd:
                    logger.error(f"Unknown command {cmd!r}")
            else:
                logger.info(f"sending {cmd!r}")
                logger.debug(f">>> {data!r}")
                self.writer.write(data)
                await self.writer.drain()
            self.command_queue.task_done()
            # throttle commands based on how long since last command
            t = now()
            since_last = t - last_sent
            last_sent = t
            if since_last > 5:
                await asyncio.sleep(1.00)
            else:
                await asyncio.sleep(0.25)

        logger.info("finished")
        self.writer.close()
        await self.writer.wait_closed()

async def main(serial_port):
    from cli import cli

    surround = HarmanKardon_Surround_Receiver(serial_port)
    await surround.connect()

    commands = asyncio.Queue()
    states = asyncio.Queue()

    print("Write surround receiver commands to stdin (Ctrl-D to stop).")
    print("Available commands:")
    for cmd in surround.commands.keys():
        print(f"    {cmd}")
    print()

    async def print_states(states):
        while True:
            s = await states.get()
            if s is None:  # shutdown
                print("Bye!")
                break
            print(s)
            states.task_done()

    await asyncio.gather(
        cli("surround> ", commands),
        surround.send(commands),
        surround.recv(states),
        print_states(states),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=HarmanKardon_Surround_Receiver.__doc__
    )
    parser.add_argument(
        "--device",
        "-D",
        default="/dev/ttyUSB1",
        help="Serial port for surround receiver (default: /dev/ttyUSB1)",
    )
    parser.add_argument(
        "--verbose", "-v", action="count", default=0, help="Increase log level"
    )
    parser.add_argument(
        "--quiet", "-q", action="count", default=0, help="Decrease log level"
    )
    args = parser.parse_args()

    loglevel = logging.WARNING + 10 * (args.quiet - args.verbose)
    logging.basicConfig(level=loglevel)

    asyncio.run(main(args.device))
