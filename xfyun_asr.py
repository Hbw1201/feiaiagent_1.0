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

def validate_asr_config():
    """验证ASR配置是否完整"""
    missing_configs = []
    
    if not XFYUN_APPID:
        missing_configs.append("XFYUN_APPID")
    if not XFYUN_APIKEY:
        missing_configs.append("XFYUN_APIKEY")
    if not XFYUN_APISECRET:
        missing_configs.append("XFYUN_APISECRET")
    
    if missing_configs:
        print(f"⚠️  ASR配置缺失: {', '.join(missing_configs)}")
        print("请检查环境变量或.env文件配置")
        return False
    
    print("✅ ASR配置验证通过")
    print(f"APPID: {XFYUN_APPID[:8]}...")
    print(f"APIKey: {XFYUN_APIKEY[:8]}...")
    print(f"APISecret: {XFYUN_APISECRET[:8]}...")
    return True

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
    # 验证ASR配置
    if not validate_asr_config():
        return "ASR配置错误，请检查科大讯飞API配置"
    
    # 检查音频文件是否存在
    if not os.path.exists(audio_wav_path):
        print(f"ASR错误: 音频文件不存在: {audio_wav_path}")
        return "音频文件不存在"
    
    # 检查音频文件大小
    file_size = os.path.getsize(audio_wav_path)
    if file_size == 0:
        print(f"ASR错误: 音频文件为空: {audio_wav_path}")
        return "音频文件为空"
    
    print(f"ASR开始处理音频文件: {audio_wav_path}, 大小: {file_size} bytes")
    
    result_text = []
    max_retries = 3
    retry_count = 0
    
    def on_message(ws, message):
        try:
            resp = json.loads(message)
            code = resp.get("code", -1)
            if code != 0:
                error_msg = resp.get("message", "未知错误")
                print(f"ASR error: {error_msg}, code: {code}")
                # 记录详细错误信息
                if "rate limit" in error_msg.lower() or "quota" in error_msg.lower():
                    print("ASR配额限制，请检查API使用量")
                elif "network" in error_msg.lower() or "timeout" in error_msg.lower():
                    print("ASR网络错误，可能需要重试")
                return
            for blk in resp["data"]["result"]["ws"]:
                for cw in blk["cw"]:
                    result_text.append(cw["w"])
        except Exception as e:
            print(f"ASR parse error: {e}")
            import traceback
            print(f"ASR parse error traceback: {traceback.format_exc()}")

    def on_error(ws, error):
        print(f"ASR WebSocket错误: {error}")
        # 记录错误类型
        if "connection refused" in str(error).lower():
            print("ASR连接被拒绝，可能是网络问题或服务不可用")
        elif "timeout" in str(error).lower():
            print("ASR连接超时，可能需要检查网络")
        elif "ssl" in str(error).lower():
            print("ASR SSL连接问题，检查HTTPS配置")

    def on_close(ws, close_status_code, close_msg):
        print(f"ASR WebSocket连接关闭: status_code={close_status_code}, msg={close_msg}")
        # 检查是否是异常关闭
        if close_status_code != 1000:  # 1000是正常关闭
            print(f"ASR连接异常关闭，状态码: {close_status_code}")

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
