import rospy
import socket
import logging
import threading

from construct import Container, ConstError
from gamestate import GameState, ReturnData, GAME_CONTROLLER_RESPONSE_VERSION

'''
    STATE_INITIAL   : 什么都没有
    STATE_READY     ：走进球场（动起来）
    STATE_SET       ：放球（走进去）
    STATE_PLAYING   ：开始比赛
    STATE_FINISHED  ：结束比赛
'''


class Receiver:
    def __init__(self, team, player, goal_keeper, debug):
        self.ip = '0.0.0.0'    # 本地ip
        self.listen_port = 3838          # 本地端口
        self.answer_port = 3939          # 服务器端口

        self.debug = debug

        self.team_input = team           # 来自初始化的team序号，用于改变上下半场team序号
        self.team = team                 # 队伍序号（0或1）
        self.opposite_team = 1 - team    # 对面球队编号
        self.player = player             # 球员序号（0-10，上场只有4个）
        self.game_state = None           # 比赛状态
        self.data = None                 # 获取消息数据
        self.player_info = None          # 球员信息
        self.penalized_time = 0          # 罚时倒计时
        self.red_card = 0                # 是否红牌(0或1)
        self.team_color = None           # 队员颜色
        self.opposite_team_color = None  # 对面队员颜色

        self.man_penalize = True            #
        self.is_goalkeeper = goal_keeper    # 守门员
        self.peer = None                    # 服务器（ip， 端口）

        self.logger = logging.getLogger('game_controller')    # 创建logger

        self.socket1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)  # UDP协议
        self.socket1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)                   # 设定选项的值
        self.addr = (self.ip, self.listen_port)    # 本地（ip， 端口）
        self.socket1.bind(self.addr)               # 主机、端口绑定到socket上
        self.socket1.settimeout(2)                 # 阻塞时间(2s收不到就警告timeout)

        self.initialize()     # 初始化

        self.t = threading.Thread(target=self.receive)  # 设置线程，持续接收信息
        self.t.start()        # 开启线程


    def receive_once(self):
        # 接收一次消息
        try:
            data, self.peer = self.socket1.recvfrom(GameState.sizeof())  # 收消息 sizeof()函数是占内存的大小
            self.data = GameState.parse(data)        # 解析消息
            self.game_state = self.data.game_state   # 比赛状态
            if self.data.first_half == False:
                self.team = 1 - self.team_input
                self.opposite_team = 1 - self.team
            self.player_info = self.data.teams[self.team].players[self.player]  # player信息
            self.penalized_time = self.player_info.secs_till_unpenalized        # 罚时信息
            self.team_color = self.data.teams[self.team].team_color                    # 队员颜色
            self.opposite_team_color = self.data.teams[self.opposite_team].team_color  # 对面队员颜色


        # 解释报错
        except AssertionError as ae:
            self.logger.error(ae.message)
        except socket.timeout:
            pass
            self.logger.warning("Socket timeout")
        except ConstError:
            self.logger.warning("Parse Error: Probably using an old protocol!")
        except Exception as e:
            self.logger.exception(e)
            pass

    def receive(self):
        # 持续接收消息，单开线程
        while not rospy.is_shutdown():
            self.receive_once()

            # 输出debug信息
            if self.debug:
                self.debug_print()


    def debug_print(self):
        print("-----------message-----------")
        # print(self.data)
        print(self.game_state)
        # print(self.penalized_time)
        # print(self.red_card)
        # print(self.player_info)
        # print(self.team_color == "RED")
        # print(self.opposite_team_color)
        # print(self.data.first_half)
        # print(self.team)
        # print(self.opposite_team)


    def initialize(self):
        # 初始化
        while not rospy.is_shutdown():
            self.receive_once()   # 持续接收消息，直到获取服务器地址

            if self.peer:
                for i in range(5):
                    self.answer_to_gamecontroller()   # 给服务器发送5次信息
                print("initialized, break")
                break


    def answer_to_gamecontroller(self):
        # 给服务器发送信息
        return_message = 0 if self.man_penalize else 2
        if self.is_goalkeeper:
            return_message = 3

        # 发送的消息
        data = Container(
            header=b"RGrt",
            version=GAME_CONTROLLER_RESPONSE_VERSION,
            team=self.team,
            player=self.player,
            message=return_message)

        destination = (self.peer[0], self.answer_port)             # 服务器（ip， 端口）
        self.socket1.sendto(ReturnData.build(data), destination)   # 给服务器发消息



if __name__ == "__main__":
    receive = Receiver(team=1, player=0, goal_keeper=False, debug=True)

