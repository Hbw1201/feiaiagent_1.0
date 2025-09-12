# config.py
# -*- coding: utf-8 -*-
"""
集中管理项目配置与可执行工具探测：
- 读取 .env
- 提供关键环境变量（ZHIPU / XFYUN）
- 统一静态目录与 TTS 输出目录
- 探测 ffmpeg / speexdec 路径（支持 FFMPEG_PATH 环境变量覆盖）
- 提供 validate_config() 自检
"""

import os
import shutil
import pathlib
import logging
# from dotenv import load_dotenv  # 临时注释，避免依赖问题

# ========== 日志级别（可选）==========
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

# ========== 读取 .env ==========
try:
    from dotenv import load_dotenv
    # 动态查找 .env 文件（支持环境变量配置）
    env_path = os.getenv("ENV_FILE_PATH")
    if not env_path:
        # 优先在当前目录查找
        current_dir = pathlib.Path(__file__).resolve().parent
        env_path = current_dir / ".env"
        if not env_path.exists():
            # 如果当前目录没有，尝试上级目录
            parent_dir = current_dir.parent
            env_path = parent_dir / ".env"
            if not env_path.exists():
                # 最后尝试项目根目录
                project_root = current_dir.parents[1]  # 回到 feiaiagent_2.0/
                env_path = project_root / ".env"
    
    env_path = pathlib.Path(env_path)
    if env_path.exists():
        load_dotenv(env_path, override=False)
        logger.info(f"✅ 已加载配置文件: {env_path}")
    else:
        logger.warning(f"⚠️ 配置文件不存在: {env_path}")
except ImportError:
    logger.warning("⚠️ python-dotenv 未安装，跳过 .env 文件加载")
except Exception as e:
    logger.warning(f"⚠️ 加载 .env 文件失败: {e}")

# ========== 智谱 Zhipu ==========
# 说明：
# - ZHIPU_API_MODE=agents      -> 使用 /api/v1/agents （智能体）
# - ZHIPU_API_MODE=open_app_v3 -> 使用 /llm-application/open/v3/application/invoke （应用v3）
ZHIPU_APP_ID   = os.getenv("ZHIPU_APP_ID", "1952963926488719360").strip()       # agents: agent_id；open_app_v3: app_id
ZHIPU_API_KEY  = os.getenv("ZHIPU_API_KEY", "232e17d40eb44d358597dbac3e75db03.bBgenNRnmYEFgRAi").strip()
ZHIPU_API_MODE = os.getenv("ZHIPU_API_MODE", "open_app_v3").strip().lower()
ZHIPU_MOCK     = os.getenv("ZHIPU_MOCK", "false").lower() in ("1", "true", "yes")

# ========== 科大讯飞 XFYUN ==========
XFYUN_APPID     = os.getenv("XFYUN_APPID", "3536bab1").strip()
XFYUN_APIKEY    = os.getenv("XFYUN_APIKEY", "fe9c6565d02d77ca53d1129df1222e37").strip()
XFYUN_APISECRET = os.getenv("XFYUN_APISECRET", "YTRlMjU3MDAyOGIxM2FhNTA0OTFjYjM1").strip()

# ========== 路径与静态目录 ==========
# 使用路径配置管理
try:
    from path_config import path_config
    BASE_DIR = path_config.base_dir
    STATIC_DIR = path_config.static_dir
    TTS_OUT_DIR = path_config.tts_dir
    PLACEHOLDER_BEEP = path_config.placeholder_beep
except ImportError:
    # 回退到默认配置
    BASE_DIR = pathlib.Path(__file__).resolve().parent
    STATIC_DIR = BASE_DIR / "static"
    TTS_OUT_DIR = STATIC_DIR / "tts"
    TTS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLACEHOLDER_BEEP = TTS_OUT_DIR / "beep.wav"

# ========== 可执行工具探测 ==========
# 服务器环境强制使用 /usr/bin/ffmpeg
# 可用环境变量 FFMPEG_PATH 覆盖（优先）
ENV_FFMPEG_PATH = os.getenv("FFMPEG_PATH", "").strip()

def resolve_ffmpeg_path() -> str:
    """
    返回可用的 ffmpeg 可执行路径：
    优先 ENV_FFMPEG_PATH，其次服务器默认路径 /usr/bin/ffmpeg，最后系统 PATH。
    若均不可用，返回空字符串。
    """
    # 1. 优先使用环境变量
    if ENV_FFMPEG_PATH:
        p = pathlib.Path(ENV_FFMPEG_PATH)
        if p.exists():
            return str(p)
        # 允许传可执行名（在 PATH 中）
        wh = shutil.which(ENV_FFMPEG_PATH)
        if wh:
            return wh
    
    # 2. 强制使用服务器默认路径 /usr/bin/ffmpeg
    server_ffmpeg_path = "/usr/bin/ffmpeg"
    if pathlib.Path(server_ffmpeg_path).exists():
        return server_ffmpeg_path
    
    # 3. 最后尝试系统 PATH
    wh = shutil.which("ffmpeg")
    return wh or ""

