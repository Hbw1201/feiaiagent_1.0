# -*- coding: utf-8 -*-
"""
Conversational Interviewer Agent (Intelligent Version)
- Dynamically selects the next best question based on conversation history and inferred facts.
- Handles complex skip logic and dependencies defined in the questionnaire.
- Rephrases questions to be less robotic and more like a real doctor.
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List, Set

from .base_agent import BaseAgent, register_agent
from ..models.questionnaire import Questionnaire, Question, UserResponse

logger = logging.getLogger(__name__)

@register_agent
class ConversationalInterviewerAgent(BaseAgent):
    """An intelligent conversational agent that dynamically selects questions to conduct a personalized interview."""

    def __init__(self, name: str = "Dr. Aiden", description: str = "A friendly and intelligent AI doctor who conducts personalized health interviews.", expertise: List[str] = ["conversational_ai", "medical_interview", "dynamic_questioning"]):
        super().__init__(name, description, expertise)

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        优化问题表述，使其更自然友好
        """
        try:
            question = context.get("question", "")
            conversation_history = context.get("conversation_history", [])
            question_category = context.get("question_category", "")
            
            # 使用DeepSeek优化问题表述
            optimized_question = await self._optimize_question_with_llm(
                question, conversation_history, question_category
            )
            
            return {
                "status": "success",
                "optimized_question": optimized_question,
                "original_question": question
            }
            
        except Exception as e:
            logger.error(f"❌ 问题优化失败: {e}")
            return {
                "status": "error",
                "optimized_question": context.get("question", ""),
                "error": str(e)
            }

    def _infer_facts_from_history(self, history: List[UserResponse], questionnaire: Questionnaire) -> Dict[str, str]:
        """Infers facts like gender or smoking status from free-text answers."""
        facts = {}
        full_text = " ".join([r.answer for r in history])

        # Infer gender
        if re.search(r"男|先生|先生", full_text):
            facts['gender'] = '1'
        elif re.search(r"女|女士|小姐", full_text):
            facts['gender'] = '2'

        # Infer smoking status from the relevant answer
        smoking_response = next((r.answer for r in history if r.question_id == 'smoking_history'), None)
        if smoking_response:
            # 先检查否定回答
            if re.search(r"不吸|不抽|没吸|没抽|否|没有|从不|不会", smoking_response):
                facts['smoking_history'] = '2'
            # 再检查肯定回答 - 更全面的模式匹配
            elif re.search(r"我吸|我抽|有吸|有抽|吸.*习惯|抽.*习惯|会吸|会抽|确实|是|有", smoking_response):
                facts['smoking_history'] = '1'
        
        # Infer passive smoking status
        passive_smoking_response = next((r.answer for r in history if r.question_id == 'passive_smoking'), None)
        if passive_smoking_response:
            # 先检查否定回答
            if re.search(r"不会|不吸|没吸|否|没有|从不|很少|不接触", passive_smoking_response):
                facts['passive_smoking'] = '2'
            # 再检查肯定回答 - 更全面的模式匹配
            elif re.search(r"会.*吸|有.*吸|经常.*吸|接触.*烟|吸.*二手|是|有|会|经常", passive_smoking_response):
                facts['passive_smoking'] = '1'
        
        # Infer kitchen fumes exposure
        kitchen_fumes_response = next((r.answer for r in history if r.question_id == 'kitchen_fumes'), None)
        if kitchen_fumes_response:
            # 先检查否定回答
            if re.search(r"不会|不接触|没接触|否|没有|从不|很少|不做饭|不炒菜", kitchen_fumes_response):
                facts['kitchen_fumes'] = '2'
            # 再检查肯定回答 - 更全面的模式匹配
            elif re.search(r"会.*做饭|有.*做饭|经常.*做饭|接触.*油烟|炒菜|做饭|是|有|会|经常", kitchen_fumes_response):
                facts['kitchen_fumes'] = '1'
        
        # Infer occupational exposure
        occupation_exposure_response = next((r.answer for r in history if r.question_id == 'occupation_exposure'), None)
        if occupation_exposure_response:
            # 先检查否定回答
            if re.search(r"不会|不接触|没接触|否|没有|从不|很少|不工作", occupation_exposure_response):
                facts['occupation_exposure'] = '2'
            # 再检查肯定回答 - 更全面的模式匹配
            elif re.search(r"会.*接触|有.*接触|经常.*接触|工作.*接触|接触.*物质|是|有|会|经常|可能", occupation_exposure_response):
                facts['occupation_exposure'] = '1'
        
        return facts

    def _get_skip_ids(self, answers: Dict[str, str]) -> Set[str]:
        """Returns a set of question IDs to skip based on known answers."""
        skip_ids = set()
        
        # 吸烟史相关跳题逻辑
        # 如果用户不吸烟，跳过所有吸烟史相关的详细问题
        if answers.get('smoking_history') == '2':
            skip_ids.update([
                'smoking_freq',           # 吸烟频率
                'smoking_years',          # 累计吸烟年数
                'smoking_quit',           # 目前是否戒烟
                'smoking_quit_years'      # 戒烟年数
            ])
        
        # 被动吸烟相关跳题逻辑
        # 如果用户不会被动吸烟，跳过所有被动吸烟相关的详细问题
        if answers.get('passive_smoking') == '2':
            skip_ids.update([
                'passive_smoking_freq',   # 被动吸烟频率
                'passive_smoking_years'   # 累计被动吸烟年数
            ])
        
        # 厨房油烟相关跳题逻辑
        # 如果用户不接触厨房油烟，跳过所有厨房油烟相关的详细问题
        if answers.get('kitchen_fumes') == '2':
            skip_ids.update([
                'kitchen_fumes_years'     # 累计厨房油烟接触年数
            ])
        
        # 职业致癌物质接触相关跳题逻辑
        # 如果用户不接触职业致癌物质，跳过所有职业暴露相关的详细问题
        if answers.get('occupation_exposure') == '2':
            skip_ids.update([
                'occupation_exposure_details'  # 致癌物类型及累计接触年数
            ])
        
        return skip_ids

    def _are_dependencies_met(self, question: Question, answers: Dict[str, str]) -> bool:
        """Checks if a question's dependencies are satisfied by the current answers."""
        deps = question.validation_rules.get('depends_on') if question.validation_rules else None
        if not deps:
            return True
        
        dep_id = deps.get('id')
        required_value = str(deps.get('value'))
        
        actual_answer = answers.get(dep_id)
        return actual_answer == required_value

    async def _determine_next_question(self, history: List[UserResponse], facts: Dict[str, str], candidates: List[Question], questionnaire: Questionnaire) -> Optional[Question]:
        """Uses an LLM to determine the most logical next question from a list of candidates."""
        history_str = "\n".join([
            f"- Q ({q.id}): {q.text} \n- A: {r.answer}"
            for r in history
            for q in questionnaire.questions if q.id == r.question_id
        ])
        if not history_str:
            history_str = "尚未回答任何问题。"

        facts_str = json.dumps(facts, ensure_ascii=False)
        candidates_str = "\n".join([f"- ID: {q.id}, Question: {q.text}" for q in candidates])

        prompt = self.get_prompt(
            "intelligent_question_selection",
            history=history_str,
            inferred_facts=facts_str,
            candidate_questions=candidates_str
        )

        try:
            llm_response = await self.call_llm(prompt)
            logger.debug(f"LLM response for next question: {llm_response}")
            match = re.search(r'{\s*"next_question_id"\s*:\s*"(.*?)"\s*}', llm_response)
            if match:
                next_question_id = match.group(1)
                selected = next((q for q in candidates if q.id == next_question_id), None)
                if not selected:
                    logger.warning(f"LLM selected an invalid question ID '{next_question_id}' not in candidates.")
                return selected
            else:
                logger.warning(f"LLM response was not in the expected JSON format: {llm_response}")
        except Exception as e:
            logger.error(f"Failed to determine next question using LLM: {e}")
        
        return None # Fallback

    async def _optimize_question_with_llm(self, question: str, conversation_history: List[Dict], question_category: str) -> str:
        """使用DeepSeek优化问题表述"""
        try:
            # 构建对话历史上下文
            history_context = ""
            if conversation_history:
                history_context = "之前的对话：\n"
                for item in conversation_history[-2:]:  # 最近2轮对话
                    history_context += f"医生：{item.get('question', '')}\n"
                    history_context += f"患者：{item.get('answer', '')}\n"
            
            # 构建提示词
            prompt = f"""你是一位友善的问卷调查者，正在与患者进行健康调研对话。

{history_context}

当前需要询问的问题：{question}
问题分类：{question_category}

请将这个问题重新表述得更加自然、友好、易懂，就像在面对面聊天一样。要求：
1. 语气要温和友善
2. 语言要通俗易懂
3. 避免过于正式的医学术语
4. 保持问题的核心意思不变
5. 可以适当添加一些解释或说明

请直接输出优化后的问题，不要添加其他内容。"""

            # 调用DeepSeek
            response = await self.call_llm(prompt)
            
            # 清理响应
            optimized = response.strip()
            if optimized and len(optimized) > 10:  # 确保有实际内容
                return optimized
            else:
                return question
                
        except Exception as e:
            logger.warning(f"⚠️ LLM问题优化失败: {e}")
            return question