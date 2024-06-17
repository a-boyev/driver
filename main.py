# Copyright Aleksey Boev, 2024

import sys, yaml, json, asyncio, logging
from aiohttp import web

default_config = {"host": "127.0.0.1", "port_device": 5000, "port_driver": 8080,
    "poll_interval": 1, "log_file": "out.log", "log_level": "INFO"}
context = {"config": {}, "state": {}}

logger = logging.getLogger(__name__)

async def send_cmd(cmd):
    logger.debug(f"[send_cmd] {cmd}")
    context["writer"].write((cmd + "\n").encode())
    await context["writer"].drain()
    if cmd[-1] == "?":
        data = await context["reader"].readline()
        return data.decode()

async def power_on(channel, current, voltage):
    logger.debug(f"[power_on] {channel}, {current}, {voltage}")
    await send_cmd(f":SOURce{channel}:CURRent {current}")
    await send_cmd(f":SOURce{channel}:VOLTage {voltage}")
    await send_cmd(f":OUTPut{channel}:STATe ON")

async def power_off(channel):
    logger.debug(f"[power_off] {channel}")
    await send_cmd(f":OUTPut{channel}:STATe OFF")

async def poll_state(channel):
    response = await send_cmd(f":MEASure{channel}:ALL?")
    voltage, current, power = tuple(map(float, response.split(",")))
    return voltage, current, power

async def polling_loop():
    while True:
        try:
            await asyncio.sleep(context["config"]["poll_interval"])
            for i in range(4):
                voltage, current, power = await poll_state(i+1)
                context["state"][i + 1] = {"voltage": voltage, "current": current, "power": power}
            logger.info("[device_state] %s" % json.dumps(context["state"]))
        except:
            await connect_device()

async def http_cmd(request):
    body = await request.json()
    response = {}
    try:
        if body["cmd"] == "power_on":
            channel = body["channel"]
            voltage = body["voltage"]
            current = body["current"]
            await power_on(channel, current, voltage)
            response = web.json_response({"status": "ok"})
        elif body["cmd"] == "power_off":
            channel = body["channel"]
            await power_off(channel)
            response = web.json_response({"status": "ok"})
        elif body["cmd"] == "get_state":
            response = {"status": "ok", "payload": context["state"]}
            response = web.json_response(response)
        else:
            response = web.json_response({"status": "error", "msg": "Command not supported"})
    except:
        response = web.json_response({"status": "error"})
    return response

async def connect_device():
    connected = False
    while connected == False:
        try:
            reader, writer = await asyncio.open_connection(context["config"]["host"],\
                context["config"]["port_device"])
            context["reader"] = reader
            context["writer"] = writer
            logger.info("Device connected, start polling...")
            connected = True
        except:
            logger.error("Device disconnected, reconnecting...")
            await asyncio.sleep(context["config"]["poll_interval"])

def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
        filename=context["config"]["log_file"], datefmt='[%Y-%m-%d %H:%M:%S]',
        level=logging.getLevelName(context["config"]["log_level"]))

    app = web.Application()
    app.add_routes([web.post('/cmd', http_cmd)])

    loop = asyncio.get_event_loop()
    connect_task = loop.create_task(connect_device())
    loop.run_until_complete(connect_task)
    loop.create_task(polling_loop())
    web.run_app(app, loop = loop, port = context["config"]["port_driver"])

if __name__ == '__main__':
    context["config"].update(default_config)
    config_file = "config.yaml"
    if len(sys.argv) > 1: config_file = sys.argv[1]
    with open(config_file) as f:
        try:
            context["config"].update(yaml.safe_load(f))
        except yaml.YAMLError as exc:
            pass
    main()
