# digital_human.py
# -*- coding: utf-8 -*-
"""
通义 CosyVoice(WS) 文本转语音 + LivePortrait 合成视频（极速&稳态版）
- 语音 wav 输出：static/tts/
- 数字人视频 mp4 输出：static/video/

环境变量（必备）：
- DASHSCOPE_API_KEY        ：阿里云 DashScope API Key（以 "sk-" 开头）
- DIGITAL_HUMAN_IMAGE_PATH ：本地真人正脸照片路径（单人、无遮挡、清晰）

（可选）若使用 OSS 预签名直传，请提供：
- OSS_PRESIGNED_URL_FACE_JPG     ：face.jpg 的 PUT 预签名 URL
- OSS_PRESIGNED_URL_SPEECH_WAV   ：speech.wav 的 PUT 预签名 URL
- OSS_PUBLIC_BASE                ：公开可读基址（例：https://your-bucket.oss-cn-xxx.aliyuncs.com）
"""

import os
import io
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PIL import Image
import websocket
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException

# ========= 基本配置 =========
API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-d8f898e299f44dad8c6f83cc51020ed2")

# 图片路径配置：优先使用环境变量，否则使用项目内默认图片
DEFAULT_IMAGE_PATH = Path(__file__).parent / "resource" / "images" / "avatar.jpg"
IMAGE_PATH = os.getenv("DIGITAL_HUMAN_IMAGE_PATH", str(DEFAULT_IMAGE_PATH))

# CosyVoice TTS 参数
TTS_MODEL = "cosyvoice-v2"
TTS_VOICE = "longxiu_v2"        # v2 模型用 *_v2 音色
TTS_FORMAT = "wav"
TTS_SAMPLE_RATE = 16000

# ====== 极速模式参数 ======
VIDEO_FPS = 15             # 20 -> 15，嘴型仍自然，渲染更快
MOUTH_MOVE_STRENGTH = 0.9  # 1.0 -> 0.9
HEAD_MOVE_STRENGTH = 0.3   # 0.4 -> 0.3
EYE_MOVE_FREQ = 0.5
TEMPLATE_ID = "normal"

POLL_INTERVAL = 2          # 3 -> 2，更快拿到SUCCEEDED
POLL_TIMEOUT = 1200

# 是否跳过单独的人脸检测（同一张头像反复用建议 True）
SKIP_FACE_DETECT = True

# DashScope API
BASE_API = "https://dashscope.aliyuncs.com/api/v1"
FACE_DETECT_ENDPOINT = f"{BASE_API}/services/aigc/image2video/face-detect"
VIDEO_SYNTH_ENDPOINT = f"{BASE_API}/services/aigc/image2video/video-synthesis/"
TASK_QUERY_ENDPOINT = f"{BASE_API}/tasks"

# CosyVoice WebSocket
COSY_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"

JSON_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
UA = {"User-Agent": "curl/8.5.0", "Accept": "*/*"}

# ========= HTTP Session（带重试） =========
SESSION = requests.Session()
SESSION.headers.update({"Connection": "keep-alive"})
_retries = Retry(
    total=3, backoff_factor=0.6,
    status_forcelist=[408, 429, 500, 502, 503, 504],
    raise_on_status=False
)
SESSION.mount("https://", HTTPAdapter(max_retries=_retries))
SESSION.mount("http://", HTTPAdapter(max_retries=_retries))

def post_json(url, headers, payload, timeout=30):
    r = SESSION.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
    r.raise_for_status()
    return r

def get_stream(url, timeout=60):
    return SESSION.get(url, stream=True, timeout=timeout)

def head_or_get_ok(url: str, timeout=8) -> bool:
    try:
        r = SESSION.head(url, timeout=timeout, allow_redirects=True)
        if r.status_code < 400 and r.headers.get("Content-Length", "1") != "0":
            return True
        rg = SESSION.get(url, stream=True, timeout=timeout)
        ok = rg.status_code < 400
        if ok:
            rg.close()
        return ok
    except requests.RequestException:
        return False

