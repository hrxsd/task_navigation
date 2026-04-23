# -*- coding:utf-8 -*-
#
# 实时语音识别（科大讯飞流式WebAPI版）
# 需要安装依赖：
# pip install websocket-client pyaudio

import websocket
import hashlib
import base64
import hmac
import json
import time
import ssl
import _thread as thread
import pyaudio
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime

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


def on_message(ws, message):
    try:
        msg = json.loads(message)
        code = msg.get("code", -1)
        sid = msg.get("sid", "")
        if code != 0:
            print(f"sid:{sid} call error: {msg.get('message')} code is: {code}")
        else:
            data = msg["data"]["result"]["ws"]
            result = ""
            for i in data:
                for w in i["cw"]:
                    result += w["w"]
            if result.strip():
                print("👉 实时识别结果:", result)
    except Exception as e:
        print("receive msg,but parse exception:", e)


def on_error(ws, error):
    print("### error:", error)


def on_close(ws, a, b):
    print("### closed ###")


def on_open(ws):
    def run(*args):
        CHUNK = 1280        # 40ms 对应 16000*0.04*2=1280字节 (16k采样, 16bit单声道)
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000

        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

        print("🎤 开始实时语音识别... 按 Ctrl+C 停止")

        status = STATUS_FIRST_FRAME
        try:
            while True:
                buf = stream.read(CHUNK, exception_on_overflow=False)

                if not buf:
                    status = STATUS_LAST_FRAME

                if status == STATUS_FIRST_FRAME:
                    d = {
                        "common": wsParam.CommonArgs,
                        "business": wsParam.BusinessArgs,
                        "data": {
                            "status": 0,
                            "format": "audio/L16;rate=16000",
                            "audio": str(base64.b64encode(buf), 'utf-8'),
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(d))
                    status = STATUS_CONTINUE_FRAME

                elif status == STATUS_CONTINUE_FRAME:
                    d = {
                        "data": {
                            "status": 1,
                            "format": "audio/L16;rate=16000",
                            "audio": str(base64.b64encode(buf), 'utf-8'),
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(d))

                elif status == STATUS_LAST_FRAME:
                    d = {
                        "data": {
                            "status": 2,
                            "format": "audio/L16;rate=16000",
                            "audio": str(base64.b64encode(buf), 'utf-8'),
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(d))
                    time.sleep(1)
                    break

                time.sleep(0.04)  # 模拟采样间隔

        except KeyboardInterrupt:
            print("🛑 手动停止识别")
            d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                          "audio": "", "encoding": "raw"}}
            ws.send(json.dumps(d))
            ws.close()
            stream.stop_stream()
            stream.close()
            p.terminate()

    thread.start_new_thread(run, ())


if __name__ == "__main__":
    wsParam = Ws_Param(APPID='fcf81c07',
                       APIKey='c9c5d895c29b63ebc79a4aea4ec0a46e',
                       APISecret='NmU4OWE4N2IyYTUyYjQ2MDQ5NzExZjRh')

    websocket.enableTrace(False)
    wsUrl = wsParam.create_url()
    ws = websocket.WebSocketApp(wsUrl,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
