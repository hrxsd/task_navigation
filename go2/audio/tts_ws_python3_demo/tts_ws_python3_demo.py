# -*- coding:utf-8 -*-
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
import simpleaudio as sa  # 播放音频

# 全局变量，累加 PCM 数据
pcm_data = b''

class Ws_Param(object):
    def __init__(self, APPID, APIKey, APISecret, Text):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.Text = Text

        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {
            "aue": "raw",
            "auf": "audio/L16;rate=16000",
            "vcn": "x4_yezi",
            "tte": "utf8"
        }
        self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-8')), "UTF8")}

    def create_url(self):
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

def on_message(ws, message):
    global pcm_data
    try:
        message = json.loads(message)
        code = message.get("code", -1)
        sid = message.get("sid", "")
        data = message.get("data", {})
        status = data.get("status", None)
        audio = data.get("audio", None)

        if code != 0:
            print("sid:%s call error:%s code is:%s" % (sid, message.get("message", ""), code))
            return

        if audio:
            pcm_data += base64.b64decode(audio)

        if status == 2:
            wav_file = 'demo.wav'
            with wave.open(wav_file, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm_data)
            print("语音合成完成，正在播放...")
            # 播放音频
            wave_obj = sa.WaveObject.from_wave_file(wav_file)
            play_obj = wave_obj.play()
            play_obj.wait_done()
            ws.close()

    except Exception as e:
        print("receive msg,but parse exception:", e)

def on_error(ws, error):
    print("### error:", error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###", close_status_code, close_msg)

def on_open(ws):
    def run(*args):
        global pcm_data
        pcm_data = b''  # 每次合成清空之前的 PCM 数据
        d = {
            "common": wsParam.CommonArgs,
            "business": wsParam.BusinessArgs,
            "data": wsParam.Data,
        }
        ws.send(json.dumps(d))
    thread.start_new_thread(run, ())

if __name__ == "__main__":
    # 输入文本循环
    APPID = '38b03603'
    APISecret = 'NzRmOGU4N2IyZWQ2ZGQ3NTJkOWU5ZTRl'
    APIKey = '52136d6271eb9e4fbc6e1da9f59ab33f'

    while True:
        text = input("请输入要合成的文本（输入 exit 退出）：\n")
        if text.strip().lower() == "exit":
            break
        wsParam = Ws_Param(APPID, APIKey, APISecret, text)
        websocket.enableTrace(False)
        wsUrl = wsParam.create_url()
        ws = websocket.WebSocketApp(
            wsUrl,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws.on_open = on_open
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
