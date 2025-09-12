# -*- coding:utf-8 -*-
#
# 基于讯飞官方demo的TTS实现
# 本demo测试时运行的环境为：Windows + Python3.7
# 本demo测试成功运行时所安装的第三方库及其版本如下：
# websocket-client==0.56.0

import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import time
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import threading
import os
import uuid
import pathlib
import struct
import subprocess
import tempfile
import shutil
import concurrent.futures
import asyncio
from functools import lru_cache
from queue import Queue

STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识

# 全局线程池和连接池
_tts_thread_pool = None
_tts_ws_connections = {}  # WebSocket连接池
_tts_connection_lock = threading.Lock()
_tts_cache = {}  # TTS结果缓存
_cache_lock = threading.Lock()

def get_tts_thread_pool():
    """获取TTS线程池"""
    global _tts_thread_pool
    if _tts_thread_pool is None:
        _tts_thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=3,  # TTS并发数不宜过高
            thread_name_prefix="tts_worker"
        )
    return _tts_thread_pool

def cleanup_tts_thread_pool():
    """清理TTS线程池"""
    global _tts_thread_pool
    if _tts_thread_pool:
        _tts_thread_pool.shutdown(wait=True)
        _tts_thread_pool = None

@lru_cache(maxsize=100)
def _get_cached_tts_config():
    """缓存TTS配置获取"""
    try:
        from config import XFYUN_APPID, XFYUN_APIKEY, XFYUN_APISECRET
        return XFYUN_APPID, XFYUN_APIKEY, XFYUN_APISECRET
    except ImportError:
        return (
            os.getenv("XFYUN_APPID", "3536bab1"),
            os.getenv("XFYUN_APIKEY", "fe9c6565d02d77ca53d1129df1222e37"),
            os.getenv("XFYUN_APISECRET", "YTRlMjU3MDAyOGIxM2FhNTA0OTFjYjM1")
        )

