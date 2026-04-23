#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强版音频接口模块
集成科大讯飞语音合成功能的音频接口
"""

import rospy
import os
import sys
import threading
import time
from typing import Optional

# 添加音频模块路径
current_dir = os.path.dirname(os.path.abspath(__file__))
audio_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), 'audio')
sys.path.append(audio_dir)

try:
    from xfyun_tts_client import XFYunTTSClient
    TTS_AVAILABLE = True
except ImportError as e:
    TTS_AVAILABLE = False
    print(f"Warning: XFYun TTS client not available: {e}")


class EnhancedAudioInterface:
    """增强版音频接口，集成科大讯飞TTS"""
    
    def __init__(self, 
                 speech_topic: str = "/audio/speech_recognition",
                 tts_topic: str = "/audio/tts",
                 use_tts: bool = True,
                 tts_config: Optional[dict] = None):
        """
        初始化增强版音频接口
        
        Args:
            speech_topic: 语音识别话题名称
            tts_topic: 语音合成话题名称
            use_tts: 是否使用真实TTS
            tts_config: TTS配置，包含app_id, api_key, api_secret等
        """
        self.speech_topic = speech_topic
        self.tts_topic = tts_topic
        self.use_tts = use_tts and TTS_AVAILABLE
        
        # TTS客户端
        self.tts_client = None
        self.tts_enabled = False
        self.tts_lock = threading.Lock()
        
        # 初始化TTS客户端
        if self.use_tts:
            self._init_tts_client(tts_config)
        
        # TODO: 当设备到达时，连接实际的ROS话题
        # self.speech_subscriber = rospy.Subscriber(speech_topic, String, self.speech_callback)
        # self.tts_publisher = rospy.Publisher(tts_topic, String, queue_size=10)
        
        mode = "TTS模式" if self.tts_enabled else "终端模式"
        rospy.loginfo(f"Enhanced Audio interface initialized ({mode})")
        
    def _init_tts_client(self, tts_config: Optional[dict]):
        """初始化TTS客户端"""
        try:
            # 默认配置
            default_config = {
                'app_id': '38b03603',
                'api_key': '52136d6271eb9e4fbc6e1da9f59ab33f',
                'api_secret': 'NzRmOGU4N2IyZWQ2ZGQ3NTJkOWU5ZTRl',
                'voice': 'x4_yezi',  # 叶子音色
                'sample_rate': 16000
            }
            
            # 合并用户配置
            if tts_config:
                default_config.update(tts_config)
            
            # 创建TTS客户端
            self.tts_client = XFYunTTSClient(
                app_id=default_config['app_id'],
                api_key=default_config['api_key'],
                api_secret=default_config['api_secret'],
                voice=default_config['voice'],
                sample_rate=default_config['sample_rate']
            )
            
            # 设置回调
            self.tts_client.on_synthesis_complete = self._on_tts_complete
            self.tts_client.on_synthesis_error = self._on_tts_error
            
            self.tts_enabled = True
            rospy.loginfo("✅ 科大讯飞TTS客户端初始化成功")
            
        except Exception as e:
            rospy.logerr(f"❌ TTS客户端初始化失败: {e}")
            self.tts_enabled = False
    
    def _on_tts_complete(self, wav_file: str):
        """TTS合成完成回调"""
        rospy.logdebug(f"TTS合成完成: {wav_file}")
    
    def _on_tts_error(self, error: str):
        """TTS错误回调"""
        rospy.logerr(f"TTS合成错误: {error}")
        
    def speak(self, text: str, priority: str = "normal", async_mode: bool = True):
        """
        语音输出
        
        Args:
            text: 要说的文本
            priority: 优先级 ("low", "normal", "high")
            async_mode: 是否异步模式
        """
        if not text.strip():
            return
        
        # 日志输出
        rospy.loginfo(f"TTS output: {text}")
        
        if self.tts_enabled:
            # 使用真实TTS
            if async_mode:
                # 异步TTS
                tts_thread = threading.Thread(
                    target=self._speak_async,
                    args=(text,),
                    daemon=True
                )
                tts_thread.start()
            else:
                # 同步TTS
                self._speak_sync(text)
        else:
            # 降级到终端输出
            print(f"\n[Robot 🤖]: {text}")
        
    def _speak_async(self, text: str):
        """异步语音输出"""
        try:
            with self.tts_lock:
                success = self.tts_client.synthesize_and_play(text)
                if not success:
                    rospy.logwarn(f"TTS failed, fallback to terminal: {text}")
                    print(f"\n[Robot 🤖]: {text}")
        except Exception as e:
            rospy.logerr(f"Async TTS error: {e}")
            print(f"\n[Robot 🤖]: {text}")
    
    def _speak_sync(self, text: str):
        """同步语音输出"""
        try:
            with self.tts_lock:
                success = self.tts_client.synthesize_and_play(text)
                if not success:
                    rospy.logwarn(f"TTS failed, fallback to terminal: {text}")
                    print(f"\n[Robot 🤖]: {text}")
        except Exception as e:
            rospy.logerr(f"Sync TTS error: {e}")
            print(f"\n[Robot 🤖]: {text}")
        
    def speak_with_emotion(self, text: str, emotion: str = "neutral", 
                          async_mode: bool = True):
        """
        带情感的语音输出
        
        Args:
            text: 要说的文本
            emotion: 情感类型 ("neutral", "happy", "sad", "excited", "warning")
            async_mode: 是否异步模式
        """
        # 添加情感标记到日志
        emotion_markers = {
            "happy": "😊",
            "excited": "🎉", 
            "warning": "⚠️",
            "sad": "😔",
            "neutral": "🤖"
        }
        
        marker = emotion_markers.get(emotion, "🤖")
        rospy.loginfo(f"TTS output ({emotion}): {text}")
        
        if self.tts_enabled:
            # 根据情感选择不同的语音参数
            emotion_voice_map = {
                "happy": "x4_yezi",      # 叶子 - 温暖
                "excited": "x4_yezi",    # 叶子 - 活泼
                "warning": "x4_xiaofeng", # 小峰 - 严肃
                "sad": "x4_xiaoshu",     # 小舒 - 温柔
                "neutral": "x4_yezi"     # 叶子 - 默认
            }
            
            # 设置语音类型
            if hasattr(self.tts_client, 'set_voice'):
                voice = emotion_voice_map.get(emotion, "x4_yezi")
                self.tts_client.set_voice(voice)
            
            # 执行TTS
            if async_mode:
                tts_thread = threading.Thread(
                    target=self._speak_async,
                    args=(text,),
                    daemon=True
                )
                tts_thread.start()
            else:
                self._speak_sync(text)
        else:
            # 降级到终端输出
            print(f"\n[Robot {marker}]: {text}")
        
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
        
    def play_sound_effect(self, sound_name: str):
        """
        播放音效
        
        Args:
            sound_name: 音效名称 ("beep", "success", "error", "warning")
        """
        sound_effects_text = {
            "beep": "哔",
            "success": "操作成功",
            "error": "发生错误", 
            "warning": "请注意",
            "navigation_start": "",
            "navigation_complete": ""
        }
        
        # 获取音效文本
        effect_text = sound_effects_text.get(sound_name, "提示音")
        
        if self.tts_enabled:
            # 使用TTS播放音效文本
            self.speak(effect_text, async_mode=True)
        else:
            # 降级到终端显示
            print(f"[音效]: {effect_text}")
        
        rospy.loginfo(f"Sound effect: {sound_name}")
        
    def announce_navigation(self, destination: str):
        """
        导航播报
        
        Args:
            destination: 目标地点
        """
        # self.speak_with_emotion(f"正在导航到{destination}。", "neutral")
        time.sleep(0.5)  # 短暂停顿
        self.play_sound_effect("navigation_start")
        
    def announce_arrival(self, destination: str):
        """
        到达播报
        
        Args:
            destination: 目标地点
        """
        self.play_sound_effect("navigation_complete")
        time.sleep(0.5)
        # self.speak_with_emotion(f"已到达{destination}。", "happy")
        
    def announce_detection(self, detection_type: str, details: str = ""):
        """
        检测结果播报
        
        Args:
            detection_type: 检测类型
            details: 详细信息
        """
        if detection_type == "vehicle_violation":
            self.speak_with_emotion(f"检测到违停车辆！{details}", "warning")
            time.sleep(0.3)
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
        self.speak(f"请确认：{action}", async_mode=False)
        
        try:
            response = input("确认? (y/n): ").strip().lower()
            confirmed = response in ['y', 'yes', '是', '确认']
            
            if confirmed:
                self.speak_with_emotion("已确认", "neutral", async_mode=False)
            else:
                self.speak_with_emotion("已取消", "neutral", async_mode=False)
                
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
        if self.tts_enabled and self.tts_client:
            return self.tts_client.is_busy()
        return False
        
    def stop_speaking(self):
        """停止当前语音输出"""
        if self.tts_enabled and self.tts_client:
            self.tts_client.stop_synthesis()
            rospy.loginfo("TTS stopped")
        else:
            print("[系统]: 停止语音输出")
            rospy.loginfo("TTS stopped (terminal mode)")
        
    def set_volume(self, volume: float):
        """
        设置音量
        
        Args:
            volume: 音量 (0.0-1.0)
        """
        # TODO: 实际实现 - 设置音量
        rospy.loginfo(f"Volume set to: {volume}")
        
    def set_voice(self, voice: str):
        """
        设置语音类型
        
        Args:
            voice: 语音类型 (x4_yezi, x4_xiaofeng, x4_xiaoshu等)
        """
        if self.tts_enabled and self.tts_client:
            self.tts_client.set_voice(voice)
            rospy.loginfo(f"Voice set to: {voice}")
        else:
            rospy.loginfo(f"Voice setting ignored (TTS not available): {voice}")
    
    def enable_tts(self, enable: bool = True):
        """
        启用/禁用TTS
        
        Args:
            enable: 是否启用TTS
        """
        if enable and TTS_AVAILABLE and self.tts_client:
            self.tts_enabled = True
            rospy.loginfo("✅ TTS enabled")
        else:
            self.tts_enabled = False
            rospy.loginfo("🔇 TTS disabled")
    
    def get_tts_status(self) -> dict:
        """
        获取TTS状态
        
        Returns:
            dict: TTS状态信息
        """
        return {
            "tts_available": TTS_AVAILABLE,
            "tts_enabled": self.tts_enabled,
            "tts_busy": self.is_speaking(),
            "client_initialized": self.tts_client is not None
        }
        
    def shutdown(self):
        """关闭音频接口"""
        rospy.loginfo("Shutting down enhanced audio interface")
        
        # 停止当前TTS
        if self.tts_enabled:
            self.stop_speaking()
        
        # TODO: 取消订阅和发布者


# 兼容性别名，保持向后兼容
AudioInterface = EnhancedAudioInterface
