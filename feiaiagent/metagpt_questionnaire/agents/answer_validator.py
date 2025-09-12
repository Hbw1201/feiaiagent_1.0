# -*- coding: utf-8 -*-
"""
答案审核智能体
使用DeepSeek审核用户回答，判断是否需要重新回答
优化版本：支持缓存、批量处理、预编译正则表达式
"""

import logging
import re
from typing import Dict, Any, List, Optional
import asyncio
import concurrent.futures
from functools import lru_cache
import threading
import time

from .base_agent import BaseAgent, register_agent

logger = logging.getLogger(__name__)

@register_agent
class AnswerValidatorAgent(BaseAgent):
    """答案审核智能体（优化版本）"""
    
    def __init__(self):
        super().__init__(
            name="答案审核专家",
            description="专业的答案审核智能体，负责验证用户回答的质量和完整性",
            expertise=["答案验证", "质量控制", "医学知识", "逻辑判断"]
        )
        
        # 性能优化配置
        self._validation_cache = {}
        self._cache_lock = threading.Lock()
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="validator_worker")
        self._cache_ttl = 300  # 缓存5分钟
        
        # 性能统计
        self._stats = {
            "total_validations": 0,
            "cache_hits": 0,
            "llm_calls": 0,
            "keyword_detections": 0,
            "avg_validation_time": 0.0,
            "last_reset": time.time()
        }
        self._stats_lock = threading.Lock()
        
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
        
        # 预编译正则表达式（性能优化）
        self._compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """预编译正则表达式以提高性能"""
        compiled = {}
        for category, patterns in self.keyword_patterns.items():
            compiled[category] = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        return compiled
    
    def _get_cache_key(self, question_text: str, user_answer: str, question_category: str = "") -> str:
        """生成缓存键"""
        return f"{hash(question_text)}_{hash(user_answer)}_{question_category}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存结果"""
        with self._cache_lock:
            if cache_key in self._validation_cache:
                result, timestamp = self._validation_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    logger.debug(f"使用验证缓存: {cache_key[:20]}...")
                    return result
                else:
                    # 缓存过期，删除
                    del self._validation_cache[cache_key]
        return None
    
    def _set_cached_result(self, cache_key: str, result: Dict[str, Any]):
        """设置缓存结果"""
        with self._cache_lock:
            self._validation_cache[cache_key] = (result, time.time())
            # 限制缓存大小
            if len(self._validation_cache) > 1000:
                # 删除最旧的缓存
                oldest_key = min(self._validation_cache.keys(), 
                               key=lambda k: self._validation_cache[k][1])
                del self._validation_cache[oldest_key]
    
    def _update_stats(self, stat_name: str, value: float = 1.0):
        """更新统计信息"""
        with self._stats_lock:
            if stat_name in self._stats:
                self._stats[stat_name] += value
            else:
                self._stats[stat_name] = value
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        with self._stats_lock:
            stats = self._stats.copy()
            stats["cache_hit_rate"] = (
                stats["cache_hits"] / max(stats["total_validations"], 1) * 100
            )
            stats["uptime"] = time.time() - stats["last_reset"]
            return stats
    
    def reset_stats(self):
        """重置统计信息"""
        with self._stats_lock:
            self._stats = {
                "total_validations": 0,
                "cache_hits": 0,
                "llm_calls": 0,
                "keyword_detections": 0,
                "avg_validation_time": 0.0,
                "last_reset": time.time()
            }
    
    def cleanup_resources(self):
        """清理资源"""
        if hasattr(self, '_thread_pool'):
            self._thread_pool.shutdown(wait=True)
        with self._cache_lock:
            self._validation_cache.clear()
        logger.info(f"✅ {self.name} 资源清理完成")
    
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
        """运行答案验证和意图分析（简化版本）"""
        logger.info(f"🔍 {self.name} 开始分析用户意图和答案质量")
        
        try:
            # 使用LLM进行综合分析（意图分析+答案验证，只调用一次）
            analysis_result = await self._comprehensive_analysis(
                user_answer=user_answer,
                question_text=question_text,
                current_index=current_index,
                total_questions=total_questions
            )
            
            # 处理分析结果
            if analysis_result.get("wants_redo"):
                logger.info(f"🎯 用户想要重新回答第{analysis_result.get('target_index', current_index) + 1}题")
                return {
                    "redo": True,
                    "target_index": analysis_result.get("target_index", current_index),
                    "reason": analysis_result.get("reason", "用户想要重新回答前面的问题"),
                    "message": "好的，我们回到前面的问题重新回答。"
                }
            
            # 处理答案验证结果
            if analysis_result.get("valid"):
                logger.info(f"✅ 答案审核通过：{analysis_result.get('reason')}")
                return {
                    "redo": False,
                    "valid": True,
                    "quality_score": analysis_result.get("quality_score", 0.8),
                    "relevance_score": analysis_result.get("relevance_score", 0.8),
                    "reason": analysis_result.get("reason", "答案审核通过"),
                    "retry": False
                }
            else:
                logger.warning(f"⚠️ 答案审核不通过：{analysis_result.get('reason')}")
                return {
                    "redo": False,
                    "valid": False,
                    "reason": analysis_result.get("reason", "答案不符合要求"),
                    "suggestion": analysis_result.get("suggestion", "请重新回答"),
                    "retry": True
                }
                
        except Exception as e:
            logger.error(f"❌ {self.name} 运行失败: {e}")
            return {
                "redo": False,
                "valid": False,
                "reason": f"验证过程出错: {str(e)}",
                "retry": False
            }
    
    async def validate_answer(self, 
                            question_text: str, 
                            user_answer: str, 
                            question_category: str = "",
                            validation_rules: Dict[str, Any] = None) -> Dict[str, Any]:
        """审核用户回答（优化版本，支持缓存）"""
        start_time = time.time()
        self._update_stats("total_validations")
        
        logger.info(f"🔍 {self.name} 开始审核答案: {question_text[:30]}...")
        
        try:
            # 检查缓存
            cache_key = self._get_cache_key(question_text, user_answer, question_category)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                self._update_stats("cache_hits")
                logger.debug(f"使用验证缓存: {question_text[:20]}...")
                return cached_result
            
            # 基本检查（增强版本）
            basic_check = self._basic_validation(user_answer, validation_rules, question_text)
            if not basic_check["valid"]:
                result = {
                    "status": "invalid",
                    "valid": False,
                    "reason": basic_check["reason"],
                    "suggestion": basic_check.get("suggestion", ""),
                    "retry": True
                }
                # 缓存基本验证结果
                self._set_cached_result(cache_key, result)
                return result
            
            # 如果用户选择不回答敏感信息问题，直接通过
            if basic_check.get("sensitive_skip"):
                result = {
                    "status": "valid",
                    "valid": True,
                    "reason": "用户选择不回答敏感信息问题",
                    "sensitive_skip": True,
                    "retry": False
                }
                self._set_cached_result(cache_key, result)
                return result
            
            # 使用DeepSeek进行智能审核
            self._update_stats("llm_calls")
            llm_validation = await self._llm_validation(
                question_text, user_answer, question_category
            )
            
            if llm_validation["valid"]:
                result = {
                    "status": "valid",
                    "valid": True,
                    "reason": "答案审核通过",
                    "quality_score": llm_validation.get("quality_score", 0.8),
                    "retry": False
                }
            else:
                result = {
                    "status": "invalid", 
                    "valid": False,
                    "reason": llm_validation["reason"],
                    "suggestion": llm_validation.get("suggestion", ""),
                    "retry": True
                }
            
            # 缓存结果
            self._set_cached_result(cache_key, result)
            
            # 更新平均验证时间
            validation_time = time.time() - start_time
            with self._stats_lock:
                total_validations = self._stats["total_validations"]
                current_avg = self._stats["avg_validation_time"]
                self._stats["avg_validation_time"] = (
                    (current_avg * (total_validations - 1) + validation_time) / total_validations
                )
            
            return result
                
        except Exception as e:
            logger.error(f"❌ {self.name} 答案审核失败: {e}")
            return {
                "status": "error",
                "valid": False,
                "reason": f"审核过程出错: {str(e)}",
                "retry": False
            }
    
    def _detect_keywords(self, user_answer: str, current_index: int, total_questions: int) -> Dict[str, Any]:
        """检测用户回答中的关键词（优化版本，使用预编译正则表达式）"""
        try:
            self._update_stats("keyword_detections")
            answer_lower = user_answer.lower().strip()
            
            # 检测"返回上一题"关键词
            for pattern in self._compiled_patterns["返回上一题"]:
                if pattern.search(answer_lower):
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
            for pattern in self._compiled_patterns["返回指定题"]:
                match = pattern.search(answer_lower)
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
            for pattern in self._compiled_patterns["重新开始"]:
                if pattern.search(answer_lower):
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
            for pattern in self._compiled_patterns["跳过当前题"]:
                if pattern.search(answer_lower):
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
    
    def _basic_validation(self, user_answer: str, validation_rules: Dict[str, Any] = None, question_text: str = "") -> Dict[str, Any]:
        """基本验证（极度宽松版本）"""
        if not user_answer or user_answer.strip() == "":
            return {
                "valid": False,
                "reason": "回答不能为空",
                "suggestion": "请提供您的回答"
            }
        
        # 极度宽松：只要不是完全空白就认为有效
        if len(user_answer.strip()) < 1:
            return {
                "valid": False,
                "reason": "回答太短",
                "suggestion": "请提供更详细的回答"
            }
        
        # 检查是否是完全无关的内容（极度宽松，只有明显无关才拒绝）
        answer_lower = user_answer.lower().strip()
        
        # 只有以下情况才认为无效：
        # 1. 完全无关的内容（如回答天气、时间等来回答医学问题）
        # 2. 明显的恶意回答（如乱码、重复字符等）
        unrelated_patterns = [
            r"^今天.*天气", r"^现在.*时间", r"^几点.*了", r"^星期.*几",
            r"^[a-z]{10,}$",  # 10个以上连续字母（可能是乱码）
            r"^.{1,3}\1{3,}$",  # 重复字符
            r"^[0-9]{20,}$"  # 20个以上连续数字（可能是乱码）
        ]
        
        for pattern in unrelated_patterns:
            if re.search(pattern, answer_lower):
                return {
                    "valid": False,
                    "reason": "回答内容不相关",
                    "suggestion": "请回答相关问题"
                }
        
        # 其他所有情况都认为有效
        return {"valid": True}
    
    
    
    
    
    async def _comprehensive_analysis(self, 
                                    user_answer: str, 
                                    question_text: str, 
                                    current_index: int, 
                                    total_questions: int) -> Dict[str, Any]:
        """综合分析：意图分析+答案验证（只调用一次LLM）"""
        try:
            # 构建简化的综合分析提示词
            prompt = f"""你是一位专业的医学问卷助手，需要分析用户的回答是否有效。

当前情况：
- 当前问题索引：{current_index + 1}/{total_questions}
- 问题：{question_text}
- 用户回答：{user_answer}

请分析：
1. 用户是否想要重新回答前面的问题（如"回到第X题"、"重新回答"等）
2. 用户的回答是否有效回答了当前问题

验证标准（极度宽松）：
- 只要用户回答了任何内容，就认为有效，除非回答完全无关或过于离谱
- 接受任何形式的回答，包括单字、词语、句子、数字等
- 接受模糊、不完整、口语化的回答
- 接受任何单位、任何表达方式
- 接受"不知道"、"不清楚"、"忘记了"等回答
- 接受"嗯"、"对"、"是"、"有"、"没有"等简单回答
- 接受"大概"、"可能"、"应该"等不确定的回答
- 接受任何数字，不管单位如何
- 接受任何是/否的表达方式
- 只有以下情况才认为无效：
  * 完全空白或只有空格
  * 完全无关的内容（如回答"今天天气很好"来回答体重问题）
  * 明显的恶意回答（如乱码、重复字符等）

请按以下格式回复：
是否重新回答：是/否
目标问题索引：[如果是重新回答，给出问题索引，否则为-1]
答案是否有效：是/否
原因：[简要说明]

请直接输出结果，不要添加其他内容。"""

            # 调用DeepSeek进行综合分析
            self._update_stats("llm_calls")
            response = await self.call_llm(prompt)
            
            # 解析响应
            return self._parse_simple_response(response, current_index, total_questions)
            
        except Exception as e:
            logger.warning(f"⚠️ 综合分析失败: {e}")
            # 降级到基本验证
            return {
                "wants_redo": False,
                "valid": True,
                "quality_score": 0.7,
                "relevance_score": 0.7,
                "reason": "综合分析失败，使用默认验证"
            }
    
    def _parse_simple_response(self, response: str, current_index: int, total_questions: int) -> Dict[str, Any]:
        """解析简化的综合分析响应"""
        try:
            response = response.strip()
            
            # 使用预编译的正则表达式进行解析
            wants_redo_pattern = re.compile(r'是否重新回答：([^\n]+)')
            target_index_pattern = re.compile(r'目标问题索引：(\d+)')
            answer_valid_pattern = re.compile(r'答案是否有效：([^\n]+)')
            reason_pattern = re.compile(r'原因：([^\n]+)')
            
            # 解析是否重新回答
            wants_redo = False
            target_index = current_index
            
            wants_redo_match = wants_redo_pattern.search(response)
            if wants_redo_match and "是" in wants_redo_match.group(1):
                wants_redo = True
                
                target_index_match = target_index_pattern.search(response)
                if target_index_match:
                    try:
                        target_index = int(target_index_match.group(1)) - 1  # 转换为0基索引
                        target_index = max(0, min(target_index, total_questions - 1))
                    except:
                        target_index = max(0, current_index - 1)
                else:
                    target_index = max(0, current_index - 1)
            
            # 解析答案是否有效
            valid = True
            answer_valid_match = answer_valid_pattern.search(response)
            if answer_valid_match and "否" in answer_valid_match.group(1):
                valid = False
            
            # 提取原因
            reason = "答案审核通过"
            reason_match = reason_pattern.search(response)
            if reason_match:
                reason = reason_match.group(1).strip()
            
            return {
                "wants_redo": wants_redo,
                "target_index": target_index,
                "valid": valid,
                "quality_score": 0.8 if valid else 0.3,
                "relevance_score": 0.8 if valid else 0.3,
                "reason": reason,
                "suggestion": "请重新回答" if not valid else ""
            }
            
        except Exception as e:
            logger.warning(f"⚠️ 解析简化响应失败: {e}")
            return {
                "wants_redo": False,
                "valid": True,
                "quality_score": 0.7,
                "relevance_score": 0.7,
                "reason": "解析失败，使用默认验证"
            }
    
    async def _validate_answer_inline(self, 
                                    question_text: str, 
                                    user_answer: str, 
                                    question_category: str = "",
                                    validation_rules: Dict[str, Any] = None) -> Dict[str, Any]:
        """内联答案验证（避免重复调用和日志）"""
        start_time = time.time()
        self._update_stats("total_validations")
        
        try:
            # 检查缓存
            cache_key = self._get_cache_key(question_text, user_answer, question_category)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                self._update_stats("cache_hits")
                return cached_result
            
            # 基本检查（增强版本）
            basic_check = self._basic_validation(user_answer, validation_rules, question_text)
            if not basic_check["valid"]:
                result = {
                    "status": "invalid",
                    "valid": False,
                    "reason": basic_check["reason"],
                    "suggestion": basic_check.get("suggestion", ""),
                    "retry": True
                }
                # 缓存基本验证结果
                self._set_cached_result(cache_key, result)
                return result
            
            # 如果用户选择不回答敏感信息问题，直接通过
            if basic_check.get("sensitive_skip"):
                result = {
                    "status": "valid",
                    "valid": True,
                    "reason": "用户选择不回答敏感信息问题",
                    "sensitive_skip": True,
                    "retry": False
                }
                self._set_cached_result(cache_key, result)
                return result
            
            # 使用DeepSeek进行智能审核（不重复日志）
            self._update_stats("llm_calls")
            llm_validation = await self._llm_validation(
                question_text, user_answer, question_category
            )
            
            if llm_validation["valid"]:
                result = {
                    "status": "valid",
                    "valid": True,
                    "reason": "答案审核通过",
                    "quality_score": llm_validation.get("quality_score", 0.8),
                    "retry": False
                }
            else:
                result = {
                    "status": "invalid", 
                    "valid": False,
                    "reason": llm_validation["reason"],
                    "suggestion": llm_validation.get("suggestion", ""),
                    "retry": True
                }
            
            # 缓存结果
            self._set_cached_result(cache_key, result)
            
            # 更新平均验证时间
            validation_time = time.time() - start_time
            with self._stats_lock:
                total_validations = self._stats["total_validations"]
                current_avg = self._stats["avg_validation_time"]
                self._stats["avg_validation_time"] = (
                    (current_avg * (total_validations - 1) + validation_time) / total_validations
                )
            
            return result
                
        except Exception as e:
            logger.error(f"❌ {self.name} 答案审核失败: {e}")
            return {
                "status": "error",
                "valid": False,
                "reason": f"审核过程出错: {str(e)}",
                "retry": False
            }
    
    async def _validate_answer_direct(self, 
                                    question_text: str, 
                                    user_answer: str, 
                                    question_category: str = "",
                                    validation_rules: Dict[str, Any] = None) -> Dict[str, Any]:
        """直接验证答案（内部使用，不重复日志）"""
        start_time = time.time()
        self._update_stats("total_validations")
        
        try:
            # 检查缓存
            cache_key = self._get_cache_key(question_text, user_answer, question_category)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                self._update_stats("cache_hits")
                return cached_result
            
            # 基本检查（增强版本）
            basic_check = self._basic_validation(user_answer, validation_rules, question_text)
            if not basic_check["valid"]:
                result = {
                    "status": "invalid",
                    "valid": False,
                    "reason": basic_check["reason"],
                    "suggestion": basic_check.get("suggestion", ""),
                    "retry": True
                }
                # 缓存基本验证结果
                self._set_cached_result(cache_key, result)
                return result
            
            # 如果用户选择不回答敏感信息问题，直接通过
            if basic_check.get("sensitive_skip"):
                result = {
                    "status": "valid",
                    "valid": True,
                    "reason": "用户选择不回答敏感信息问题",
                    "sensitive_skip": True,
                    "retry": False
                }
                self._set_cached_result(cache_key, result)
                return result
            
            # 使用DeepSeek进行智能审核
            self._update_stats("llm_calls")
            llm_validation = await self._llm_validation(
                question_text, user_answer, question_category
            )
            
            if llm_validation["valid"]:
                result = {
                    "status": "valid",
                    "valid": True,
                    "reason": "答案审核通过",
                    "quality_score": llm_validation.get("quality_score", 0.8),
                    "retry": False
                }
            else:
                result = {
                    "status": "invalid", 
                    "valid": False,
                    "reason": llm_validation["reason"],
                    "suggestion": llm_validation.get("suggestion", ""),
                    "retry": True
                }
            
            # 缓存结果
            self._set_cached_result(cache_key, result)
            
            # 更新平均验证时间
            validation_time = time.time() - start_time
            with self._stats_lock:
                total_validations = self._stats["total_validations"]
                current_avg = self._stats["avg_validation_time"]
                self._stats["avg_validation_time"] = (
                    (current_avg * (total_validations - 1) + validation_time) / total_validations
                )
            
            return result
                
        except Exception as e:
            logger.error(f"❌ {self.name} 答案审核失败: {e}")
            return {
                "status": "error",
                "valid": False,
                "reason": f"审核过程出错: {str(e)}",
                "retry": False
            }
    
    async def _llm_validation(self, question_text: str, user_answer: str, question_category: str) -> Dict[str, Any]:
        """使用DeepSeek进行智能审核（人性化版本）"""
        try:
            # 构建审核提示词
            prompt = f"""你是一位温和、专业的医学问卷审核专家，需要以人性化的方式审核患者的回答质量。

问题：{question_text}
问题分类：{question_category}
患者回答：{user_answer}

请以温暖、理解的态度审核回答，考虑以下维度：
1. 完整性：回答是否完整回答了问题
2. 相关性：回答是否与问题相关（重点检查是否答非所问）
3. 具体性：回答是否具体明确
4. 逻辑性：回答是否符合逻辑
5. 医学合理性：回答是否符合医学常识
6. 表达自然性：回答是否自然、人性化

评分标准：
- 质量评分：0.0-1.0（0.0-0.3很差，0.3-0.5较差，0.5-0.7一般，0.7-0.9良好，0.9-1.0优秀）
- 相关性评分：0.0-1.0（0.0-0.3不相关，0.3-0.5部分相关，0.5-0.7相关，0.7-1.0高度相关）

特别注意：
- 理解患者可能用不同的方式表达同一意思（如"吸烟"和"抽烟"）
- 接受自然的口语化表达（如"嗯"、"对的"、"是的"）
- 理解患者可能用不同的单位（如体重用"斤"而不是"kg"）
- 接受患者选择不回答敏感问题的权利
- 如果用户回答与问题完全不相关，相关性评分应为0.1-0.3，必须标记为不通过
- 如果用户只是重复问题内容，相关性评分应为0.2-0.4，必须标记为不通过
- 如果用户回答过于模糊或简短，质量评分应为0.2-0.4，必须标记为不通过
- 对于选择题，检查是否选择了有效选项（支持灵活表达）
- 对于数值题，检查数值是否在合理范围内（支持多种单位）
- 质量评分 < 0.5 或 相关性评分 < 0.5 时，必须标记为不通过

请给出审核结果，格式如下：
审核结果：通过/不通过
质量评分：0.0-1.0
相关性评分：0.0-1.0
不通过原因：（如果不通过，请用温和的语气）
改进建议：（如果不通过，请用鼓励的语气）

请直接输出结果，不要添加其他内容。"""

            # 调用DeepSeek
            response = await self.call_llm(prompt)
            
            # 解析响应
            return self._parse_validation_response(response, question_text)
            
        except Exception as e:
            logger.warning(f"⚠️ LLM审核失败: {e}")
            # 降级到基本验证
            return {
                "valid": True,
                "quality_score": 0.7,
                "reason": "LLM审核失败，使用基本验证"
            }
    
    def _parse_validation_response(self, response: str, question_text: str = "") -> Dict[str, Any]:
        """解析LLM审核响应（优化版本，减少字符串操作）"""
        try:
            response = response.strip()
            
            # 使用预编译的正则表达式进行解析
            pass_pattern = re.compile(r'审核结果：通过|通过')
            quality_pattern = re.compile(r'质量评分：(\d+\.?\d*)')
            relevance_pattern = re.compile(r'相关性评分：(\d+\.?\d*)')
            reason_pattern = re.compile(r'不通过原因：([^\n]+)')
            suggestion_pattern = re.compile(r'改进建议：(.+)', re.DOTALL)
            
            # 检查是否通过
            if pass_pattern.search(response):
                # 提取质量评分
                quality_score = 0.8
                quality_match = quality_pattern.search(response)
                if quality_match:
                    try:
                        quality_score = float(quality_match.group(1))
                    except:
                        pass
                
                # 提取相关性评分
                relevance_score = 0.8
                relevance_match = relevance_pattern.search(response)
                if relevance_match:
                    try:
                        relevance_score = float(relevance_match.group(1))
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
                
                reason_match = reason_pattern.search(response)
                if reason_match:
                    reason = reason_match.group(1).strip()
                
                suggestion_match = suggestion_pattern.search(response)
                if suggestion_match:
                    suggestion = suggestion_match.group(1).strip()
                
                # 检查是否是相关性问题，提供更人性化的回复
                if any(keyword in reason.lower() for keyword in ["不相关", "答非所问", "无关", "偏离"]):
                    question_type = self._get_question_type(question_text)
                    reason = "您的回答似乎与问题不太相关，让我们重新来回答这个问题"
                    suggestion = self._generate_encouraging_message(question_type)
                
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
    
    async def batch_validate_answers(self, qa_pairs: List[Dict[str, str]], max_concurrent: int = 5) -> List[Dict[str, Any]]:
        """批量审核答案（优化版本，支持并发处理）"""
        if not qa_pairs:
            return []
        
        # 创建信号量限制并发数
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def validate_single(qa_pair: Dict[str, str]) -> Dict[str, Any]:
            async with semaphore:
                return await self.validate_answer(
                    question_text=qa_pair.get("question", ""),
                    user_answer=qa_pair.get("answer", ""),
                    question_category=qa_pair.get("category", "")
                )
        
        # 并发执行所有验证任务
        tasks = [validate_single(qa_pair) for qa_pair in qa_pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"批量验证第{i+1}个答案时出错: {result}")
                processed_results.append({
                    "status": "error",
                    "valid": False,
                    "reason": f"验证过程出错: {str(result)}",
                    "retry": False
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
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