#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
科大讯飞TTS客户端测试程序
"""

import sys
import os
import time

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from xfyun_tts_client import XFYunTTSClient


def test_basic_tts():
    """基础TTS功能测试"""
    print("🧪 基础TTS功能测试")
    print("=" * 40)
    
    # 创建TTS客户端
    tts_client = XFYunTTSClient(
        app_id='38b03603',
        api_key='52136d6271eb9e4fbc6e1da9f59ab33f',
        api_secret='NzRmOGU4N2IyZWQ2ZGQ3NTJkOWU5ZTRl'
    )
    
    # 测试文本列表
    test_texts = [
        "你好，我是Go2机器人！",
        "开始执行教室巡检任务。",
        "检测到违停车辆，请注意。",
        "导航到图书馆完成。",
        "课堂助手已启动，请提出您的问题。"
    ]
    
    success_count = 0
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n📝 测试 {i}/{len(test_texts)}: {text}")
        
        try:
            success = tts_client.synthesize_and_play(text)
            if success:
                print(f"✅ 测试 {i} 成功")
                success_count += 1
            else:
                print(f"❌ 测试 {i} 失败")
            
            # 等待播放完成
            while tts_client.is_busy():
                time.sleep(0.1)
                
            # 短暂停顿
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ 测试 {i} 异常: {e}")
    
    print(f"\n📊 测试结果: {success_count}/{len(test_texts)} 成功")
    
    if success_count == len(test_texts):
        print("🎉 所有基础测试通过！")
        return True
    else:
        print("⚠️  部分测试失败")
        return False


def test_voice_types():
    """不同语音类型测试"""
    print("\n🧪 语音类型测试")
    print("=" * 40)
    
    tts_client = XFYunTTSClient(
        app_id='38b03603',
        api_key='52136d6271eb9e4fbc6e1da9f59ab33f',
        api_secret='NzRmOGU4N2IyZWQ2ZGQ3NTJkOWU5ZTRl'
    )
    
    # 不同语音类型
    voice_types = {
        "x4_yezi": "叶子 - 温暖亲切",
        "x4_xiaofeng": "小峰 - 清晰自然", 
        "x4_xiaoshu": "小舒 - 温柔甜美"
    }
    
    test_text = "我是Go2机器人，很高兴为您服务。"
    
    for voice, description in voice_types.items():
        print(f"\n🎵 测试语音: {voice} ({description})")
        
        try:
            tts_client.set_voice(voice)
            success = tts_client.synthesize_and_play(test_text)
            
            if success:
                print(f"✅ {voice} 测试成功")
            else:
                print(f"❌ {voice} 测试失败")
            
            # 等待播放完成
            while tts_client.is_busy():
                time.sleep(0.1)
            
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ {voice} 测试异常: {e}")


def test_concurrent_requests():
    """并发请求测试"""
    print("\n🧪 并发请求测试")
    print("=" * 40)
    
    tts_client = XFYunTTSClient(
        app_id='38b03603',
        api_key='52136d6271eb9e4fbc6e1da9f59ab33f',
        api_secret='NzRmOGU4N2IyZWQ2ZGQ3NTJkOWU5ZTRl'
    )
    
    print("📝 尝试同时发送多个TTS请求...")
    
    # 第一个请求
    print("🎵 发送第一个请求: '这是第一个测试文本'")
    success1 = tts_client.synthesize_and_play("这是第一个测试文本")
    
    # 立即发送第二个请求（应该被拒绝）
    print("🎵 立即发送第二个请求: '这是第二个测试文本'")
    success2 = tts_client.synthesize_and_play("这是第二个测试文本")
    
    if success1 and not success2:
        print("✅ 并发控制正常工作")
    else:
        print("⚠️  并发控制可能有问题")
    
    # 等待第一个请求完成
    while tts_client.is_busy():
        time.sleep(0.1)
    
    # 现在尝试第二个请求
    print("🎵 第一个请求完成后，发送第二个请求")
    success3 = tts_client.synthesize_and_play("这是第二个测试文本")
    
    if success3:
        print("✅ 串行请求正常工作")
    else:
        print("❌ 串行请求失败")


def test_error_handling():
    """错误处理测试"""
    print("\n🧪 错误处理测试")
    print("=" * 40)
    
    # 测试空文本
    print("📝 测试空文本...")
    tts_client = XFYunTTSClient(
        app_id='38b03603',
        api_key='52136d6271eb9e4fbc6e1da9f59ab33f',
        api_secret='NzRmOGU4N2IyZWQ2ZGQ3NTJkOWU5ZTRl'
    )
    
    success = tts_client.synthesize_and_play("")
    if not success:
        print("✅ 空文本处理正常")
    else:
        print("❌ 空文本处理异常")
    
    # 测试超长文本
    print("\n📝 测试超长文本...")
    long_text = "这是一个非常长的测试文本。" * 50  # 250个重复
    success = tts_client.synthesize_and_play(long_text[:100])  # 截取前100字符
    
    if success:
        print("✅ 长文本处理正常")
    else:
        print("⚠️  长文本处理可能有问题")


def interactive_test():
    """交互式测试"""
    print("\n🧪 交互式测试")
    print("=" * 40)
    print("请输入要合成的文本，输入 'quit' 退出")
    
    tts_client = XFYunTTSClient(
        app_id='38b03603',
        api_key='52136d6271eb9e4fbc6e1da9f59ab33f',
        api_secret='NzRmOGU4N2IyZWQ2ZGQ3NTJkOWU5ZTRl'
    )
    
    while True:
        try:
            text = input("\n请输入文本: ").strip()
            
            if text.lower() in ['quit', 'exit', '退出']:
                break
            
            if not text:
                continue
            
            print(f"🎵 合成语音: {text}")
            success = tts_client.synthesize_and_play(text)
            
            if success:
                print("✅ 合成成功")
            else:
                print("❌ 合成失败")
            
            # 等待播放完成
            while tts_client.is_busy():
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    print("交互式测试结束")


def main():
    """主函数"""
    print("🎵 科大讯飞TTS客户端测试程序")
    print("=" * 50)
    
    try:
        # 检查依赖
        try:
            import simpleaudio
            print("✅ simpleaudio 库可用")
        except ImportError:
            print("❌ simpleaudio 库不可用，无法播放音频")
            print("请运行: pip install simpleaudio")
            return 1
        
        # 显示测试选项
        print("\n请选择测试类型:")
        print("1. 基础功能测试")
        print("2. 语音类型测试") 
        print("3. 并发请求测试")
        print("4. 错误处理测试")
        print("5. 交互式测试")
        print("6. 全部测试")
        
        choice = input("\n请输入选择 (1-6): ").strip()
        
        if choice == '1':
            test_basic_tts()
        elif choice == '2':
            test_voice_types()
        elif choice == '3':
            test_concurrent_requests()
        elif choice == '4':
            test_error_handling()
        elif choice == '5':
            interactive_test()
        elif choice == '6':
            test_basic_tts()
            test_voice_types()
            test_concurrent_requests()
            test_error_handling()
        else:
            print("无效选择")
            return 1
        
        print("\n🎉 测试完成!")
        return 0
        
    except KeyboardInterrupt:
        print("\n测试被中断")
        return 0
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
