# -*- coding: utf-8 -*-
"""
路径配置文件
统一管理项目中的所有路径，支持环境变量配置
"""

import os
import pathlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class PathConfig:
    """路径配置管理类"""
    
    def __init__(self):
        self._base_dir = pathlib.Path(__file__).resolve().parent
        self._project_root = self._base_dir.parents[1]  # feiaiagent_2.0/
        
    @property
    def base_dir(self) -> pathlib.Path:
        """当前模块目录"""
        return self._base_dir
    
    @property
    def project_root(self) -> pathlib.Path:
        """项目根目录"""
        return self._project_root
    
    @property
    def static_dir(self) -> pathlib.Path:
        """静态文件目录"""
        return self.base_dir / "static"
    
    @property
    def tts_dir(self) -> pathlib.Path:
        """TTS音频输出目录"""
        tts_dir = self.static_dir / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)
        return tts_dir
    
    @property
    def video_dir(self) -> pathlib.Path:
        """视频文件目录"""
        video_dir = self.static_dir / "video"
        video_dir.mkdir(parents=True, exist_ok=True)
        return video_dir
    
    @property
    def reports_dir(self) -> pathlib.Path:
        """报告存储目录"""
        reports_dir = self.base_dir / "report"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir
    
    @property
    def local_questionnaire_path(self) -> str:
        """本地问卷文件路径"""
        env_path = os.getenv("LOCAL_QUESTIONNAIRE_PATH")
        if env_path:
            return env_path
        return str(self.base_dir / "local_questionnaire.py")
    
    @property
    def env_file_path(self) -> Optional[pathlib.Path]:
        """环境变量文件路径"""
        env_path = os.getenv("ENV_FILE_PATH")
        if env_path:
            return pathlib.Path(env_path)
        
        # 按优先级查找 .env 文件
        search_paths = [
            self.base_dir / ".env",           # 当前目录
            self.base_dir.parent / ".env",    # 上级目录
            self.project_root / ".env",       # 项目根目录
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        return None
    
    @property
    def ffmpeg_path(self) -> str:
        """FFmpeg可执行文件路径"""
        env_path = os.getenv("FFMPEG_PATH")
        if env_path:
            return env_path
        
        # 默认路径（可根据系统调整）
        if os.name == 'nt':  # Windows
            return "ffmpeg.exe"
        else:  # Linux/macOS
            return "/usr/bin/ffmpeg"
    
    @property
    def speexdec_path(self) -> str:
        """SpeexDec可执行文件路径"""
        env_path = os.getenv("SPEEXDEC_PATH")
        if env_path:
            return env_path
        return "speexdec"
    
    @property
    def placeholder_beep(self) -> pathlib.Path:
        """占位音频文件路径"""
        return self.tts_dir / "beep.wav"
    
    @property
    def digital_human_image_path(self) -> str:
        """数字人图片路径"""
        env_path = os.getenv("DIGITAL_HUMAN_IMAGE_PATH")
        if env_path:
            return env_path
        
        # 默认图片路径
        default_image = self.base_dir / "resource" / "images" / "avatar.jpg"
        return str(default_image)
    
    def get_metagpt_dir(self) -> pathlib.Path:
        """MetaGPT问卷模块目录"""
        return self.project_root / "metagpt_questionnaire"
    
    def get_metagpt_config_path(self) -> pathlib.Path:
        """MetaGPT配置文件路径"""
        return self.get_metagpt_dir() / "config" / "metagpt_config.py"
    
    def get_metagpt_workflow_path(self) -> pathlib.Path:
        """MetaGPT工作流文件路径"""
        return self.get_metagpt_dir() / "workflows" / "questionnaire_workflow.py"
    
    def validate_paths(self) -> dict:
        """验证所有路径的有效性"""
        results = {
            "valid": True,
            "paths": {},
            "errors": []
        }
        
        # 检查关键路径
        paths_to_check = {
            "base_dir": self.base_dir,
            "static_dir": self.static_dir,
            "tts_dir": self.tts_dir,
            "video_dir": self.video_dir,
            "reports_dir": self.reports_dir,
            "local_questionnaire": pathlib.Path(self.local_questionnaire_path),
            "env_file": self.env_file_path,
        }
        
        for name, path in paths_to_check.items():
            if path and path.exists():
                results["paths"][name] = str(path)
            else:
                results["paths"][name] = str(path) if path else "None"
                if name in ["base_dir", "static_dir", "tts_dir", "video_dir", "reports_dir"]:
                    results["errors"].append(f"关键路径不存在: {name} = {path}")
                    results["valid"] = False
        
        return results
    
    def print_paths(self):
        """打印所有路径信息"""
        logger.info("=== 路径配置信息 ===")
        logger.info(f"基础目录: {self.base_dir}")
        logger.info(f"项目根目录: {self.project_root}")
        logger.info(f"静态文件目录: {self.static_dir}")
        logger.info(f"TTS音频目录: {self.tts_dir}")
        logger.info(f"视频文件目录: {self.video_dir}")
        logger.info(f"报告存储目录: {self.reports_dir}")
        logger.info(f"本地问卷路径: {self.local_questionnaire_path}")
        logger.info(f"环境变量文件: {self.env_file_path}")
        logger.info(f"FFmpeg路径: {self.ffmpeg_path}")
        logger.info(f"SpeexDec路径: {self.speexdec_path}")
        logger.info(f"数字人图片路径: {self.digital_human_image_path}")
        logger.info(f"MetaGPT目录: {self.get_metagpt_dir()}")
        logger.info("==================")

# 创建全局路径配置实例
path_config = PathConfig()

# 导出常用路径
BASE_DIR = path_config.base_dir
PROJECT_ROOT = path_config.project_root
STATIC_DIR = path_config.static_dir
TTS_DIR = path_config.tts_dir
VIDEO_DIR = path_config.video_dir
REPORTS_DIR = path_config.reports_dir
LOCAL_QUESTIONNAIRE_PATH = path_config.local_questionnaire_path
ENV_FILE_PATH = path_config.env_file_path
FFMPEG_PATH = path_config.ffmpeg_path
SPEEXDEC_PATH = path_config.speexdec_path
PLACEHOLDER_BEEP = path_config.placeholder_beep
DIGITAL_HUMAN_IMAGE_PATH = path_config.digital_human_image_path

if __name__ == "__main__":
    # 测试路径配置
    logging.basicConfig(level=logging.INFO)
    path_config.print_paths()
    
    # 验证路径
    validation = path_config.validate_paths()
    if validation["valid"]:
        print("✅ 所有路径验证通过")
    else:
        print("❌ 路径验证失败:")
        for error in validation["errors"]:
            print(f"  - {error}")