# ========= 全局 WS 连接（复用&预热&自愈） =========
_TTS_WS = None

def _build_ws(api_key: str):
    for k in ("HTTP_PROXY","http_proxy","HTTPS_PROXY","https_proxy"):
        os.environ.pop(k, None)
    headers = [f"Authorization: Bearer {api_key}"]
    ws = websocket.create_connection(
        COSY_WS_URL,
        header=headers,
        enable_multithread=True,
        timeout=30
    )
    return ws

def _get_ws(api_key: str, force_new: bool = False):
    global _TTS_WS
    if force_new or _TTS_WS is None:
        _TTS_WS = _build_ws(api_key)
    return _TTS_WS

def _safe_send(ws, payload: str) -> bool:
    try:
        ws.send(payload)
        return True
    except (WebSocketConnectionClosedException, WebSocketTimeoutException, BrokenPipeError, OSError):
        return False

def _safe_recv(ws):
    try:
        return ws.recv()
    except (WebSocketConnectionClosedException, WebSocketTimeoutException, BrokenPipeError, OSError):
        return None

# ===== 工具与异常 =====
class DashScopeError(Exception):
    pass

def _raise_for_status(resp: requests.Response):
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise DashScopeError(f"HTTP {resp.status_code}: {detail}") from e

# ---------- 压图 ----------
def compress_image_to_jpeg_bytes(
    img_path: str,
    max_side: int = 1024,
    target_max_bytes: int = 5 * 1024 * 1024
) -> bytes:
    img = Image.open(img_path)
    if img.mode in ("RGBA", "LA"):
        from PIL import Image as _Image
        bg = _Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")

    w, h = img.size
    ratio = max(w, h) / max(1, min(w, h))
    if ratio > 2:
        if w >= h:
            new_w = min(int(2 * h), max_side)
            new_h = int(h * new_w / w)
        else:
            new_h = min(int(2 * w), max_side)
            new_w = int(w * new_h / h)
        img = img.resize((max(1, new_w), max(1, new_h)), Image.LANCZOS)
        w, h = img.size

    if max(w, h) > max_side:
        if w >= h:
            new_w = max_side
            new_h = int(h * new_w / w)
        else:
            new_h = max_side
            new_w = int(w * new_h / h)
        img = img.resize((max(1, new_w), max(1, new_h)), Image.LANCZOS)

    def encode(quality: int) -> bytes:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()

    quality = 88
    jpg = encode(quality)
    while len(jpg) > target_max_bytes and quality > 50:
        quality -= 6
        jpg = encode(quality)
    return jpg

# ---------- 公网直链上传（OSS 优先，失败回落） ----------
def upload_to_0x0(file_bytes: bytes, filename: str, mime: str) -> str:
    files = {"file": (filename, io.BytesIO(file_bytes), mime)}
    resp = SESSION.post("https://0x0.st", files=files, headers=UA, timeout=60)
    _raise_for_status(resp)
    url = resp.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise DashScopeError(f"0x0.st 返回异常：{resp.text[:200]}")
    return url

def upload_to_catbox(file_bytes: bytes, filename: str, mime: str) -> str:
    data = {"reqtype": "fileupload"}
    files = {"fileToUpload": (filename, io.BytesIO(file_bytes), mime)}
    resp = SESSION.post("https://catbox.moe/user/api.php", data=data, files=files, headers=UA, timeout=120)
    _raise_for_status(resp)
    url = resp.text.strip()
    if not url.startswith("http"):
        raise DashScopeError(f"catbox 返回异常：{resp.text[:200]}")
    return url

def upload_to_transfer_sh(file_bytes: bytes, filename: str, mime: str) -> str:
    resp = SESSION.put(f"https://transfer.sh/{filename}", data=file_bytes, headers=UA, timeout=120)
    _raise_for_status(resp)
    url = resp.text.strip()
    if not url.startswith("http"):
        raise DashScopeError(f"transfer.sh 返回异常：{resp.text[:200]}")
    return url

