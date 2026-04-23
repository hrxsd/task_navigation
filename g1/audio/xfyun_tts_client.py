#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
科大讯飞语音合成客户端
将科大讯飞TTS API封装为可复用的模块
"""

import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
import ssl
import os
import wave
import tempfile
import threading
import time
from typing import Optional, Callable

try:
    import simpleaudio as sa
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Warning: simpleaudio not available, audio playback disabled")


class XFYunTTSClient:
    """科大讯飞语音合成客户端"""
    
    def __init__(self, app_id: str, api_key: str, api_secret: str, 
                 voice: str = "x4_yezi", sample_rate: int = 16000):
        """
        初始化TTS客户端
        
        Args:
            app_id: 科大讯飞应用ID
            api_key: API Key
            api_secret: API Secret
            voice: 语音类型 (x4_yezi: 叶子, x4_xiaoshan: 小山等)
            sample_rate: 采样率
        """
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.voice = voice
        self.sample_rate = sample_rate
        
        # 合成状态
        self.is_synthesizing = False
        self.synthesis_complete = False
        self.pcm_data = b''
        self.synthesis_error = None
        
        # 回调函数
        self.on_synthesis_complete: Optional[Callable[[str], None]] = None
        self.on_synthesis_error: Optional[Callable[[str], None]] = None
        
        # 线程安全
        self.synthesis_lock = threading.Lock()
        
        print("🎵 科大讯飞TTS客户端初始化完成")
    
    def synthesize_and_play(self, text: str, save_file: bool = False, 
                           output_path: Optional[str] = None) -> bool:
        """
        合成并播放语音
        
        Args:
            text: 要合成的文本
            save_file: 是否保存音频文件
            output_path: 保存路径，如果为None则使用临时文件
            
        Returns:
            bool: 是否成功
        """
        if not text.strip():
            print("⚠️  文本为空，跳过语音合成")
            return False
        
        with self.synthesis_lock:
            if self.is_synthesizing:
                print("⚠️  语音合成正在进行中，请稍等...")
                return False
            
            print(f"🎵 开始语音合成: {text}")
            self.is_synthesizing = True
            self.synthesis_complete = False
            self.pcm_data = b''
            self.synthesis_error = None
        
        try:
            # 创建WebSocket参数
            ws_param = self._create_ws_param(text)
            
            # 建立WebSocket连接
            websocket.enableTrace(False)
            ws_url = ws_param.create_url()
            
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # 设置当前WebSocket实例
            self.current_ws = ws
            self.current_ws_param = ws_param
            
            # 启动WebSocket连接
            ws_thread = threading.Thread(
                target=ws.run_forever,
                kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}},
                daemon=True
            )
            ws_thread.start()
            
            # 等待合成完成
            timeout = 30  # 30秒超时
            start_time = time.time()
            
            while not self.synthesis_complete and not self.synthesis_error:
                if time.time() - start_time > timeout:
                    print("❌ 语音合成超时")
                    with self.synthesis_lock:
                        self.is_synthesizing = False
                    return False
                
                time.sleep(0.1)
            
            # 检查合成结果
            if self.synthesis_error:
                print(f"❌ 语音合成失败: {self.synthesis_error}")
                if self.on_synthesis_error:
                    self.on_synthesis_error(self.synthesis_error)
                return False
            
            if not self.pcm_data:
                print("❌ 未收到音频数据")
                return False
            
            # 保存并播放音频
            return self._save_and_play_audio(save_file, output_path)
            
        except Exception as e:
            print(f"❌ 语音合成异常: {e}")
            with self.synthesis_lock:
                self.is_synthesizing = False
            return False
    
    def synthesize_only(self, text: str, output_path: str) -> bool:
        """
        仅合成语音，不播放
        
        Args:
            text: 要合成的文本
            output_path: 输出文件路径
            
        Returns:
            bool: 是否成功
        """
        # 先合成
        success = self.synthesize_and_play(text, save_file=True, output_path=output_path)
        return success
    
    def _create_ws_param(self, text: str):
        """创建WebSocket参数"""
        return Ws_Param(self.app_id, self.api_key, self.api_secret, text, 
                       self.voice, self.sample_rate)
    
    def _on_message(self, ws, message):
        """WebSocket消息处理"""
        try:
            message = json.loads(message)
            code = message.get("code", -1)
            sid = message.get("sid", "")
            data = message.get("data", {})
            status = data.get("status", None)
            audio = data.get("audio", None)

            if code != 0:
                error_msg = f"sid:{sid} call error:{message.get('message', '')} code:{code}"
                print(f"❌ TTS错误: {error_msg}")
                self.synthesis_error = error_msg
                return

            # 累积音频数据
            if audio:
                self.pcm_data += base64.b64decode(audio)
                print(f"📥 接收音频数据块，累计大小: {len(self.pcm_data)} 字节")

            # 合成完成
            if status == 2:
                print("✅ 语音合成完成")
                self.synthesis_complete = True
                ws.close()

        except Exception as e:
            error_msg = f"消息处理异常: {e}"
            print(f"❌ {error_msg}")
            self.synthesis_error = error_msg
    
    def _on_error(self, ws, error):
        """WebSocket错误处理"""
        error_msg = f"WebSocket错误: {error}"
        print(f"❌ {error_msg}")
        self.synthesis_error = error_msg
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket关闭处理"""
        print("🔌 TTS WebSocket连接已关闭")
    
    def _on_open(self, ws):
        """WebSocket连接建立"""
        def run(*args):
            try:
                # 发送合成请求
                d = {
                    "common": self.current_ws_param.CommonArgs,
                    "business": self.current_ws_param.BusinessArgs,
                    "data": self.current_ws_param.Data,
                }
                ws.send(json.dumps(d))
                print("📤 发送TTS合成请求")
            except Exception as e:
                print(f"❌ 发送请求失败: {e}")
                self.synthesis_error = f"发送请求失败: {e}"
        
        thread.start_new_thread(run, ())
    
    def _save_and_play_audio(self, save_file: bool = False, 
                           output_path: Optional[str] = None) -> bool:
        """保存并播放音频"""
        try:
            # 确定输出文件路径
            if save_file and output_path:
                wav_file = output_path
            else:
                # 使用临时文件
                temp_fd, wav_file = tempfile.mkstemp(suffix='.wav', prefix='tts_')
                os.close(temp_fd)
            
            # 保存为WAV文件
            with wave.open(wav_file, 'wb') as wf:
                wf.setnchannels(1)  # 单声道
                wf.setsampwidth(2)  # 16位
                wf.setframerate(self.sample_rate)
                wf.writeframes(self.pcm_data)
            
            print(f"💾 音频已保存: {wav_file}")
            
            # 播放音频
            if AUDIO_AVAILABLE:
                print("🔊 正在播放语音...")
                try:
                    wave_obj = sa.WaveObject.from_wave_file(wav_file)
                    play_obj = wave_obj.play()
                    play_obj.wait_done()
                    print("✅ 语音播放完成")
                    
                    # 调用完成回调
                    if self.on_synthesis_complete:
                        self.on_synthesis_complete(wav_file)
                        
                except Exception as e:
                    print(f"❌ 音频播放失败: {e}")
                    return False
            else:
                print("⚠️  音频播放库不可用，仅保存文件")
            
            # 清理临时文件
            if not save_file or not output_path:
                try:
                    os.unlink(wav_file)
                    print("🗑️  临时文件已清理")
                except:
                    pass
            
            return True
            
        except Exception as e:
            print(f"❌ 音频保存/播放失败: {e}")
            return False
        finally:
            with self.synthesis_lock:
                self.is_synthesizing = False
    
    def stop_synthesis(self):
        """停止当前合成"""
        with self.synthesis_lock:
            if self.is_synthesizing:
                print("🛑 停止语音合成")
                self.synthesis_error = "用户取消"
                if hasattr(self, 'current_ws'):
                    self.current_ws.close()
    
    def is_busy(self) -> bool:
        """检查是否正在合成"""
        with self.synthesis_lock:
            return self.is_synthesizing
    
    def set_voice(self, voice: str):
        """设置语音类型"""
        self.voice = voice
        print(f"🎵 语音类型已设置为: {voice}")


