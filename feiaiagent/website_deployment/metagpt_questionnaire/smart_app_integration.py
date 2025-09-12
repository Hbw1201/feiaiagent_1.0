# -*- coding: utf-8 -*-
"""
智能问卷app.py集成
支持答案审核和重新提问功能
"""

import logging
import time
from typing import Dict, Any
from flask import jsonify, request

from .smart_questionnaire_manager import SmartQuestionnaireManager

logger = logging.getLogger(__name__)

# 全局问卷管理器
_smart_managers: Dict[str, SmartQuestionnaireManager] = {}

def setup_smart_questionnaire_routes(app, _run_async, generate_tts_audio, shorten_for_avatar, report_manager):
    """设置智能问卷路由"""
    
    @app.route("/api/smart_questionnaire/start", methods=["POST"])
    def smart_questionnaire_start():
        """启动智能问卷"""
        try:
            data = request.get_json(force=True)
            session_id = data.get("session_id", str(int(time.time() * 1000)))
            
            logger.info(f"🚀 启动智能问卷: {session_id}")
            
            # 创建智能问卷管理器
            manager = SmartQuestionnaireManager()
            if not manager.initialize_questionnaire():
                return jsonify({"error": "问卷初始化失败"}), 500
            
            # 保存会话
            _smart_managers[session_id] = manager
            
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
    
    @app.route("/api/smart_questionnaire/reply", methods=["POST"])
    def smart_questionnaire_reply():
        """提交答案并获取下一个问题"""
        try:
            data = request.get_json(force=True)
            session_id = data["session_id"]
            answer_text = data.get("answer", "").strip()
            
            logger.info(f"📝 提交答案: {session_id}, 答案: {answer_text[:50]}...")
            
            # 获取问卷管理器
            manager = _smart_managers.get(session_id)
            if not manager:
                return jsonify({"error": "会话不存在，请重新开始"}), 400
            
            # 获取下一个问题
            result = _run_async(manager.get_next_question(answer_text))
            
            if result["status"] == "retry_question":
                # 需要重新回答
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
                    "is_complete": False,
                    "retry": True,
                    "retry_reason": result["reason"],
                    "suggestion": result.get("suggestion", "")
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
                        answers_map[response.question_id] = response.answer
                    
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
    
    @app.route("/api/smart_questionnaire/progress", methods=["GET"])
    def smart_questionnaire_progress():
        """获取问卷进度"""
        try:
            session_id = request.args.get("session_id")
            if not session_id:
                return jsonify({"error": "缺少session_id参数"}), 400
            
            manager = _smart_managers.get(session_id)
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
    
    @app.route("/api/smart_questionnaire/reset", methods=["POST"])
    def smart_questionnaire_reset():
        """重置问卷会话"""
        try:
            data = request.get_json(force=True)
            session_id = data.get("session_id")
            if not session_id:
                return jsonify({"error": "缺少session_id"}), 400
            
            manager = _smart_managers.get(session_id)
            if manager:
                manager.reset_session()
                return jsonify({"status": "success", "message": "会话已重置"})
            else:
                return jsonify({"error": "会话不存在"}), 404
                
        except Exception as e:
            logger.error(f"❌ 重置会话失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    logger.info("✅ 智能问卷路由设置完成")

# 使用说明
INTEGRATION_INSTRUCTIONS = """
=== 智能问卷系统集成说明 ===

1. 在app.py中导入：
   from metagpt_questionnaire.smart_app_integration import setup_smart_questionnaire_routes

2. 设置路由：
   setup_smart_questionnaire_routes(app, _run_async, generate_tts_audio, shorten_for_avatar, report_manager)

3. 新的API端点：
   - POST /api/smart_questionnaire/start    - 启动智能问卷
   - POST /api/smart_questionnaire/reply    - 提交答案
   - GET  /api/smart_questionnaire/progress - 获取进度
   - POST /api/smart_questionnaire/reset    - 重置会话

4. 前端修改：
   - 将原有的 /api/metagpt_agent/* 调用改为 /api/smart_questionnaire/*
   - 检查返回的 retry 字段来判断是否需要重新回答
   - 检查 retry_reason 和 suggestion 字段来显示提示信息

5. 特性：
   - 本地书写问卷，便于控制
   - 智能答案审核，确保回答质量
   - 支持重新提问，提高数据质量
   - 使用DeepSeek优化问题表述
   - 自动生成专业报告

6. 问卷配置：
   - 在 local_questionnaire_simple.py 中直接编辑问卷
   - 支持依赖关系、选项限制、验证规则
   - 支持问题分类和优先级

这个系统更加可控，问卷内容完全由您控制，智能体只负责审核和优化。
"""

if __name__ == "__main__":
    print(INTEGRATION_INSTRUCTIONS)
