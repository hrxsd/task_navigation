#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Voice Integrated Task System - 集成语音识别的任务系统
结合语音识别和键盘输入的智能任务调度系统
"""

import os
import sys
import json
import yaml
import rospy
import threading
import time
from typing import Dict, Optional
from queue import Queue, Empty

# 导入原有的任务系统组件
from core.task_manager import TaskManager

# 导入增强版音频接口
try:
    from ros_interface.enhanced_audio_interface import EnhancedAudioInterface
    ENHANCED_AUDIO_AVAILABLE = True
except ImportError:
    ENHANCED_AUDIO_AVAILABLE = False

# 导入语音识别组件
current_dir = os.path.dirname(os.path.abspath(__file__))
audio_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'audio')
sys.path.append(audio_dir)

from voice_remote_controller import VoiceRemoteController
from unitree_sdk2py.core.channel import ChannelFactoryInitialize


class InputSource:
    """输入源枚举"""
    KEYBOARD = "keyboard"
    VOICE = "voice"


class VoiceIntegratedTaskSystem:
    """集成语音识别的任务系统"""

    def __init__(self, config_path: str):
        """初始化系统"""
        self.config_path = config_path
        
        # 初始化ROS节点
        rospy.init_node('voice_integrated_task_system', anonymous=True)
        rospy.loginfo("Voice Integrated Task System Starting...")
        
        # 初始化任务管理器
        self.task_manager = TaskManager(config_path)
        
        # 输入处理
        self.input_queue = Queue()
        self.input_lock = threading.Lock()
        self.running = True
        
        # 语音识别组件
        self.voice_controller = None
        self.voice_thread = None
        self.voice_enabled = True
        
        # 键盘输入线程
        self.keyboard_thread = None
        
        rospy.loginfo("Voice Integrated Task System initialized successfully")
        
    def initialize_voice_system(self):
        """初始化语音识别系统"""
        try:
            rospy.loginfo("Initializing voice recognition system...")
            
            # 初始化通道工厂（如果还没初始化）
            try:
                ChannelFactoryInitialize(0)
            except Exception as e:
                rospy.logwarn(f"Channel factory may already be initialized: {e}")
            
            # 创建自定义语音控制器
            self.voice_controller = CustomVoiceController(self.input_queue)
            
            # 启动语音识别线程
            self.voice_thread = threading.Thread(target=self._voice_worker, daemon=True)
            self.voice_thread.start()
            
            rospy.loginfo("✅ Voice recognition system initialized")
            return True
            
        except Exception as e:
            rospy.logerr(f"❌ Failed to initialize voice system: {e}")
            self.voice_enabled = False
            return False
    
    def _voice_worker(self):
        """语音识别工作线程"""
        try:
            if self.voice_controller:
                self.voice_controller.run()
        except Exception as e:
            rospy.logerr(f"Voice worker error: {e}")
            self.voice_enabled = False
    
    def _keyboard_worker(self):
        """键盘输入工作线程"""
        while self.running:
            try:
                user_input = input().strip()
                if user_input:
                    with self.input_lock:
                        self.input_queue.put({
                            'source': InputSource.KEYBOARD,
                            'content': user_input,
                            'timestamp': time.time()
                        })
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                rospy.logerr(f"Keyboard input error: {e}")
    
    def run(self):
        """运行主循环"""
        print("\n" + "="*60)
        print("🎤 智能语音任务系统")
        print("="*60)
        print("📋 支持的输入方式:")
        print("1. 🎮 遥控器语音输入 - 按下L1键开始/结束录音")
        print("2. ⌨️  键盘文字输入 - 直接输入指令")
        print()
        print("🤖 支持的任务类型:")
        print("1. 教室巡检 - 检查学生行为")
        print("2. 车辆违停巡检 - 识别违停车辆")
        print("3. 快递派送 - 送达指定地点")
        print("4. 校园导引 - 引导到目标位置")
        print("5. 课堂助手 - 智能问答交互")
        print()
        print("🔧 特殊命令:")
        print("- 'status': 查看系统状态")
        print("- 'waypoints': 查看可用导航点")
        print("- 'cancel': 取消当前任务")
        print("- 'voice off/on': 关闭/开启语音识别")
        print("- 'quit/exit': 退出系统")
        print("="*60)
        
        # 初始化语音系统
        if self.voice_enabled:
            voice_init_success = self.initialize_voice_system()
            if voice_init_success:
                print("🎤 语音识别系统已启动 - 按下遥控器L1键开始语音输入")
            else:
                print("⚠️  语音识别系统启动失败，仅支持键盘输入")
        else:
            print("⌨️  仅键盘输入模式")
        
        print("\n💡 现在可以通过语音或键盘输入指令...")
        print("请输入您的指令: ", end='', flush=True)
        
        # 启动键盘输入线程
        self.keyboard_thread = threading.Thread(target=self._keyboard_worker, daemon=True)
        self.keyboard_thread.start()
        
        # 主循环处理输入
        while not rospy.is_shutdown() and self.running:
            try:
                # 从输入队列获取指令
                try:
                    input_data = self.input_queue.get(timeout=0.5)
                except Empty:
                    continue
                
                source = input_data['source']
                content = input_data['content']
                timestamp = input_data['timestamp']
                
                # 显示输入来源
                source_icon = "🎤" if source == InputSource.VOICE else "⌨️"
                print(f"\n{source_icon} [{source}] 收到指令: {content}")
                
                # 处理特殊命令
                if content.lower() in ['quit', 'exit', '退出']:
                    print("正在关闭任务系统...")
                    self.shutdown()
                    break
                
                if content.lower() == 'status':
                    self._print_status()
                    self._prompt_next_input()
                    continue
                
                if content.lower() == 'waypoints':
                    self._print_waypoints()
                    self._prompt_next_input()
                    continue
                
                if content.lower() == 'cancel':
                    self._cancel_current_task()
                    self._prompt_next_input()
                    continue
                
                if content.lower() == 'voice off':
                    self._toggle_voice(False)
                    self._prompt_next_input()
                    continue
                
                if content.lower() == 'voice on':
                    self._toggle_voice(True)
                    self._prompt_next_input()
                    continue
                
                if not content:
                    self._prompt_next_input()
                    continue
                
                # 处理任务请求
                print(f"🔄 处理指令: {content}")
                result = self.task_manager.process_user_input(content)
                
                # 显示结果
                self._print_result(result, source)
                
                # 如果任务开始执行，提供相应提示
                if result.get("success", False) and result.get("task_type") != "conflict":
                    if result.get("task_type") == "assistant":
                        print("💡 提示: 课堂助手已启动，可以通过语音或键盘继续对话，输入 'cancel' 取消任务")
                    else:
                        print("💡 提示: 任务执行期间可以输入 'cancel' 取消任务")
                
                # 如果是交互输入处理，不显示额外提示
                if result.get("task_type") != "interactive_input":
                    self._prompt_next_input()
                
            except KeyboardInterrupt:
                print("\n正在关闭任务系统...")
                self.shutdown()
                break
            except Exception as e:
                rospy.logerr(f"Error in main loop: {e}")
                print(f"❌ 发生错误: {e}")
                self._prompt_next_input()
    
    def _prompt_next_input(self):
        """提示下一次输入"""
        print("\n请输入您的指令: ", end='', flush=True)
    
    def _toggle_voice(self, enable: bool):
        """切换语音识别开关"""
        if enable and not self.voice_enabled:
            print("🎤 正在启动语音识别系统...")
            self.voice_enabled = True
            if self.initialize_voice_system():
                print("✅ 语音识别系统已启动")
            else:
                print("❌ 语音识别系统启动失败")
                self.voice_enabled = False
        elif not enable and self.voice_enabled:
            print("🔇 正在关闭语音识别系统...")
            self.voice_enabled = False
            if self.voice_controller:
                self.voice_controller.cleanup()
            print("✅ 语音识别系统已关闭")
        else:
            status = "已启动" if self.voice_enabled else "已关闭"
            print(f"ℹ️  语音识别系统当前状态: {status}")
    
    def _print_status(self):
        """打印系统状态"""
        status = self.task_manager.get_status()
        
        print("\n" + "-"*40)
        print("📊 系统状态")
        print("-"*40)
        print(f"当前任务: {status.get('current_task', '无')}")
        print(f"任务状态: {status.get('task_status', '空闲')}")
        print(f"可用任务: {len(status.get('available_tasks', []))}")
        print(f"导航点数量: {status.get('waypoints_count', 0)}")
        print(f"语音识别: {'启用' if self.voice_enabled else '禁用'}")
        print(f"输入队列: {self.input_queue.qsize()} 条待处理")
        print("-"*40)
        
    def _print_waypoints(self):
        """打印可用导航点"""
        waypoints = self.task_manager.get_available_waypoints()
        
        print("\n" + "-"*40)
        print("📍 可用导航点")
        print("-"*40)
        for i, waypoint in enumerate(waypoints, 1):
            print(f"{i}. {waypoint}")
        print("-"*40)
        
    def _cancel_current_task(self):
        """取消当前任务"""
        print("🛑 正在取消当前任务...")
        success = self.task_manager.stop_current_task()
        if success:
            print("✅ 当前任务已取消，机器人已停止移动")
            
            # 短暂等待确保所有系统都收到了停止信号
            time.sleep(0.5)
            
            # 显示当前状态
            status = self.task_manager.get_status()
            print(f"📊 系统状态: {status.get('task_status', '未知')}")
        else:
            print("ℹ️ 没有正在执行的任务")
            
    def _print_result(self, result: Dict, source: str):
        """打印任务执行结果"""
        source_icon = "🎤" if source == InputSource.VOICE else "⌨️"
        
        print("\n" + "="*50)
        print(f"📋 执行结果 [{source_icon} {source}]")
        print("="*50)
        
        success = result.get("success", False)
        message = result.get("message", "无消息")
        task_type = result.get("task_type", "unknown")
        
        status_emoji = "✅" if success else "❌"
        print(f"状态: {status_emoji} {'成功' if success else '失败'}")
        print(f"任务类型: {task_type}")
        print(f"消息: {message}")
        
        # 显示额外信息
        if "results" in result:
            results = result["results"]
            print(f"详细结果: 共处理{len(results)}项")
            
        if "destination" in result:
            print(f"目标地点: {result['destination']}")
            
        if "total_violations" in result:
            print(f"违停检测: {result['total_violations']}起")
            
        if "interaction_count" in result:
            print(f"交互次数: {result['interaction_count']}次")
            
        print("="*50)
    
    def shutdown(self):
        """关闭系统"""
        try:
            print("🔄 正在关闭系统组件...")
            
            self.running = False
            
            # 关闭语音识别系统
            if self.voice_controller:
                self.voice_controller.cleanup()
            
            # 关闭任务管理器
            if hasattr(self, 'task_manager'):
                self.task_manager.shutdown()
            
            # 关闭ROS节点
            rospy.signal_shutdown("User requested shutdown")
            
            print("✅ 系统已完全关闭")
            
        except Exception as e:
            rospy.logerr(f"Error during shutdown: {e}")


class CustomVoiceController(VoiceRemoteController):
    """自定义语音控制器，将识别结果发送到输入队列"""
    
    def __init__(self, input_queue: Queue):
        """初始化自定义语音控制器"""
        super().__init__()
        self.input_queue = input_queue
        self.system_running = True
    
    def on_message(self, ws, message):
        """处理语音识别结果并发送到输入队列"""
        try:
            msg = json.loads(message)
            code = msg.get("code", -1)
            sid = msg.get("sid", "")
            
            if code != 0:
                print(f"\n❌ 语音识别错误 sid:{sid} 错误信息: {msg.get('message')} 错误码: {code}")
            else:
                data = msg["data"]["result"]["ws"]
                result = ""
                for i in data:
                    for w in i["cw"]:
                        result += w["w"]
                
                if result.strip():
                    self.recognition_result += result
                    print(f"\n🎤 实时识别: {result}", end='', flush=True)
                    
                # 检查是否识别完成
                if msg["data"]["status"] == 2:
                    final_result = self.recognition_result.strip()
                    print(f"\n✅ 语音识别完成: {final_result}")
                    
                    # 将识别结果添加到输入队列
                    if final_result:
                        self.input_queue.put({
                            'source': InputSource.VOICE,
                            'content': final_result,
                            'timestamp': time.time()
                        })
                    
                    ws.close()
                    
        except Exception as e:
            print(f"\n❌ 处理语音识别结果时出错: {e}")
    
    def cleanup(self):
        """清理资源"""
        self.system_running = False
        super().cleanup()


def main():
    """主函数"""
    # 获取配置文件路径
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        # 默认配置文件路径
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '../config/task_config.yaml'
        )
    
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)
    
    try:
        # 创建并运行系统
        system = VoiceIntegratedTaskSystem(config_path)
        system.run()
    except rospy.ROSInterruptException:
        pass
    except Exception as e:
        print(f"❌ 系统启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
