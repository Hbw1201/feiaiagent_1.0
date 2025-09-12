# -*- coding: utf-8 -*-
"""
智能问题选择专家
基于多因素优先级评分系统，智能选择下一个问题
"""

import logging
import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import asyncio

from .base_agent import BaseAgent, register_agent
from ..models.questionnaire import Question, Questionnaire

logger = logging.getLogger(__name__)

@register_agent
class IntelligentQuestionSelectorAgent(BaseAgent):
    """智能问题选择专家"""
    
    def __init__(self):
        super().__init__(
            name="智能问题选择专家",
            description="基于多因素优先级评分系统，智能选择下一个问题",
            expertise=["问题选择", "优先级评估", "逻辑推理", "用户体验优化"]
        )
        
        # 问题分类优先级权重
        self.category_weights = {
            "基本信息": 1.0,      # 基础信息，优先级最高
            "身体指标": 0.9,      # 身体指标，重要
            "吸烟史": 0.95,       # 吸烟史，肺癌风险核心因素
            "被动吸烟": 0.8,      # 被动吸烟，重要风险因素
            "厨房油烟": 0.7,      # 厨房油烟，中等重要
            "社会信息": 0.6,      # 社会信息，一般重要
            "职业暴露": 0.85,     # 职业暴露，高风险因素
            "肿瘤相关史": 0.9,    # 肿瘤史，高风险因素
            "影像检查": 0.75,     # 影像检查，重要
            "呼吸系统疾病史": 0.8, # 呼吸系统疾病，重要
            "近期症状": 0.9,      # 近期症状，高风险因素
            "健康自评": 0.6       # 健康自评，一般重要
        }
        
        # 风险指标相关性权重
        self.risk_factors = {
            "smoking_history": 0.95,      # 吸烟史
            "passive_smoking": 0.8,       # 被动吸烟
            "occupation_exposure": 0.85,  # 职业暴露
            "family_cancer_history": 0.9, # 家族肿瘤史
            "personal_tumor_history": 0.9, # 个人肿瘤史
            "recent_symptoms": 0.9,       # 近期症状
            "chronic_lung_disease": 0.8,  # 慢性肺部疾病
            "kitchen_fumes": 0.7          # 厨房油烟
        }
    
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """处理问题选择请求"""
        try:
            answered_questions = data.get("answered_questions", [])
            available_questions = data.get("available_questions", [])
            conversation_history = data.get("conversation_history", [])
            user_profile = data.get("user_profile", {})
            
            logger.info(f"🔍 智能问题选择开始，可用问题数: {len(available_questions)}")
            
            if not available_questions:
                return {
                    "status": "completed",
                    "message": "所有问题已完成",
                    "selected_question": None
                }
            
            # 计算每个问题的优先级分数
            question_scores = []
            for question in available_questions:
                score = await self._calculate_question_score(
                    question, answered_questions, conversation_history, user_profile
                )
                question_scores.append((question, score))
            
            # 按分数排序，选择最高分的问题
            question_scores.sort(key=lambda x: x[1], reverse=True)
            selected_question, score = question_scores[0]
            
            logger.info(f"✅ 选择问题: {selected_question.text} (分数: {score:.2f})")
            
            return {
                "status": "next_question",
                "selected_question": selected_question,
                "score": score,
                "reasoning": self._generate_reasoning(selected_question, score, question_scores[:3])
            }
            
        except Exception as e:
            logger.error(f"❌ 智能问题选择失败: {e}")
            return {
                "status": "error",
                "message": f"问题选择失败: {str(e)}",
                "selected_question": None
            }
    
    async def _calculate_question_score(self, question: Question, answered_questions: List, 
                                      conversation_history: List, user_profile: Dict) -> float:
        """计算问题的优先级分数"""
        score = 0.0
        
        # 1. 基础分类权重 (0-1)
        category_weight = self.category_weights.get(question.category, 0.5)
        score += category_weight * 0.3
        
        # 2. 风险因素相关性 (0-1)
        risk_score = self._calculate_risk_relevance(question, answered_questions, user_profile)
        score += risk_score * 0.25
        
        # 3. 逻辑流程连贯性 (0-1)
        flow_score = self._calculate_flow_coherence(question, answered_questions, conversation_history)
        score += flow_score * 0.2
        
        # 4. 依赖关系满足度 (0-1)
        dependency_score = self._calculate_dependency_satisfaction(question, answered_questions)
        score += dependency_score * 0.15
        
        # 5. 用户体验优化 (0-1)
        ux_score = self._calculate_ux_optimization(question, conversation_history, user_profile)
        score += ux_score * 0.1
        
        return min(score, 1.0)  # 确保分数不超过1.0
    
    def _calculate_risk_relevance(self, question: Question, answered_questions: List, user_profile: Dict) -> float:
        """计算风险因素相关性"""
        if not question.id:
            return 0.5
        
        # 检查是否是高风险问题
        high_risk_keywords = ["吸烟", "肿瘤", "症状", "暴露", "家族"]
        question_text = question.text.lower()
        
        risk_relevance = 0.0
        for keyword in high_risk_keywords:
            if keyword in question_text:
                risk_relevance += 0.2
        
        # 根据已回答问题调整
        if answered_questions:
            # 如果已经回答了高风险问题，优先问相关的高风险问题
            answered_high_risk = any(
                any(keyword in str(q).lower() for keyword in high_risk_keywords)
                for q in answered_questions
            )
            if answered_high_risk and risk_relevance > 0:
                risk_relevance += 0.3
        
        return min(risk_relevance, 1.0)
    
    def _calculate_flow_coherence(self, question: Question, answered_questions: List, 
                                conversation_history: List) -> float:
        """计算逻辑流程连贯性"""
        if not answered_questions:
            return 0.8  # 第一个问题，给较高分数
        
        # 检查问题分类的连续性
        last_question_category = answered_questions[-1].category if answered_questions else ""
        current_category = question.category
        
        # 同分类问题有连续性加分
        if last_question_category == current_category:
            return 0.9
        # 相关分类有中等分数
        elif self._are_categories_related(last_question_category, current_category):
            return 0.7
        else:
            return 0.5
    
    def _calculate_dependency_satisfaction(self, question: Question, answered_questions: List) -> float:
        """计算依赖关系满足度"""
        # 检查问题是否有依赖关系
        if hasattr(question, 'depends_on') and question.depends_on:
            # 检查依赖是否满足
            dependency_met = self._check_dependency(question.depends_on, answered_questions)
            if dependency_met:
                return 1.0
            else:
                # 依赖不满足，检查是否有自动填充值
                auto_fill_value = getattr(question, 'auto_fill_value', None)
                if auto_fill_value:
                    # 有自动填充值，给中等分数（可以询问但会自动填充）
                    return 0.6
                else:
                    # 无自动填充值，跳过
                    return 0.0
        else:
            # 无依赖关系，给中等分数
            return 0.8
    
    def _calculate_ux_optimization(self, question: Question, conversation_history: List, 
                                 user_profile: Dict) -> float:
        """计算用户体验优化分数"""
        score = 0.5  # 基础分数
        
        # 根据用户年龄调整问题优先级
        if user_profile.get("age"):
            age = int(user_profile["age"])
            if age >= 50:  # 高龄用户，优先问高风险问题
                if any(keyword in question.text for keyword in ["症状", "肿瘤", "检查"]):
                    score += 0.3
        
        # 根据对话历史调整
        if conversation_history:
            # 如果用户回答简短，优先问简单问题
            recent_answers = [h.get("answer", "") for h in conversation_history[-3:]]
            avg_answer_length = sum(len(str(a)) for a in recent_answers) / len(recent_answers)
            
            if avg_answer_length < 10:  # 简短回答
                if question.type == "单选" or question.type == "数值":
                    score += 0.2
        
        return min(score, 1.0)
    
    def _are_categories_related(self, cat1: str, cat2: str) -> bool:
        """判断两个问题分类是否相关"""
        related_groups = [
            ["吸烟史", "被动吸烟"],
            ["肿瘤相关史", "家族史"],
            ["近期症状", "健康自评"],
            ["职业暴露", "社会信息"],
            ["身体指标", "基本信息"]
        ]
        
        for group in related_groups:
            if cat1 in group and cat2 in group:
                return True
        return False
    
    def _check_dependency(self, dependency: Dict, answered_questions: List) -> bool:
        """检查依赖关系是否满足"""
        if not dependency:
            return True
        
        question_id = dependency.get("id")
        required_value = dependency.get("value")
        possible_values = dependency.get("values", [required_value])  # 支持多个可能的值
        
        if not question_id:
            return True
        
        # 查找已回答问题中是否有匹配的依赖
        for answered_q in answered_questions:
            if str(answered_q.id) == str(question_id):
                answer_text = str(answered_q.answer).lower()
                # 检查是否匹配任何一个可能的值
                for value in possible_values:
                    value_lower = value.lower()
                    # 更精确的匹配：检查是否包含完整的值，且不包含否定词
                    if (value_lower in answer_text and 
                        not any(neg_word in answer_text for neg_word in ['不', '没', '无', '否', '没有', '不会', '不会'])):
                        return True
        return False
    
    def _generate_reasoning(self, selected_question: Question, score: float, 
                          top_questions: List[Tuple]) -> str:
        """生成选择理由"""
        reasons = []
        
        # 分数分析
        if score > 0.8:
            reasons.append("高优先级问题")
        elif score > 0.6:
            reasons.append("中等优先级问题")
        else:
            reasons.append("基础问题")
        
        # 分类分析
        if selected_question.category in ["吸烟史", "肿瘤相关史", "近期症状"]:
            reasons.append("高风险因素")
        
        # 逻辑分析
        if len(top_questions) > 1:
            score_diff = top_questions[0][1] - top_questions[1][1]
            if score_diff > 0.1:
                reasons.append("明显优于其他选项")
        
        return f"选择理由: {', '.join(reasons)} (分数: {score:.2f})"
    
    async def run(self, *args, **kwargs) -> Dict[str, Any]:
        """运行智能体（兼容接口）"""
        return await self.process(kwargs if kwargs else args[0] if args else {})
