#!/usr/bin/env python3

import aiohttp
from aiohttp import web
import asyncio
import logging

# from surround_receiver_hk import HarmanKardon_Surround_Receiver

logger = logging.getLogger(__name__)


async def index(request):
    raise web.HTTPFound('/static/index.html')


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            print("Got message:", msg.data)
            if msg.data == 'close':
                await ws.close()
            else:
                await ws.send_str(msg.data + '/answer')
        elif msg.type == aiohttp.WSMsgType.ERROR:
            print('ws connection closed with exception %s' %
                  ws.exception())

    print('websocket connection closed')
    return ws


if __name__ == '__main__':
    app = web.Application()
    app.add_routes([
        web.get('/', index),
        web.static('/static', 'http_static'),
        web.get('/ws', websocket_handler),
    ])

    for resource in app.router.resources():
        print(resource)

    web.run_app(app)
