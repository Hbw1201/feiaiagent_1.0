# -*- coding: utf-8 -*-
"""
简化版app.py集成
基于医院本地问卷的智能调研系统
"""

import logging
import time
from typing import Dict, Any
from flask import jsonify, request

from .simple_questionnaire_manager import SimpleQuestionnaireManager
from .agents.questionnaire_designer import QuestionnaireDesignerAgent

logger = logging.getLogger(__name__)

# 全局问卷管理器
_questionnaire_managers: Dict[str, SimpleQuestionnaireManager] = {}

def setup_simple_questionnaire_routes(app, _run_async, generate_tts_audio, shorten_for_avatar, report_manager):
    """设置简化版问卷路由"""
    
    @app.route("/api/simple_questionnaire/start", methods=["POST"])
    def simple_questionnaire_start():
        """启动智能问卷"""
        try:
            data = request.get_json(force=True)
            session_id = data.get("session_id", str(int(time.time() * 1000)))
            local_questionnaire_path = data.get("local_questionnaire_path")
            
            logger.info(f"🚀 启动智能问卷: {session_id}")
            
            # 创建问卷设计器
            designer = QuestionnaireDesignerAgent()
            
            # 设计问卷
            questionnaire = _run_async(designer.design_questionnaire({
                "source": "local",
                "local_questionnaire_path": local_questionnaire_path
            }))
            
            # 创建问卷管理器
            manager = SimpleQuestionnaireManager()
            if not manager.initialize_questionnaire(questionnaire):
                return jsonify({"error": "问卷初始化失败"}), 500
            
            # 保存会话
            _questionnaire_managers[session_id] = manager
            
            # 获取第一个问题
            result = _run_async(manager.get_next_question())
            
            if result["status"] == "next_question":
                question_text = result["question"]
                video_url = "/static/video/human.mp4"
                video_stream_url = "/static/video/human.mp4"
                tts_url = generate_tts_audio(shorten_for_avatar(question_text), session_id)
                
                return jsonify({
                    "session_id": session_id,
                    "question": question_text,
                    "question_id": result["question_id"],
                    "category": result["category"],
                    "progress": result["progress"],
                    "tts_url": tts_url,
                    "video_url": video_url,
                    "video_stream_url": video_stream_url,
                    "is_complete": False
                })
            else:
                return jsonify({"error": "无法获取首个问题"}), 500
                
        except Exception as e:
            logger.error(f"❌ 启动智能问卷失败: {e}")
            return jsonify({"error": f"启动失败: {str(e)}"}), 500
    
    @app.route("/api/simple_questionnaire/reply", methods=["POST"])
    def simple_questionnaire_reply():
        """提交答案并获取下一个问题"""
        try:
            data = request.get_json(force=True)
            session_id = data["session_id"]
            answer_text = data.get("answer", "").strip()
            
            logger.info(f"📝 提交答案: {session_id}, 答案: {answer_text[:50]}...")
            
            # 获取问卷管理器
            manager = _questionnaire_managers.get(session_id)
            if not manager:
                return jsonify({"error": "会话不存在，请重新开始"}), 400
            
            # 获取下一个问题
            result = _run_async(manager.get_next_question(answer_text))
            
            if result["status"] == "invalid_answer":
                # 答案无效，重新询问
                hint = f"回答不够具体，请重新回答：{result['question']}"
                video_url = "/static/video/human.mp4"
                video_stream_url = "/static/video/human.mp4"
                tts_url = generate_tts_audio(shorten_for_avatar(hint), session_id)
                
                return jsonify({
                    "session_id": session_id,
                    "question": hint,
                    "tts_url": tts_url,
                    "video_url": video_url,
                    "video_stream_url": video_stream_url,
                    "is_complete": False,
                    "invalid_answer": True,
                    "invalid_reason": result["error"],
                    "retry": True
                })
            
            elif result["status"] == "completed":
                # 问卷完成
                report_text = result["report"]
                video_url = "/static/video/human.mp4"
                video_stream_url = "/static/video/human.mp4"
                tts_url = generate_tts_audio(shorten_for_avatar(report_text), session_id)
                
                # 保存报告
                try:
                    answers_map = {}
                    for response in manager.answered_questions:
                        question_text = "未知问题"
                        for q in manager.questionnaire.questions:
                            if q.id == response.question_id:
                                question_text = q.text
                                break
                        answers_map[question_text] = response.answer
                    
                    _ = report_manager.save_report(report_text, answers_map, session_id)
                    _ = report_manager.save_report_json(report_text, answers_map, session_id)
                except Exception as e:
                    logger.warning(f"⚠️ 保存报告失败: {e}")
                
                return jsonify({
                    "session_id": session_id,
                    "question": report_text,
                    "tts_url": tts_url,
                    "video_url": video_url,
                    "video_stream_url": video_stream_url,
                    "is_complete": True,
                    "progress": f"{result['total_questions']}/{result['total_questions']}",
                    "total_questions": result["total_questions"]
                })
            
            elif result["status"] == "next_question":
                # 继续下一个问题
                question_text = result["question"]
                video_url = "/static/video/human.mp4"
                video_stream_url = "/static/video/human.mp4"
                tts_url = generate_tts_audio(shorten_for_avatar(question_text), session_id)
                
                return jsonify({
                    "session_id": session_id,
                    "question": question_text,
                    "question_id": result["question_id"],
                    "category": result["category"],
                    "progress": result["progress"],
                    "tts_url": tts_url,
                    "video_url": video_url,
                    "video_stream_url": video_stream_url,
                    "is_complete": False
                })
            
            else:
                return jsonify({"error": result.get("error", "未知错误")}), 500
                
        except Exception as e:
            logger.error(f"❌ 提交答案失败: {e}")
            return jsonify({"error": f"提交失败: {str(e)}"}), 500
    
    @app.route("/api/simple_questionnaire/progress", methods=["GET"])
    def simple_questionnaire_progress():
        """获取问卷进度"""
        try:
            session_id = request.args.get("session_id")
            if not session_id:
                return jsonify({"error": "缺少session_id参数"}), 400
            
            manager = _questionnaire_managers.get(session_id)
            if not manager:
                return jsonify({"error": "会话不存在"}), 404
            
            progress = manager.get_progress()
            return jsonify({
                "status": "success",
                "progress": progress
            })
            
        except Exception as e:
            logger.error(f"❌ 获取进度失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/simple_questionnaire/reset", methods=["POST"])
    def simple_questionnaire_reset():
        """重置问卷会话"""
        try:
            data = request.get_json(force=True)
            session_id = data.get("session_id")
            if not session_id:
                return jsonify({"error": "缺少session_id"}), 400
            
            manager = _questionnaire_managers.get(session_id)
            if manager:
                manager.reset_session()
                return jsonify({"status": "success", "message": "会话已重置"})
            else:
                return jsonify({"error": "会话不存在"}), 404
                
        except Exception as e:
            logger.error(f"❌ 重置会话失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    logger.info("✅ 简化版问卷路由设置完成")

# 使用说明
INTEGRATION_INSTRUCTIONS = """
=== 简化版智能问卷系统集成说明 ===

1. 在app.py中导入：
   from metagpt_questionnaire.simple_app_integration import setup_simple_questionnaire_routes

2. 设置路由：
   setup_simple_questionnaire_routes(app, _run_async, generate_tts_audio, shorten_for_avatar, report_manager)

3. 新的API端点：
   - POST /api/simple_questionnaire/start    - 启动智能问卷
   - POST /api/simple_questionnaire/reply    - 提交答案
   - GET  /api/simple_questionnaire/progress - 获取进度
   - POST /api/simple_questionnaire/reset    - 重置会话

4. 前端修改：
   - 将原有的 /api/metagpt_agent/* 调用改为 /api/simple_questionnaire/*
   - 检查返回的 is_complete 字段来判断是否完成

5. 特性：
   - 基于医院本地问卷
   - 使用DeepSeek优化问题表述
   - 智能输入验证
   - 支持重新回答
   - 自动生成专业报告

这个简化版本专注于核心功能，易于维护和使用。
"""

if __name__ == "__main__":
    print(INTEGRATION_INSTRUCTIONS)