class Ws_Param(object):
    """WebSocket参数类"""
    
    def __init__(self, app_id: str, api_key: str, api_secret: str, text: str,
                 voice: str = "x4_yezi", sample_rate: int = 16000):
        self.APPID = app_id
        self.APIKey = api_key
        self.APISecret = api_secret
        self.Text = text

        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {
            "aue": "raw",  # 音频编码格式
            "auf": f"audio/L16;rate={sample_rate}",  # 音频格式
            "vcn": voice,  # 语音类型
            "tte": "utf8"  # 文本编码
        }
        self.Data = {
            "status": 2, 
            "text": str(base64.b64encode(self.Text.encode('utf-8')), "UTF8")
        }

    def create_url(self):
        """创建WebSocket URL"""
        url = 'wss://tts-api.xfyun.cn/v2/tts'
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = "host: ws-api.xfyun.cn\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET /v2/tts HTTP/1.1"

        signature_sha = hmac.new(self.APISecret.encode('utf-8'),
                                 signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode('utf-8')

        authorization_origin = 'api_key="{}", algorithm="{}", headers="host date request-line", signature="{}"'.format(
            self.APIKey, "hmac-sha256", signature_sha
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        return url + '?' + urlencode(v)


# 测试函数
def test_tts_client():
    """测试TTS客户端"""
    print("🧪 测试科大讯飞TTS客户端...")
    
    # 使用默认配置
    tts_client = XFYunTTSClient(
        app_id='38b03603',
        api_key='52136d6271eb9e4fbc6e1da9f59ab33f',
        api_secret='NzRmOGU4N2IyZWQ2ZGQ3NTJkOWU5ZTRl'
    )
    
    # 测试文本
    test_texts = [
        "你好，我是G1机器人！",
        "任务执行完成。",
        "检测到异常情况，请注意。"
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n📝 测试 {i}/{len(test_texts)}: {text}")
        success = tts_client.synthesize_and_play(text)
        if success:
            print(f"✅ 测试 {i} 成功")
        else:
            print(f"❌ 测试 {i} 失败")
        
        # 短暂等待
        time.sleep(1)
    
    print("\n✅ TTS客户端测试完成")


if __name__ == "__main__":
    test_tts_client()
