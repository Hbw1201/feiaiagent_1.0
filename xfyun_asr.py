# xfyun_asr.py
import websocket, hashlib, base64, hmac, json, time, ssl
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
import os

STATUS_FIRST_FRAME = 0
STATUS_CONTINUE_FRAME = 1
STATUS_LAST_FRAME = 2

XFYUN_APPID    = os.getenv("XFYUN_APPID")
XFYUN_APIKEY   = os.getenv("XFYUN_APIKEY")
XFYUN_APISECRET= os.getenv("XFYUN_APISECRET")

class WsParam:
    def __init__(self, audio_file: str):
        self.APPID = XFYUN_APPID
        self.APIKey = XFYUN_APIKEY
        self.APISecret = XFYUN_APISECRET
        self.AudioFile = audio_file
        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {
            #根据需要加点方言进去
            "domain": "xfime-mianqie", "language": "zh_cn", "accent": "mandarin",
            "vinfo": 1, "vad_eos": 10000
        }
        
        # 检查环境变量，支持HTTPS部署
        if not self.APPID or not self.APIKey or not self.APISecret:
            # 尝试从环境变量获取
            import os
            self.APPID = os.getenv("XFYUN_APPID", self.APPID)
            self.APIKey = os.getenv("XFYUN_APIKEY", self.APIKey)
            self.APISecret = os.getenv("XFYUN_APISECRET", self.APISecret)

    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = "host: ws-api.xfyun.cn\n"
        signature_origin += f"date: {date}\n"
        signature_origin += "GET /v2/iat HTTP/1.1"
        signature_sha = hmac.new(self.APISecret.encode('utf-8'),
                                 signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(signature_sha).decode('utf-8')
        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        v = {"authorization": authorization, "date": date, "host": "ws-api.xfyun.cn"}
        return url + '?' + urlencode(v)

def asr_transcribe_file(audio_wav_path: str) -> str:
    """
    输入：已转换为 16k/16bit/mono 的 wav 文件路径
    输出：识别文本（一次性返回）
    """
    result_text = []

    def on_message(ws, message):
        try:
            resp = json.loads(message)
            code = resp.get("code", -1)
            if code != 0:
                print("ASR error:", resp.get("message"), code)
                return
            for blk in resp["data"]["result"]["ws"]:
                for cw in blk["cw"]:
                    result_text.append(cw["w"])
        except Exception as e:
            print("ASR parse error:", e)

    def on_error(ws, error):
        print("ASR ws error:", error)

    def on_close(ws, a, b):
        pass

    def on_open(ws):
        def run(*args):
            frameSize = 8000
            interval = 0.04
            status = STATUS_FIRST_FRAME
            with open(audio_wav_path, "rb") as fp:
                while True:
                    buf = fp.read(frameSize)
                    if not buf:
                        status = STATUS_LAST_FRAME
                    if status == STATUS_FIRST_FRAME:
                        d = {
                            "common": wsParam.CommonArgs,
                            "business": wsParam.BusinessArgs,
                            "data": {
                                "status": 0,
                                "format": "audio/L16;rate=16000",
                                "audio": base64.b64encode(buf).decode("utf-8"),
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
                                "audio": base64.b64encode(buf).decode("utf-8"),
                                "encoding": "raw"
                            }
                        }
                        ws.send(json.dumps(d))
                    elif status == STATUS_LAST_FRAME:
                        d = {
                            "data": {
                                "status": 2,
                                "format": "audio/L16;rate=16000",
                                "audio": base64.b64encode(b"").decode("utf-8"),
                                "encoding": "raw"
                            }
                        }
                        ws.send(json.dumps(d))
                        time.sleep(0.5)
                        break
                    time.sleep(interval)
            ws.close()
        thread.start_new_thread(run, ())

    wsParam = WsParam(audio_file=audio_wav_path)
    wsUrl = wsParam.create_url()
    ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.on_open = on_open
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    return "".join(result_text).strip()
