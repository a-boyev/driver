# Copyright Aleksey Boev, 2024
# Based on https://gist.github.com/pklaus/b741eedc66b5dc01f49a

import socketserver
import socket, threading
import sys, logging, time, yaml
from logging import DEBUG, INFO

logger = logging.getLogger('scpi-server')
default_config = {"host": "127.0.0.1", "port_device": 5000}
context = {"config": {}, "state": {i: {"voltage": 0, "current": 0, "active": 0} for i in range(4)}}

class CmdTCPServer(socketserver.ThreadingTCPServer):
    """
    A TCP server made to respond to line based commands.
    """

    #: newline character(s) to be added to string responses
    newline = '\n'
    #: Ctrl-C will cleanly kill all spawned threads
    daemon_threads = True
    #: much faster rebinding possible
    allow_reuse_address = True
    address_family = socket.AF_INET

    class CmdRequestHandler(socketserver.StreamRequestHandler):
        def handle(self):
            if not self.server.lock.acquire(blocking=False):
                self.log(DEBUG, 'An additional cliend tried to connect from {client}. Denying...')
                return
            self.log(DEBUG, 'Connected to {client}.')
            try:
                while True:
                    self.single_cmd()
            except Disconnected:
                pass
                self.log(DEBUG, 'The client {client} closed the connection')
            finally:
                self.server.lock.release()
        def read_cmd(self):
            return self.rfile.readline().decode('utf-8').strip()
        def log(self, level, msg, *args, **kwargs):
            if type(level) == str:
                level = getattr(logging, level.upper())
            msg = msg.format(client=self.client_address[0])
            logger.log(level, msg, *args, **kwargs)
        def send_reply(self, reply):
            if type(reply) == str:
                if self.server.newline: reply += self.server.newline
                reply = reply.encode('utf-8')
            self.wfile.write(reply)
        def single_cmd(self):
            cmd = self.read_cmd()
            if not cmd: raise Disconnected
            self.log(DEBUG, 'Received a cmd: {}'.format(cmd))
            try:
                reply = self.server.process(cmd)
                if reply is not None:
                    self.send_reply(reply)
            except:
                self.send_reply('ERR')

    def __init__(self, server_address, name=None):
        socketserver.TCPServer.__init__(self, server_address, self.CmdRequestHandler)
        self.lock = threading.Lock()
        self.name = name if name else "{}:{}".format(*server_address)

    def process(self, cmd):
        """
        Implement this method to handle command processing.
        For each command, this method will be called.
        Return a string or bytes as appropriate.
        If your the message is only a command (not a query), return None.
        """
        raise NotImplemented

class SCPIServerExample(CmdTCPServer):

    def get_state(self, channel):
        if context["state"][channel]["active"] == 1:
            voltage = context["state"][channel]["voltage"]
            current = context["state"][channel]["current"]
            power = voltage * current
            return voltage, current, power
        else:
            return 0, 0, 0

    def process(self, cmd):
        """
        This is the method to process each SCPI command
        received from the client.
        """
        for i in range(4):
          if cmd.startswith(f":MEASure{i+1}:ALL"):
              v, c, p = self.get_state(i)
              time.sleep(0.1)
              return "%f, %f, %f" % (v, c, p)
        for i in range(4):
          if cmd.startswith(f":SOURce{i+1}:CURRent"):
              current = float(cmd.split(" ")[1])
              context["state"][i]["current"] = current
              return
        for i in range(4):
          if cmd.startswith(f":SOURce{i+1}:VOLTage"):
              voltage = float(cmd.split(" ")[1])
              context["state"][i]["voltage"] = voltage
              return
        for i in range(4):
          if cmd.startswith(f":OUTPut{i+1}:STATe"):
              state = cmd.split(" ")[1].lstrip().rstrip()
              if state in ["ON", "1"]:
                  context["state"][i]["active"] = 1
              elif state in ["OFF", "0"]:
                  context["state"][i]["active"] = 0
              return
        return 'unknown cmd'

def main():
    logging.basicConfig(format='%(message)s', level="INFO")
    scpi_server = SCPIServerExample((context["config"]["host"], context["config"]["port_device"]))
    try:
        scpi_server.serve_forever()
    except KeyboardInterrupt:
        logger.info('Ctrl-C pressed. Shutting down...')
    scpi_server.server_close()

class Disconnected(Exception): pass

if __name__ == "__main__":
    context["config"].update(default_config)
    config_file = "config.yaml"
    if len(sys.argv) > 1: config_file = sys.argv[1]
    with open(config_file) as f:
        try:
            context["config"].update(yaml.safe_load(f))
        except yaml.YAMLError as exc:
            pass
    main()
