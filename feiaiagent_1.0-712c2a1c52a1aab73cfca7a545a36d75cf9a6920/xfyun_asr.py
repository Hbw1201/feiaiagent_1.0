# xfyun_asr.py
import websocket, hashlib, base64, hmac, json, time, ssl
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import threading  # [MOD] 用 threading 代替 _thread，便于 join
import os
from typing import List

STATUS_FIRST_FRAME = 0
STATUS_CONTINUE_FRAME = 1
STATUS_LAST_FRAME = 2

XFYUN_APPID     = os.getenv("XFYUN_APPID")
XFYUN_APIKEY    = os.getenv("XFYUN_APIKEY")
XFYUN_APISECRET = os.getenv("XFYUN_APISECRET")

def validate_asr_config():
    """验证ASR配置是否完整"""
    missing = []
    if not XFYUN_APPID:     missing.append("XFYUN_APPID")
    if not XFYUN_APIKEY:    missing.append("XFYUN_APIKEY")
    if not XFYUN_APISECRET: missing.append("XFYUN_APISECRET")
    if missing:
        print(f"⚠️  ASR配置缺失: {', '.join(missing)}")
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

        # [MOD] IAT 正确业务参数：domain='iat'，中文普通话
        # 可选：dwa='wpgs' 动态修正，示例先不用以简化结果拼接
        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {
            "domain": "iat",
            "language": "zh_cn",
            "accent": "mandarin",
            "vad_eos": 10000,   # 尾点静音判定 ms
            "vinfo": 1,
            # 可选：启用动态修正（wpgs），提升长音频/纠错能力
            # "dwa": "wpgs"
        }

        # 兜底环境变量
        if not self.APPID or not self.APIKey or not self.APISecret:
            self.APPID     = os.getenv("XFYUN_APPID", self.APPID)
            self.APIKey    = os.getenv("XFYUN_APIKEY", self.APIKey)
            self.APISecret = os.getenv("XFYUN_APISECRET", self.APISecret)

    def create_url(self):
        # [MOD] IAT WebSocket 入口
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        now = datetime.utcnow()  # [MOD] 用 UTC 生成 GMT 时间
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = "host: ws-api.xfyun.cn\n"
        signature_origin += f"date: {date}\n"
        signature_origin += "GET /v2/iat HTTP/1.1"
        signature_sha = hmac.new(self.APISecret.encode('utf-8'),
                                 signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(signature_sha).decode('utf-8')
        authorization_origin = (
            f'api_key="{self.APIKey}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        v = {"authorization": authorization, "date": date, "host": "ws-api.xfyun.cn"}
        return url + '?' + urlencode(v)

def _concat_words(ws_list: List[dict]) -> str:
    """把返回的 ws/cw 结构拼成文本"""
    out = []
    for blk in ws_list:
        for cw in blk.get("cw", []):
            w = cw.get("w")
            if w:
                out.append(w)
    return "".join(out)

def asr_transcribe_file(audio_wav_path: str) -> str:
    """
    输入：16k/16bit/mono 的 wav 文件路径
    输出：识别文本（一次性返回）
    """
    if not validate_asr_config():
        return ""

    if not os.path.exists(audio_wav_path):
        print(f"ASR错误: 音频文件不存在: {audio_wav_path}")
        return ""

    size = os.path.getsize(audio_wav_path)
    if size == 0:
        print(f"ASR错误: 音频文件为空: {audio_wav_path}")
        return ""

    print(f"ASR开始处理音频文件: {audio_wav_path}, 大小: {size} bytes")

    # [MOD] 先读到内存，避免 Windows 文件句柄长时间占用
    with open(audio_wav_path, "rb") as f:
        audio_bytes = f.read()

    result_text_parts: List[str] = []
    wsParam = WsParam(audio_file=audio_wav_path)
    wsUrl = wsParam.create_url()

    def on_message(ws, message):
        try:
            resp = json.loads(message)
            code = resp.get("code", -1)
            if code != 0:
                msg = resp.get("message", "未知错误")
                sid = resp.get("sid", "")
                print(f"ASR error: {msg}, code: {code}, sid={sid}")
                # 11200 多为许可/鉴权：检查 domain/appid/时间/host 等
                return
            data = resp.get("data", {})
            result = data.get("result", {})
            ws_list = result.get("ws", [])
            if ws_list:
                text = _concat_words(ws_list)
                if text:
                    result_text_parts.append(text)
        except Exception as e:
            print(f"ASR parse error: {e}")

    def on_error(ws, error):
        print(f"ASR WebSocket错误: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"ASR WebSocket连接关闭: status_code={close_status_code}, msg={close_msg}")

    def on_open(ws):
        def run():
            # [MOD] 按官方建议：40ms 一帧，16k*2*0.04 ≈ 1280 字节
            frame_size = 1280
            interval = 0.04

            total = len(audio_bytes)
            idx = 0

            # 首帧
            first_chunk = audio_bytes[idx: idx + frame_size]
            idx += len(first_chunk)
            d = {
                "common": wsParam.CommonArgs,
                "business": wsParam.BusinessArgs,
                "data": {
                    "status": STATUS_FIRST_FRAME,
                    # [MOD] 格式带上 channel=1 更严谨
                    "format": "audio/L16;rate=16000;channel=1",
                    "audio": base64.b64encode(first_chunk).decode("utf-8"),
                    "encoding": "raw"
                }
            }
            try:
                ws.send(json.dumps(d))
            except Exception as e:
                print(f"ASR 首帧发送失败: {e}")
                return

            # 中间帧
            while idx < total:
                chunk = audio_bytes[idx: idx + frame_size]
                idx += len(chunk)
                d = {
                    "data": {
                        "status": STATUS_CONTINUE_FRAME,
                        "format": "audio/L16;rate=16000;channel=1",
                        "audio": base64.b64encode(chunk).decode("utf-8"),
                        "encoding": "raw"
                    }
                }
                try:
                    ws.send(json.dumps(d))
                except Exception as e:
                    print(f"ASR 中间帧发送失败，可能连接已关闭: {e}")
                    break
                time.sleep(interval)

            # 结束帧
            end = {
                "data": {
                    "status": STATUS_LAST_FRAME,
                    "format": "audio/L16;rate=16000;channel=1",
                    "audio": "",  # 最后一帧可为空
                    "encoding": "raw"
                }
            }
            try:
                ws.send(json.dumps(end))
            except Exception as e:
                print(f"ASR 结束帧发送失败: {e}")
                return
            # 不主动关闭，等待服务端返回最终结果与关闭连接
            # 若需要超时保护，可在外层 ws.run_forever 超时后退出

        t = threading.Thread(target=run, daemon=True)
        t.start()

    ws = websocket.WebSocketApp(
        wsUrl,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.on_open = on_open

    # [MOD] 加 ping 保活 & 允许自签（按需）
    ws.run_forever(
        sslopt={"cert_reqs": ssl.CERT_NONE},
        ping_interval=20,
        ping_timeout=10
    )

    final_text = "".join(result_text_parts).strip()
    print(f"ASR识别完成，结果: '{final_text}'")
    return final_text
