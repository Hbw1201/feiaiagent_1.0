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
from dotenv import load_dotenv

# ========== 读取 .env ==========
load_dotenv()

# ========== 日志级别（可选）==========
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

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
BASE_DIR     = pathlib.Path(__file__).resolve().parent
STATIC_DIR   = BASE_DIR / "static"
TTS_OUT_DIR  = STATIC_DIR / "tts"
TTS_OUT_DIR.mkdir(parents=True, exist_ok=True)

# 占位音频：你项目里是 static/tts/beep.wav（如需修改这行）
PLACEHOLDER_BEEP = TTS_OUT_DIR / "beep.wav"

# ========== 可执行工具探测 ==========
# 可用环境变量 FFMPEG_PATH 覆盖（优先）
ENV_FFMPEG_PATH = os.getenv("FFMPEG_PATH", "").strip()

def resolve_ffmpeg_path() -> str:
    """
    返回可用的 ffmpeg 可执行路径：
    优先 ENV_FFMPEG_PATH，其次系统 PATH（shutil.which）。
    若均不可用，返回空字符串。
    """
    if ENV_FFMPEG_PATH:
        p = pathlib.Path(ENV_FFMPEG_PATH)
        if p.exists():
            return str(p)
        # 允许传可执行名（在 PATH 中）
        wh = shutil.which(ENV_FFMPEG_PATH)
        if wh:
            return wh

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
        logger.warning("⚠️  未检测到 ffmpeg，请安装并加入 PATH，或在 .env 中设置 FFMPEG_PATH。")

# ========== 肺癌早筛问卷配置 ==========
questions = [
    "姓名", "性别(1男 2女)", "出生年份", "身份证号", "医保卡号(选填)",
    "家庭医生", "问卷调查人(楼栋负责人)", "身高(cm)", "体重(kg)",
    "职业", "文化程度(1小学 2初中 3中专 4高中 5大专 6大学 7硕士 8博士 9博士后)",
    "家庭地址", "联系电话1(住宅)", "联系电话2(手机)", "联系电话3(家属)",
    "吸烟史(1是 2否)", "吸烟频率(支/天)", "累计吸烟年数", "目前是否戒烟(1是 2否)", "戒烟年数",
    "被动吸烟(1否 2是)", "被动吸烟频率(1≤1小时/天 2 1-2小时/天 3>2小时/天)", "累计被动吸烟年数",
    "长期厨房油烟接触(1每周<1次 2每周1-3次 3每周>3次 4每天)", "累计厨房油烟接触年数",
    "职业致癌物质接触(1有 2无)", "致癌物类型及累计接触年数(如有)",
    "既往个人肿瘤史(1有 2无)", "肿瘤类型及确诊年份(如有)",
    "三代以内直系亲属肺癌家族史(1有 2无)", "肿瘤类型及关系(如有)",
    "一年内胸部CT检查(1是 2否)",
    "慢性支气管炎(1是 2否)", "患病年数", "肺气肿(1是 2否)", "患病年数",
    "肺结核(1是 2否)", "患病年数", "慢性阻塞性肺病(1是 2否)", "患病年数",
    "肺间质纤维化(1是 2否)", "患病年数",
    "近半年不明原因消瘦(1有 2无)", "体重下降kg(如有)",
    "最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)", "具体症状(如有)",
    "最近自我感觉(1好 2一般 3不好)"
]

questionnaire_reference = {
    "基本信息": {
        "姓名": "2~4个汉字",
        "性别(1男 2女)": "1 或 2",
        "出生年份": "四位数字，如 1950~2010",
        "身份证号": "18位，最后一位可能是 X",
        "医保卡号(选填)": "10~20位字母或数字，可为空",
        "家庭医生": "2~4个字",
        "问卷调查人(楼栋负责人)": "2~4个字"
    },
    "身体指标": {
        "身高(cm)": "数值，100~250",
        "体重(kg)": "数值，30~200"
    },
    "社会信息": {
        "职业": "自由文本，如工人、教师",
        "文化程度(1小学 2初中 3中专 4高中 5大专 6大学 7硕士 8博士 9博士后)": "1~9之间整数"
    },
    "联系方式": {
        "家庭地址": "不少于10个字的详细地址",
        "联系电话1(住宅)": "区号+号码，如 010-12345678",
        "联系电话2(手机)": "11位手机号",
        "联系电话3(家属)": "可为固话或手机号"
    },
    "吸烟史": {
        "吸烟史(1是 2否)": "1 或 2",
        "吸烟频率(支/天)": "0~100",
        "累计吸烟年数": "0~80",
        "目前是否戒烟(1是 2否)": "1 或 2",
        "戒烟年数": "0~80（如已戒烟）"
    },
    "被动吸烟": {
        "被动吸烟(1否 2是)": "1 或 2",
        "被动吸烟频率(1≤1小时/天 2 1-2小时/天 3>2小时/天)": "1~3",
        "累计被动吸烟年数": "0~80"
    },
    "厨房油烟": {
        "长期厨房油烟接触(1每周<1次 2每周1-3次 3每周>3次 4每天)": "1~4",
        "累计厨房油烟接触年数": "0~80"
    },
    "职业暴露": {
        "职业致癌物质接触(1有 2无)": "1 或 2",
        "致癌物类型及累计接触年数(如有)": "如石棉10年，无可为空或无"
    },
    "肿瘤相关史": {
        "既往个人肿瘤史(1有 2无)": "1 或 2",
        "肿瘤类型及确诊年份(如有)": "如肺癌2010年，无可为空",
        "三代以内直系亲属肺癌家族史(1有 2无)": "1 或 2",
        "肿瘤类型及关系(如有)": "如父亲肺癌，无可为空"
    },
    "影像检查": {
        "一年内胸部CT检查(1是 2否)": "1 或 2"
    },
    "呼吸系统疾病史": {
        "慢性支气管炎(1是 2否)": "1 或 2",
        "患病年数": "0~80",
        "肺气肿(1是 2否)": "1 或 2",
        "患病年数": "0~80",
        "肺结核(1是 2否)": "1 或 2",
        "患病年数": "0~80",
        "慢性阻塞性肺病(1是 2否)": "1 或 2",
        "患病年数": "0~80",
        "肺间质纤维化(1是 2否)": "1 或 2",
        "患病年数": "0~80"
    },
    "近期症状": {
        "近半年不明原因消瘦(1有 2无)": "1 或 2",
        "体重下降kg(如有)": "0~30",
        "最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)": "1 或 2",
        "具体症状(如有)": "自由描述，或填无"
    },
    "健康自评": {
        "最近自我感觉(1好 2一般 3不好)": "1~3"
    }
}

# 可选：模块导入时自动打印一次（不想打印就注释掉）
# validate_config()
