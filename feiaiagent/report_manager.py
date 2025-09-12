# report_manager.py
# -*- coding: utf-8 -*-
"""
报告管理模块
- 保存评估报告到文件
- 按姓名和手机号命名文件
- 提供报告查看和管理功能
- 支持PDF导出功能
"""

import os
import time
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime

# PDF生成相关导入
try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    # 尝试使用weasyprint作为备选方案
    try:
        import weasyprint
        WEASYPRINT_AVAILABLE = True
    except ImportError:
        WEASYPRINT_AVAILABLE = False

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
    
    def save_report_pdf(self, report_content: str, answers: Dict[str, str], 
                       session_id: str = None) -> Optional[str]:
        """
        保存评估报告为PDF格式（如果PDF库不可用，则生成HTML格式）
        
        Args:
            report_content: 报告内容
            answers: 用户答案字典
            session_id: 会话ID
            
        Returns:
            保存的文件路径，失败返回None
        """
        if not PDF_AVAILABLE and not WEASYPRINT_AVAILABLE:
            # 如果PDF库不可用，生成HTML格式作为替代
            logger.warning("PDF功能不可用，生成HTML格式报告作为替代")
            return self._save_report_html(report_content, answers, session_id)
        
        # 优先使用reportlab，如果不可用则使用HTML转PDF
        if PDF_AVAILABLE:
            return self._save_report_pdf_reportlab(report_content, answers, session_id)
        else:
            return self._save_report_pdf_html(report_content, answers, session_id)
    
    def _save_report_html(self, report_content: str, answers: Dict[str, str], 
                         session_id: str = None) -> Optional[str]:
        """
        保存评估报告为HTML格式（PDF的替代方案）
        
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
                filename = f"{name}_{phone}_{timestamp}.html"
            else:
                filename = f"{name}_{timestamp}.html"
            
            file_path = self.reports_dir / filename
            
            # 生成HTML内容
            html_content = self._generate_html_report(report_content, answers, session_id)
            
            # 保存HTML文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML报告保存成功: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"保存HTML报告失败: {e}")
            return None
    
    def _save_report_pdf_html(self, report_content: str, answers: Dict[str, str], 
                             session_id: str = None) -> Optional[str]:
        """
        使用HTML转PDF的方式生成报告
        """
        try:
            # 提取用户信息
            name, phone = self._extract_user_info(answers)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if phone and phone != "无手机号":
                filename = f"{name}_{phone}_{timestamp}.pdf"
            else:
                filename = f"{name}_{timestamp}.pdf"
            
            file_path = self.reports_dir / filename
            
            # 生成HTML内容
            html_content = self._generate_html_report(report_content, answers, session_id)
            
            # 使用weasyprint转换为PDF
            import weasyprint
            weasyprint.HTML(string=html_content).write_pdf(str(file_path))
            
            logger.info(f"HTML转PDF报告保存成功: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"HTML转PDF失败: {e}")
            return None
    
    def _generate_html_report(self, report_content: str, answers: Dict[str, str], 
                             session_id: str = None) -> str:
        """
        生成HTML格式的报告
        """
        html_template = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>肺癌早筛风险评估报告</title>
            <style>
                body {
                    font-family: "Microsoft YaHei", Arial, sans-serif;
                    line-height: 1.6;
                    margin: 40px;
                    color: #333;
                }
                .header {
                    text-align: center;
                    color: #2c3e50;
                    border-bottom: 3px solid #3498db;
                    padding-bottom: 20px;
                    margin-bottom: 30px;
                }
                .section {
                    margin-bottom: 25px;
                }
                .section-title {
                    color: #27ae60;
                    font-size: 16px;
                    font-weight: bold;
                    margin-bottom: 10px;
                    padding: 8px;
                    background-color: #ecf0f1;
                    border-left: 4px solid #27ae60;
                }
                .info-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }
                .info-table th, .info-table td {
                    border: 1px solid #bdc3c7;
                    padding: 8px 12px;
                    text-align: left;
                }
                .info-table th {
                    background-color: #34495e;
                    color: white;
                    font-weight: bold;
                }
                .info-table tr:nth-child(even) {
                    background-color: #f8f9fa;
                }
                .answer-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }
                .answer-table th, .answer-table td {
                    border: 1px solid #bdc3c7;
                    padding: 6px 8px;
                    text-align: left;
                    vertical-align: top;
                }
                .answer-table th {
                    background-color: #7f8c8d;
                    color: white;
                    font-weight: bold;
                }
                .answer-table tr:nth-child(even) {
                    background-color: #f8f9fa;
                }
                .report-content {
                    white-space: pre-line;
                    line-height: 1.8;
                }
                .footer {
                    text-align: center;
                    color: #7f8c8d;
                    font-size: 12px;
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #bdc3c7;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>肺癌早筛风险评估报告</h1>
            </div>
            
            <div class="section">
                <div class="section-title">【用户信息】</div>
                <table class="info-table">
                    <tr><th>姓名</th><td>{name}</td></tr>
                    <tr><th>性别</th><td>{gender}</td></tr>
                    <tr><th>出生年份</th><td>{birth_year}</td></tr>
                    <tr><th>手机号</th><td>{phone}</td></tr>
                    <tr><th>住宅电话</th><td>{home_phone}</td></tr>
                    <tr><th>家庭地址</th><td>{address}</td></tr>
                </table>
            </div>
            
            <div class="section">
                <div class="section-title">【会话信息】</div>
                <table class="info-table">
                    <tr><th>会话ID</th><td>{session_id}</td></tr>
                    <tr><th>生成时间</th><td>{generate_time}</td></tr>
                    <tr><th>报告类型</th><td>肺癌早筛风险评估报告</td></tr>
                </table>
            </div>
            
            {answers_section}
            
            <div class="section">
                <div class="section-title">【评估报告】</div>
                <div class="report-content">{report_content}</div>
            </div>
            
            <div class="footer">
                报告生成时间: {generate_time}
            </div>
        </body>
        </html>
        """
        
        # 准备数据
        name = answers.get("姓名", "未知")
        gender = answers.get("性别(1男 2女)", "未知")
        birth_year = answers.get("出生年份", "未知")
        phone = answers.get("联系电话2(手机)", "无")
        home_phone = answers.get("联系电话1(住宅)", "无")
        address = answers.get("家庭地址", "无")
        generate_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        
        # 生成答案表格
        answers_section = ""
        if answers:
            answers_section = """
            <div class="section">
                <div class="section-title">【用户答案】</div>
                <table class="answer-table">
                    <tr><th>问题</th><th>答案</th></tr>
            """
            for question, answer in answers.items():
                # 限制问题长度
                short_question = question[:50] + "..." if len(question) > 50 else question
                short_answer = str(answer)[:100] + "..." if len(str(answer)) > 100 else str(answer)
                answers_section += f'<tr><td>{short_question}</td><td>{short_answer}</td></tr>'
            answers_section += "</table></div>"
        
        # 填充模板
        html_content = html_template.format(
            name=name,
            gender=gender,
            birth_year=birth_year,
            phone=phone,
            home_phone=home_phone,
            address=address,
            session_id=session_id or "未知",
            generate_time=generate_time,
            answers_section=answers_section,
            report_content=report_content
        )
        
        return html_content
    
    def _save_report_pdf_reportlab(self, report_content: str, answers: Dict[str, str], 
                                  session_id: str = None) -> Optional[str]:
        """
        使用reportlab生成PDF报告
        """
        try:
            # 提取用户信息
            name, phone = self._extract_user_info(answers)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if phone and phone != "无手机号":
                filename = f"{name}_{phone}_{timestamp}.pdf"
            else:
                filename = f"{name}_{timestamp}.pdf"
            
            file_path = self.reports_dir / filename
            
            # 创建PDF文档
            doc = SimpleDocTemplate(str(file_path), pagesize=A4)
            story = []
            
            # 获取样式
            styles = getSampleStyleSheet()
            
            # 标题样式
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=1,  # 居中
                textColor=colors.darkblue
            )
            
            # 子标题样式
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                spaceBefore=12,
                textColor=colors.darkgreen
            )
            
            # 正文样式
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                leading=14
            )
            
            # 添加标题
            story.append(Paragraph("肺癌早筛风险评估报告", title_style))
            story.append(Spacer(1, 20))
            
            # 添加用户信息
            story.append(Paragraph("【用户信息】", heading_style))
            user_info_data = [
                ["姓名", answers.get("姓名", "未知")],
                ["性别", answers.get("性别(1男 2女)", "未知")],
                ["出生年份", answers.get("出生年份", "未知")],
                ["手机号", answers.get("联系电话2(手机)", "无")],
                ["住宅电话", answers.get("联系电话1(住宅)", "无")],
                ["家庭地址", answers.get("家庭地址", "无")]
            ]
            
            user_table = Table(user_info_data, colWidths=[2*inch, 4*inch])
            user_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (0, 0), (0, -1), colors.grey),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
            ]))
            story.append(user_table)
            story.append(Spacer(1, 20))
            
            # 添加会话信息
            story.append(Paragraph("【会话信息】", heading_style))
            session_info_data = [
                ["会话ID", session_id or "未知"],
                ["生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                ["报告类型", "肺癌早筛风险评估报告"]
            ]
            
            session_table = Table(session_info_data, colWidths=[2*inch, 4*inch])
            session_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (0, 0), (0, -1), colors.grey),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
            ]))
            story.append(session_table)
            story.append(Spacer(1, 20))
            
            # 添加用户答案
            if answers:
                story.append(Paragraph("【用户答案】", heading_style))
                answer_data = [["问题", "答案"]]
                for question, answer in answers.items():
                    # 限制问题长度，避免表格过宽
                    short_question = question[:50] + "..." if len(question) > 50 else question
                    answer_data.append([short_question, str(answer)[:100]])
                
                answer_table = Table(answer_data, colWidths=[3*inch, 3*inch])
                answer_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                story.append(answer_table)
                story.append(Spacer(1, 20))
            
            # 添加评估报告
            story.append(Paragraph("【评估报告】", heading_style))
            
            # 将报告内容按段落分割
            report_paragraphs = report_content.split('\n')
            for para in report_paragraphs:
                if para.strip():
                    story.append(Paragraph(para.strip(), normal_style))
                    story.append(Spacer(1, 6))
            
            # 添加页脚
            story.append(Spacer(1, 30))
            story.append(Paragraph(f"报告生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}", 
                                 ParagraphStyle('Footer', parent=styles['Normal'], 
                                               fontSize=8, alignment=1, textColor=colors.grey)))
            
            # 构建PDF
            doc.build(story)
            
            logger.info(f"PDF报告保存成功: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"保存PDF报告失败: {e}")
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
                "latest_report": reports[0]["created"] if reports else None,
                "pdf_available": PDF_AVAILABLE or WEASYPRINT_AVAILABLE
            }
        except Exception as e:
            logger.error(f"获取报告统计失败: {e}")
            return {
                "total_reports": 0,
                "total_size": 0,
                "total_size_mb": 0,
                "reports_dir": str(self.reports_dir),
                "latest_report": None,
                "pdf_available": PDF_AVAILABLE or WEASYPRINT_AVAILABLE
            }


# 全局报告管理器实例（保存到项目内 report/ 目录）
report_manager = ReportManager()
