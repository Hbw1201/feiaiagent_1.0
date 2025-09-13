# -*- coding: utf-8 -*-
"""
简化版智能问卷管理器
基于医院本地问卷，使用DeepSeek和多个智能体完成智能调研
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .models.questionnaire import UserResponse, Question, Questionnaire
from .agents.base_agent import agent_registry
from .persistent_agent_manager import process_with_persistent_agent

logger = logging.getLogger(__name__)

class SimpleQuestionnaireManager:
    """简化版智能问卷管理器"""
    
    def __init__(self):
        self.questionnaire: Optional[Questionnaire] = None
        self.current_question_index: int = 0
        self.answered_questions: List[UserResponse] = []
        self.conversation_history: List[Dict[str, Any]] = []
        self.is_completed: bool = False
        
        # 获取答案验证智能体
        self.answer_validator = agent_registry.get_agent("answer_validator")
    
    def initialize_questionnaire(self, questionnaire: Questionnaire) -> bool:
        """初始化问卷"""
        try:
            self.questionnaire = questionnaire
            self.current_question_index = 0
            self.answered_questions.clear()
            self.conversation_history.clear()
            self.is_completed = False
            logger.info(f"✅ 问卷初始化成功: {len(questionnaire.questions)}个问题")
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
                
                # 对于特定问题，使用智能体进行答案标准化
                standardized_answer = user_answer.strip()
                if current_question.id in ["smoking_history", "passive_smoking", "kitchen_fumes", "occupation_exposure", "family_cancer", "recent_symptoms"]:
                    standardized_answer = await self._standardize_yes_no_answer(current_question, user_answer)
                
                # 记录有效回答（使用标准化后的答案）
                self.answered_questions.append(UserResponse(
                    question_id=current_question.id,
                    answer=standardized_answer
                ))
                
                # 记录对话历史
                self.conversation_history.append({
                    "question": current_question.text,
                    "answer": user_answer.strip(),
                    "standardized_answer": standardized_answer,
                    "timestamp": datetime.now().isoformat()
                })
                
                self.current_question_index += 1
            
            # 检查是否完成
            if self.current_question_index >= len(self.questionnaire.questions):
                return await self._complete_questionnaire()
            
            # 智能跳题：找到下一个应该问的问题
            next_question_index = self._find_next_valid_question()
            
            if next_question_index == -1:
                return await self._complete_questionnaire()
            
            # 更新当前问题索引
            self.current_question_index = next_question_index
            
            # 获取下一个问题
            next_question = self.questionnaire.questions[self.current_question_index]
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
    def _find_next_valid_question(self) -> int:
        """智能跳题：找到下一个应该问的问题"""
        # 构建已回答问题的答案映射
        answers_dict = {}
        for response in self.answered_questions:
            answers_dict[response.question_id] = response.answer
        
        # 从当前索引开始查找下一个有效问题
        for i in range(self.current_question_index, len(self.questionnaire.questions)):
            question = self.questionnaire.questions[i]
            
            # 检查是否应该跳过这个问题
            if self._should_skip_question(question, answers_dict):
                logger.info(f"⏭️ 跳过问题: {question.id} - 根据跳题逻辑")
                continue
            
            # 检查依赖条件
            if self._is_question_available(question, answers_dict):
                logger.info(f"✅ 找到下一个问题: {question.id} (索引: {i})")
                return i
            else:
                logger.info(f"⏭️ 跳过问题: {question.id} (索引: {i}) - 依赖条件不满足")
        
        # 没有找到有效问题，问卷完成
        return -1
    
    def _should_skip_question(self, question: Question, answers_dict: Dict[str, str]) -> bool:
        """检查问题是否应该被跳过（基于跳题逻辑）"""
        # 获取跳题逻辑
        skip_ids = self._get_skip_ids(answers_dict)
        
        # 检查当前问题是否在跳过列表中
        if question.id in skip_ids:
            logger.info(f"⏭️ 问题 {question.id} 被跳过: 根据跳题逻辑")
            return True
        
        return False
    
    def _get_skip_ids(self, answers: Dict[str, str]) -> set:
        """返回基于已知答案应该跳过的问题ID集合"""
        skip_ids = set()
        
        # 吸烟史相关跳题逻辑
        # 如果用户不吸烟，跳过所有吸烟史相关的详细问题
        if answers.get('smoking_history') == '2' or self._is_negative_answer(answers.get('smoking_history', '')):
            skip_ids.update([
                'smoking_freq',           # 吸烟频率
                'smoking_years',          # 累计吸烟年数
                'smoking_quit',           # 目前是否戒烟
                'smoking_quit_years'      # 戒烟年数
            ])
        
        # 被动吸烟相关跳题逻辑
        # 如果用户不会被动吸烟，跳过所有被动吸烟相关的详细问题
        if answers.get('passive_smoking') == '2' or self._is_negative_answer(answers.get('passive_smoking', '')):
            skip_ids.update([
                'passive_smoking_freq',   # 被动吸烟频率
                'passive_smoking_years'   # 累计被动吸烟年数
            ])
        
        # 厨房油烟相关跳题逻辑
        # 如果用户不接触厨房油烟，跳过所有厨房油烟相关的详细问题
        if answers.get('kitchen_fumes') == '2' or self._is_negative_answer(answers.get('kitchen_fumes', '')):
            skip_ids.update([
                'kitchen_fumes_years'     # 累计厨房油烟接触年数
            ])
        
        # 职业致癌物质接触相关跳题逻辑
        # 如果用户不接触职业致癌物质，跳过所有职业暴露相关的详细问题
        if answers.get('occupation_exposure') == '2' or self._is_negative_answer(answers.get('occupation_exposure', '')):
            skip_ids.update([
                'occupation_exposure_details'  # 致癌物类型及累计接触年数
            ])
        
        return skip_ids
    
    def _is_negative_answer(self, answer: str) -> bool:
        """检查回答是否为否定回答"""
        if not answer:
            return False
        
        # 否定词汇模式
        negative_patterns = [
            r"不吸|不抽|没吸|没抽|否|没有|从不|不会|不接触|没接触|很少|不做饭"
        ]
        
        for pattern in negative_patterns:
            if re.search(pattern, answer):
                return True
        
        return False
    
    def _is_question_available(self, question: Question, answers_dict: Dict[str, str]) -> bool:
        """检查问题是否应该被问（基于依赖条件）"""
        # 检查依赖条件
        if question.validation_rules and "depends_on" in question.validation_rules:
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

    async def _standardize_yes_no_answer(self, question: Question, user_answer: str) -> str:
        """使用持久化智能体标准化是/否类问题的答案"""
        try:
            # 先进行简单的关键词检查，避免智能体误判
            user_answer_lower = user_answer.lower().strip()
            
            # 对于特定问题，进行特殊处理
            if question.id == "smoking_history" or "吸烟" in question.text:
                # 吸烟史问题的关键词检查
                positive_keywords = [
                    "我吸烟", "我抽烟", "有吸烟", "有抽烟", 
                    "吸烟的习惯", "抽烟的习惯", "会吸烟", "会抽烟", 
                    "有这个习惯", "有习惯", "我吸过", "我抽过",
                    "有吸过", "有抽过", "吸过烟", "抽过烟"
                ]
                negative_keywords = [
                    "不吸烟", "不抽烟", "没有吸烟", "没有抽烟", 
                    "从不吸烟", "从不抽烟", "不会吸烟", "不会抽烟",
                    "没吸过", "没抽过", "从不吸", "从不抽"
                ]
                
                # 检查否定关键词
                for neg_keyword in negative_keywords:
                    if neg_keyword in user_answer:
                        logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '否' (包含否定关键词: {neg_keyword})")
                        return "否"
                
                # 检查肯定关键词
                for pos_keyword in positive_keywords:
                    if pos_keyword in user_answer:
                        logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '是' (包含肯定关键词: {pos_keyword})")
                        return "是"
                
                # 检查简单的肯定词汇
                positive_words = ["有", "是", "会", "确实", "对", "嗯"]
                negative_words = ["没有", "不", "否", "没"]
                
                has_positive = any(word in user_answer for word in positive_words)
                has_negative = any(word in user_answer for word in negative_words)
                
                if has_positive and not has_negative:
                    logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '是' (包含肯定词汇且无否定词汇)")
                    return "是"
            
            elif question.id == "passive_smoking" or "被动吸烟" in question.text:
                # 被动吸烟问题的关键词检查
                positive_keywords = [
                    "会吸", "有吸", "经常吸", "接触二手烟", "吸二手烟",
                    "会接触", "有接触", "经常接触", "被动吸烟", "二手烟"
                ]
                negative_keywords = [
                    "不会吸", "没吸", "不吸", "不接触", "没接触",
                    "从不吸", "从不接触", "不会接触", "没有接触"
                ]
                
                # 检查否定关键词
                for neg_keyword in negative_keywords:
                    if neg_keyword in user_answer:
                        logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '否' (包含否定关键词: {neg_keyword})")
                        return "否"
                
                # 检查肯定关键词
                for pos_keyword in positive_keywords:
                    if pos_keyword in user_answer:
                        logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '是' (包含肯定关键词: {pos_keyword})")
                        return "是"
                
                # 检查简单的肯定词汇
                positive_words = ["有", "是", "会", "确实", "对", "嗯", "经常"]
                negative_words = ["没有", "不", "否", "没", "很少"]
                
                has_positive = any(word in user_answer for word in positive_words)
                has_negative = any(word in user_answer for word in negative_words)
                
                if has_positive and not has_negative:
                    logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '是' (包含肯定词汇且无否定词汇)")
                    return "是"
            
            elif question.id == "kitchen_fumes" or "厨房油烟" in question.text:
                # 厨房油烟问题的关键词检查
                positive_keywords = [
                    "会做饭", "有做饭", "经常做饭", "接触油烟", "炒菜",
                    "会炒菜", "有炒菜", "经常炒菜", "厨房油烟", "油烟"
                ]
                negative_keywords = [
                    "不会做饭", "没做饭", "不做饭", "不炒菜", "没炒菜",
                    "从不做饭", "从不炒菜", "不会炒菜", "没有做饭"
                ]
                
                # 检查否定关键词
                for neg_keyword in negative_keywords:
                    if neg_keyword in user_answer:
                        logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '否' (包含否定关键词: {neg_keyword})")
                        return "否"
                
                # 检查肯定关键词
                for pos_keyword in positive_keywords:
                    if pos_keyword in user_answer:
                        logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '是' (包含肯定关键词: {pos_keyword})")
                        return "是"
                
                # 检查简单的肯定词汇
                positive_words = ["有", "是", "会", "确实", "对", "嗯", "经常"]
                negative_words = ["没有", "不", "否", "没", "很少"]
                
                has_positive = any(word in user_answer for word in positive_words)
                has_negative = any(word in user_answer for word in negative_words)
                
                if has_positive and not has_negative:
                    logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '是' (包含肯定词汇且无否定词汇)")
                    return "是"
            
            elif question.id == "occupation_exposure" or "职业" in question.text or "致癌" in question.text:
                # 职业致癌物质接触问题的关键词检查
                positive_keywords = [
                    "会接触", "有接触", "经常接触", "工作接触", "接触物质",
                    "会工作", "有工作", "经常工作", "职业暴露", "致癌物质"
                ]
                negative_keywords = [
                    "不会接触", "没接触", "不接触", "不工作", "没工作",
                    "从不接触", "从不工作", "不会工作", "没有接触"
                ]
                
                # 检查否定关键词
                for neg_keyword in negative_keywords:
                    if neg_keyword in user_answer:
                        logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '否' (包含否定关键词: {neg_keyword})")
                        return "否"
                
                # 检查肯定关键词
                for pos_keyword in positive_keywords:
                    if pos_keyword in user_answer:
                        logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '是' (包含肯定关键词: {pos_keyword})")
                        return "是"
                
                # 检查简单的肯定词汇
                positive_words = ["有", "是", "会", "确实", "对", "嗯", "经常", "可能"]
                negative_words = ["没有", "不", "否", "没", "很少"]
                
                has_positive = any(word in user_answer for word in positive_words)
                has_negative = any(word in user_answer for word in negative_words)
                
                if has_positive and not has_negative:
                    logger.info(f"✅ 关键词检查标准化答案: '{user_answer}' -> '是' (包含肯定词汇且无否定词汇)")
                    return "是"
                
            # 如果关键词检查没有匹配，继续使用智能体处理
            context = {
                "question": question.text,
                "user_answer": user_answer,
                "question_category": question.category,
                "task": "standardize_yes_no_answer",
                "instructions": f"""
                请将用户的回答标准化为"是"或"否"。
                
                问题：{question.text}
                用户回答：{user_answer}
                
                ⚠️ 重要：请仔细分析用户回答的含义，不要被表面文字误导！
                
                核心判断规则：
                - 如果用户表示有、是、会、存在、曾经、以前、现在等肯定含义，返回"是"
                - 如果用户表示没有、不是、不会、不存在、从不、从不、没有等否定含义，返回"否"
                
                🚬 吸烟史问题特别说明：
                - 以下回答必须识别为"是"（表示有吸烟史）：
                  * "我吸烟"、"我抽烟"、"我吸过烟"、"我抽过烟"
                  * "有吸烟的习惯"、"有抽烟的习惯"、"有吸烟史"、"有这个习惯"
                  * "有"、"是"、"会"、"曾经"、"以前"、"现在"、"确实"
                  * "偶尔"、"经常"、"每天"、"少量"、"很多"等表示有吸烟行为的回答
                  * 任何包含"有"、"是"、"会"、"确实"等肯定词汇的回答
                - 以下回答才识别为"否"（表示没有吸烟史）：
                  * "我不吸烟"、"我不抽烟"、"从不吸烟"、"从来不"
                  * "没有吸烟的习惯"、"没有抽烟的习惯"、"没有吸烟史"
                  * "没有"、"不是"、"不会"、"从不"、"否"、"不"
                
                📝 标准示例：
                - "有吸烟的习惯" -> "是"（包含"有"字，明确表示肯定）
                - "有吸烟的习惯。" -> "是"（包含"有"字，明确表示肯定）
                - "我吸烟" -> "是"（直接表示有吸烟行为）
                - "我吸烟。" -> "是"（直接表示有吸烟行为）
                - "我不吸烟" -> "否"（包含"不"字，表示否定）
                - "没有" -> "否"（明确表示否定）
                
                请严格按照以上规则判断，如果回答包含"有"字，必须返回"是"！
                
                返回格式：
                {{
                    "standardized_answer": "是" 或 "否",
                    "reasoning": "判断理由"
                }}
                """
            }
            
            # 使用持久化智能体，避免重复初始化
            result = await process_with_persistent_agent("Dr. Aiden", context)
            standardized_answer = result.get("standardized_answer", "否")
            
            # 验证结果
            if standardized_answer in ["是", "否"]:
                logger.info(f"✅ 持久化智能体标准化答案: '{user_answer}' -> '{standardized_answer}'")
                return standardized_answer
            else:
                logger.warning(f"⚠️ 智能体返回非标准答案: {standardized_answer}，使用默认值'否'")
                return "否"
                
        except Exception as e:
            logger.error(f"❌ 答案标准化失败: {e}")
            return "否"  # 出错时默认返回"否"以跳过相关问题

