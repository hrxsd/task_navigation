#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
课堂助手任务
与用户进行智能对话交互，配合手臂动作
"""

import rospy
import random
from typing import Dict, Optional

from tasks.base_task import BaseTask, TaskStatus
from llm.llm_client import LLMClient


class AssistantTask(BaseTask):
    """课堂助手任务"""
    
    def __init__(self, config: Dict, waypoint_engine=None):
        # 课堂助手不需要导航，所以waypoint_engine可以为None
        super().__init__(config, waypoint_engine)
        
        self.llm_client = LLMClient(
            api_key=config['llm']['api_key'],
            api_base=config['llm']['api_base'],
            model=config['llm']['model']
        )
        
        self.task_config = config['tasks']['assistant']
        self.interaction_timeout = self.task_config.get('interaction_timeout', 300)
        self.arm_gestures_enabled = self.task_config.get('arm_gestures', True)
        self.gesture_probability = self.task_config.get('gesture_probability', 0.3)
        
        # 任务管理器引用（用于获取交互输入）
        self.task_manager = None
        
        # 初始化手臂控制（如果启用）
        self.arm_controller = None
        if self.arm_gestures_enabled:
            self._init_arm_controller()
    
    def set_task_manager(self, task_manager):
        """设置任务管理器引用"""
        self.task_manager = task_manager
        rospy.loginfo("Task manager reference set for interactive input")
            
    def _init_arm_controller(self):
        """初始化手臂控制器"""
        try:
            # 导入G1手臂控制器
            import sys
            import os
            
            # 添加arm控制器路径
            arm_path = os.path.abspath(os.path.join(
                os.path.dirname(__file__), 
                '../../../g1_base_controller/arm'
            ))
            if arm_path not in sys.path:
                sys.path.append(arm_path)
            
            from arm_controller import ArmController
            self.arm_controller = ArmController()
            rospy.loginfo("Arm controller initialized for assistant task")
            
        except ImportError as e:
            rospy.logwarn(f"Arm controller module not found: {e}. Disabling arm gestures.")
            self.arm_gestures_enabled = False
        except Exception as e:
            rospy.logwarn(f"Failed to initialize arm controller: {e}. Disabling arm gestures.")
            self.arm_gestures_enabled = False
            
    def execute(self, user_input: str) -> Dict:
        """执行课堂助手任务"""
        try:
            self.status = TaskStatus.RUNNING
            rospy.loginfo("Starting assistant task")
            
            # 欢迎词
            self.audio.speak_with_emotion("您好！我是您的课堂助手，有什么可以帮助您的吗？", "happy")
            self._perform_startup_gesture()
            
            # 交互循环
            interaction_count = 0
            while self.status == TaskStatus.RUNNING and not rospy.is_shutdown():
                # 检查停止标志
                if self.stop_flag and self.stop_flag.is_set():
                    rospy.loginfo("Assistant task interrupted by stop flag")
                    break
                
                # 获取用户输入
                if interaction_count == 0:
                    # 第一次交互，如果用户输入只是唤醒词，则跳过，否则处理问题
                    # 清理输入文本，去除标点符号
                    cleaned_input = user_input.strip().rstrip('。！？.,!?')
                    if cleaned_input in ["课堂助手", "启动课堂助手", "我需要课堂助手", "助手", "智能助手"]:
                        # 只是唤醒词，等待用户提问
                        user_question = None
                    else:
                        # 包含了具体问题
                        user_question = user_input
                else:
                    # 后续交互从任务管理器获取
                    # self.audio.speak("请提出您的问题：")
                    user_question = self._get_interactive_input(self.interaction_timeout)
                    
                if not user_question:
                    if interaction_count == 0:
                        # 纯唤醒词，等待用户提问
                        # self.audio.speak("请提出您的问题：")
                        user_question = self._get_interactive_input(self.interaction_timeout)
                        if not user_question:
                            self.audio.speak("没有收到您的问题，课堂助手模式结束。")
                            break
                    else:
                        self.audio.speak("没有收到您的问题，课堂助手模式结束。")
                        break
                        
                # 检查退出指令
                if self._is_exit_command(user_question):
                    self.audio.speak_with_emotion("感谢您的使用，再见！", "happy")
                    self._perform_goodbye_gesture()
                    break
                    
                # 生成回答
                rospy.loginfo(f"Processing question: {user_question}")
                answer = self.llm_client.generate_assistant_response(user_question)
                
                # 输出回答
                self.audio.speak_with_emotion(answer, "neutral")
                
                # 随机手势
                if self.arm_gestures_enabled and random.random() < self.gesture_probability:
                    self._perform_random_gesture()
                
                interaction_count += 1
                
                # 检查是否达到最大交互次数（防止无限循环）
                if interaction_count >= 10:
                    self.audio.speak("本次课堂助手会话已达到最大交互次数，感谢您的使用！")
                    break
            
            self.status = TaskStatus.COMPLETED
            return {
                "success": True,
                "message": f"课堂助手任务完成，共进行了{interaction_count}次交互",
                "task_type": "assistant",
                "interaction_count": interaction_count
            }
            
        except Exception as e:
            rospy.logerr(f"Error in assistant task: {e}")
            self.status = TaskStatus.FAILED
            return {
                "success": False,
                "message": f"课堂助手任务失败: {e}",
                "task_type": "assistant"
            }
            
    def _is_exit_command(self, user_input: str) -> bool:
        """检查是否为退出指令"""
        if not user_input:
            return False
        
        # 清理输入文本，去除标点符号
        cleaned_input = user_input.strip().rstrip('。！？.,!?').lower()
        exit_commands = ["退出", "结束", "再见", "谢谢", "exit", "quit", "bye", "停止", "取消"]
        
        # 检查完全匹配
        if cleaned_input in exit_commands:
            return True
        
        # 检查包含关系（用于"谢谢你"、"再见了"等变体）
        return any(cmd in cleaned_input for cmd in exit_commands)
        
    def _perform_startup_gesture(self):
        """执行启动手势 (face wave, ID=6)"""
        if self.arm_controller:
            try:
                rospy.loginfo("Performing startup gesture: face_wave (ID: 6)")
                success = self.arm_controller.perform_startup_gesture()
                if success:
                    rospy.loginfo("Performed startup gesture")
                else:
                    rospy.logwarn("Failed to perform startup gesture")
            except Exception as e:
                rospy.logwarn(f"Failed to perform startup gesture: {e}")
                
    def _perform_goodbye_gesture(self):
        """执行告别手势 (left kiss, ID=7)"""
        if self.arm_controller:
            try:
                rospy.loginfo("Performing goodbye gesture: left_kiss (ID: 7)")
                success = self.arm_controller.perform_goodbye_gesture()
                if success:
                    rospy.loginfo("Performed goodbye gesture")
                else:
                    rospy.logwarn("Failed to perform goodbye gesture")
            except Exception as e:
                rospy.logwarn(f"Failed to perform goodbye gesture: {e}")
    
    def _perform_random_gesture(self):
        """执行随机手势"""
        if self.arm_controller:
            try:
                # 随机选择一个手势
                gestures = ["nod", "wave", "think"]  # 可用的手势列表
                gesture = random.choice(gestures)
                rospy.loginfo(f"Performing random gesture: {gesture}")
                success = self.arm_controller.perform_gesture(gesture)
                if success:
                    rospy.loginfo(f"Performed random gesture: {gesture}")
                else:
                    rospy.logwarn(f"Failed to perform random gesture: {gesture}")
            except Exception as e:
                rospy.logwarn(f"Failed to perform random gesture: {e}")
                
    def stop(self):
        """停止课堂助手任务"""
        super().stop()
        self.audio.speak("课堂助手任务已停止。")
        
        # 执行告别手势
        if self.arm_controller:
            try:
                rospy.loginfo("Performing gesture: release (ID: 0)")
                success = self.arm_controller.perform_gesture("release")
                if success:
                    rospy.loginfo("Performed release gesture")
                else:
                    rospy.logwarn("Failed to perform release gesture")
            except Exception as e:
                rospy.logwarn(f"Failed to release arm: {e}")
                
    def shutdown(self):
        """关闭课堂助手任务"""
        super().shutdown()
        
        if self.arm_controller:
            try:
                self.arm_controller.shutdown()
            except Exception as e:
                rospy.logwarn(f"Failed to shutdown arm controller: {e}") 

    def _get_interactive_input(self, timeout: float = 30.0) -> Optional[str]:
        """获取交互式输入"""
        if self.task_manager:
            # 从任务管理器获取交互输入
            return self.task_manager.get_interactive_input(timeout)
        else:
            # 降级为音频接口（备用方案）
            rospy.logwarn("No task manager reference, falling back to audio interface")
            return self.audio.get_speech_input(timeout) 