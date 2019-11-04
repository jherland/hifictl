#!/usr/bin/env python3

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import pytest
import sys

sys.path.append(str(Path(__file__).parent.parent))
from virtual_serial_port import virtual_serial_port
from fake_surround_receiver_hk import Fake_HK_AVR
from surround_receiver_hk import HarmanKardon_Surround_Receiver


@asynccontextmanager
async def serial_port_to_fake_avr():
    host_tty = Path('./ttyTestHK')
    device_tty = Path('./ttyFakeHK')
    with virtual_serial_port(host_tty, device_tty, debug=True):
        fake_device = await Fake_HK_AVR.create(str(device_tty))
        device_task = asyncio.create_task(fake_device.run())
        try:
            yield str(host_tty)
        finally:
            device_task.cancel()
            try:
                await device_task
            except asyncio.CancelledError:
                pass


@asynccontextmanager
async def surround_receiver(serial_port):
    receiver = await HarmanKardon_Surround_Receiver.create(serial_port)
    command_q = asyncio.Queue()
    state_q = asyncio.Queue()
    receiver_task = asyncio.create_task(receiver.run(command_q, state_q))
    try:
        yield command_q, state_q
    finally:
        await command_q.put(None)
        await receiver_task


async def last_in_queue(q):
    last = None
    while True:
        current = await q.get()
        if current is None:  # shutdown
            break
        last = current
        q.task_done()
    return last


async def receiver_state_after_commands(serial_port, commands):
    async with surround_receiver(serial_port) as (command_q, state_q):
        state_sink = asyncio.create_task(last_in_queue(state_q))
        for command in commands:
            await command_q.put(command)

    return await state_sink


pytestmark = pytest.mark.asyncio


async def test_initial_state_is_standby():
    async with serial_port_to_fake_avr() as serial_port:
        async with surround_receiver(serial_port) as (command_q, state_q):
            state = await state_q.get()
            state_q.task_done()

    assert not state.off
    assert state.standby


async def test_sending_on_leaves_standby():
    async with serial_port_to_fake_avr() as serial_port:
        last_state = await receiver_state_after_commands(serial_port, ['on'])

    assert not last_state.off
    assert not last_state.standby
    assert not last_state.muted


async def test_sending_on_then_off_enters_standby():
    async with serial_port_to_fake_avr() as serial_port:
        last_state = await receiver_state_after_commands(serial_port, [
            'on', 'off'])

    assert not last_state.off
    assert last_state.standby


async def test_increase_volume_by_10():
    async with serial_port_to_fake_avr() as serial_port:
        async with surround_receiver(serial_port) as (command_q, state_q):
            await command_q.put('on')

            state = await state_q.get()
            state_q.task_done()
            while state.volume is None:
                state = await state_q.get()
                state_q.task_done()

            target = state.volume + 10
            state_sink = asyncio.create_task(last_in_queue(state_q))
            for _ in range(10):
                await command_q.put('vol+')

        last_state = await state_sink

    assert not last_state.off
    assert not last_state.standby
    assert last_state.volume == target


if __name__ == '__main__':
    import inspect
    import logging

    logging.basicConfig(level=logging.DEBUG)
    test_funcs = {
        name: obj
        for name, obj in inspect.getmembers(sys.modules[__name__])
        if inspect.isfunction(obj) and name.startswith('test_')}

    for name, func in test_funcs.items():
        if len(sys.argv) > 1 and not name.startswith(sys.argv[1]):
            continue
        print(f'*** Running {name}() ***')
        asyncio.run(func())