def upload_to_oss_presigned(file_bytes: bytes, filename: str, mime: str) -> Optional[str]:
    env_key = "OSS_PRESIGNED_URL_" + filename.upper().replace('.', '_')
    presigned_url = os.getenv(env_key)
    base_url = os.getenv("OSS_PUBLIC_BASE", "")
    if not presigned_url or not base_url:
        return None
    try:
        r = SESSION.put(presigned_url, data=file_bytes, headers={"Content-Type": mime, **UA}, timeout=30)
        r.raise_for_status()
        return f"{base_url.rstrip('/')}/{filename}"
    except Exception as e:
        print(f"[Upload][OSS] 失败：{e}")
        return None

def upload_public(file_bytes: bytes, filename: str, mime: str) -> str:
    url = upload_to_oss_presigned(file_bytes, filename, mime)
    if url:
        print(f"[Upload] 使用 OSS 成功：{url}")
        return url

    errors = []
    for uploader in (upload_to_0x0, upload_to_catbox, upload_to_transfer_sh):
        try:
            url = uploader(file_bytes, filename, mime)
            print(f"[Upload] 使用 {uploader.__name__} 成功：{url}")
            return url
        except Exception as e:
            errors.append(f"{uploader.__name__}: {e}")
            print(f"[Upload] {uploader.__name__} 失败：{e}")
    raise DashScopeError("所有上传方式均失败：\n" + "\n".join(errors))

