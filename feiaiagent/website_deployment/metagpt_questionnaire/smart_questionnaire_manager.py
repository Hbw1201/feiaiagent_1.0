# -*- coding: utf-8 -*-
"""
智能问卷管理器
支持答案审核和重新提问功能
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .models.questionnaire import UserResponse, Question, Questionnaire
from .agents.base_agent import agent_registry
from .local_questionnaire_simple import QUESTIONS, QUESTIONNAIRE_CONFIG, get_question_by_id, get_next_question_index, validate_answer, generate_simple_report

logger = logging.getLogger(__name__)

class SmartQuestionnaireManager:
    """智能问卷管理器 - 支持答案审核和重新提问"""
    
    def __init__(self):
        self.questionnaire: Optional[Questionnaire] = None
        self.answered_questions: List[UserResponse] = []
        self.current_question_index: int = 0
        self.conversation_history: List[Dict[str, Any]] = []
        self.pending_retry_questions: List[Dict[str, Any]] = []  # 待重新提问的问题
        self.answer_validator = None
        
    def initialize_questionnaire(self) -> bool:
        """初始化问卷"""
        try:
            # 创建问卷对象
            self.questionnaire = Questionnaire(
                id=f"smart_questionnaire_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                title=QUESTIONNAIRE_CONFIG["title"],
                description=QUESTIONNAIRE_CONFIG["description"],
                version=QUESTIONNAIRE_CONFIG["version"],
                estimated_time=QUESTIONNAIRE_CONFIG["estimated_time"]
            )
            
            # 转换问题格式
            questions = []
            for q_data in QUESTIONS:
                question = Question(
                    id=q_data["id"],
                    text=q_data["text"],
                    type="text",  # 添加必需的类型参数
                    help_text=q_data.get("prompt", q_data["text"]),
                    category=q_data["category"],
                    required=q_data.get("required", False),
                    validation_rules={
                        "validation": q_data.get("validation", ""),
                        "options": q_data.get("options", []),
                        "depends_on": q_data.get("depends_on")
                    }
                )
                questions.append(question)
            
            self.questionnaire.questions = questions
            
            # 初始化答案审核器
            self.answer_validator = agent_registry.get_agent("答案审核专家")
            if not self.answer_validator:
                logger.warning("⚠️ 答案审核智能体未找到，将使用基本验证")
            
            # 重置状态
            self.answered_questions.clear()
            self.current_question_index = 0
            self.conversation_history.clear()
            self.pending_retry_questions.clear()
            
            logger.info(f"✅ 智能问卷初始化成功: {self.questionnaire.title}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 智能问卷初始化失败: {e}")
            return False
    
    async def get_next_question(self, user_answer: Optional[str] = None) -> Dict[str, Any]:
        """获取下一个问题"""
        try:
            # 处理用户回答
            if user_answer and self.current_question_index < len(self.questionnaire.questions):
                await self._process_user_answer(user_answer)
            
            # 检查是否有待重新提问的问题
            if self.pending_retry_questions:
                return await self._handle_retry_question()
            
            # 智能跳题：找到下一个应该问的问题
            next_question_index = self._find_next_valid_question()
            
            # 检查是否完成
            if next_question_index >= len(self.questionnaire.questions):
                return await self._complete_questionnaire()
            
            # 更新当前问题索引
            self.current_question_index = next_question_index
            next_question = self.questionnaire.questions[self.current_question_index]
            
            # 使用智能体优化问题表述
            optimized_question = await self._optimize_question_text(next_question)
            
            return {
                "status": "next_question",
                "question": optimized_question,
                "question_id": next_question.id,
                "category": next_question.category,
                "progress": f"{self.current_question_index + 1}/{len(self.questionnaire.questions)}",
                "is_complete": False
            }
            
        except Exception as e:
            logger.error(f"❌ 获取下一个问题失败: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _process_user_answer(self, user_answer: str) -> None:
        """处理用户回答"""
        current_question = self.questionnaire.questions[self.current_question_index]
        
        # 基本验证
        is_valid, validation_msg = validate_answer(current_question.id, user_answer)
        if not is_valid:
            # 基本验证失败，直接重新提问
            self.pending_retry_questions.append({
                "question": current_question,
                "answer": user_answer,
                "reason": validation_msg,
                "retry_count": 1
            })
            return
        
        # 使用智能体审核
        if self.answer_validator:
            validation_result = await self.answer_validator.process({
                "question_text": current_question.text,
                "user_answer": user_answer,
                "question_category": current_question.category,
                "validation_rules": current_question.validation_rules
            })
            
            if not validation_result.get("valid", True):
                # 智能体审核失败，加入重试队列
                self.pending_retry_questions.append({
                    "question": current_question,
                    "answer": user_answer,
                    "reason": validation_result.get("reason", "回答质量不符合要求"),
                    "suggestion": validation_result.get("suggestion", ""),
                    "retry_count": 1
                })
                return
        
        # 审核通过，记录答案
        self.answered_questions.append(UserResponse(
            question_id=current_question.id,
            answer=user_answer.strip()
        ))
        
        # 记录对话历史
        self.conversation_history.append({
            "question": current_question.text,
            "answer": user_answer.strip(),
            "timestamp": datetime.now().isoformat(),
            "validated": True
        })
        
        # 移动到下一个问题
        self.current_question_index += 1
        
        logger.info(f"✅ 答案审核通过: {current_question.id}")
    
    async def _handle_retry_question(self) -> Dict[str, Any]:
        """处理重新提问"""
        retry_item = self.pending_retry_questions.pop(0)
        question = retry_item["question"]
        reason = retry_item["reason"]
        suggestion = retry_item.get("suggestion", "")
        
        # 构建重新提问的文本
        retry_text = f"刚才的回答可能不够完整，请重新回答：\n{question.help_text}"
        if suggestion:
            retry_text += f"\n\n建议：{suggestion}"
        
        # 使用智能体优化重新提问的表述
        optimized_question = await self._optimize_retry_question(retry_text, question)
        
        return {
            "status": "retry_question",
            "question": optimized_question,
            "question_id": question.id,
            "category": question.category,
            "reason": reason,
            "suggestion": suggestion,
            "retry": True,
            "progress": f"{self.current_question_index + 1}/{len(self.questionnaire.questions)}",
            "is_complete": False
        }
    
    async def _optimize_question_text(self, question: Question) -> str:
        """优化问题表述"""
        try:
            # 获取对话智能体
            interviewer = agent_registry.get_agent("Dr. Aiden")
            if interviewer:
                context = {
                    "question": question.help_text,
                    "conversation_history": self.conversation_history[-3:],
                    "question_category": question.category
                }
                result = await interviewer.process(context)
                return result.get("optimized_question", question.help_text)
            else:
                return question.help_text
        except Exception as e:
            logger.warning(f"⚠️ 问题优化失败: {e}")
            return question.help_text
    
    async def _optimize_retry_question(self, retry_text: str, question: Question) -> str:
        """优化重新提问的表述"""
        try:
            # 获取对话智能体
            interviewer = agent_registry.get_agent("Dr. Aiden")
            if interviewer:
                context = {
                    "question": retry_text,
                    "conversation_history": self.conversation_history[-2:],
                    "question_category": question.category,
                    "is_retry": True
                }
                result = await interviewer.process(context)
                return result.get("optimized_question", retry_text)
            else:
                return retry_text
        except Exception as e:
            logger.warning(f"⚠️ 重新提问优化失败: {e}")
            return retry_text
    
    async def _complete_questionnaire(self) -> Dict[str, Any]:
        """完成问卷"""
        try:
            # 生成分析报告
            report = await self._generate_report()
            
            return {
                "status": "completed",
                "is_complete": True,
                "report": report,
                "total_questions": len(self.questionnaire.questions),
                "answered_questions": len(self.answered_questions),
                "retry_questions": len(self.pending_retry_questions)
            }
        except Exception as e:
            logger.error(f"❌ 问卷完成处理失败: {e}")
            return {
                "status": "completed",
                "is_complete": True,
                "error": str(e),
                "report": "报告生成失败，请联系管理员"
            }
    
    async def _generate_report(self) -> str:
        """生成问卷报告"""
        try:
            # 使用报告生成智能体
            generator = agent_registry.get_agent("报告生成专家")
            if generator:
                # 准备数据
                analysis_data = {
                    "questionnaire": self.questionnaire,
                    "answered_questions": self.answered_questions,
                    "conversation_history": self.conversation_history
                }
                
                result = await generator.process(analysis_data)
                return result.get("report_content", self._generate_simple_report())
            else:
                return self._generate_simple_report()
        except Exception as e:
            logger.error(f"❌ 报告生成失败: {e}")
            return self._generate_simple_report()
    
    def _find_next_valid_question(self) -> int:
        """智能跳题：找到下一个应该问的问题"""
        # 构建已回答问题的答案映射
        answers_dict = {}
        for response in self.answered_questions:
            answers_dict[response.question_id] = response.answer
        
        # 从当前索引开始查找下一个有效问题
        for i in range(self.current_question_index, len(self.questionnaire.questions)):
            question = self.questionnaire.questions[i]
            
            # 检查依赖条件
            if self._is_question_available(question, answers_dict):
                logger.info(f"✅ 找到下一个问题: {question.id} (索引: {i})")
                return i
            else:
                logger.info(f"⏭️ 跳过问题: {question.id} (索引: {i}) - 依赖条件不满足")
        
        # 没有找到有效问题，问卷完成
        return len(self.questionnaire.questions)
    
    def _is_question_available(self, question: Question, answers_dict: Dict[str, str]) -> bool:
        """检查问题是否应该被问（基于依赖条件）"""
        # 检查依赖条件
        if "depends_on" in question.validation_rules:
            depends_on = question.validation_rules["depends_on"]
            if depends_on:
                dependent_question_id = depends_on["id"]
                required_value = depends_on["value"]
                
                # 检查依赖问题的答案
                dependent_answer = answers_dict.get(dependent_question_id, "")
                if dependent_answer != required_value:
                    logger.info(f"⏭️ 问题 {question.id} 被跳过: 依赖问题 {dependent_question_id} 的答案是 '{dependent_answer}'，需要 '{required_value}'")
                    return False
        
        return True
    
    def _generate_simple_report(self) -> str:
        """生成简单报告"""
        # 转换答案为字典格式
        answers_dict = {}
        for response in self.answered_questions:
            answers_dict[response.question_id] = response.answer
        
        return generate_simple_report(answers_dict)
    
    def get_progress(self) -> Dict[str, Any]:
        """获取进度信息"""
        return {
            "current_index": self.current_question_index,
            "total_questions": len(self.questionnaire.questions) if self.questionnaire else 0,
            "answered_count": len(self.answered_questions),
            "retry_count": len(self.pending_retry_questions),
            "progress_percentage": (self.current_question_index / len(self.questionnaire.questions) * 100) if self.questionnaire else 0
        }
    
    def reset_session(self):
        """重置会话"""
        self.answered_questions.clear()
        self.current_question_index = 0
        self.conversation_history.clear()
        self.pending_retry_questions.clear()
        logger.info("🔄 会话已重置")
