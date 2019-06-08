from ..config import Config
from ..env import reversi_env as reversiEnv
from ..lib.bitboard import board_to_string
from ..play_game.game_model import PlayWithHuman, GameEvent
import threading
import hashlib
import socket
import base64
import struct
import time

Data = []
restart = False


# logger = getLogger(__name__)

def read_data():
    mes = Data[len(Data) - 1]
    Data.clear()
    return mes


class websocket_thread(threading.Thread):
    def __init__(self, connection):
        super(websocket_thread, self).__init__()
        self.connection = connection

    def run(self):
        print('new websocket client joined!')
        reply = 'i got u, from websocket server.'
        while True:
            data = self.connection.recv(1024)
            real_data = parse_data(data)
            print(real_data)
            Data.append(real_data)
            message = write_msg(reply)
            print(message)
            self.connection.send(message)


def parse_data(msg):
    if not msg:
        print("111111111")
        return
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
    data = struct.pack('B', 129)
    msg_len = len(message)
    if msg_len <= 125:
        data += struct.pack('B', msg_len)
    elif msg_len <= (2 ** 16 - 1):
        data += struct.pack('!BH', 126, msg_len)
    elif msg_len <= (2 ** 64 - 1):
        data += struct.pack('!BQ', 127, msg_len)
    else:
        logging.error('Message is too long!')
        return
    data += bytes(message, encoding='utf-8')
    return data


class AIvsHuman:
    def __init__(self, model: PlayWithHuman, connection):
        self.model = model
        self.model.add_observer(self.handle_game_event)
        self.connection = connection
        self.restart = False

    def handle_game_event(self, event):
        if event == GameEvent.update:
            self.update_status_bar()
        elif event == GameEvent.over:
            self.game_over()
        elif event == GameEvent.ai_move:
            self.ai_move()

    def new_game(self, human_is_black):
        self.model.start_game(human_is_black)
        self.model.play_next_turn()

    def ai_move(self):
        print("AI is thinking...")
        action = self.model.move_by_ai()

        if type(action) != bool:
            ai_x, ai_y = action_to_cor(action)
            print("ai落子x:" + str(ai_x))
            print("ai落子y:" + str(ai_y))
            # 发送数据
            message = str(ai_x) + str(ai_y)
            reply = write_msg(message)
            self.connection.send(reply)
            time.sleep(1)

        else:
            print("AI被你打的跳步了，帅逼！！！！！")
        self.model.play_next_turn()

    def try_move(self):
        print("come?!")
        if self.model.over or self.restart == True:
            return
        while True:

            # print('请输入row col:\n>>', end="")
            # tmp = input()
            # tmp = tmp.split()
            # 接收数据
            # if len(Data)!=0:
            #    data = read_data()
            print("come????")
            data = self.connection.recv(1024)
            data = parse_data(data)
            print("~~~")
            if data[:7] == "restart":
                print("gegege")
                self.restart = True
                return
            print(data)
            x = int(data[0])
            y = int(data[1])
            if self.model.available(y, x):
                break

            print("该位置不能下，请重新输入。")

        self.model.move(y, x)
        print(board_to_string(self.model.env.board.white, self.model.env.board.black))
        self.model.play_next_turn()

    def game_over(self):
        black, white = self.model.number_of_black_and_white
        mes = "black: %d\nwhite: %d\n" % (black, white)
        if black == white:
            mes += "** draw **"
        else:
            mes += "winner: %s" % ["black", "white"][black < white]
        print(mes)

    def update_status_bar(self):
        print("current player is " + ["White", "Black"][self.model.next_player == reversiEnv.Player.black])
        if self.model.last_evaluation:
            print(f"AI Confidence = {self.model.last_evaluation*100:.4f}%")
        # self.SetStatusText(msg)

    def refresh(self, event):
        self.update_status_bar()


def action_to_cor(action):
    for i in range(8):
        for j in range(8):
            if i * 8 + j == action:
                return i, j


def start(config: Config, connection):
    while True:
        restart = False
        config.play_with_human.update_play_config(config.play)
        reversi_model = PlayWithHuman(config)
        temp = AIvsHuman(reversi_model, connection)
        MainLoop(temp)


def MainLoop(temp: AIvsHuman):
    # 开始游戏
    # choose = eval(input("选择先后手（1为先手，0为后手）:\n>>"))
    # print("请选择先后手（1为先手，0为后手")
    # if len(Data)!=0:
    #    choose = read_data()
    # Recv = temp.connection.recv(1024)
    # choose = eval(parse_data(Recv))
    choose = 1
    print(choose)
    temp.new_game(human_is_black=choose)
    temp.role = choose  # 1为黑棋，0为白棋
    num = 0
    print(board_to_string(temp.model.env.board.white, temp.model.env.board.black))
    if temp.role == 0:
        temp.handle_game_event(GameEvent.ai_move)
    while (not temp.model.over):
        if temp.restart == True:
            break
        temp.try_move()
        print("round:" + str(num))
        print(board_to_string(temp.model.env.board.white, temp.model.env.board.black))
        temp.update_status_bar()
        num += 1
    print("finish")


class mainloop_thread(threading.Thread):
    def __init__(self, config: Config):
        super(mainloop_thread, self).__init__()
        self.config = config

    def run(self):
        start(self.config)

# sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# #s.setsockopt(level,optname,value) 设置给定套接字选项的值。
# #打开或关闭地址复用功能。当option_value不等于0时，打开，否则，关闭。它实际所做的工作是置sock->sk->sk_reuse为1或0。
# sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# sock.bind(('127.0.0.1', 3000))
# sock.listen(1)
# print("listening...")
# #首先，我们创建了一个套接字，然后让套接字开始监听接口，并且最多只能监听5个请求
#
# connection, address = sock.accept()
# #接受监听到的连接请求，
# print(address)
# try:
#     data = connection.recv(1024)
#    # print(data)
#     data = data.decode()
#     #print(data)
#     headers = parse_headers(data)
#     token = generate_token(headers['Sec-WebSocket-Key'])
#     token = token.decode()
#     message = '\
# HTTP/1.1 101 WebSocket Protocol Hybi-10\r\n\
# Upgrade: WebSocket\r\n\
# Connection: Upgrade\r\n\
# Sec-WebSocket-Accept: %s\r\n\r\n' % (token)
#     message = message.encode()
#     connection.send(message)
#     #thread = websocket_thread(connection)
#     #thread.start()
#    # thread2 = mainloop_thread(Config)
#     #thread2.start()
# except socket.timeout:
#     print('websocket connection timeout')