# ---------- TTS（CosyVoice WS，同步；断线自愈） ----------
def tts_cosyvoice_ws_to_file_sync(
    text: str,
    api_key: str,
    model: str = TTS_MODEL,
    voice: str = TTS_VOICE,
    sample_rate: int = TTS_SAMPLE_RATE,
    fmt: str = TTS_FORMAT,
    out_path: Path = Path("static/tts") / "tts.wav",
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _run(ws) -> bool:
        task_id = str(uuid.uuid4())
        start_msg = json.dumps({
            "header":{"action":"run-task","task_id":task_id,"streaming":"duplex"},
            "payload":{"task_group":"audio","task":"tts","function":"SpeechSynthesizer",
                       "model":model,"parameters":{"text_type":"PlainText","voice":voice,
                                                  "format":fmt,"sample_rate":sample_rate},
                       "input":{}}
        })
        if not _safe_send(ws, start_msg):
            return False

        started = finished = False
        with open(out_path, "wb") as f:
            while True:
                msg = _safe_recv(ws)
                if msg is None:
                    return False
                if isinstance(msg, (bytes, bytearray)):
                    f.write(msg)
                    continue
                try:
                    data = json.loads(msg)
                except Exception:
                    continue
                ev = data.get("header",{}).get("event")
                if ev == "task-started":
                    started = True
                    _safe_send(ws, json.dumps({
                        "header":{"action":"continue-task","task_id":task_id,"streaming":"duplex"},
                        "payload":{"input":{"text":text}}
                    }))
                    _safe_send(ws, json.dumps({
                        "header":{"action":"finish-task","task_id":task_id,"streaming":"duplex"},
                        "payload":{"input":{}}
                    }))
                elif ev == "task-finished":
                    finished = True
                    break
                elif ev == "task-failed":
                    raise DashScopeError(f"TTS 失败：{data}")
        if not started or not finished:
            return False
        return True

    ws = _get_ws(api_key)
    ok = _run(ws)
    if not ok:
        try:
            ws.close()
        except Exception:
            pass
        ws = _get_ws(api_key, force_new=True)
        ok = _run(ws)
        if not ok:
            raise DashScopeError("TTS 连接丢失且重试失败")
    return out_path

# ---------- LivePortrait ----------
def face_detect(image_url: str) -> bool:
    payload = {"model": "liveportrait-detect", "input": {"image_url": image_url}}
    resp = post_json(FACE_DETECT_ENDPOINT, JSON_HEADERS, payload)
    data = resp.json()
    print("[FaceDetect] 结果：", json.dumps(data, ensure_ascii=False, indent=2))
    return bool(data.get("output", {}).get("pass") is True)

def start_liveportrait(image_url: str, audio_url: str) -> str:
    headers = {**JSON_HEADERS, "X-DashScope-Async": "enable"}
    payload = {
        "model": "liveportrait",
        "input": {"image_url": image_url, "audio_url": audio_url},
        "parameters": {
            "template_id": TEMPLATE_ID,
            "eye_move_freq": EYE_MOVE_FREQ,
            "video_fps": VIDEO_FPS,
            "mouth_move_strength": MOUTH_MOVE_STRENGTH,
            "paste_back": False,  # 极速：关闭背景融合
            "head_move_strength": HEAD_MOVE_STRENGTH,
        },
    }
    resp = post_json(VIDEO_SYNTH_ENDPOINT, headers, payload)
    data = resp.json()
    print("[LivePortrait] 发起任务返回：", json.dumps(data, ensure_ascii=False, indent=2))
    task_id = data.get("task_id") or data.get("output", {}).get("task_id") or data.get("request_id")
    if not task_id:
        raise DashScopeError(f"[LivePortrait] 未获取到 task_id，原始返回：{json.dumps(data, ensure_ascii=False)}")
    print(f"[LivePortrait] task_id: {task_id}")
    return task_id

def _extract_status(d: Dict[str, Any]) -> Optional[str]:
    return d.get("status") or d.get("task_status") or d.get("output", {}).get("status") or d.get("output", {}).get("task_status")

def poll_task(task_id: str) -> Dict[str, Any]:
    url = f"{TASK_QUERY_ENDPOINT}/{task_id}"
    start = time.time()
    while True:
        resp = SESSION.get(url, headers=JSON_HEADERS, timeout=30)
        _raise_for_status(resp)
        data = resp.json()
        status = _extract_status(data)
        print(f"[Poll] task_id={task_id} status={status}")
        if status in ("SUCCEEDED", "FAILED", "CANCELED"):
            return data
        if time.time() - start > POLL_TIMEOUT:
            raise DashScopeError(f"[Poll] 超时（>{POLL_TIMEOUT}s），请稍后手动查询：{task_id}")
        time.sleep(POLL_INTERVAL)

def _scan_for_video_url(v: Any, out: List[str]):
    if isinstance(v, dict):
        for _k, _v in v.items():
            _scan_for_video_url(_v, out)
    elif isinstance(v, list):
        for _x in v:
            _scan_for_video_url(_x, out)
    else:
        if isinstance(v, str) and v.startswith("http") and ("mp4" in v or "video" in v):
            out.append(v)

def extract_remote_video_url(result_json: Dict[str, Any]) -> Optional[str]:
    video_url = (
        result_json.get("output", {}).get("results", {}).get("video_url")
        or result_json.get("output", {}).get("video_url")
        or result_json.get("video_url")
    )
    if not video_url:
        cands: List[str] = []
        _scan_for_video_url(result_json, cands)
        if cands:
            video_url = cands[0]
    return video_url

def download_video(result_json: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    video_url = extract_remote_video_url(result_json)
    if not video_url:
        print("[Download] 未找到视频URL，原始结果：", json.dumps(result_json, ensure_ascii=False, indent=2))
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"liveportrait_{int(time.time())}.mp4"
    print(f"[Download] 开始下载视频：{video_url}")
    with get_stream(video_url, timeout=120) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print(f"[Download] 视频已保存：{out_path.resolve()}")
    return out_path

# ---------- 预热 ----------
def warmup_tts(static_root: str = "static"):
    if not API_KEY or not API_KEY.startswith("sk-"):
        return
    tts_dir = Path(static_root) / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    warmup_file = tts_dir / "warmup.wav"
    try:
        _ = _get_ws(API_KEY)
        tts_cosyvoice_ws_to_file_sync("您好", API_KEY, out_path=warmup_file)
        print("[Warmup] TTS 预热完成：", warmup_file)
    except Exception as e:
        print("[Warmup] TTS 预热失败：", e)

# ---------- 对外主函数 ----------
def generate_digital_human_assets(
    text: str,
    prefix: str,
    ffmpeg_path: str = "",   # 保留签名，但不再转 mp3
    static_root: str = "static",
) -> Tuple[Path, Optional[Path], str, str, str]:
    """
    返回：(wav_path, mp4_path, tts_url, video_url, video_stream_url)
    - wav_path：本地 wav 路径（供前端播放）
    - mp4_path：本地 mp4 路径（数字人视频，可能为空）
    - tts_url ：/static/tts/<file>.wav
    - video_url：/static/video/<file>.mp4（若已落盘）
    - video_stream_url：远端 mp4 直链（优先用于“即播”）
    """
    if not API_KEY or not API_KEY.startswith("sk-"):
        raise RuntimeError("DASHSCOPE_API_KEY 未配置或格式不正确（应以 sk- 开头）")
    if not IMAGE_PATH or not Path(IMAGE_PATH).exists():
        raise RuntimeError(f"DIGITAL_HUMAN_IMAGE_PATH 不存在：{IMAGE_PATH}")

    static_root = Path(static_root)
    tts_dir = static_root / "tts"
    video_dir = static_root / "video"
    tts_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time())
    wav_out = tts_dir / f"{prefix}_{ts}.wav"

    # 1) TTS
    t0 = time.time()
    wav_path = tts_cosyvoice_ws_to_file_sync(
        text, API_KEY,
        model=TTS_MODEL, voice=TTS_VOICE, sample_rate=TTS_SAMPLE_RATE, fmt=TTS_FORMAT,
        out_path=wav_out
    )
    print(f"[TIMING] TTS {time.time()-t0:.2f}s")

    # 2) 上传图片/音频获取直链（OSS 优先）
    t1 = time.time()
    jpg_bytes = compress_image_to_jpeg_bytes(IMAGE_PATH)
    image_url = upload_public(jpg_bytes, "face.jpg", "image/jpeg")
    with open(wav_path, "rb") as f:
        audio_url = upload_public(f.read(), "speech.wav", "audio/wav")

    if not head_or_get_ok(image_url) or not head_or_get_ok(audio_url):
        raise DashScopeError("外链不可达：请使用可读直链（建议 OSS 预签名+PUBLIC_BASE）")
    print(f"[TIMING] 上传+校验 {time.time()-t1:.2f}s")

    # 3) LivePortrait 渲染
    t2 = time.time()
    if not SKIP_FACE_DETECT:
        if not face_detect(image_url):
            raise DashScopeError("人脸检测未通过：请用清晰、无遮挡、单人正脸，≤5MB，最长边≤1024。")
    task_id = start_liveportrait(image_url, audio_url)
    result_json = poll_task(task_id)
    remote_video_url = extract_remote_video_url(result_json)
    if not remote_video_url:
        raise DashScopeError("LivePortrait 成功但未拿到视频地址，请检查返回 JSON。")
    print(f"[TIMING] LP 渲染完成 {time.time()-t2:.2f}s")

    # 4) 后台/同步落盘（这里仍同步下载一次，若想更极致可改成线程后台）
    mp4_path = download_video(result_json, video_dir)

    # 5) URL
    tts_url = f"/static/tts/{wav_path.name}"
    video_url = f"/static/video/{mp4_path.name}" if mp4_path else ""
    video_stream_url = remote_video_url
    return wav_path, mp4_path, tts_url, video_url, video_stream_url

if __name__ == "__main__":
    warmup_tts()
