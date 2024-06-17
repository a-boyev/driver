# Copyright Aleksey Boev, 2024

import os, signal, yaml, json, socket, subprocess, time, requests, datetime, random

context = {"config": {"host": "127.0.0.1", "port_device": 5555, "port_driver": 8080,
                      "log_level": "DEBUG", "poll_interval": 1},
           "test_dir": "_tmp", "proc_device": None, "proc_driver": None}

def setup():
    '''
       Global setup:
           - Create 'test_dir' for temporary artifacts (test config and test log)
           - Save test config file to 'test_dir'
           - Launch mock device and driver subprocesses
           - Allow small time delta for bootup time
    '''
    os.makedirs(context["test_dir"], exist_ok=True)
    context["config"]["port_driver"] = get_free_port(context["config"]["port_driver"])
    context["config"]["port_device"] = get_free_port(context["config"]["port_device"])
    context["config"]["log_file"] = os.path.join(context["test_dir"], "log.txt")
    if os.path.exists(context["config"]["log_file"]): os.remove(context["config"]["log_file"])
    config_file = os.path.join(context["test_dir"], "config.yaml")
    with open(config_file, 'w') as f:
        yaml.dump(context["config"], f)
    context["proc_device"] = subprocess.Popen(["python", "mock.py", config_file])
    time.sleep(0.5)
    context["proc_driver"] = subprocess.Popen(["python", "main.py", config_file])
    time.sleep(0.5)

def teardown():
    '''
       Global teardown:
           - Terminate mock device and driver subprocesses
    '''
    if context["proc_driver"] != None: context["proc_driver"].kill()
    if context["proc_device"] != None: context["proc_device"].kill()

def make_cmd(cmd, channel = None, voltage = None, current = None):
    result = {"cmd": cmd, "scpi": []}
    if channel == None: channel = random.randint(1, 4)
    result["channel"] = channel
    if cmd == "power_on":
        if voltage == None: voltage = random.randint(10, 150) / 10.0
        if current == None: current = random.randint(10, 30) / 10.0
        result["voltage"] = voltage
        result["current"] = current
        result["scpi"].append(f":SOURce{channel}:CURRent {current}")
        result["scpi"].append(f":SOURce{channel}:VOLTage {voltage}")
        result["scpi"].append(f":OUTPut{channel}:STATe ON")
    elif cmd == "power_off":
        result["scpi"].append(f":OUTPut{channel}:STATe OFF")
    return result
 
def send_cmd(cmd_json):
    driver_url = "http://" + context["config"]["host"] + ":" + str(context["config"]["port_driver"]) + "/cmd"
    r = requests.post(driver_url, data=json.dumps(cmd_json))

def test_routing():
    '''
      Routing tests: check that proper driver method is invoked upon http request
    '''
    cmd_json = make_cmd("power_on")
    send_cmd(cmd_json)
    log_item = find_log_item(cmd = "power_on")
    assert log_item != None
    assert log_item["channel"] == cmd_json["channel"]
    assert log_item["voltage"] == cmd_json["voltage"]
    assert log_item["current"] == cmd_json["current"]

    cmd_json = make_cmd(cmd = "power_off")
    send_cmd(cmd_json)
    log_item = find_log_item(cmd = "power_off")
    assert log_item != None
    assert log_item["channel"] == cmd_json["channel"]

def test_scpi():
    '''
      SCPI tests: check that proper SCPI command is invoked upon http request
    '''
    cmd_json = make_cmd("power_on")
    send_cmd(cmd_json)
    for scpi_cmd in cmd_json["scpi"]:
        log_item = find_log_item(cmd = "send_cmd", keyword = scpi_cmd)
        assert log_item != None

def test_device():
    '''
      Device tests: check that device replies with proper values upon http requests
      Overall scenario:
         - Check that 'device_state' keyword is included in log file
         - Send 'power_off' command to all channels
         - Check that current, voltage and power values are all zero
         - Send 'power_on' command to all channels
         - Check that current, voltage and power values match target
    '''
    
    time.sleep(context["config"]["poll_interval"] * 2) # wait for polling
    log_item = find_log_item(keyword = "device_state")
    assert log_item != None
    for i in range(4):
        cmd_json = make_cmd("power_off", i + 1)
        send_cmd(cmd_json)
    time.sleep(context["config"]["poll_interval"] * 2)
    timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    time.sleep(context["config"]["poll_interval"] * 2)
    log_item = find_log_item(keyword = "device_state", time_min = timestamp)
    assert log_item != None
    for i in range(4):
        assert log_item["state"][str(i+1)]["voltage"] == 0
        assert log_item["state"][str(i+1)]["current"] == 0
        assert log_item["state"][str(i+1)]["power"] == 0
    for i in range(4):
        cmd_json = make_cmd("power_on", i + 1)
        send_cmd(cmd_json)
        time.sleep(context["config"]["poll_interval"] * 2)
        timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        time.sleep(context["config"]["poll_interval"] * 2)
        log_item = find_log_item(keyword = "device_state", time_min = timestamp)
        assert log_item["state"][str(i+1)]["voltage"] == cmd_json["voltage"]
        assert log_item["state"][str(i+1)]["current"] == cmd_json["current"]
        assert log_item["state"][str(i+1)]["power"] > 0

def get_free_port(start_port = 5555):
    def check_port(sock, port):
        if sock.connect_ex((context["config"]["host"], port)) == 0:
            return True
        else:
            return False
    port = start_port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while check_port(sock, port) == True: port = port + 1
    sock.close()
    return port

def parse_log_item(log_item):
    result = {}
    result["timestamp"] = log_item.split("]")[0][1:]
    if "power_on" in log_item:
        result["cmd"] = "power_on"
        params = log_item.split("[power_on] ")[1]
        channel, current, voltage = tuple(map(float,params.split(", ")))
        result["channel"] = channel
        result["current"] = current
        result["voltage"] = voltage
    elif "power_off" in log_item:
        result["cmd"] = "power_off"
        result["channel"] = int(log_item.split("[power_off] ")[1])
    elif "send_cmd" in log_item:
        result["cmd"] = "send_cmd"
        result["scpi_cmd"] = log_item.split("[send_cmd] ")[1]
    elif "device_state" in log_item:
        state_json = log_item.split("[device_state] ")[1]
        result["state"] = json.loads(state_json)
    return result

def find_log_item(cmd = None, keyword = None, time_min = None):
    with open(context["config"]["log_file"], 'r') as f:
        for log_item in f.readlines():
            item = parse_log_item(log_item)
            if (cmd == None) or (item.get("cmd", "") == cmd):
                if (time_min == None) or (item.get("timestamp", "") >= time_min):
                    if (keyword == None) or (keyword in log_item):
                        return item
    return None
