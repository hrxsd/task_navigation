#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
结合遥控器控制的语音识别程序
按下L1键开始录音，再次按下L1键结束录音并进行语音识别
"""

import websocket
import hashlib
import base64
import hmac
import json
import time
import ssl
import _thread as thread
import pyaudio
import sys
import os
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import threading

# 添加路径以导入遥控器模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(os.path.join(parent_dir, 'go2_base_controller'))

from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_ as LowStateGo2
from loco.remote_controller import RemoteController, KeyMap

# 语音识别状态常量
STATUS_FIRST_FRAME = 0
STATUS_CONTINUE_FRAME = 1
STATUS_LAST_FRAME = 2

class Ws_Param(object):
    def __init__(self, APPID, APIKey, APISecret):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {
            "domain": "iat",
            "language": "zh_cn",
            "accent": "mandarin",
            "vinfo": 1,
            "vad_eos": 10000
        }

    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"

        signature_sha = hmac.new(self.APISecret.encode('utf-8'),
                                 signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode('utf-8')

        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

        v = {"authorization": authorization, "date": date, "host": "ws-api.xfyun.cn"}
        return url + '?' + urlencode(v)


class VoiceRemoteController:
    def __init__(self):
        # 初始化遥控器
        self.remote_controller = RemoteController()
        
        # 录音状态
        self.is_recording = False
        self.recording_lock = threading.Lock()
        self.l1_pressed = False
        self.l1_last_state = False
        
        # 音频参数
        self.CHUNK = 1280  # 40ms 对应 16000*0.04*2=1280字节
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        
        # 音频流
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.audio_buffer = []
        
        # WebSocket相关
        self.ws = None
        self.ws_param = Ws_Param(
            APPID='fcf81c07',
            APIKey='c9c5d895c29b63ebc79a4aea4ec0a46e',
            APISecret='NmU4OWE4N2IyYTUyYjQ2MDQ5NzExZjRh'
        )
        
        # 识别结果
        self.recognition_result = ""
        
        # 初始化状态订阅
        self.low_state = unitree_go_msg_dds__LowState_()
        self.lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowStateGo2)
        self.lowstate_subscriber.Init(self.LowStateHandler, 10)
        
        print("🎮 语音遥控器已初始化")
        print("📝 操作说明：按下L1键开始录音，再次按下L1键结束录音并进行语音识别")
        print("🛑 按 Ctrl+C 退出程序")

    def LowStateHandler(self, msg: LowStateGo2):
        """处理来自机器人的低级状态消息"""
        try:
            self.remote_controller.set(msg.wireless_remote)
            
            # 检测L1键的状态变化
            current_l1_state = self.remote_controller.button[KeyMap.L1]
            
            # 检测按键从未按下到按下的状态变化（边沿触发）
            if current_l1_state == 1 and self.l1_last_state == 0:
                self.handle_l1_press()
            
            self.l1_last_state = current_l1_state
            
        except Exception as e:
            print(f"❌ 解析遥控器数据时出错: {e}")

    def handle_l1_press(self):
        """处理L1键按下事件"""
        with self.recording_lock:
            if not self.is_recording:
                self.start_recording()
            else:
                self.stop_recording()

    def start_recording(self):
        """开始录音"""
        try:
            print("🎤 开始录音...")
            self.is_recording = True
            self.audio_buffer = []
            
            # 初始化音频流
            self.stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            # 启动录音线程
            self.recording_thread = threading.Thread(target=self.record_audio)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
        except Exception as e:
            print(f"❌ 开始录音失败: {e}")
            self.is_recording = False

    def record_audio(self):
        """录音线程"""
        try:
            while self.is_recording:
                if self.stream:
                    data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                    self.audio_buffer.append(data)
                time.sleep(0.01)  # 防止CPU占用过高
        except Exception as e:
            print(f"❌ 录音过程中出错: {e}")

    def stop_recording(self):
        """停止录音并进行语音识别"""
        try:
            print("🛑 停止录音，开始语音识别...")
            self.is_recording = False
            
            # 等待录音线程结束
            if hasattr(self, 'recording_thread'):
                self.recording_thread.join(timeout=1.0)
            
            # 关闭音频流
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            
            # 检查是否有录音数据
            if not self.audio_buffer:
                print("⚠️  没有录音数据")
                return
            
            # 开始语音识别
            self.start_speech_recognition()
            
        except Exception as e:
            print(f"❌ 停止录音失败: {e}")

    def start_speech_recognition(self):
        """开始语音识别"""
        try:
            print("🔄 连接语音识别服务...")
            self.recognition_result = ""
            
            # 创建WebSocket连接
            websocket.enableTrace(False)
            wsUrl = self.ws_param.create_url()
            self.ws = websocket.WebSocketApp(
                wsUrl,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            # 启动WebSocket连接
            ws_thread = threading.Thread(target=self.ws.run_forever, kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}})
            ws_thread.daemon = True
            ws_thread.start()
            
        except Exception as e:
            print(f"❌ 语音识别启动失败: {e}")

    def on_message(self, ws, message):
        """处理语音识别结果"""
        try:
            msg = json.loads(message)
            code = msg.get("code", -1)
            sid = msg.get("sid", "")
            
            if code != 0:
                print(f"❌ 识别错误 sid:{sid} 错误信息: {msg.get('message')} 错误码: {code}")
            else:
                data = msg["data"]["result"]["ws"]
                result = ""
                for i in data:
                    for w in i["cw"]:
                        result += w["w"]
                
                if result.strip():
                    self.recognition_result += result
                    print(f"👂 识别结果: {result}")
                    
                # 检查是否识别完成
                if msg["data"]["status"] == 2:
                    print(f"✅ 最终识别结果: {self.recognition_result}")
                    ws.close()
                    
        except Exception as e:
            print(f"❌ 处理识别结果时出错: {e}")

    def on_error(self, ws, error):
        """WebSocket错误处理"""
        print(f"❌ WebSocket错误: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket关闭处理"""
        print("🔌 语音识别连接已关闭")

    def on_open(self, ws):
        """WebSocket连接建立后发送音频数据"""
        def send_audio():
            try:
                print(f"📤 发送音频数据，共 {len(self.audio_buffer)} 个音频块")
                
                for i, audio_data in enumerate(self.audio_buffer):
                    if i == 0:
                        # 第一帧
                        status = STATUS_FIRST_FRAME
                        d = {
                            "common": self.ws_param.CommonArgs,
                            "business": self.ws_param.BusinessArgs,
                            "data": {
                                "status": 0,
                                "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(audio_data), 'utf-8'),
                                "encoding": "raw"
                            }
                        }
                    elif i == len(self.audio_buffer) - 1:
                        # 最后一帧
                        status = STATUS_LAST_FRAME
                        d = {
                            "data": {
                                "status": 2,
                                "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(audio_data), 'utf-8'),
                                "encoding": "raw"
                            }
                        }
                    else:
                        # 中间帧
                        status = STATUS_CONTINUE_FRAME
                        d = {
                            "data": {
                                "status": 1,
                                "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(audio_data), 'utf-8'),
                                "encoding": "raw"
                            }
                        }
                    
                    ws.send(json.dumps(d))
                    time.sleep(0.01)  # 小间隔，避免发送过快
                
                print("📤 音频数据发送完成")
                
            except Exception as e:
                print(f"❌ 发送音频数据时出错: {e}")
        
        # 启动音频发送线程
        thread.start_new_thread(send_audio, ())

    def cleanup(self):
        """清理资源"""
        try:
            self.is_recording = False
            
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            
            if self.p:
                self.p.terminate()
                
            if self.ws:
                self.ws.close()
                
            print("🧹 资源清理完成")
            
        except Exception as e:
            print(f"❌ 清理资源时出错: {e}")

    def run(self):
        """主运行循环"""
        try:
            print("🚀 程序开始运行...")
            while True:
                time.sleep(0.1)  # 减少CPU占用
                
        except KeyboardInterrupt:
            print("\n⏹️  收到退出信号")
        except Exception as e:
            print(f"❌ 程序运行出错: {e}")
        finally:
            self.cleanup()


if __name__ == "__main__":
    try:
        # 初始化通道工厂
        ChannelFactoryInitialize(0)
        
        # 创建语音遥控器实例
        controller = VoiceRemoteController()
        
        # 运行程序
        controller.run()
        
    except Exception as e:
        print(f"❌ 程序启动失败: {e}")
        sys.exit(1)
