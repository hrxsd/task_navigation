#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
G1机器人手臂控制器
集成unitree_sdk2_python的手臂动作功能
"""

import rospy
import sys
import os
from typing import Dict, List


class ArmController:
    """G1机器人手臂控制器"""
    
    def __init__(self, network_interface: str = "enp3s0"):
        """
        初始化手臂控制器
        
        Args:
            network_interface: 网络接口名称
        """
        self.network_interface = network_interface
        self.arm_client = None
        self.is_initialized = False
        
        # 基于unitree官方的动作映射
        # 根据g1_arm_action_example.py的option_list定义
        self.gesture_id_mapping = {
            "release": 0,        # release arm
            "shake_hand": 1,     # shake hand  
            "high_five": 2,      # high five
            "hug": 3,            # hug
            "high_wave": 4,      # high wave
            "clap": 5,           # clap
            "face_wave": 6,      # face wave (启动手势)
            "left_kiss": 7,      # left kiss (告别手势)
            "heart": 8,          # heart
            "right_heart": 9,    # right heart
            "hands_up": 10,      # hands up
            "x_ray": 11,         # x-ray
            "right_hand_up": 12, # right hand up
            "reject": 13,        # reject
            "right_kiss": 14,    # right kiss
            "two_hand_kiss": 15, # two-hand kiss
        }
        
        # 基于action_map的动作名称映射
        self.action_name_mapping = {
            "release": "release arm",
            "shake_hand": "shake hand",
            "high_five": "high five", 
            "hug": "hug",
            "wave": "high wave",  # 向后兼容
            "clap": "clap",
            "face_wave": "face wave",
            "left_kiss": "left kiss",  # 告别手势
            "kiss": "left kiss",  # 向后兼容
            "heart": "heart",
            "right_heart": "right heart",
            "hands_up": "hands up",
            "x_ray": "x-ray",
            "point": "right hand up",  # 向后兼容
            "reject": "reject",
            "thumbs_up": "hands up",   # 向后兼容，使用hands up代替
        }
        
        self._init_arm_client()
        
    def _init_arm_client(self):
        """初始化手臂客户端"""
        try:
            # 添加unitree SDK路径
            sdk_path = os.path.join(
                os.path.dirname(__file__), 
                '../../unitree_sdk2_python'
            )
            sys.path.append(sdk_path)
            
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize
            from unitree_sdk2py.g1.arm.g1_arm_action_client import G1ArmActionClient, action_map
            
            # 保存action_map为实例变量
            self.action_map = action_map
            
            # 初始化通道工厂
            ChannelFactoryInitialize(0, self.network_interface)
            
            # 创建手臂动作客户端
            self.arm_client = G1ArmActionClient()
            self.arm_client.SetTimeout(10.0)
            self.arm_client.Init()
            
            self.is_initialized = True
            rospy.loginfo("G1 arm controller initialized successfully")
            
        except Exception as e:
            rospy.logwarn(f"Failed to initialize G1 arm controller: {e}")
            self.is_initialized = False
            self.action_map = None  # 确保action_map被定义
            
    def perform_gesture(self, gesture_name: str) -> bool:
        """
        执行手势动作
        
        Args:
            gesture_name: 手势名称
            
        Returns:
            bool: 是否成功执行
        """
        if not self.is_initialized:
            rospy.logwarn("Arm controller not initialized")
            return False
            
        if gesture_name not in self.action_name_mapping:
            rospy.logwarn(f"Unknown gesture: {gesture_name}")
            return False
            
        try:
            action_name = self.action_name_mapping[gesture_name]
            action_id = self.gesture_id_mapping.get(gesture_name, 0)
            rospy.loginfo(f"Performing gesture: {gesture_name} (ID: {action_id})")
            
            # 使用正确的API方法ExecuteAction，传入action_map中的值
            if not hasattr(self, 'action_map') or self.action_map is None:
                rospy.logwarn("action_map not available, cannot perform gesture")
                return False
                
            result = self.arm_client.ExecuteAction(self.action_map.get(action_name))
            
            if result == 0:
                rospy.loginfo(f"Successfully performed gesture: {gesture_name}")
                return True
            else:
                rospy.logwarn(f"Failed to perform gesture {gesture_name}, error code: {result}")
                return False
            
        except Exception as e:
            rospy.logerr(f"Failed to perform gesture {gesture_name}: {e}")
            return False
            
    def perform_startup_gesture(self) -> bool:
        """执行启动手势 (face wave, ID=6)"""
        return self.perform_gesture("face_wave")
        
    def perform_goodbye_gesture(self) -> bool:
        """执行告别手势 (left kiss, ID=7)"""
        return self.perform_gesture("left_kiss")
            
    def perform_classroom_gesture(self, context: str = "greeting") -> bool:
        """
        执行课堂相关手势
        
        Args:
            context: 上下文 ("greeting", "teaching", "praise", "goodbye")
            
        Returns:
            bool: 是否成功执行
        """
        gesture_map = {
            "greeting": "wave",
            "teaching": "point", 
            "praise": "thumbs_up",
            "goodbye": "wave"
        }
        
        gesture = gesture_map.get(context, "wave")
        return self.perform_gesture(gesture)
        
    def get_available_gestures(self) -> List[str]:
        """获取可用手势列表"""
        return list(self.action_name_mapping.keys())
        
    def is_gesture_available(self, gesture_name: str) -> bool:
        """检查手势是否可用"""
        return gesture_name in self.action_name_mapping
        
    def get_gesture_info(self) -> Dict:
        """获取手势信息"""
        return {
            "initialized": self.is_initialized,
            "available_gestures": self.get_available_gestures(),
            "network_interface": self.network_interface
        }
        
    def reset_to_default(self) -> bool:
        """重置到默认姿态"""
        return self.perform_gesture("release")
        
    def shutdown(self):
        """关闭手臂控制器"""
        try:
            if self.is_initialized:
                # 重置到默认姿态
                self.reset_to_default()
                rospy.loginfo("G1 arm controller shutdown")
        except Exception as e:
            rospy.logwarn(f"Error during arm controller shutdown: {e}")


# 测试函数
def test_arm_controller():
    """测试手臂控制器"""
    if len(sys.argv) < 2:
        print("Usage: python3 arm_controller.py <network_interface>")
        print("Example: python3 arm_controller.py enp3s0")
        return
        
    network_interface = sys.argv[1]
    
    print("Testing G1 Arm Controller...")
    
    # 初始化控制器
    controller = ArmController(network_interface)
    
    if not controller.is_initialized:
        print("Failed to initialize arm controller")
        return
        
    print("Arm controller initialized successfully")
    print(f"Available gestures: {controller.get_available_gestures()}")
    
    # 测试一些基本手势
    test_gestures = ["wave", "clap", "thumbs_up", "release"]
    
    for gesture in test_gestures:
        print(f"Performing gesture: {gesture}")
        success = controller.perform_gesture(gesture)
        print(f"Result: {'Success' if success else 'Failed'}")
        rospy.sleep(3)  # 等待3秒
        
    print("Test completed")
    controller.shutdown()


if __name__ == "__main__":
    test_arm_controller() 