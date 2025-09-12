# -*- coding: utf-8 -*-
"""
MetaGPT问卷系统
基于MetaGPT架构的智能问卷填写和分析系统
"""

__version__ = "1.0.0"
__author__ = "MetaGPT Questionnaire Team"
__description__ = "基于MetaGPT架构的智能问卷填写和分析系统"
__license__ = "MIT"

# 导入主要模块
from .config.metagpt_config import *
from .models.questionnaire import *
from .workflows.questionnaire_workflow import *
from .agents.base_agent import *

# 版本信息
__all__ = [
    "__version__",
    "__author__", 
    "__description__",
    "__license__",
    "validate_config",
    "get_llm_config",
    "create_lung_cancer_questionnaire",
    "create_workflow",
    "agent_registry"
]
