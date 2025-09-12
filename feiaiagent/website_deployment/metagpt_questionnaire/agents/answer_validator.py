# -*- coding: utf-8 -*-
"""
答案审核智能体
使用DeepSeek审核用户回答，判断是否需要重新回答
"""

import logging
import re
from typing import Dict, Any, List, Optional

from .base_agent import BaseAgent, register_agent

logger = logging.getLogger(__name__)

@register_agent
class AnswerValidatorAgent(BaseAgent):
    """答案审核智能体"""
    
    def __init__(self):
        super().__init__(
            name="答案审核专家",
            description="专业的答案审核智能体，负责验证用户回答的质量和完整性",
            expertise=["答案验证", "质量控制", "医学知识", "逻辑判断"]
        )
        
        # 关键词识别配置
        self.keyword_patterns = {
            "返回上一题": [
                r"上一题", r"上一道题", r"上一个问题", r"前面一题", r"前面一道题",
                r"回到上一题", r"回到上一道题", r"回到上一个问题", r"回到前面一题",
                r"重新回答上一题", r"重新回答上一道题", r"重新回答上一个问题",
                r"返回", r"回去", r"回到前面", r"回到上题", r"回到上道题"
            ],
            "返回指定题": [
                r"第(\d+)题", r"第(\d+)道题", r"第(\d+)个问题", r"(\d+)题", r"(\d+)道题",
                r"回到第(\d+)题", r"回到第(\d+)道题", r"回到第(\d+)个问题",
                r"重新回答第(\d+)题", r"重新回答第(\d+)道题", r"重新回答第(\d+)个问题",
                r"跳到第(\d+)题", r"跳到第(\d+)道题", r"跳到第(\d+)个问题"
            ],
            "重新开始": [
                r"重新开始", r"重新来", r"重新填写", r"重新回答", r"重新来一遍",
                r"从头开始", r"从头来", r"重新来过", r"重新做", r"重新填"
            ],
            "跳过当前题": [
                r"跳过", r"下一题", r"下一道题", r"下一个问题", r"过", r"不要了",
                r"不回答", r"不填", r"跳过这题", r"跳过这道题", r"跳过这个问题"
            ]
        }
    
    async def process(self, input_data: Any) -> Any:
        """处理答案审核请求"""
        if isinstance(input_data, dict):
            return await self.validate_answer(
                question_text=input_data.get("question_text", ""),
                user_answer=input_data.get("user_answer", ""),
                question_category=input_data.get("question_category", ""),
                validation_rules=input_data.get("validation_rules", {})
            )
        else:
            raise ValueError(f"不支持的输入类型: {type(input_data)}")
    
    async def run(self, user_answer: str, question_text: str, current_index: int, total_questions: int) -> Dict[str, Any]:
        """运行答案验证和意图分析（兼容原有调用方式）"""
        logger.info(f"🔍 {self.name} 开始分析用户意图和答案质量")
        
        try:
            # 1. 首先进行关键词识别
            keyword_result = self._detect_keywords(user_answer, current_index, total_questions)
            if keyword_result.get("detected"):
                logger.info(f"🎯 检测到关键词: {keyword_result.get('intent_type')}")
                return keyword_result
            
            # 2. 如果关键词识别失败，使用LLM分析用户是否想返回前面的问题
            redo_analysis = await self._analyze_redo_intent(user_answer, current_index, total_questions)
            
            if redo_analysis.get("wants_redo"):
                return {
                    "redo": True,
                    "target_index": redo_analysis.get("target_index", current_index),
                    "reason": redo_analysis.get("reason", "用户想要重新回答前面的问题"),
                    "message": redo_analysis.get("message", "好的，我们回到前面的问题重新回答。")
                }
            
            # 3. 验证答案质量和相关性
            validation_result = await self.validate_answer(
                question_text=question_text,
                user_answer=user_answer,
                question_category="医学问卷"
            )
            
            if validation_result.get("valid"):
                quality_score = validation_result.get("quality_score", 0.8)
                relevance_score = validation_result.get("relevance_score", 0.8)
                
                # 添加评分阈值判断
                if quality_score < 0.5 or relevance_score < 0.5:
                    logger.warning(f"⚠️ 答案评分过低，质量：{quality_score}，相关性：{relevance_score}")
                    return {
                        "redo": False,
                        "valid": False,
                        "reason": f"答案质量不符合要求（质量评分：{quality_score:.1f}，相关性评分：{relevance_score:.1f}）",
                        "suggestion": "请提供更准确、相关的回答",
                        "retry": True
                    }
                
                logger.info(f"✅ 答案审核通过，质量：{quality_score:.1f}，相关性：{relevance_score:.1f}")
                return {
                    "redo": False,
                    "valid": True,
                    "quality_score": quality_score,
                    "relevance_score": relevance_score,
                    "message": "答案验证通过"
                }
            else:
                return {
                    "redo": False,
                    "valid": False,
                    "reason": validation_result.get("reason", "答案质量不符合要求"),
                    "suggestion": validation_result.get("suggestion", "请提供更准确的回答"),
                    "retry": True
                }
                
        except Exception as e:
            logger.error(f"❌ {self.name} 运行失败: {e}")
            return {
                "redo": False,
                "valid": False,
                "reason": f"分析过程出错: {str(e)}",
                "retry": False
            }
    
    async def validate_answer(self, 
                            question_text: str, 
                            user_answer: str, 
                            question_category: str = "",
                            validation_rules: Dict[str, Any] = None) -> Dict[str, Any]:
        """审核用户回答"""
        logger.info(f"🔍 {self.name} 开始审核答案: {question_text[:30]}...")
        
        try:
            # 基本检查
            basic_check = self._basic_validation(user_answer, validation_rules)
            if not basic_check["valid"]:
                return {
                    "status": "invalid",
                    "valid": False,
                    "reason": basic_check["reason"],
                    "suggestion": basic_check.get("suggestion", ""),
                    "retry": True
                }
            
            # 使用DeepSeek进行智能审核
            llm_validation = await self._llm_validation(
                question_text, user_answer, question_category
            )
            
            if llm_validation["valid"]:
                return {
                    "status": "valid",
                    "valid": True,
                    "reason": "答案审核通过",
                    "quality_score": llm_validation.get("quality_score", 0.8),
                    "retry": False
                }
            else:
                return {
                    "status": "invalid", 
                    "valid": False,
                    "reason": llm_validation["reason"],
                    "suggestion": llm_validation.get("suggestion", ""),
                    "retry": True
                }
                
        except Exception as e:
            logger.error(f"❌ {self.name} 答案审核失败: {e}")
            return {
                "status": "error",
                "valid": False,
                "reason": f"审核过程出错: {str(e)}",
                "retry": False
            }
    
    def _detect_keywords(self, user_answer: str, current_index: int, total_questions: int) -> Dict[str, Any]:
        """检测用户回答中的关键词"""
        try:
            answer_lower = user_answer.lower().strip()
            
            # 检测"返回上一题"关键词
            for pattern in self.keyword_patterns["返回上一题"]:
                if re.search(pattern, answer_lower):
                    target_index = max(0, current_index - 1)
                    return {
                        "detected": True,
                        "intent_type": "返回上一题",
                        "redo": True,
                        "target_index": target_index,
                        "reason": "检测到返回上一题的关键词",
                        "message": f"好的，我们回到第{target_index + 1}题",
                        "clear_previous_answer": True
                    }
            
            # 检测"返回指定题"关键词
            for pattern in self.keyword_patterns["返回指定题"]:
                match = re.search(pattern, answer_lower)
                if match:
                    try:
                        question_num = int(match.group(1))
                        target_index = question_num - 1  # 转换为0基索引
                        target_index = max(0, min(target_index, total_questions - 1))
                        return {
                            "detected": True,
                            "intent_type": "返回指定题",
                            "redo": True,
                            "target_index": target_index,
                            "reason": f"检测到返回第{question_num}题的关键词",
                            "message": f"好的，我们回到第{question_num}题",
                            "clear_previous_answer": True
                        }
                    except (ValueError, IndexError):
                        continue
            
            # 检测"重新开始"关键词
            for pattern in self.keyword_patterns["重新开始"]:
                if re.search(pattern, answer_lower):
                    return {
                        "detected": True,
                        "intent_type": "重新开始",
                        "redo": True,
                        "target_index": 0,
                        "reason": "检测到重新开始的关键词",
                        "message": "好的，我们从头开始",
                        "clear_all_answers": True
                    }
            
            # 检测"跳过当前题"关键词
            for pattern in self.keyword_patterns["跳过当前题"]:
                if re.search(pattern, answer_lower):
                    return {
                        "detected": True,
                        "intent_type": "跳过当前题",
                        "skip": True,
                        "target_index": current_index + 1,
                        "reason": "检测到跳过当前题的关键词",
                        "message": "好的，我们跳过这道题，继续下一题。"
                    }
            
            # 没有检测到关键词
            return {"detected": False}
            
        except Exception as e:
            logger.warning(f"⚠️ 关键词检测失败: {e}")
            return {"detected": False}
    
    def _basic_validation(self, user_answer: str, validation_rules: Dict[str, Any] = None) -> Dict[str, Any]:
        """基本验证"""
        if not user_answer or user_answer.strip() == "":
            return {
                "valid": False,
                "reason": "回答不能为空",
                "suggestion": "请提供您的回答"
            }
        
        if len(user_answer.strip()) < 1:
            return {
                "valid": False,
                "reason": "回答太短",
                "suggestion": "请提供更详细的回答"
            }
        
        # 检查选项限制
        if validation_rules and "options" in validation_rules:
            options = validation_rules["options"]
            if user_answer not in options:
                return {
                    "valid": False,
                    "reason": f"请从以下选项中选择：{', '.join(options)}",
                    "suggestion": f"请选择：{', '.join(options)}"
                }
        
        return {"valid": True}
    
    async def _llm_validation(self, question_text: str, user_answer: str, question_category: str) -> Dict[str, Any]:
        """使用DeepSeek进行智能审核"""
        try:
            # 构建审核提示词
            prompt = f"""你是一位专业的医学问卷审核专家，需要审核患者的回答质量。

问题：{question_text}
问题分类：{question_category}
患者回答：{user_answer}

请从以下维度审核回答：
1. 完整性：回答是否完整回答了问题
2. 相关性：回答是否与问题相关（重点检查是否答非所问）
3. 具体性：回答是否具体明确
4. 逻辑性：回答是否符合逻辑
5. 医学合理性：回答是否符合医学常识
6. 格式正确性：回答格式是否符合问题要求

评分标准：
- 质量评分：0.0-1.0（0.0-0.3很差，0.3-0.5较差，0.5-0.7一般，0.7-0.9良好，0.9-1.0优秀）
- 相关性评分：0.0-1.0（0.0-0.3不相关，0.3-0.5部分相关，0.5-0.7相关，0.7-1.0高度相关）

特别注意：
- 如果用户回答与问题完全不相关（如问年龄答吃饭），相关性评分应为0.1-0.3，必须标记为不通过
- 如果用户只是重复问题内容，相关性评分应为0.2-0.4，必须标记为不通过
- 如果用户回答过于模糊或简短，质量评分应为0.2-0.4，必须标记为不通过
- 对于选择题，检查是否选择了有效选项
- 对于数值题，检查数值是否在合理范围内
- 质量评分 < 0.5 或 相关性评分 < 0.5 时，必须标记为不通过

请给出审核结果，格式如下：
审核结果：通过/不通过
质量评分：0.0-1.0
相关性评分：0.0-1.0
不通过原因：（如果不通过）
改进建议：（如果不通过）

请直接输出结果，不要添加其他内容。"""

            # 调用DeepSeek
            response = await self.call_llm(prompt)
            
            # 解析响应
            return self._parse_validation_response(response)
            
        except Exception as e:
            logger.warning(f"⚠️ LLM审核失败: {e}")
            # 降级到基本验证
            return {
                "valid": True,
                "quality_score": 0.7,
                "reason": "LLM审核失败，使用基本验证"
            }
    
    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """解析LLM审核响应"""
        try:
            response = response.strip()
            response_lower = response.lower()
            
            # 检查是否通过
            if "审核结果：通过" in response or "通过" in response:
                # 提取质量评分
                quality_score = 0.8
                if "质量评分：" in response:
                    try:
                        score_text = response.split("质量评分：")[1].split()[0]
                        quality_score = float(score_text)
                    except:
                        pass
                
                # 提取相关性评分
                relevance_score = 0.8
                if "相关性评分：" in response:
                    try:
                        score_text = response.split("相关性评分：")[1].split()[0]
                        relevance_score = float(score_text)
                    except:
                        pass
                
                return {
                    "valid": True,
                    "quality_score": quality_score,
                    "relevance_score": relevance_score,
                    "reason": "LLM审核通过"
                }
            else:
                # 提取不通过原因和建议
                reason = "回答质量不符合要求"
                suggestion = "请提供更详细、准确的回答"
                
                if "不通过原因：" in response:
                    try:
                        reason = response.split("不通过原因：")[1].split("\n")[0].strip()
                    except:
                        pass
                
                if "改进建议：" in response:
                    try:
                        suggestion = response.split("改进建议：")[1].strip()
                    except:
                        pass
                
                # 检查是否是相关性问题
                if any(keyword in reason.lower() for keyword in ["不相关", "答非所问", "无关", "偏离"]):
                    reason = "回答与问题不相关，请针对问题内容进行回答"
                    suggestion = "请仔细阅读问题，提供与问题相关的回答"
                
                return {
                    "valid": False,
                    "reason": reason,
                    "suggestion": suggestion
                }
                
        except Exception as e:
            logger.warning(f"⚠️ 解析审核响应失败: {e}")
            return {
                "valid": True,
                "quality_score": 0.7,
                "relevance_score": 0.7,
                "reason": "解析失败，默认通过"
            }
    
    async def batch_validate_answers(self, qa_pairs: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """批量审核答案"""
        results = []
        
        for qa_pair in qa_pairs:
            result = await self.validate_answer(
                question_text=qa_pair.get("question", ""),
                user_answer=qa_pair.get("answer", ""),
                question_category=qa_pair.get("category", "")
            )
            results.append(result)
        
        return results
    
    async def _analyze_redo_intent(self, user_answer: str, current_index: int, total_questions: int) -> Dict[str, Any]:
        """分析用户是否想返回前面的问题重新回答"""
        try:
            # 构建分析提示词
            prompt = f"""你是一位专业的医学问卷助手，需要分析用户的回答意图。

当前情况：
- 当前问题索引：{current_index + 1}/{total_questions}
- 用户回答：{user_answer}

请分析用户是否想要：
1. 重新回答前面的问题
2. 跳过当前问题
3. 返回特定问题
4. 正常回答当前问题

常见的返回意图表达：
- "我想重新回答第X题"
- "回到前面"
- "重新填写"
- "修改之前的答案"
- "我想改一下第X个问题"
- "回到第X题"
- "重新回答"
- "重新来"
- "重新开始"
- "回到第X个问题"
- "我想重新回答第X个问题"

特别注意：
- 如果用户明确表达想要重新回答某个问题，应该标记为返回意图
- 如果用户只是说"重新回答"但没有指定问题，默认返回上一个问题
- 如果用户说"重新开始"，应该返回第1题
- 如果用户说"回到前面"，应该返回上一个问题

请按以下格式回复：
意图类型：[重新回答/跳过/返回特定/正常回答]
是否返回：是/否
目标问题索引：[如果是返回特定，给出问题索引，否则为-1]
原因：[简要说明]
回复消息：[给用户的回复]

请直接输出结果，不要添加其他内容。"""

            # 调用DeepSeek分析
            response = await self.call_llm(prompt)
            
            # 解析响应
            return self._parse_redo_intent_response(response, current_index, total_questions)
            
        except Exception as e:
            logger.warning(f"⚠️ 重新回答意图分析失败: {e}")
            return {
                "wants_redo": False,
                "target_index": current_index,
                "reason": "分析失败，继续当前问题",
                "message": "请继续回答当前问题。"
            }
    
    def _parse_redo_intent_response(self, response: str, current_index: int, total_questions: int) -> Dict[str, Any]:
        """解析重新回答意图分析响应"""
        try:
            response = response.strip()
            
            # 检查是否想要重新回答
            if "是否返回：是" in response or "是否返回：true" in response.lower():
                # 提取目标问题索引
                target_index = current_index
                if "目标问题索引：" in response:
                    try:
                        index_text = response.split("目标问题索引：")[1].split()[0]
                        target_index = int(index_text) - 1  # 转换为0基索引
                        # 确保索引在有效范围内
                        target_index = max(0, min(target_index, total_questions - 1))
                    except:
                        target_index = max(0, current_index - 1)  # 默认返回上一个问题
                
                # 提取原因和消息
                reason = "用户想要重新回答前面的问题"
                message = "好的，我们回到前面的问题重新回答。"
                
                if "原因：" in response:
                    try:
                        reason = response.split("原因：")[1].split("\n")[0].strip()
                    except:
                        pass
                
                if "回复消息：" in response:
                    try:
                        message = response.split("回复消息：")[1].strip()
                    except:
                        pass
                
                return {
                    "wants_redo": True,
                    "target_index": target_index,
                    "reason": reason,
                    "message": message
                }
            else:
                return {
                    "wants_redo": False,
                    "target_index": current_index,
                    "reason": "用户正常回答当前问题",
                    "message": "继续当前问题。"
                }
                
        except Exception as e:
            logger.warning(f"⚠️ 解析重新回答意图失败: {e}")
            return {
                "wants_redo": False,
                "target_index": current_index,
                "reason": "解析失败，继续当前问题",
                "message": "请继续回答当前问题。"
            }