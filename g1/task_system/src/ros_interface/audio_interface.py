#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
音频接口模块
基于ROS话题进行语音输入输出（当前版本使用终端模拟）
"""

import rospy
from typing import Optional


class AudioInterface:
    """基于ROS话题的音频接口"""
    
    def __init__(self, 
                 speech_topic: str = "/audio/speech_recognition",
                 tts_topic: str = "/audio/tts"):
        """
        初始化音频接口
        
        Args:
            speech_topic: 语音识别话题名称
            tts_topic: 语音合成话题名称
        """
        self.speech_topic = speech_topic
        self.tts_topic = tts_topic
        
        # TODO: 当设备到达时，连接实际的ROS话题
        # self.speech_subscriber = rospy.Subscriber(speech_topic, String, self.speech_callback)
        # self.tts_publisher = rospy.Publisher(tts_topic, String, queue_size=10)
        
        rospy.loginfo("Audio interface initialized (terminal mode)")
        
    def speak(self, text: str, priority: str = "normal"):
        """
        语音输出
        
        Args:
            text: 要说的文本
            priority: 优先级 ("low", "normal", "high")
        """
        # 当前版本：打印到终端
        print(f"\n[Robot 🤖]: {text}")
        
        # TODO: 实际实现 - 发布到TTS话题
        # tts_msg = String()
        # tts_msg.data = text
        # self.tts_publisher.publish(tts_msg)
        
        rospy.loginfo(f"TTS output: {text}")
        
    def speak_with_emotion(self, text: str, emotion: str = "neutral"):
        """
        带情感的语音输出
        
        Args:
            text: 要说的文本
            emotion: 情感类型 ("neutral", "happy", "sad", "excited", "warning")
        """
        # 添加情感标记
        emotion_markers = {
            "happy": "😊",
            "excited": "🎉", 
            "warning": "⚠️",
            "sad": "😔",
            "neutral": "🤖"
        }
        
        marker = emotion_markers.get(emotion, "🤖")
        print(f"\n[Robot {marker}]: {text}")
        
        rospy.loginfo(f"TTS output ({emotion}): {text}")
        
    def get_speech_input(self, timeout: float = 30.0) -> Optional[str]:
        """
        获取语音输入
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            str: 识别的语音文本，如果失败则返回None
        """
        # 当前版本：从终端获取输入
        try:
            print(f"\n[等待语音输入] (或直接输入文字，{timeout}秒超时)")
            user_input = input("请输入: ").strip()
            
            if user_input:
                rospy.loginfo(f"Speech input received: {user_input}")
                return user_input
            else:
                return None
                
        except Exception as e:
            rospy.logerr(f"Error getting speech input: {e}")
            return None
            
        # TODO: 实际实现 - 从语音识别话题获取
        # 等待语音识别结果，带超时
        
    def play_sound_effect(self, sound_name: str):
        """
        播放音效
        
        Args:
            sound_name: 音效名称 ("beep", "success", "error", "warning")
        """
        sound_effects = {
            "beep": "哔~",
            "success": "✅ 成功提示音",
            "error": "❌ 错误提示音", 
            "warning": "⚠️ 警告提示音",
            "navigation_start": "🎯 开始导航提示音",
            "navigation_complete": "🏁 导航完成提示音"
        }
        
        effect = sound_effects.get(sound_name, "🎵 音效")
        print(f"[音效]: {effect}")
        
        rospy.loginfo(f"Sound effect: {sound_name}")
        
    def announce_navigation(self, destination: str):
        """
        导航播报
        
        Args:
            destination: 目标地点
        """
        self.speak_with_emotion(f"正在导航到{destination}。", "neutral")
        self.play_sound_effect("navigation_start")
        
    def announce_arrival(self, destination: str):
        """
        到达播报
        
        Args:
            destination: 目标地点
        """
        self.play_sound_effect("navigation_complete")
        
    def announce_detection(self, detection_type: str, details: str = ""):
        """
        检测结果播报
        
        Args:
            detection_type: 检测类型
            details: 详细信息
        """
        if detection_type == "vehicle_violation":
            self.speak_with_emotion(f"检测到违停车辆！{details}", "warning")
            self.play_sound_effect("warning")
        elif detection_type == "student_behavior":
            self.speak_with_emotion(f"检测到学生行为异常：{details}", "warning")
        else:
            self.speak_with_emotion(f"检测结果：{details}", "neutral")
            
    def confirm_action(self, action: str) -> bool:
        """
        确认操作
        
        Args:
            action: 要确认的操作
            
        Returns:
            bool: 用户是否确认
        """
        self.speak(f"请确认：{action} (yes/no)")
        
        try:
            response = input("确认? (y/n): ").strip().lower()
            confirmed = response in ['y', 'yes', '是', '确认']
            
            if confirmed:
                self.speak_with_emotion("已确认", "neutral")
            else:
                self.speak_with_emotion("已取消", "neutral")
                
            return confirmed
            
        except Exception as e:
            rospy.logerr(f"Error in confirmation: {e}")
            return False
            
    def speech_callback(self, msg):
        """
        语音识别话题回调函数（将来实现）
        
        Args:
            msg: 语音识别消息
        """
        # TODO: 处理语音识别结果
        pass
        
    def is_speaking(self) -> bool:
        """
        检查是否正在说话
        
        Returns:
            bool: 是否正在说话
        """
        # TODO: 实际实现 - 检查TTS状态
        return False
        
    def stop_speaking(self):
        """停止当前语音输出"""
        # TODO: 实际实现 - 停止TTS
        print("[系统]: 停止语音输出")
        rospy.loginfo("TTS stopped")
        
    def set_volume(self, volume: float):
        """
        设置音量
        
        Args:
            volume: 音量 (0.0-1.0)
        """
        # TODO: 实际实现 - 设置音量
        rospy.loginfo(f"Volume set to: {volume}")
        
    def shutdown(self):
        """关闭音频接口"""
        rospy.loginfo("Shutting down audio interface")
        # TODO: 取消订阅和发布者 