def resolve_speexdec_path() -> str:
    """
    返回可用的 speexdec 可执行路径（若不存在，返回空字符串）。
    """
    return shutil.which("speexdec") or ""

FFMPEG_PATH   = resolve_ffmpeg_path()
SPEEXDEC_PATH = resolve_speexdec_path()

# ========== 启动前自检 ==========
def validate_config() -> None:
    """
    打印关键配置与工具状态；发现高风险配置时给出警告。
    建议在 app.py 顶部调用： from config import validate_config; validate_config()
    """
    logger.info("========== 配置自检 ==========")
    # Zhipu
    mode = ZHIPU_API_MODE
    logger.info(f"ZHIPU_API_MODE = {mode}")
    logger.info(f"ZHIPU_APP_ID   = {ZHIPU_APP_ID}")
    logger.info(f"ZHIPU_API_KEY  = {'<set>' if ZHIPU_API_KEY else '<missing>'} (长度: {len(ZHIPU_API_KEY) if ZHIPU_API_KEY else 0})")
    logger.info(f"ZHIPU_MOCK     = {ZHIPU_MOCK}")

    # XFYUN
    logger.info(f"XFYUN_APPID    = {XFYUN_APPID}")
    logger.info(f"XFYUN_APIKEY   = {'<set>' if XFYUN_APIKEY else '<missing>'} (长度: {len(XFYUN_APIKEY) if XFYUN_APIKEY else 0})")
    logger.info(f"XFYUN_APISECRET = {'<set>' if XFYUN_APISECRET else '<missing>'} (长度: {len(XFYUN_APISECRET) if XFYUN_APISECRET else 0})")

    # 路径
    logger.info(f"STATIC_DIR     = {STATIC_DIR}")
    logger.info(f"TTS_OUT_DIR    = {TTS_OUT_DIR} (exists={TTS_OUT_DIR.exists()})")
    logger.info(f"PLACEHOLDER_BEEP = {PLACEHOLDER_BEEP} (exists={PLACEHOLDER_BEEP.exists()})")

    # 工具
    logger.info(f"FFMPEG_PATH    = {FFMPEG_PATH or '<not found>'}")
    if FFMPEG_PATH == "/usr/bin/ffmpeg":
        logger.info("✅ 使用服务器默认FFMPEG路径: /usr/bin/ffmpeg")
    elif ENV_FFMPEG_PATH and FFMPEG_PATH == ENV_FFMPEG_PATH:
        logger.info(f"✅ 使用环境变量FFMPEG路径: {FFMPEG_PATH}")
    elif FFMPEG_PATH:
        logger.info(f"✅ 使用系统PATH中的FFMPEG: {FFMPEG_PATH}")
    logger.info(f"SPEEXDEC_PATH  = {SPEEXDEC_PATH or '<not found>'}")
    
    # 设置环境变量供其他模块使用
    os.environ["ZHIPU_APP_ID"] = ZHIPU_APP_ID
    os.environ["ZHIPU_API_KEY"] = ZHIPU_API_KEY
    os.environ["ZHIPU_API_MODE"] = ZHIPU_API_MODE
    os.environ["XFYUN_APPID"] = XFYUN_APPID
    os.environ["XFYUN_APIKEY"] = XFYUN_APIKEY
    os.environ["XFYUN_APISECRET"] = XFYUN_APISECRET

    # 业务必需项提示
    if not ZHIPU_MOCK:
        if not ZHIPU_APP_ID or not ZHIPU_API_KEY:
            logger.warning("⚠️  智谱配置不完整：缺少 ZHIPU_APP_ID 或 ZHIPU_API_KEY。")
    if not XFYUN_APPID or not XFYUN_APIKEY or not XFYUN_APISECRET:
        logger.warning("⚠️  讯飞配置不完整：缺少 XFYUN_APPID / XFYUN_APIKEY / XFYUN_APISECRET。")
    if not FFMPEG_PATH:
        logger.warning("⚠️  未检测到 ffmpeg，请检查以下路径：")
        logger.warning("    1. 环境变量 FFMPEG_PATH")
        logger.warning("    2. 服务器默认路径 /usr/bin/ffmpeg")
        logger.warning("    3. 系统 PATH 中的 ffmpeg")
        logger.warning("    或在 .env 中设置 FFMPEG_PATH")

# ========== 肺癌早筛问卷配置 ==========
# 本地问卷配置已移至 local_questionnaire.py 模块
# 如需使用，请从该模块导入：
# from local_questionnaire import questions, questionnaire_reference

# 可选：模块导入时自动打印一次（不想打印就注释掉）
# validate_config()
