#!/usr/bin/env python3
import time
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_ as LowStateGo2
from remote_controller import RemoteController, KeyMap

class RemoteTest:
    def __init__(self):
        # 初始化遥控器
        self.remote_controller = RemoteController()
        
        # 初始化状态订阅
        self.low_state = unitree_go_msg_dds__LowState_()
        self.lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowStateGo2)
        self.lowstate_subscriber.Init(self.LowStateHandler, 10)
        
        print("Go2 Remote Test initialized.")
        print("Press Select button on remote to test...")
    
    def LowStateHandler(self, msg: LowStateGo2):
        """处理来自机器人的低级状态消息"""
        self.low_state = msg
        try:
            # 打印原始数据
            print(f"Raw wireless_remote data: {list(msg.wireless_remote)}")
            
            self.remote_controller.set(msg.wireless_remote)
            
            # 打印按键状态
            print(f"Select button: {self.remote_controller.button[KeyMap.select]}")
            print(f"All buttons: {self.remote_controller.button}")
            print(f"Joystick: Lx={self.remote_controller.lx:.2f}, Ly={self.remote_controller.ly:.2f}, Rx={self.remote_controller.rx:.2f}, Ry={self.remote_controller.ry:.2f}")
            print("-" * 50)
            
        except Exception as e:
            print(f"Error parsing remote data: {e}")

if __name__ == '__main__':
    try:
        ChannelFactoryInitialize(0)
        test = RemoteTest()
        
        print("Press Ctrl+C to stop...")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Test stopped.") 