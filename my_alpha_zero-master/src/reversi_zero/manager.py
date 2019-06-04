import argparse
from logging import getLogger

import yaml
from moke_config import create_config

from .config import Config
from .lib.logger import setup_logger

import threading
import hashlib
import socket
import base64
import struct

logger = getLogger(__name__)

CMD_LIST = ['self', 'opt', 'eval', 'play_console', 'play_gui','play_online']


def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", help="what to do", choices=CMD_LIST)
    parser.add_argument("-c", help="specify config yaml", dest="config_file")
    parser.add_argument("--new", help="run from new best model", action="store_true")
    parser.add_argument("--type", help="deprecated. Please use -c instead")
    parser.add_argument("--total-step", help="set TrainerConfig.start_total_steps", type=int)
    return parser


def setup(config: Config, args):
    config.opts.new = args.new
    if args.total_step is not None:
        config.trainer.start_total_steps = args.total_step
    config.resource.create_directories()
    setup_logger(config.resource.main_log_path)


def start():
    parser = create_parser()
    args = parser.parse_args()
    if args.type:
        print("I'm very sorry. --type option was deprecated. Please use -c option instead!")
        return 1

    if args.config_file:
        with open(args.config_file, "rt") as f:
            config = create_config(Config, yaml.load(f))
    else:
        config = create_config(Config)
    setup(config, args)

    if args.cmd != "nboard":
        logger.info(f"config type: {config.type}")

    if args.cmd == "self":
        from .worker import self_play
        return self_play.start(config)
    elif args.cmd == 'opt':
        from .worker import optimize
        return optimize.start(config)
    elif args.cmd == 'eval':
        from .worker import evaluate
        return evaluate.start(config)
    elif args.cmd == 'play_console':
        from .play_game import console
        return console.start(config)
    elif args.cmd == 'play_gui':
        from .play_game import gui
        return gui.start(config)
    elif args.cmd == 'play_online':
        from .play_game import play_online
        return play_online.start(config, connection)

def parse_data(msg):
    v = msg[1] & 0x7f
    if v == 0x7e:
        p = 4
    elif v == 0x7f:
        p = 10
    else:
        p = 2
    mask = msg[p:p + 4]
    data = msg[p + 4:]

    return ''.join([chr(v ^ mask[k % 4]) for k, v in enumerate(data)])


def parse_headers(msg):
    headers = {}
    header, data = msg.split('\r\n\r\n', 1)
    for line in header.split('\r\n')[1:]:
        key, value = line.split(': ', 1)
        headers[key] = value
    headers['data'] = data
    return headers


def generate_token(msg):
    key = msg + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    key = key.encode()
    ser_key = hashlib.sha1(key).digest()
    return base64.b64encode(ser_key)

def write_msg(message):
    data = struct.pack('B',129)
    msg_len = len(message)
    if msg_len <= 125:
        data += struct.pack('B',msg_len)
    elif msg_len <= (2**16-1):
        data += struct.pack('!BH',126,msg_len)
    elif msg_len <= (2**64-1):
        data += struct.pack('!BQ',127,msg_len)
    else:
        logging.error('Message is too long!')
        return
    data +=bytes(message,encoding='utf-8')
    return data

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#s.setsockopt(level,optname,value) 设置给定套接字选项的值。
#打开或关闭地址复用功能。当option_value不等于0时，打开，否则，关闭。它实际所做的工作是置sock->sk->sk_reuse为1或0。
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('127.0.0.1', 3000))
sock.listen(1)
print("listening...")
#首先，我们创建了一个套接字，然后让套接字开始监听接口，并且最多只能监听5个请求


connection, address = sock.accept()
#接受监听到的连接请求，
print(address)
try:
    data = connection.recv(1024)
   # print(data)
    data = data.decode()
    #print(data)
    headers = parse_headers(data)
    token = generate_token(headers['Sec-WebSocket-Key'])
    token = token.decode()
    message = '\
HTTP/1.1 101 WebSocket Protocol Hybi-10\r\n\
Upgrade: WebSocket\r\n\
Connection: Upgrade\r\n\
Sec-WebSocket-Accept: %s\r\n\r\n' % (token)
    message = message.encode()
    connection.send(message)
    #thread = websocket_thread(connection)
    #thread.start()
   # thread2 = mainloop_thread(Config)
    #thread2.start()
except socket.timeout:
    print('websocket connection timeout')