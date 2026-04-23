#!/usr/bin/env python3
import rospy
import json
import os
import sys
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Pose, Point, Quaternion
import time
import tf

# 添加g1_base_controller路径以导入遥控器相关模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
g1_base_controller_path = os.path.join(parent_dir, 'go2_base_controller', 'loco')
sys.path.append(g1_base_controller_path)

from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowState_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_ as LowStateGo2
from remote_controller import RemoteController, KeyMap

class NavigationPointRecorder:
    def __init__(self):
        rospy.init_node('navigation_point_recorder', anonymous=True)
        
        # 初始化遥控器
        self.remote_controller = RemoteController()
        
        # 初始化状态订阅
        self.low_state = unitree_hg_msg_dds__LowState_()
        self.lowstate_subscriber = ChannelSubscriber("rt/lf/lowstate", LowStateGo2)
        self.lowstate_subscriber.Init(self.LowStateHandler, 10)
        
        # 订阅里程计话题
        self.odom_sub = rospy.Subscriber('/Odometry_loc', Odometry, self.odom_callback)
        
        # 当前里程计数据
        self.current_odom = None
        
        # 导航点数据
        self.navigation_points = []
        self.point_counter = 1
        
        # 按键状态
        self.last_button_state = 0
        
        rospy.loginfo("Navigation Point Recorder initialized.")
        rospy.loginfo("Press button A on the remote controller to record a navigation point.")
        
        # 10Hz检查频率
        self.timer = rospy.Timer(rospy.Duration(0.1), self.check_button_press)
        
        # 注册关闭时的回调函数
        rospy.on_shutdown(self.save_data)
    
    def LowStateHandler(self, msg: LowStateGo2):
        """处理来自机器人的低级状态消息"""
        self.low_state = msg
        self.remote_controller.set(self.low_state.wireless_remote)
    
    def odom_callback(self, msg):
        """处理里程计消息"""
        self.current_odom = msg
    
    def check_button_press(self, event):
        """检查A键按下事件"""
        try:
            current_button_state = self.remote_controller.button[KeyMap.A]
            
            # 检测按键按下事件（边沿触发）
            if current_button_state == 1 and self.last_button_state == 0:
                self.record_navigation_point()
            
            self.last_button_state = current_button_state
            
        except Exception as e:
            rospy.logwarn(f"Button check failed: {e}")
    
    def record_navigation_point(self):
        """记录导航点"""
        if self.current_odom is None:
            rospy.logwarn("No odometry data available. Cannot record navigation point.")
            return
        
        # 获取位置和方向信息
        position = self.current_odom.pose.pose.position
        orientation = self.current_odom.pose.pose.orientation
        
        # 将四元数转换为欧拉角（yaw）
        # 使用ROS标准的tf转换方法
        quaternion = [orientation.x, orientation.y, orientation.z, orientation.w]
        euler = tf.transformations.euler_from_quaternion(quaternion)
        yaw = euler[2]  # yaw是绕z轴的旋转
        
        # 创建导航点数据
        navigation_point = {
            "id": self.point_counter,
            "name": f"Point_{self.point_counter}",
            "position": [
                position.x,
                position.y,
                yaw
            ],
            "timestamp": time.time()
        }
        
        # 添加到列表中
        self.navigation_points.append(navigation_point)
        
        rospy.loginfo(f"Navigation point {self.point_counter} recorded: "
                      f"x={position.x:.3f}, y={position.y:.3f}, z={position.z:.3f}")
        
        self.point_counter += 1
    
    def save_data(self):
        """保存数据到JSON文件"""
        if not self.navigation_points:
            rospy.loginfo("No navigation points to save.")
            return
        
        # 确保data目录存在
        data_dir = os.path.join(current_dir, '..', 'data', 'waypoints')
        os.makedirs(data_dir, exist_ok=True)
        
        # 保存到文件（直接保存数组格式）
        output_file = os.path.join(data_dir, 'navigation_points.json')
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.navigation_points, f, indent=2, ensure_ascii=False)
            rospy.loginfo(f"Navigation points saved to {output_file}")
        except Exception as e:
            rospy.logerr(f"Failed to save navigation points: {e}")

def main():
    try:
        ChannelFactoryInitialize(0)
        recorder = NavigationPointRecorder()
        rospy.spin()
    except rospy.ROSInitException:
        pass
    except KeyboardInterrupt:
        rospy.loginfo("Navigation point recorder shutdown.")
    except Exception as e:
        rospy.logerr(f"Navigation point recorder error: {e}")

if __name__ == '__main__':
    main() 