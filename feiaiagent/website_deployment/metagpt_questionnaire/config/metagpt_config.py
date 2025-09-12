# -*- coding: utf-8 -*-
"""
MetaGPT配置文件
配置各种API密钥和系统参数
"""

import os
from pathlib import Path
from typing import Optional

try:
    # 优先从项目根目录加载 .env
    from dotenv import load_dotenv  # type: ignore

    def _load_env_files():
        """按优先级加载 .env 文件，不覆盖已存在的系统环境变量"""
        # 项目根目录（feiaiagent_2.0/）
        project_root = Path(__file__).parent.parent.parent
        candidates = [
            project_root / ".env",  # 项目根目录的 .env（统一配置）
            Path(__file__).parent.parent / ".env",  # metagpt_questionnaire/.env
        ]
        for env_path in candidates:
            try:
                if env_path.exists():
                    load_dotenv(env_path, override=False)
                    print(f"✅ 已加载配置文件: {env_path}")
            except Exception:
                # 忽略 dotenv 的加载错误，保持容错
                pass

    _load_env_files()
except Exception:
    # dotenv 非必需；没有也不影响，仍可从系统环境读取
    pass

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# DeepSeek配置（仅保留 DeepSeek 通道）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your-deepseek-api-key")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 系统配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4000"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

# 问卷配置
QUESTIONNAIRE_TYPES = {
    "lung_cancer": "肺癌早筛问卷",
    "general_health": "一般健康问卷",
    "custom": "自定义问卷"
}

# 风险评估配置
RISK_LEVELS = {
    "low": {"range": (0, 2), "color": "🟢", "description": "低风险"},
    "medium": {"range": (3, 5), "color": "🟡", "description": "中风险"},
    "high": {"range": (6, 10), "color": "🔴", "description": "高风险"}
}

# 智能体配置
AGENT_CONFIGS = {
    "questionnaire_designer": {
        "name": "问卷设计专家",
        "description": "专业设计医学问卷的智能体",
        "expertise": ["问卷设计", "医学知识", "用户体验"]
    },
    "risk_assessor": {
        "name": "风险评估专家",
        "description": "专业评估健康风险的智能体",
        "expertise": ["医学诊断", "风险评估", "预防医学"]
    },
    "data_analyzer": {
        "name": "数据分析专家",
        "description": "分析问卷数据的智能体",
        "expertise": ["数据分析", "统计学", "模式识别"]
    },
    "report_generator": {
        "name": "报告生成专家",
        "description": "生成专业分析报告的智能体",
        "expertise": ["报告写作", "医学写作", "数据可视化"]
    }
}

def validate_config():
    """验证配置是否完整"""
    required_keys = [
        "DEEPSEEK_API_KEY"
    ]
    
    missing_keys = []
    for key in required_keys:
        if not globals().get(key) or globals().get(key).startswith("your-"):
            missing_keys.append(key)
    
    if missing_keys:
        print(f"⚠️ 配置缺失: {', '.join(missing_keys)}")
        print("请在环境变量中设置这些值，或修改配置文件")
        return False
    
    print("✅ 配置验证通过")
    return True

def get_llm_config():
    """获取LLM配置"""
    return {
        "deepseek": {
            "api_key": DEEPSEEK_API_KEY,
            "base_url": DEEPSEEK_BASE_URL,
            "model": DEEPSEEK_MODEL,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE
        }
    }

if __name__ == "__main__":
    validate_config()
    print("\n=== 配置信息 ===")
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"DeepSeek模型: {DEEPSEEK_MODEL}")
