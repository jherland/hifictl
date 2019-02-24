#!/usr/bin/env python3

import asyncio
import responder


api = responder.API(static_dir='http_static')
api.add_route("/", static=True)


async def communicate(cmd=None):
    if cmd is not None:
        return {"status": "Executing " + cmd}
    return {"status": "foobar"}


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
