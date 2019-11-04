#!/usr/bin/env python3

import asyncio
import logging
import serial_asyncio
from time import monotonic as now

import avr_command
import avr_dgram
from avr_status import AVR_Status
from avr_state import AVR_State


class HarmanKardon_Surround_Receiver:
    """Async communication with a Harman/Kardon AVR 430 surround receiver.

    Encapsulate RS-232 commands and responses to/from the serial port
    connected to this receiver.
    """

    in_spec = avr_dgram.AVR_PC_Status
    out_spec = avr_dgram.PC_AVR_Command

    # Map simple string commands to corresponding H/K serial commands
    commands = {
        'on': 'POWER ON',
        'off': 'POWER OFF',
        # 'on_off': _toggle_standby,  # Toggle on/off
        'mute': 'MUTE',
        'vol+': 'VOL UP',
        'vol-': 'VOL DOWN',
        'vol?': 'VOL DOWN',  # Use vol- to _trigger_ volume display
        'source vid1': 'VID1',
        'source vid2': 'VID2',
        'surround 6ch': '6CH/8CH',
        'surround dolby': 'DOLBY',
        'surround dts': 'DTS',
        'surround stereo': 'STEREO',
        'dig+': 'DIGITAL UP',
        'dig-': 'DIGITAL DOWN',
        'dig?': 'DIGITAL',
        # 'update': lambda self: [],  # We only _emit_ this command
    }

    @classmethod
    async def create(cls, url, baudrate=38400, *args, **kwargs):
        # The instance must be able to reconnect to the same serial port after
        # losing the connection (which happens when the surround receiver loses
        # power). Therefore, we cannot simply open the connection here and pass
        # the read + write streams onto .__init__(), as the instance would not
        # know how to _reopen_ the connection later. Instead, pass function to
        # open the serial connection to .__init__() and then call ._connect().
        async def open_serial_port():
            return await serial_asyncio.open_serial_connection(
                url=url, baudrate=baudrate, *args, **kwargs)

        obj = cls(open_serial_port)
        await obj._connect()
        return obj

    def __init__(self, connector):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.connector = connector
        self.rstream = None
        self.wstream = None
        self.state = AVR_State()
        self.command_queue = None

    async def _connect(self):
        if self.wstream is not None:
            self.wstream.close()
            await self.wstream.wait_closed()
        self.rstream, self.wstream = await self.connector()
        self.logger.info(f'Connected via {self.wstream.transport.serial.name}')

    async def _recv(self, state_queue):
        """Read state updates from surround receiver and put onto state_queue.

        If EOF is received over the serial port, put None as a sentinel onto
        the 'state_queue' and exit immediately.
        """
        logger = self.logger.getChild('recv')
        while True:
            try:
                dgram = await asyncio.wait_for(
                    self.rstream.read(avr_dgram.dgram_len(self.in_spec)), 10)
            except asyncio.TimeoutError:
                logger.warning('Nothing incoming. Re-establishing connection.')
                # TODO: Pass status=None to self.state.update() to signal Off?
                await self._connect()
                continue
            except asyncio.IncompleteReadError as e:
                logger.debug('incomplete read:')
                dgram = e.partial
            logger.debug(f'<<< {dgram!r}')
            try:
                status = AVR_Status.parse(
                    avr_dgram.decode(dgram, self.in_spec))
            except ValueError as e:
                logger.warning(f'Discarding datagram: {e}')
                # TODO: Pass status=None to self.state.update() to signal Off?
            else:
                logger.debug(f'received {status}')
                new_state = self.state.update(status)
                if new_state != self.state:
                    logger.debug(f'state -> {new_state}')
                    await state_queue.put(new_state)
                    await state_queue.join()
                    await self._control(new_state)
            if self.rstream.at_eof():
                await state_queue.put(None)  # EOF
                logger.info('finished')
                break

    async def _control(self, new_state):
        assert self.command_queue is not None
        prev = self.state
        self.state = new_state

        if not self.command_queue.empty():
            return  # Hold off while there are pending commands
        if self.state.off or self.state.standby or self.state.muted:
            return  # Nothing to do

        if self.state.volume is None:
            await self.command_queue.put('vol?')  # Trigger volume display
            await self.command_queue.join()
        # TODO: REMOVE? assert self.state.source is not None
        if self.state.digital is None:
            await self.command_queue.put('dig?')  # Trigger digital display
            await self.command_queue.join()
        assert self.state.line1 is not None
        assert self.state.line2 is not None

        # Trigger wake from standby if we just went from OFF -> STANDBY
        if prev.off and self.state.standby:
            await self.command_queue.put('on')
            await self.command_queue.join()

        # My receiver has "episodes" where volume increases suddenly...
        if self.state.volume is None:
            pass
        elif self.state.volume > -15:
            self.logger.error('*** PANIC: Volume runaway, shutting down!')
            await self.command_queue.put('off')
            await self.command_queue.join()
        elif self.state.volume > -20:
            self.logger.warning('*** WARNING: Volume runaway? decreasing...')
            await self.command_queue.put('vol-')
            await self.command_queue.join()

    async def _send(self):
        """Write receiver commands from the to the serial port."""
        assert self.command_queue is not None
        logger = self.logger.getChild('send')
        last_sent = 0.0

        while True:
            cmd = await self.command_queue.get()
            if cmd is None:  # shutdown
                break
            try:
                data = avr_dgram.encode(
                    avr_command.encode(self.commands[cmd]),
                    self.out_spec)
            except KeyError:
                if cmd:
                    logger.error(f'Unknown command {cmd!r}')
            else:
                logger.info(f'sending {cmd!r}')
                logger.debug(f'>>> {data!r}')
                self.wstream.write(data)
                await self.wstream.drain()
            self.command_queue.task_done()
            # throttle commands based on how long since last command
            t = now()
            since_last = t - last_sent
            last_sent = t
            if since_last > 5:
                await asyncio.sleep(1.00)
            else:
                await asyncio.sleep(0.3)

        logger.info('finished')
        self.wstream.close()
        await self.wstream.wait_closed()

    async def run(self, command_queue, state_queue):
        try:
            self.command_queue = command_queue
            await asyncio.gather(
                self._send(),
                self._recv(state_queue),
            )
        finally:
            self.command_queue = None


async def main(serial_port):
    from cli import cli

    surround = await HarmanKardon_Surround_Receiver.create(serial_port)

    commands = asyncio.Queue()
    states = asyncio.Queue()

    print('Write surround receiver commands to stdin (Ctrl-D to stop).')
    print('Available commands:')
    for cmd in surround.commands.keys():
        print(f'    {cmd}')
    print()

    async def print_states(states):
        while True:
            s = await states.get()
            if s is None:  # shutdown
                print('Bye!')
                break
            print(s)
            states.task_done()

    await asyncio.gather(
        cli('surround> ', commands),
        surround.run(commands, states),
        print_states(states),
    )


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description=HarmanKardon_Surround_Receiver.__doc__)
    parser.add_argument(
        '--device', '-D', default='/dev/ttyUSB1',
        help='Serial port for surround receiver (default: /dev/ttyUSB1)')
    parser.add_argument(
        '--verbose', '-v', action='count', default=0,
        help='Increase log level')
    parser.add_argument(
        '--quiet', '-q', action='count', default=0,
        help='Decrease log level')
    args = parser.parse_args()

    loglevel = logging.WARNING + 10 * (args.quiet - args.verbose)
    logging.basicConfig(level=loglevel)

    asyncio.run(main(args.device))
