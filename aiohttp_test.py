#!/usr/bin/env python3

import aiohttp
from aiohttp import web
import asyncio
import logging

from surround_receiver_hk import HarmanKardon_Surround_Receiver


logger = logging.getLogger(__name__)

audio_commands = asyncio.Queue()
audio_states = asyncio.Queue()
last_audio_state = None
hifictl = None
ws_connections = set()


async def audio_state_listener(audio_states):
    global ws_connections
    global last_audio_state
    while True:
        state = await audio_states.get()
        if state is None:  # shutdown
            logger.info('Bye!')
            break
        logger.info(state)
        last_audio_state = state.json()
        for conn in ws_connections:
            await conn.send_json(last_audio_state)
        audio_states.task_done()


async def forward_command(cmd):
    try:
        category, rest = cmd.split(' ', 1)
        if category != 'audio':
            raise ValueError(f'Unknown category {category!r}')
    except Exception as e:
        logger.warning('Command failed: %s', e)
    else:
        await audio_commands.put(rest)


async def on_startup(app):
    logger.info('starting up...')
    global hifictl
    surround = HarmanKardon_Surround_Receiver('/dev/ttyUSB1')
    await surround.connect()

    hifictl = asyncio.gather(
        surround.send(audio_commands),
        surround.recv(audio_states),
        audio_state_listener(audio_states),
    )


async def on_cleanup(app):
    logger.info('cleaning up...')
    await audio_commands.put(None)
    await hifictl


async def index(request):
    raise web.HTTPFound('/static/index.html')


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    logger.info('websocket connection open')

    await ws.send_json(last_audio_state)
    ws_connections.add(ws) # future updates are sent by audio_state_listener()

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            logger.info('got command: %s', msg.data)
            await forward_command(msg.data)
        elif msg.type == aiohttp.WSMsgType.ERROR:
            logger.warning(
                'ws connection closed with exception %s', ws.exception())

    logger.info('websocket connection closed')
    ws_connections.remove(ws)
    return ws


def init():
    app = web.Application()
    app.add_routes([
        web.get('/', index),
        web.static('/static', 'http_static'),
        web.get('/ws', websocket_handler),
    ])
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    app = init()

    for resource in app.router.resources():
        print(resource)

    web.run_app(app)
