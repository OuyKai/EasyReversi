# -*- coding:utf8 -*-

import threading
import hashlib
import socket
import base64
import struct


class websocket_thread(threading.Thread):
    def __init__(self, connection):
        super(websocket_thread, self).__init__()
        self.connection = connection

    def run(self):
        print ('new websocket client joined!')
        reply = 'i got u, from websocket server.'
        length = len(reply)
        while True:
            data = self.connection.recv(1024)
            real_data = parse_data(data)
            print(real_data)

            message = write_msg(reply)

            print(message)
            self.connection.send(message)


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


def connect():
    #socket(family,type[,protocal]) 使用给定的地址族、套接字类型、协议编号（默认为0）来创建套接字。
    '''
    socket.AF_UNIX  只能够用于单一的Unix系统进程间通信
    socket.AF_INET  服务器之间网络通信
    socket.AF_INET6 IPv6
    socket.SOCK_STREAM  流式socket , for TCP
    socket.SOCK_DGRAM   数据报式socket , for UDP
    创建TCP Socket：s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    创建UDP Socket：s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    '''

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #s.setsockopt(level,optname,value) 设置给定套接字选项的值。
    #打开或关闭地址复用功能。当option_value不等于0时，打开，否则，关闭。它实际所做的工作是置sock->sk->sk_reuse为1或0。
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 3000))
    sock.listen(1)
    print("listening...")
    #首先，我们创建了一个套接字，然后让套接字开始监听接口，并且最多只能监听5个请求
    while True:
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
        except socket.timeout:
            print('websocket connection timeout')
