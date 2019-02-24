#!/usr/bin/env python3

import asyncio
import logging
import responder

from surround_receiver_hk import HarmanKardon_Surround_Receiver


logger = logging.getLogger(__name__)

api = responder.API(static_dir='http_static')
api.add_route("/", static=True)

audio_commands = asyncio.Queue()
audio_states = asyncio.Queue()
last_audio_state = None
hifictl = None


@api.on_event('startup')
async def startup_hifictl():
    global hifictl
    surround = HarmanKardon_Surround_Receiver("/dev/ttyUSB1")
    await surround.connect()

    async def collect_states(audio_states):
        global last_audio_state
        while True:
            state = await audio_states.get()
            if state is None:  # shutdown
                logger.info("Bye!")
                break
            logger.info(state)
            last_audio_state = state
            audio_states.task_done()

    hifictl = asyncio.gather(
        surround.send(audio_commands),
        surround.recv(audio_states),
        collect_states(audio_states),
    )


@api.on_event('shutdown')
async def shutdown_hifictl():
    await audio_commands.put(None)
    await hifictl


async def communicate(cmd=None):
    if cmd is not None:
        try:
            category, rest = cmd.split(" ", 1)
            if category != "audio":
                raise ValueError(f"Unknown category {category!r}")
        except Exception as e:
            logger.warning("Command failed: ", e)
        else:
            await audio_commands.put(rest)

    return last_audio_state.json()


@api.route("/ws", websocket=True)
async def events(ws):
    await ws.accept()
    status = await communicate()
    while True:
        await ws.send_json(status)
        try:
            cmd = await asyncio.wait_for(ws.receive_text(), 10)
            print("Got command:", cmd)
        except:
            cmd = None
        status = await communicate(cmd)
    await ws.close()


if __name__ == '__main__':
    api.run()
