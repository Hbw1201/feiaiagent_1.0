# cleanup_media.py
# -*- coding: utf-8 -*-
"""
自动清理音频和视频文件模块
在每次开始新对话时，自动删除上一次对话生成的音频和视频文件
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

def cleanup_old_media_files(static_root: str = "static", keep_latest: int = 0) -> Tuple[int, int]:
    """
    清理旧的音频和视频文件
    
    Args:
        static_root: 静态文件根目录
        keep_latest: 保留最新的文件数量，0表示全部删除
    
    Returns:
        Tuple[int, int]: (删除的音频文件数量, 删除的视频文件数量)
    """
    static_path = Path(static_root)
    tts_dir = static_path / "tts"
    video_dir = static_path / "video"
    
    deleted_audio_count = 0
    deleted_video_count = 0
    
    try:
        # 清理音频文件
        if tts_dir.exists():
            audio_files = []
            for file_path in tts_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.wav', '.mp3']:
                    # 排除系统文件（如beep.wav, warmup.wav）
                    if file_path.name not in ['beep.wav', 'warmup.wav']:
                        audio_files.append(file_path)
            
            # 按修改时间排序，最新的在前
            audio_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 删除文件（保留最新的几个）
            files_to_delete = audio_files[keep_latest:]
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    deleted_audio_count += 1
                    logger.info(f"删除音频文件: {file_path}")
                except Exception as e:
                    logger.error(f"删除音频文件失败 {file_path}: {e}")
        
        # 清理视频文件
        if video_dir.exists():
            video_files = []
            for file_path in video_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() == '.mp4':
                    video_files.append(file_path)
            
            # 按修改时间排序，最新的在前
            video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 删除文件（保留最新的几个）
            files_to_delete = video_files[keep_latest:]
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    deleted_video_count += 1
                    logger.info(f"删除视频文件: {file_path}")
                except Exception as e:
                    logger.error(f"删除视频文件失败 {file_path}: {e}")
        
        logger.info(f"清理完成: 删除 {deleted_audio_count} 个音频文件, {deleted_video_count} 个视频文件")
        
    except Exception as e:
        logger.error(f"清理媒体文件时发生错误: {e}")
    
    return deleted_audio_count, deleted_video_count

def cleanup_by_session_id(session_id: str, static_root: str = "static") -> Tuple[int, int]:
    """
    根据会话ID清理特定的音频和视频文件
    
    Args:
        session_id: 会话ID
        static_root: 静态文件根目录
    
    Returns:
        Tuple[int, int]: (删除的音频文件数量, 删除的视频文件数量)
    """
    static_path = Path(static_root)
    tts_dir = static_path / "tts"
    video_dir = static_path / "video"
    
    deleted_audio_count = 0
    deleted_video_count = 0
    
    try:
        # 清理以session_id开头的音频文件
        if tts_dir.exists():
            for file_path in tts_dir.iterdir():
                if (file_path.is_file() and 
                    file_path.suffix.lower() in ['.wav', '.mp3'] and 
                    file_path.stem.startswith(session_id)):
                    try:
                        file_path.unlink()
                        deleted_audio_count += 1
                        logger.info(f"删除会话音频文件: {file_path}")
                    except Exception as e:
                        logger.error(f"删除会话音频文件失败 {file_path}: {e}")
        
        # 清理以session_id开头的视频文件（如果有的话）
        if video_dir.exists():
            for file_path in video_dir.iterdir():
                if (file_path.is_file() and 
                    file_path.suffix.lower() == '.mp4' and 
                    file_path.stem.startswith(session_id)):
                    try:
                        file_path.unlink()
                        deleted_video_count += 1
                        logger.info(f"删除会话视频文件: {file_path}")
                    except Exception as e:
                        logger.error(f"删除会话视频文件失败 {file_path}: {e}")
        
        logger.info(f"会话 {session_id} 清理完成: 删除 {deleted_audio_count} 个音频文件, {deleted_video_count} 个视频文件")
        
    except Exception as e:
        logger.error(f"清理会话 {session_id} 媒体文件时发生错误: {e}")
    
    return deleted_audio_count, deleted_video_count

def cleanup_old_files_by_age(static_root: str = "static", max_age_hours: int = 24) -> Tuple[int, int]:
    """
    根据文件年龄清理音频和视频文件
    
    Args:
        static_root: 静态文件根目录
        max_age_hours: 文件最大保留时间（小时）
    
    Returns:
        Tuple[int, int]: (删除的音频文件数量, 删除的视频文件数量)
    """
    static_path = Path(static_root)
    tts_dir = static_path / "tts"
    video_dir = static_path / "video"
    
    deleted_audio_count = 0
    deleted_video_count = 0
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    try:
        # 清理过期的音频文件
        if tts_dir.exists():
            for file_path in tts_dir.iterdir():
                if (file_path.is_file() and 
                    file_path.suffix.lower() in ['.wav', '.mp3'] and
                    file_path.name not in ['beep.wav', 'warmup.wav']):
                    
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        try:
                            file_path.unlink()
                            deleted_audio_count += 1
                            logger.info(f"删除过期音频文件: {file_path} (年龄: {file_age/3600:.1f}小时)")
                        except Exception as e:
                            logger.error(f"删除过期音频文件失败 {file_path}: {e}")
        
        # 清理过期的视频文件
        if video_dir.exists():
            for file_path in video_dir.iterdir():
                if (file_path.is_file() and 
                    file_path.suffix.lower() == '.mp4'):
                    
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        try:
                            file_path.unlink()
                            deleted_video_count += 1
                            logger.info(f"删除过期视频文件: {file_path} (年龄: {file_age/3600:.1f}小时)")
                        except Exception as e:
                            logger.error(f"删除过期视频文件失败 {file_path}: {e}")
        
        logger.info(f"按年龄清理完成: 删除 {deleted_audio_count} 个音频文件, {deleted_video_count} 个视频文件")
        
    except Exception as e:
        logger.error(f"按年龄清理媒体文件时发生错误: {e}")
    
    return deleted_audio_count, deleted_video_count

def get_media_files_info(static_root: str = "static") -> dict:
    """
    获取媒体文件信息统计
    
    Args:
        static_root: 静态文件根目录
    
    Returns:
        dict: 包含文件统计信息的字典
    """
    static_path = Path(static_root)
    tts_dir = static_path / "tts"
    video_dir = static_path / "video"
    
    info = {
        "audio_files": [],
        "video_files": [],
        "total_audio_size": 0,
        "total_video_size": 0,
        "audio_count": 0,
        "video_count": 0
    }
    
    try:
        # 统计音频文件
        if tts_dir.exists():
            for file_path in tts_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.wav', '.mp3']:
                    file_size = file_path.stat().st_size
                    file_info = {
                        "name": file_path.name,
                        "size": file_size,
                        "modified": file_path.stat().st_mtime
                    }
                    info["audio_files"].append(file_info)
                    info["total_audio_size"] += file_size
                    info["audio_count"] += 1
        
        # 统计视频文件
        if video_dir.exists():
            for file_path in video_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() == '.mp4':
                    file_size = file_path.stat().st_size
                    file_info = {
                        "name": file_path.name,
                        "size": file_size,
                        "modified": file_path.stat().st_mtime
                    }
                    info["video_files"].append(file_info)
                    info["total_video_size"] += file_size
                    info["video_count"] += 1
        
        # 按修改时间排序
        info["audio_files"].sort(key=lambda x: x["modified"], reverse=True)
        info["video_files"].sort(key=lambda x: x["modified"], reverse=True)
        
    except Exception as e:
        logger.error(f"获取媒体文件信息时发生错误: {e}")
    
    return info

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    print("=== 媒体文件清理测试 ===")
    
    # 显示当前文件信息
    info = get_media_files_info()
    print(f"当前音频文件数量: {info['audio_count']}")
    print(f"当前视频文件数量: {info['video_count']}")
    print(f"音频文件总大小: {info['total_audio_size'] / 1024 / 1024:.2f} MB")
    print(f"视频文件总大小: {info['total_video_size'] / 1024 / 1024:.2f} MB")
    
    # 清理旧文件（保留最新的2个）
    print("\n=== 清理旧文件（保留最新2个）===")
    audio_count, video_count = cleanup_old_media_files(keep_latest=2)
    print(f"删除了 {audio_count} 个音频文件和 {video_count} 个视频文件")
