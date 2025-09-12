# report_manager.py
# -*- coding: utf-8 -*-
"""
报告管理模块
- 保存评估报告到文件
- 按姓名和手机号命名文件
- 提供报告查看和管理功能
"""

import os
import time
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportManager:
    def __init__(self, reports_dir: str = "report"):
        """
        初始化报告管理器
        
        Args:
            reports_dir: 报告保存目录
        """
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"报告管理器初始化，保存目录: {self.reports_dir}")
    
    def _sanitize_filename(self, text: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文件名
        """
        # 移除或替换非法字符
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            text = text.replace(char, '_')
        
        # 限制长度
        if len(text) > 50:
            text = text[:50]
        
        return text.strip()
    
    def _extract_user_info(self, answers: Dict[str, str]) -> Tuple[str, str]:
        """
        从答案中提取用户信息
        
        Args:
            answers: 用户答案字典
            
        Returns:
            (姓名, 手机号)
        """
        name = answers.get("姓名", "未知用户")
        phone = answers.get("联系电话2(手机)", answers.get("联系电话1(住宅)", "无手机号"))
        
        # 清理姓名和手机号
        name = self._sanitize_filename(name)
        phone = self._sanitize_filename(phone)
        
        return name, phone
    
    def save_report(self, report_content: str, answers: Dict[str, str], 
                   session_id: str = None) -> Optional[str]:
        """
        保存评估报告到文件
        
        Args:
            report_content: 报告内容
            answers: 用户答案字典
            session_id: 会话ID
            
        Returns:
            保存的文件路径，失败返回None
        """
        try:
            # 提取用户信息
            name, phone = self._extract_user_info(answers)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if phone and phone != "无手机号":
                filename = f"{name}_{phone}_{timestamp}.txt"
            else:
                filename = f"{name}_{timestamp}.txt"
            
            file_path = self.reports_dir / filename
            
            # 准备报告数据
            report_data = {
                "用户信息": {
                    "姓名": answers.get("姓名", "未知"),
                    "性别": answers.get("性别(1男 2女)", "未知"),
                    "出生年份": answers.get("出生年份", "未知"),
                    "手机号": answers.get("联系电话2(手机)", "无"),
                    "住宅电话": answers.get("联系电话1(住宅)", "无"),
                    "家庭地址": answers.get("家庭地址", "无")
                },
                "会话信息": {
                    "会话ID": session_id or "未知",
                    "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "报告类型": "肺癌早筛风险评估报告"
                },
                "评估报告": report_content
            }
            
            # 保存报告
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("肺癌早筛风险评估报告\n")
                f.write("=" * 60 + "\n\n")
                
                f.write("【用户信息】\n")
                f.write("-" * 30 + "\n")
                for key, value in report_data["用户信息"].items():
                    f.write(f"{key}: {value}\n")
                
                f.write(f"\n【会话信息】\n")
                f.write("-" * 30 + "\n")
                for key, value in report_data["会话信息"].items():
                    f.write(f"{key}: {value}\n")
                
                f.write(f"\n【评估报告】\n")
                f.write("-" * 30 + "\n")
                f.write(report_content)
                f.write("\n\n" + "=" * 60 + "\n")
                f.write(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n")
            
            logger.info(f"报告保存成功: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"保存报告失败: {e}")
            return None
    
    def save_report_json(self, report_content: str, answers: Dict[str, str], 
                        session_id: str = None) -> Optional[str]:
        """
        保存评估报告为JSON格式
        
        Args:
            report_content: 报告内容
            answers: 用户答案字典
            session_id: 会话ID
            
        Returns:
            保存的文件路径，失败返回None
        """
        try:
            # 提取用户信息
            name, phone = self._extract_user_info(answers)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if phone and phone != "无手机号":
                filename = f"{name}_{phone}_{timestamp}.json"
            else:
                filename = f"{name}_{timestamp}.json"
            
            file_path = self.reports_dir / filename
            
            # 准备报告数据
            report_data = {
                "用户信息": {
                    "姓名": answers.get("姓名", "未知"),
                    "性别": answers.get("性别(1男 2女)", "未知"),
                    "出生年份": answers.get("出生年份", "未知"),
                    "手机号": answers.get("联系电话2(手机)", "无"),
                    "住宅电话": answers.get("联系电话1(住宅)", "无"),
                    "家庭地址": answers.get("家庭地址", "无")
                },
                "会话信息": {
                    "会话ID": session_id or "未知",
                    "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "报告类型": "肺癌早筛风险评估报告"
                },
                "用户答案": answers,
                "评估报告": report_content
            }
            
            # 保存JSON文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"JSON报告保存成功: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"保存JSON报告失败: {e}")
            return None
    
    def get_reports_list(self) -> List[Dict[str, str]]:
        """
        获取所有报告文件列表
        
        Returns:
            报告文件信息列表
        """
        reports = []
        try:
            for file_path in self.reports_dir.glob("*.txt"):
                stat = file_path.stat()
                reports.append({
                    "filename": file_path.name,
                    "path": str(file_path),
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
            
            # 按创建时间倒序排列
            reports.sort(key=lambda x: x["created"], reverse=True)
            
        except Exception as e:
            logger.error(f"获取报告列表失败: {e}")
        
        return reports
    
    def get_report_content(self, filename: str) -> Optional[str]:
        """
        读取指定报告文件内容
        
        Args:
            filename: 文件名
            
        Returns:
            报告内容，失败返回None
        """
        try:
            file_path = self.reports_dir / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning(f"报告文件不存在: {filename}")
                return None
        except Exception as e:
            logger.error(f"读取报告文件失败: {e}")
            return None
    
    def delete_report(self, filename: str) -> bool:
        """
        删除指定报告文件
        
        Args:
            filename: 文件名
            
        Returns:
            删除是否成功
        """
        try:
            file_path = self.reports_dir / filename
            if file_path.exists():
                file_path.unlink()
                logger.info(f"报告文件删除成功: {filename}")
                return True
            else:
                logger.warning(f"报告文件不存在: {filename}")
                return False
        except Exception as e:
            logger.error(f"删除报告文件失败: {e}")
            return False
    
    def cleanup_old_reports(self, days: int = 30) -> int:
        """
        清理指定天数前的旧报告
        
        Args:
            days: 保留天数
            
        Returns:
            删除的文件数量
        """
        deleted_count = 0
        try:
            current_time = time.time()
            cutoff_time = current_time - (days * 24 * 3600)
            
            for file_path in self.reports_dir.glob("*.txt"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"删除旧报告: {file_path.name}")
            
            logger.info(f"清理完成，删除了 {deleted_count} 个旧报告")
            
        except Exception as e:
            logger.error(f"清理旧报告失败: {e}")
        
        return deleted_count
    
    def get_reports_stats(self) -> Dict[str, any]:
        """
        获取报告统计信息
        
        Returns:
            统计信息字典
        """
        try:
            reports = self.get_reports_list()
            total_size = sum(report["size"] for report in reports)
            
            return {
                "total_reports": len(reports),
                "total_size": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "reports_dir": str(self.reports_dir),
                "latest_report": reports[0]["created"] if reports else None
            }
        except Exception as e:
            logger.error(f"获取报告统计失败: {e}")
            return {
                "total_reports": 0,
                "total_size": 0,
                "total_size_mb": 0,
                "reports_dir": str(self.reports_dir),
                "latest_report": None
            }


# 全局报告管理器实例（保存到项目内 report/ 目录）
report_manager = ReportManager()


