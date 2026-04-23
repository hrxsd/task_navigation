#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
TTS集成功能测试程序
测试增强版音频接口的TTS功能
"""

import sys
import os
import time
import tempfile

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from ros_interface.enhanced_audio_interface import EnhancedAudioInterface
    ENHANCED_AUDIO_AVAILABLE = True
except ImportError as e:
    ENHANCED_AUDIO_AVAILABLE = False
    print(f"❌ 增强版音频接口不可用: {e}")

# 模拟rospy
class MockRospy:
    @staticmethod
    def loginfo(msg):
        print(f"[INFO] {msg}")
    
    @staticmethod
    def logerr(msg):
        print(f"[ERROR] {msg}")
    
    @staticmethod
    def logwarn(msg):
        print(f"[WARN] {msg}")
    
    @staticmethod
    def logdebug(msg):
        print(f"[DEBUG] {msg}")

# 替换rospy模块
sys.modules['rospy'] = MockRospy()


def test_enhanced_audio_interface():
    """测试增强版音频接口"""
    print("🧪 测试增强版音频接口")
    print("=" * 50)
    
    if not ENHANCED_AUDIO_AVAILABLE:
        print("❌ 增强版音频接口不可用，跳过测试")
        return False
    
    # 创建音频接口实例
    print("🔧 初始化增强版音频接口...")
    
    tts_config = {
        'app_id': '38b03603',
        'api_key': '52136d6271eb9e4fbc6e1da9f59ab33f',
        'api_secret': 'NzRmOGU4N2IyZWQ2ZGQ3NTJkOWU5ZTRl',
        'voice': 'x4_yezi',
        'sample_rate': 16000
    }
    
    try:
        audio = EnhancedAudioInterface(
            use_tts=True,
            tts_config=tts_config
        )
        
        print("✅ 音频接口初始化成功")
        print(f"📊 TTS状态: {audio.get_tts_status()}")
        
    except Exception as e:
        print(f"❌ 音频接口初始化失败: {e}")
        return False
    
    return audio


def test_basic_speak_functions(audio):
    """测试基础语音输出功能"""
    print("\n🧪 测试基础语音输出功能")
    print("=" * 40)
    
    # 测试基础speak方法
    print("📝 测试 speak() 方法...")
    audio.speak("你好，我是Go2机器人。", async_mode=False)
    time.sleep(1)
    
    # 测试带情感的speak方法
    print("📝 测试 speak_with_emotion() 方法...")
    
    emotions = {
        "happy": "任务执行成功！",
        "warning": "检测到异常情况！", 
        "neutral": "正在执行导航任务。",
        "excited": "发现了有趣的事物！"
    }
    
    for emotion, text in emotions.items():
        print(f"🎭 测试情感: {emotion}")
        audio.speak_with_emotion(text, emotion, async_mode=False)
        time.sleep(1)
    
    print("✅ 基础语音输出测试完成")


def test_sound_effects(audio):
    """测试音效功能"""
    print("\n🧪 测试音效功能")
    print("=" * 40)
    
    sound_effects = [
        "beep",
        "success", 
        "error",
        "warning",
        "navigation_start",
        "navigation_complete"
    ]
    
    for effect in sound_effects:
        print(f"🔊 播放音效: {effect}")
        audio.play_sound_effect(effect)
        time.sleep(2)
    
    print("✅ 音效测试完成")


def test_announcement_functions(audio):
    """测试播报功能"""
    print("\n🧪 测试播报功能")
    print("=" * 40)
    
    # 测试导航播报
    print("📍 测试导航播报...")
    audio.announce_navigation("图书馆")
    time.sleep(3)
    
    # 测试到达播报
    print("🏁 测试到达播报...")
    audio.announce_arrival("图书馆")
    time.sleep(3)
    
    # 测试检测播报
    print("🔍 测试检测播报...")
    audio.announce_detection("vehicle_violation", "车牌号: 京A12345")
    time.sleep(3)
    
    audio.announce_detection("student_behavior", "学生在睡觉")
    time.sleep(3)
    
    print("✅ 播报功能测试完成")


def test_voice_settings(audio):
    """测试语音设置功能"""
    print("\n🧪 测试语音设置功能")
    print("=" * 40)
    
    # 测试不同语音类型
    voices = ["x4_yezi", "x4_xiaofeng", "x4_xiaoshu"]
    test_text = "这是语音类型测试。"
    
    for voice in voices:
        print(f"🎵 设置语音类型: {voice}")
        audio.set_voice(voice)
        audio.speak(test_text, async_mode=False)
        time.sleep(2)
    
    # 测试音量设置
    print("🔊 测试音量设置...")
    audio.set_volume(0.8)
    
    print("✅ 语音设置测试完成")


def test_tts_control(audio):
    """测试TTS控制功能"""
    print("\n🧪 测试TTS控制功能")
    print("=" * 40)
    
    # 测试状态检查
    print("📊 测试状态检查...")
    status = audio.get_tts_status()
    print(f"TTS状态: {status}")
    
    # 测试TTS开关
    print("🔇 测试TTS关闭...")
    audio.enable_tts(False)
    audio.speak("这条消息应该只在终端显示。")
    time.sleep(1)
    
    print("🔊 测试TTS开启...")
    audio.enable_tts(True)
    audio.speak("TTS已重新启用。", async_mode=False)
    time.sleep(1)
    
    # 测试is_speaking
    print("🎵 测试说话状态检查...")
    audio.speak("这是一个较长的测试文本，用于检查说话状态。", async_mode=True)
    
    # 检查说话状态
    start_time = time.time()
    while time.time() - start_time < 5:
        if audio.is_speaking():
            print("🎤 正在说话...")
            time.sleep(0.5)
        else:
            print("🤐 没有在说话")
            break
    
    print("✅ TTS控制测试完成")


def test_error_scenarios(audio):
    """测试错误场景"""
    print("\n🧪 测试错误场景")
    print("=" * 40)
    
    # 测试空文本
    print("📝 测试空文本...")
    audio.speak("")
    audio.speak("   ")  # 只有空格
    
    # 测试None文本
    print("📝 测试None文本...")
    try:
        audio.speak(None)
    except:
        print("✅ None文本处理正常")
    
    # 测试停止功能
    print("🛑 测试停止功能...")
    audio.speak("这是一个很长的测试文本，应该会被中途停止。这个文本故意写得很长，以便测试停止功能。")
    time.sleep(1)
    audio.stop_speaking()
    time.sleep(1)
    
    print("✅ 错误场景测试完成")


def interactive_test(audio):
    """交互式测试"""
    print("\n🧪 交互式测试")
    print("=" * 40)
    print("请输入要合成的文本，输入 'quit' 退出")
    print("特殊命令:")
    print("- 'status': 查看TTS状态")
    print("- 'stop': 停止当前TTS") 
    print("- 'voice <类型>': 设置语音类型")
    print("- 'emotion <情感> <文本>': 带情感说话")
    
    while True:
        try:
            user_input = input("\n请输入: ").strip()
            
            if user_input.lower() in ['quit', 'exit', '退出']:
                break
            
            if user_input.lower() == 'status':
                status = audio.get_tts_status()
                print(f"📊 TTS状态: {status}")
                continue
            
            if user_input.lower() == 'stop':
                audio.stop_speaking()
                print("🛑 已停止TTS")
                continue
            
            if user_input.lower().startswith('voice '):
                voice = user_input[6:].strip()
                audio.set_voice(voice)
                print(f"🎵 语音类型已设置为: {voice}")
                continue
            
            if user_input.lower().startswith('emotion '):
                parts = user_input[8:].split(' ', 1)
                if len(parts) >= 2:
                    emotion, text = parts[0], parts[1]
                    audio.speak_with_emotion(text, emotion, async_mode=False)
                else:
                    print("格式: emotion <情感> <文本>")
                continue
            
            if not user_input:
                continue
            
            print(f"🎵 合成语音: {user_input}")
            audio.speak(user_input, async_mode=False)
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    print("交互式测试结束")


def main():
    """主函数"""
    print("🎵 TTS集成功能测试程序")
    print("=" * 50)
    
    # 初始化音频接口
    audio = test_enhanced_audio_interface()
    if not audio:
        return 1
    
    try:
        print("\n请选择测试类型:")
        print("1. 基础语音输出测试")
        print("2. 音效功能测试")
        print("3. 播报功能测试") 
        print("4. 语音设置测试")
        print("5. TTS控制测试")
        print("6. 错误场景测试")
        print("7. 交互式测试")
        print("8. 全部测试")
        
        choice = input("\n请输入选择 (1-8): ").strip()
        
        if choice == '1':
            test_basic_speak_functions(audio)
        elif choice == '2':
            test_sound_effects(audio)
        elif choice == '3':
            test_announcement_functions(audio)
        elif choice == '4':
            test_voice_settings(audio)
        elif choice == '5':
            test_tts_control(audio)
        elif choice == '6':
            test_error_scenarios(audio)
        elif choice == '7':
            interactive_test(audio)
        elif choice == '8':
            test_basic_speak_functions(audio)
            test_sound_effects(audio)
            test_announcement_functions(audio)
            test_voice_settings(audio)
            test_tts_control(audio)
            test_error_scenarios(audio)
        else:
            print("无效选择")
            return 1
        
        print("\n🎉 测试完成!")
        
        # 清理
        if hasattr(audio, 'shutdown'):
            audio.shutdown()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n测试被中断")
        return 0
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
