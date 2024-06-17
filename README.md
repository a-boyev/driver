# Gwinstek driver (DC power supply)

This repository contains python driver for [Gwinstek DC power supply](https://www.gwinstek.com/en-global/products/downloadSeriesDownNew/14242/1737).
It supports following features:
- Sending SCPI commands: turn on/off power channel, get device state
- Periodic device state polling, logging
- Asynchronous REST API interface

## Quick-start (Ubuntu)

1. Install [python3.4+](https://phoenixnap.com/kb/how-to-install-python-3-ubuntu), [python3-pip](https://www.cherryservers.com/blog/how-to-install-pip-ubuntu) and dependencies:
```bash
pip install -r requirements.txt
```
2. Update `host`, `port_device` and `port_driver` in config.yaml 
```yaml
host: 127.0.0.1
port_device: 5025 # Gwinstek
port_driver: 8080 # HTTP API
```
3. Launch driver
```bash
python main.py
```

4. Sample HTTP commands

```bash
# Turn on power channel
curl -X POST http://127.0.0.1:8080/cmd -d '{"cmd": "power_on", "channel": 1, "voltage": 15.0, "current": 1.0}'
# Get channel state
curl -X POST http://127.0.0.1:8080/cmd -d '{"cmd": "get_state"}'
# Turn off power channel
curl -X POST http://127.0.0.1:8080/cmd -d '{"cmd": "power_off", "channel": 1}'
```

## Running tests

```bash
pytest tests.py
```