class Ws_Param(object):
    # 初始化
    def __init__(self, APPID, APIKey, APISecret, Text):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.Text = Text

        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business)，更多个性化参数可在官网查看
        self.BusinessArgs = {
            "aue": "raw",  # 音频编码格式：raw (PCM)
            "auf": "audio/L16;rate=16000",  # 音频采样率：16kHz
            "vcn": "xiaoyan",  # 发音人：xiaoyan
            "tte": "utf8"  # 文本编码格式：utf8
        }
        self.Data = {"status": 2, "text": str(base64.b64encode(self.Text.encode('utf-8')), "UTF8")}

    # 生成url
    def create_url(self):
        url = 'wss://tts-api.xfyun.cn/v2/tts'
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/tts " + "HTTP/1.1"
        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        # 拼接鉴权参数，生成url
        url = url + '?' + urlencode(v)
        return url

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """
    将PCM音频数据转换为WAV格式
    """
    # WAV文件头
    wav_header = bytearray()
    
    # RIFF头
    wav_header.extend(b'RIFF')
    wav_header.extend(struct.pack('<I', 36 + len(pcm_data)))  # 文件大小
    wav_header.extend(b'WAVE')
    
    # fmt子块
    wav_header.extend(b'fmt ')
    wav_header.extend(struct.pack('<I', 16))  # fmt子块大小
    wav_header.extend(struct.pack('<H', 1))   # 音频格式 (PCM = 1)
    wav_header.extend(struct.pack('<H', channels))  # 声道数
    wav_header.extend(struct.pack('<I', sample_rate))  # 采样率
    wav_header.extend(struct.pack('<I', sample_rate * channels * bits_per_sample // 8))  # 字节率
    wav_header.extend(struct.pack('<H', channels * bits_per_sample // 8))  # 块对齐
    wav_header.extend(struct.pack('<H', bits_per_sample))  # 位深度
    
    # data子块
    wav_header.extend(b'data')
    wav_header.extend(struct.pack('<I', len(pcm_data)))  # 数据大小
    
    # 组合WAV文件
    wav_data = wav_header + pcm_data
    return bytes(wav_data)

def convert_wav_to_mp3(wav_path: pathlib.Path, mp3_path: pathlib.Path) -> bool:
    """
    将WAV文件转换为MP3格式，提高浏览器兼容性
    优先使用ffmpeg，如果没有则尝试使用pydub
    """
    try:
        # 方法1：使用ffmpeg（推荐，质量更好）
        if shutil.which("ffmpeg"):
            print(f"使用ffmpeg转换WAV到MP3: {wav_path} -> {mp3_path}")
            result = subprocess.run([
                "ffmpeg", "-y", "-i", str(wav_path), 
                "-acodec", "libmp3lame", "-ab", "128k", 
                str(mp3_path)
            ], capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0 and mp3_path.exists():
                print(f"ffmpeg转换成功: {mp3_path}")
                return True
            else:
                print(f"ffmpeg转换失败: {result.stderr}")
                return False
        
        # 方法2：使用pydub（Python库，需要安装）
        try:
            from pydub import AudioSegment
            print(f"使用pydub转换WAV到MP3: {wav_path} -> {mp3_path}")
            audio = AudioSegment.from_wav(str(wav_path))
            audio.export(str(mp3_path), format="mp3", bitrate="128k")
            print(f"pydub转换成功: {mp3_path}")
            return True
        except ImportError:
            print("pydub未安装，跳过pydub转换")
            return False
        except Exception as e:
            print(f"pydub转换失败: {e}")
            return False
            
    except Exception as e:
        print(f"WAV转MP3转换失败: {e}")
        return False

def tts_text_to_mp3_async(text: str, out_dir: pathlib.Path, prefix: str) -> pathlib.Path:
    """
    异步版本的TTS文本转MP3函数，使用线程池和缓存
    """
    # 检查缓存
    cache_key = f"{text}_{prefix}"
    with _cache_lock:
        if cache_key in _tts_cache:
            cached_path = _tts_cache[cache_key]
            if cached_path.exists():
                print(f"使用TTS缓存: {cached_path}")
                return cached_path
    
    # 在线程池中执行TTS处理
    thread_pool = get_tts_thread_pool()
    future = thread_pool.submit(_tts_text_to_mp3_sync, text, out_dir, prefix)
    
    try:
        result = future.result(timeout=30)  # 30秒超时
        if result and result.exists():
            # 缓存结果
            with _cache_lock:
                _tts_cache[cache_key] = result
            return result
        return None
    except concurrent.futures.TimeoutError:
        print(f"TTS处理超时: {text[:50]}...")
        return None
    except Exception as e:
        print(f"TTS处理异常: {e}")
        return None

def _tts_text_to_mp3_sync(text: str, out_dir: pathlib.Path, prefix: str) -> pathlib.Path:
    """
    同步版本的TTS文本转MP3函数（内部使用）
    """
    # 生成临时WAV文件名和最终MP3文件名
    temp_wav_fname = f"{prefix}_{uuid.uuid4().hex}.wav"
    final_mp3_fname = f"{prefix}_{uuid.uuid4().hex}.mp3"
    temp_wav_path = out_dir / temp_wav_fname
    final_mp3_path = out_dir / final_mp3_fname
    
    print(f"开始TTS转换，文本长度: {len(text)} 字符")
    print(f"临时WAV文件: {temp_wav_path}")
    print(f"最终MP3文件: {final_mp3_path}")
    
    # 调用讯飞TTS API
    pcm_audio_bytes = call_xfyun_tts_api(text)
    
    if pcm_audio_bytes and len(pcm_audio_bytes) > 0:
        print(f"✅ 科大讯飞TTS API调用成功，获得PCM音频数据: {len(pcm_audio_bytes)} bytes")
        
        # 将PCM数据转换为WAV格式
        wav_audio_bytes = pcm_to_wav(pcm_audio_bytes)
        print(f"✅ PCM转WAV成功，WAV大小: {len(wav_audio_bytes)} bytes")
        
        # 先写入临时WAV文件
        with open(temp_wav_path, "wb") as f:
            f.write(wav_audio_bytes)
        print(f"✅ 临时WAV文件生成成功: {temp_wav_path}")
        
        # 验证文件是否真的写入
        if temp_wav_path.exists():
            actual_size = temp_wav_path.stat().st_size
            print(f"✅ 文件验证: 实际文件大小 {actual_size} bytes")
        else:
            print(f"❌ 文件写入失败: {temp_wav_path} 不存在")
            return None
        
        # 尝试将WAV转换为MP3
        try:
            if convert_wav_to_mp3(temp_wav_path, final_mp3_path):
                # 转换成功，删除临时WAV文件
                temp_wav_path.unlink()
                print(f"TTS成功生成MP3音频文件: {final_mp3_path}")
                return final_mp3_path
            else:
                # 转换失败，使用WAV文件
                print(f"WAV转MP3失败，使用WAV文件: {temp_wav_path}")
                return temp_wav_path
        except Exception as e:
            print(f"WAV转MP3过程中出错: {e}，使用WAV文件: {temp_wav_path}")
            return temp_wav_path
    else:
        # 没有音频数据，使用占位符
        print("TTS生成失败，使用占位符音频")
        # 尝试使用配置中的占位符路径
        try:
            from config import PLACEHOLDER_BEEP
            if PLACEHOLDER_BEEP.exists():
                import shutil
                shutil.copy2(PLACEHOLDER_BEEP, temp_wav_path)
                print(f"使用配置中的占位符音频: {temp_wav_path}")
                return temp_wav_path
        except ImportError:
            pass
        
        # 如果配置中的路径不存在，尝试相对路径
        placeholder = pathlib.Path("static/beep.wav")
        if placeholder.exists():
            import shutil
            shutil.copy2(placeholder, temp_wav_path)
            print(f"使用相对路径占位符音频: {temp_wav_path}")
            return temp_wav_path
        else:
            print("错误：占位符音频文件不存在")
        return None

def call_xfyun_tts_api(text: str) -> bytes:
    """
    调用讯飞TTS API，将文本转换为语音
    """
    try:
        # 从配置文件读取讯飞TTS配置
        try:
            from config import XFYUN_APPID, XFYUN_APIKEY, XFYUN_APISECRET
            APPID = XFYUN_APPID
            APIKey = XFYUN_APIKEY
            APISecret = XFYUN_APISECRET
            print(f"✅ 使用配置文件中的讯飞TTS配置: APPID={APPID}")
        except ImportError:
            # 如果无法导入配置，使用环境变量
            APPID = os.getenv("XFYUN_APPID", "3536bab1")
            APIKey = os.getenv("XFYUN_APIKEY", "fe9c6565d02d77ca53d1129df1222e37")
            APISecret = os.getenv("XFYUN_APISECRET", "YTRlMjU3MDAyOGIxM2FhNTA0OTFjYjM1")
            print(f"⚠️ 使用环境变量中的讯飞TTS配置: APPID={APPID}")
        
        # 创建参数对象
        wsParam = Ws_Param(APPID=APPID, APISecret=APISecret, APIKey=APIKey, Text=text)
        
        # 存储音频数据
        audio_data = b""
        
        def on_message(ws, message):
            nonlocal audio_data
            try:
                message = json.loads(message)
                code = message["code"]
                sid = message["sid"]
                audio = message["data"]["audio"]
                audio = base64.b64decode(audio)
                status = message["data"]["status"]
                
                print(f"TTS响应: code={code}, sid={sid}, status={status}")
                
                if status == 2:
                    print("TTS WebSocket连接关闭")
                    ws.close()
                
                if code != 0:
                    errMsg = message["message"]
                    print(f"TTS错误: sid:{sid} call error:{errMsg} code is:{code}")
                else:
                    # 累积音频数据
                    audio_data += audio
                    print(f"接收到音频数据: {len(audio)} bytes, 累计: {len(audio_data)} bytes")
                    
                    # 检查音频数据的前几个字节
                    if len(audio_data) <= 100:
                        print(f"音频数据前10字节: {audio_data[:10].hex()}")

            except Exception as e:
                print(f"解析TTS响应时出错: {e}")

        def on_error(ws, error):
            print(f"TTS WebSocket错误: {error}")

        def on_close(ws, close_status_code=None, close_msg=None):
            print(f"TTS WebSocket连接关闭: status_code={close_status_code}, msg={close_msg}")

        def on_open(ws):
            def run(*args):
                d = {"common": wsParam.CommonArgs,
                     "business": wsParam.BusinessArgs,
                     "data": wsParam.Data,
                     }
                d = json.dumps(d)
                print("开始发送文本数据到讯飞TTS")
                ws.send(d)

            threading.Thread(target=run).start()

        # 建立WebSocket连接
        websocket.enableTrace(False)
        wsUrl = wsParam.create_url()
        ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close)
        ws.on_open = on_open
        
        # 运行WebSocket
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        
        print(f"TTS完成，总音频数据大小: {len(audio_data)} bytes")
        return audio_data
        
    except Exception as e:
        print(f"调用讯飞TTS API失败: {e}")
        return b""

def tts_text_to_mp3(text: str, out_dir: pathlib.Path, prefix: str):
    """
    将文本转换为音频文件，生成MP3格式以提高浏览器兼容性
    默认使用异步版本以提升性能
    """
    return tts_text_to_mp3_async(text, out_dir, prefix)

# 测试函数
def test_xfyun_tts():
    """
    测试科大讯飞TTS功能
    """
    print("=== 开始测试科大讯飞TTS ===")
    
    # 测试文本
    test_text = "你好，这是科大讯飞TTS测试。"
    print(f"测试文本: {test_text}")
    
    # 创建临时目录
    import tempfile
    temp_dir = pathlib.Path(tempfile.mkdtemp())
    print(f"临时目录: {temp_dir}")
    
    try:
        # 调用TTS
        print("开始调用TTS...")
        result = tts_text_to_mp3(test_text, temp_dir, "test")
        print(f"TTS调用结果: {result}")
        
        if result and result.exists():
            print(f"✅ TTS测试成功: {result}")
            print(f"文件大小: {result.stat().st_size} bytes")
            
            # 检查文件内容
            with open(result, 'rb') as f:
                header = f.read(44)  # WAV文件头
                print(f"WAV文件头: {header[:12]}")
        else:
            print("❌ TTS测试失败")
            
    except Exception as e:
        print(f"❌ TTS测试异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理临时文件
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("临时文件已清理")

if __name__ == "__main__":
    test_xfyun_tts()
