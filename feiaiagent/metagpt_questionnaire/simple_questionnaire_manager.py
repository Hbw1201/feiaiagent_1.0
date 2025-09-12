# -*- coding: utf-8 -*-
"""
简化版智能问卷管理器
基于医院本地问卷，使用DeepSeek和多个智能体完成智能调研
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .models.questionnaire import UserResponse, Question, Questionnaire
from .agents.base_agent import agent_registry

logger = logging.getLogger(__name__)

class SimpleQuestionnaireManager:
    """简化版智能问卷管理器"""
    
    def __init__(self):
        self.questionnaire: Optional[Questionnaire] = None
        self.answered_questions: List[UserResponse] = []
        self.current_question_index: int = 0
        self.conversation_history: List[Dict[str, Any]] = []
        
    def initialize_questionnaire(self, questionnaire: Questionnaire) -> bool:
        """初始化问卷"""
        try:
            self.questionnaire = questionnaire
            self.answered_questions.clear()
            self.current_question_index = 0
            self.conversation_history.clear()
            logger.info(f"✅ 问卷初始化成功: {questionnaire.title}")
            return True
        except Exception as e:
            logger.error(f"❌ 问卷初始化失败: {e}")
            return False
    
    async def get_next_question(self, user_answer: Optional[str] = None) -> Dict[str, Any]:
        """获取下一个问题"""
        try:
            # 处理用户回答
            if user_answer and self.current_question_index < len(self.questionnaire.questions):
                current_question = self.questionnaire.questions[self.current_question_index]
                
                # 使用答案验证智能体进行关键词检测和验证
                validation_result = await self._validate_answer_with_agent(user_answer, current_question)
                
                # 处理关键词检测结果
                if validation_result.get("detected"):
                    return await self._handle_keyword_detection(validation_result, current_question)
                
                # 处理重新回答意图
                if validation_result.get("redo"):
                    return await self._handle_redo_request(validation_result, current_question)
                
                # 处理跳过意图
                if validation_result.get("skip"):
                    return await self._handle_skip_request(validation_result, current_question)
                
                # 处理答案验证
                if not validation_result.get("valid", True):
                    return {
                        "status": "invalid_answer",
                        "question": current_question.text,
                        "error": validation_result.get("reason", "回答不够具体"),
                        "suggestion": validation_result.get("suggestion", "请提供更详细的回答"),
                        "retry": True
                    }
                
                # 记录有效回答
                self.answered_questions.append(UserResponse(
                    question_id=current_question.id,
                    answer=user_answer.strip()
                ))
                
                # 记录对话历史
                self.conversation_history.append({
                    "question": current_question.text,
                    "answer": user_answer.strip(),
                    "timestamp": datetime.now().isoformat()
                })
                
                self.current_question_index += 1
            
            # 检查是否完成
            if self.current_question_index >= len(self.questionnaire.questions):
                return await self._complete_questionnaire()
            
            # 获取下一个问题
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
    
    async def _validate_answer_with_agent(self, answer: str, question: Question) -> Dict[str, Any]:
        """使用答案验证智能体验证用户回答"""
        try:
            # 获取答案验证智能体
            validator = agent_registry.get_agent("答案审核专家")
            if validator:
                result = await validator.run(
                    user_answer=answer,
                    question_text=question.text,
                    current_index=self.current_question_index,
                    total_questions=len(self.questionnaire.questions)
                )
                return result
            else:
                # 降级到基本验证
                is_valid, msg = self._validate_answer(answer, question)
                return {"valid": is_valid, "reason": msg if not is_valid else "基本验证通过"}
        except Exception as e:
            logger.warning(f"⚠️ 智能体验证失败: {e}")
            # 降级到基本验证
            is_valid, msg = self._validate_answer(answer, question)
            return {"valid": is_valid, "reason": msg if not is_valid else "验证失败，使用基本验证"}
    
    async def _handle_keyword_detection(self, validation_result: Dict[str, Any], current_question: Question) -> Dict[str, Any]:
        """处理关键词检测结果"""
        intent_type = validation_result.get("intent_type")
        target_index = validation_result.get("target_index", self.current_question_index)
        message = validation_result.get("message", "好的，我们重新开始。")
        
        # 处理清空答案的逻辑
        if validation_result.get("clear_all_answers"):
            # 清空所有答案
            self.answered_questions.clear()
            self.conversation_history.clear()
            self.current_question_index = 0
            logger.info("🔄 已清空所有答案，重新开始问卷")
        elif validation_result.get("clear_previous_answer"):
            # 清空指定问题的答案
            self._clear_answer_at_index(target_index)
            self.current_question_index = target_index
            logger.info(f"🔄 已清空第{target_index + 1}题的答案")
        
        # 获取目标问题
        target_question = self.questionnaire.questions[target_index]
        optimized_question = await self._optimize_question_text(target_question)
        
        return {
            "status": "redo_question",
            "question": f"{message}\n\n{optimized_question}",
            "question_id": target_question.id,
            "category": target_question.category,
            "progress": f"{target_index + 1}/{len(self.questionnaire.questions)}",
            "is_complete": False,
            "redo": True,
            "target_index": target_index,
            "intent_type": intent_type
        }
    
    async def _handle_redo_request(self, validation_result: Dict[str, Any], current_question: Question) -> Dict[str, Any]:
        """处理重新回答请求"""
        target_index = validation_result.get("target_index", self.current_question_index)
        message = validation_result.get("message", "好的，我们重新回答这个问题。")
        
        # 清空指定问题的答案
        self._clear_answer_at_index(target_index)
        self.current_question_index = target_index
        
        # 获取目标问题
        target_question = self.questionnaire.questions[target_index]
        optimized_question = await self._optimize_question_text(target_question)
        
        return {
            "status": "redo_question",
            "question": f"{message}\n\n{optimized_question}",
            "question_id": target_question.id,
            "category": target_question.category,
            "progress": f"{target_index + 1}/{len(self.questionnaire.questions)}",
            "is_complete": False,
            "redo": True,
            "target_index": target_index
        }
    
    async def _handle_skip_request(self, validation_result: Dict[str, Any], current_question: Question) -> Dict[str, Any]:
        """处理跳过请求"""
        target_index = validation_result.get("target_index", self.current_question_index + 1)
        message = validation_result.get("message", "好的，我们跳过这道题。")
        
        # 更新当前问题索引
        self.current_question_index = target_index
        
        # 检查是否完成
        if self.current_question_index >= len(self.questionnaire.questions):
            return await self._complete_questionnaire()
        
        # 获取下一个问题
        next_question = self.questionnaire.questions[self.current_question_index]
        optimized_question = await self._optimize_question_text(next_question)
        
        return {
            "status": "next_question",
            "question": f"{message}\n\n{optimized_question}",
            "question_id": next_question.id,
            "category": next_question.category,
            "progress": f"{self.current_question_index + 1}/{len(self.questionnaire.questions)}",
            "is_complete": False,
            "skip": True
        }
    
    def _clear_answer_at_index(self, target_index: int):
        """清空指定索引的答案"""
        # 从已回答问题列表中移除
        self.answered_questions = [
            response for response in self.answered_questions 
            if response.question_id != self.questionnaire.questions[target_index].id
        ]
        
        # 从对话历史中移除
        self.conversation_history = [
            history for history in self.conversation_history
            if history.get("question") != self.questionnaire.questions[target_index].text
        ]
        
        logger.info(f"🗑️ 已清空第{target_index + 1}题的答案")
    
    def _validate_answer(self, answer: str, question: Question) -> Tuple[bool, str]:
        """验证用户回答"""
        if not answer or answer.strip() == "":
            return False, "请提供回答"
        
        # 基本验证
        if len(answer.strip()) < 1:
            return False, "回答太短，请提供更详细的信息"
        
        # 可以添加更多验证逻辑
        return True, "回答有效"
    
    async def _optimize_question_text(self, question: Question) -> str:
        """使用智能体优化问题表述"""
        try:
            # 获取对话智能体
            interviewer = agent_registry.get_agent("Dr. Aiden")
            if interviewer:
                # 使用智能体重新表述问题
                context = {
                    "question": question.text,
                    "conversation_history": self.conversation_history[-3:],  # 最近3轮对话
                    "question_category": question.category
                }
                result = await interviewer.process(context)
                return result.get("optimized_question", question.text)
            else:
                return question.text
        except Exception as e:
            logger.warning(f"⚠️ 问题优化失败，使用原始问题: {e}")
            return question.text
    
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
                "answered_questions": len(self.answered_questions)
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
                return result.get("report_content", "报告生成中...")
            else:
                # 使用简单报告生成
                return self._generate_simple_report()
        except Exception as e:
            logger.error(f"❌ 报告生成失败: {e}")
            return self._generate_simple_report()
    
    def _generate_simple_report(self) -> str:
        """生成简单报告"""
        report = "肺癌早筛风险评估报告\n\n" + "=" * 50 + "\n\n"
        
        # 基本信息
        report += f"问卷完成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n"
        report += f"总问题数: {len(self.questionnaire.questions)}\n"
        report += f"已回答数: {len(self.answered_questions)}\n\n"
        
        # 用户回答
        report += "【用户回答】\n"
        for i, response in enumerate(self.answered_questions, 1):
            question_text = "未知问题"
            for q in self.questionnaire.questions:
                if q.id == response.question_id:
                    question_text = q.text
                    break
            
            report += f"{i}. {question_text}\n"
            report += f"   回答: {response.answer}\n\n"
        
        # 简单建议
        report += "【建议】\n"
        report += "1. 建议定期体检\n"
        report += "2. 保持良好的生活习惯\n"
        report += "3. 如有异常症状及时就医\n"
        
        return report
    
    def get_progress(self) -> Dict[str, Any]:
        """获取进度信息"""
        return {
            "current_index": self.current_question_index,
            "total_questions": len(self.questionnaire.questions) if self.questionnaire else 0,
            "answered_count": len(self.answered_questions),
            "progress_percentage": (self.current_question_index / len(self.questionnaire.questions) * 100) if self.questionnaire else 0
        }
    
    def reset_session(self):
        """重置会话"""
        self.answered_questions.clear()
        self.current_question_index = 0
        self.conversation_history.clear()
        logger.info("🔄 会话已重置")
