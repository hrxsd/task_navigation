#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ROS导航控制器模块
负责与move_base交互，发送导航目标和监控导航状态
"""

import rospy
import actionlib
import threading
import time
from typing import List, Tuple, Optional

from geometry_msgs.msg import PoseStamped, Twist
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from actionlib_msgs.msg import GoalStatus
import tf
from tf.transformations import quaternion_from_euler


class NavigationController:
    """导航控制器类"""
    
    def __init__(self, map_frame: str = "map", robot_frame: str = "base_link"):
        """
        初始化导航控制器
        
        Args:
            map_frame: 地图坐标系
            robot_frame: 机器人坐标系
        """
        self.map_frame = map_frame
        self.robot_frame = robot_frame
        
        # 初始化move_base客户端
        self.move_base_client = actionlib.SimpleActionClient(
            'move_base', MoveBaseAction
        )
        
        rospy.loginfo("Waiting for move_base action server...")
        if self.move_base_client.wait_for_server(rospy.Duration(10)):
            rospy.loginfo("Connected to move_base server")
        else:
            rospy.logwarn("Could not connect to move_base server")
        
        # 初始化TF监听器
        self.tf_listener = tf.TransformListener()
        
        # 初始化底盘速度控制发布者（用于紧急停止）
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        
        # 导航状态
        self.is_navigating = False
        self.navigation_thread = None
        self.current_goal = None
        self.force_stop_flag = False  # 强制停止标志
        
        # 状态映射
        self.status_map = {
            GoalStatus.PENDING: "等待中",
            GoalStatus.ACTIVE: "执行中",
            GoalStatus.PREEMPTED: "已取消",
            GoalStatus.SUCCEEDED: "已完成",
            GoalStatus.ABORTED: "已中止",
            GoalStatus.REJECTED: "已拒绝",
            GoalStatus.PREEMPTING: "取消中",
            GoalStatus.RECALLING: "召回中",
            GoalStatus.RECALLED: "已召回",
            GoalStatus.LOST: "已丢失"
        }
    
    def send_goal(self, position: List[float]) -> bool:
        """
        发送导航目标
        
        Args:
            position: [x, y, w] 坐标和朝向
            
        Returns:
            bool: 是否成功发送
        """
        try:
            # 取消之前的导航
            if self.is_navigating:
                self.cancel_navigation()
                time.sleep(0.5)
            
            # 创建导航目标
            goal = self._create_goal(position)
            self.current_goal = position
            
            rospy.loginfo(
                f"Sending navigation goal: x={position[0]:.2f}, "
                f"y={position[1]:.2f}, yaw={position[2]:.2f}"
            )
            
            # 发送目标
            self.move_base_client.send_goal(goal)
            self.is_navigating = True
            
            # 启动监控线程
            self.navigation_thread = threading.Thread(
                target=self._monitor_navigation
            )
            self.navigation_thread.daemon = True
            self.navigation_thread.start()
            
            return True
            
        except Exception as e:
            rospy.logerr(f"Failed to send navigation goal: {e}")
            return False
    
    def wait_for_result(self, timeout: float = None) -> bool:
        """
        等待导航结果
        
        Args:
            timeout: 超时时间（秒），如果为None则无超时限制
            
        Returns:
            bool: 导航是否成功
        """
        if not self.is_navigating:
            rospy.logwarn("No navigation in progress")
            return False
            
        try:
            # 等待导航完成，不设置超时或使用指定超时
            if timeout is None:
                # 无超时限制，等待直到完成
                success = self.move_base_client.wait_for_result()
            else:
                success = self.move_base_client.wait_for_result(rospy.Duration(timeout))
            
            if success:
                state = self.move_base_client.get_state()
                if state == GoalStatus.SUCCEEDED:
                    rospy.loginfo("Navigation succeeded")
                    self.is_navigating = False
                    return True
                else:
                    rospy.logwarn(f"Navigation failed with state: {self.status_map.get(state, state)}")
                    self.is_navigating = False
                    return False
            else:
                # 只有在设置了超时且超时时才会到这里
                rospy.logwarn("Navigation timeout")
                self.cancel_navigation()
                return False
                
        except Exception as e:
            rospy.logerr(f"Error waiting for navigation result: {e}")
            self.cancel_navigation()
            return False

    def cancel_navigation(self):
        """强制取消当前导航"""
        if self.is_navigating:
            rospy.loginfo("Force canceling navigation...")
            
            # 设置强制停止标志
            self.force_stop_flag = True
            
            # 1. 立即发送零速度命令停止机器人移动
            self._emergency_stop()
            
            # 2. 检查ActionClient状态，只有在合适的状态下才取消
            try:
                current_state = self.move_base_client.get_state()
                # 只有在这些状态下才发送取消命令
                if current_state in [GoalStatus.PENDING, GoalStatus.ACTIVE, GoalStatus.PREEMPTING]:
                    self.move_base_client.cancel_goal()
                    rospy.loginfo("Move_base goal cancellation sent")
                    
                    # 3. 等待取消确认（最多等待2秒）
                    self._wait_for_cancellation(timeout=2.0)
                else:
                    rospy.loginfo(f"Navigation already in terminal state: {self.status_map.get(current_state)}")
                    
            except Exception as e:
                rospy.logwarn(f"Error checking/cancelling move_base goal: {e}")
            
            # 4. 清理状态
            self.is_navigating = False
            self.current_goal = None
            self.force_stop_flag = False
            
            rospy.loginfo("Navigation cancellation completed")
        else:
            rospy.logdebug("No active navigation to cancel")
    
    def _emergency_stop(self):
        """紧急停止机器人移动"""
        try:
            # 发送零速度命令
            stop_cmd = Twist()
            # 连续发送几次确保机器人停止
            for _ in range(5):
                self.cmd_vel_pub.publish(stop_cmd)
                rospy.sleep(0.1)
            rospy.loginfo("Emergency stop command sent")
        except Exception as e:
            rospy.logerr(f"Error sending emergency stop: {e}")
    
    def _wait_for_cancellation(self, timeout: float = 2.0):
        """等待取消确认"""
        start_time = rospy.Time.now()
        while (rospy.Time.now() - start_time).to_sec() < timeout:
            try:
                state = self.move_base_client.get_state()
                if state in [GoalStatus.PREEMPTED, GoalStatus.RECALLED, 
                           GoalStatus.ABORTED, GoalStatus.SUCCEEDED]:
                    rospy.loginfo(f"Cancellation confirmed with state: {self.status_map.get(state)}")
                    return True
            except Exception as e:
                rospy.logdebug(f"Error checking cancellation state: {e}")
            
            rospy.sleep(0.1)
        
        rospy.logwarn("Cancellation confirmation timeout")
        return False

    def get_navigation_status(self) -> str:
        """
        获取导航状态
        
        Returns:
            str: 导航状态描述
        """
        if self.force_stop_flag:
            return "强制停止中"
            
        if not self.is_navigating:
            return "空闲"
        
        try:
            state = self.move_base_client.get_state()
            return self.status_map.get(state, f"未知状态({state})")
        except Exception as e:
            rospy.logdebug(f"Error getting navigation status: {e}")
            return "状态未知"
    
    def get_robot_position(self) -> Optional[Tuple[float, float, float]]:
        """
        获取机器人当前位置
        
        Returns:
            Tuple[float, float, float]: (x, y, yaw) 或 None
        """
        try:
            (trans, rot) = self.tf_listener.lookupTransform(
                self.map_frame, self.robot_frame, rospy.Time(0)
            )
            
            # 转换四元数到欧拉角
            euler = tf.transformations.euler_from_quaternion(rot)
            yaw = euler[2]
            
            return (trans[0], trans[1], yaw)
            
        except (tf.LookupException, tf.ConnectivityException, 
                tf.ExtrapolationException) as e:
            rospy.logdebug(f"Failed to get robot position: {e}")
            return None
    
    def shutdown(self):
        """关闭控制器"""
        rospy.loginfo("Shutting down navigation controller...")
        
        if self.is_navigating:
            self.cancel_navigation()
            
        # 确保机器人停止
        self._emergency_stop()
        
        rospy.loginfo("Navigation controller shutdown complete")
    
    def _create_goal(self, position: List[float]) -> MoveBaseGoal:
        """
        创建导航目标
        
        Args:
            position: [x, y, w] 坐标和朝向
            
        Returns:
            MoveBaseGoal: 导航目标
        """
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = self.map_frame
        goal.target_pose.header.stamp = rospy.Time.now()
        
        # 设置位置
        goal.target_pose.pose.position.x = position[0]
        goal.target_pose.pose.position.y = position[1]
        goal.target_pose.pose.position.z = 0.0
        
        # 设置朝向（从弧度转换为四元数）
        q = quaternion_from_euler(0, 0, position[2])
        goal.target_pose.pose.orientation.x = q[0]
        goal.target_pose.pose.orientation.y = q[1]
        goal.target_pose.pose.orientation.z = q[2]
        goal.target_pose.pose.orientation.w = q[3]
        
        return goal
    
    def _monitor_navigation(self):
        """监控导航状态的线程函数"""
        while self.is_navigating and not rospy.is_shutdown():
            state = self.move_base_client.get_state()
            
            if state == GoalStatus.SUCCEEDED:
                rospy.loginfo("Navigation goal reached successfully!")
                self.is_navigating = False
                break
            elif state == GoalStatus.ABORTED:
                rospy.logwarn("Navigation aborted!")
                self.is_navigating = False
                break
            elif state == GoalStatus.PREEMPTED:
                rospy.loginfo("Navigation preempted!")
                self.is_navigating = False
                break
            
            time.sleep(0.5)