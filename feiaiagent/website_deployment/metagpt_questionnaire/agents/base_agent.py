# -*- coding: utf-8 -*-
"""
智能体基类
定义所有智能体的通用接口和方法
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
try:
    import openai as _openai
except Exception:  # 环境未安装 openai 也不影响（仅使用 DeepSeek）
    _openai = None
import requests

from ..config.metagpt_config import get_llm_config
from ..prompts.design_prompts import get_prompt_template

logger = logging.getLogger(__name__)

# ===== 通用超时/重试参数（增强鲁棒性） =====
_HTTP_TIMEOUT_SECS_DEFAULT = 60
_HTTP_RETRY_TIMES = 2
_HTTP_BACKOFF_SECS = 1.2

class BaseAgent(ABC):
    """智能体基类"""
    
    def __init__(self, name: str, description: str, expertise: List[str]):
        self.name = name
        self.description = description
        self.expertise = expertise
        self.llm_config = get_llm_config()
        self.conversation_history: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        
        # 初始化LLM客户端
        self._init_llm_clients()
    
    def _init_llm_clients(self):
        """初始化LLM客户端"""
        try:
            # DeepSeek客户端（OpenAI兼容接口）
            self.deepseek_config = self.llm_config.get("deepseek", {})
            self.deepseek_available = bool(self.deepseek_config.get("api_key")) and not self.deepseek_config.get("api_key", "").startswith("your-")
            if self.deepseek_available:
                logger.info(f"✅ {self.name} DeepSeek配置加载成功")
            else:
                logger.warning(f"⚠️ {self.name} DeepSeek API密钥未配置或无效")
            # 强制禁用 OpenAI（只用 DeepSeek）
            self.openai_client = None
            logger.info(f"ℹ️ {self.name} 已禁用 OpenAI 通道（仅使用 DeepSeek）")
                
        except Exception as e:
            logger.error(f"❌ {self.name} LLM客户端初始化失败: {e}")
            self.openai_client = None
            self.deepseek_available = False
    
    def add_to_history(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """添加到对话历史"""
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.conversation_history.append(entry)
        logger.debug(f"{self.name} 添加对话历史: {role} - {content[:50]}...")
    
    def get_history_summary(self, max_entries: int = 10) -> str:
        """获取对话历史摘要"""
        recent_history = self.conversation_history[-max_entries:]
        summary = f"最近{len(recent_history)}条对话记录:\n"
        for entry in recent_history:
            summary += f"- {entry['role']}: {entry['content'][:100]}...\n"
        return summary
    
    async def call_openai(self, prompt: str, model: str = "gpt-4", max_tokens: int = 2000) -> str:
        """调用OpenAI API"""
        if not self.openai_client:
            raise RuntimeError("OpenAI客户端未初始化")
        
        try:
            # 兼容 Python < 3.9 版本
            import concurrent.futures
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    lambda: self.openai_client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=0.7
                    )
                )
            
            result = response.choices[0].message.content
            self.add_to_history("user", prompt)
            self.add_to_history("assistant", result)
            
            logger.info(f"✅ {self.name} OpenAI调用成功")
            return result
            
        except Exception as e:
            logger.error(f"❌ {self.name} OpenAI调用失败: {e}")
            raise

    async def call_deepseek(self, prompt: str, model: Optional[str] = None, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        """调用DeepSeek（OpenAI兼容 /chat/completions 接口）"""
        if not self.deepseek_available:
            raise RuntimeError("DeepSeek未配置")

        cfg = self.deepseek_config
        base_url = (cfg.get("base_url") or "https://api.deepseek.com").strip().rstrip("/")
        if not base_url.startswith("http"):
            base_url = "https://api.deepseek.com"
        endpoint = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg.get('api_key')}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or cfg.get("model", "deepseek-chat"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": cfg.get("temperature", 0.7) if temperature is None else temperature,
            "max_tokens": cfg.get("max_tokens", 4000) if max_tokens is None else max_tokens
        }

        def _post_with_retry():
            last_exc = None
            for i in range(_HTTP_RETRY_TIMES + 1):
                try:
                    resp = requests.post(endpoint, headers=headers, json=payload, timeout=_HTTP_TIMEOUT_SECS_DEFAULT)
                    # 明确处理429/5xx
                    if resp.status_code == 429 or 500 <= resp.status_code < 600:
                        last_exc = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                        raise last_exc
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    last_exc = e
                    if i < _HTTP_RETRY_TIMES:
                        import time as _t
                        _t.sleep(_HTTP_BACKOFF_SECS * (i + 1))
                        continue
                    raise last_exc

        try:
            # 兼容 Python < 3.9 版本
            import concurrent.futures
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                data = await loop.run_in_executor(executor, _post_with_retry)
            # 解析OpenAI兼容返回
            result = None
            try:
                result = data.get("choices", [{}])[0].get("message", {}).get("content")
            except Exception:
                result = None
            if not result:
                # 兼容其他可能字段
                try:
                    result = data.get("choices", [{}])[0].get("text")
                except Exception:
                    result = None
            if not result:
                raise RuntimeError(f"DeepSeek响应为空: {str(data)[:200]}")
            self.add_to_history("user", prompt)
            self.add_to_history("assistant", result)
            logger.info(f"✅ {self.name} DeepSeek调用成功")
            return result
        except Exception as e:
            logger.error(f"❌ {self.name} DeepSeek调用失败: {e}")
            raise
    
    async def call_zhipu(self, prompt: str) -> str:
        """调用智谱AI API"""
        try:
            # 这里可以集成原有的智谱AI调用逻辑
            # 暂时返回模拟结果
            logger.info(f"✅ {self.name} 智谱AI调用成功（模拟）")
            return f"智谱AI回复: {prompt[:50]}..."
            
        except Exception as e:
            logger.error(f"❌ {self.name} 智谱AI调用失败: {e}")
            raise
    
    async def call_llm(self, prompt: str, provider: str = "auto") -> str:
        """统一走 DeepSeek"""
        if not getattr(self, "deepseek_available", False):
            raise RuntimeError("DeepSeek未配置，无法调用LLM。请设置 DEEPSEEK_API_KEY。")
        return await self.call_deepseek(prompt)
    
    def get_prompt(self, prompt_type: str, **kwargs) -> str:
        """获取提示词模板"""
        return get_prompt_template(prompt_type, **kwargs)
    
    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        """处理输入数据的主要方法"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """获取智能体状态"""
        return {
            "name": self.name,
            "description": self.description,
            "expertise": self.expertise,
            "created_at": self.created_at.isoformat(),
            "conversation_count": len(self.conversation_history),
            "last_activity": self.conversation_history[-1]["timestamp"] if self.conversation_history else None
        }
    
    def reset(self):
        """重置智能体状态"""
        self.conversation_history.clear()
        logger.info(f"🔄 {self.name} 状态已重置")
    
    def __str__(self) -> str:
        return f"{self.name} - {self.description}"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"

class AgentRegistry:
    """智能体注册表"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
    
    def register(self, agent):
        """注册智能体（兼容传入类或实例）"""
        try:
            # 若传入类，则尝试无参实例化
            if isinstance(agent, type):
                try:
                    agent = agent()
                except Exception as e:
                    logger.error(f"❌ 智能体类实例化失败: {getattr(agent, '__name__', str(agent))}: {e}")
                    return
            name = getattr(agent, 'name', None)
            if not name:
                logger.error("❌ 智能体缺少 name 属性，注册失败")
                return
            self.agents[name] = agent
            logger.info(f"✅ 智能体已注册: {name}")
        except Exception as e:
            logger.error(f"❌ 注册智能体失败: {e}")
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取智能体"""
        return self.agents.get(name)
    
    def list_agents(self) -> List[str]:
        """列出所有智能体"""
        return list(self.agents.keys())
    
    def get_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有智能体状态"""
        return {name: agent.get_status() for name, agent in self.agents.items()}

# 全局智能体注册表
agent_registry = AgentRegistry()

def register_agent(target):
    """装饰器/函数：自动注册智能体
    - 既支持 @register_agent 装饰类（将用无参构造实例化）
    - 也支持直接传入实例进行注册
    """
    try:
        # 若是类（type），尝试无参实例化
        if isinstance(target, type):
            try:
                instance = target()
                agent_registry.register(instance)
                return target
            except Exception as e:
                logger.error(f"❌ 智能体类实例化失败: {target.__name__}: {e}")
                return target
        # 若是实例
        elif isinstance(target, BaseAgent):
            agent_registry.register(target)
            return target
        else:
            logger.error(f"❌ register_agent 收到不支持的目标: {type(target)}")
            return target
    except Exception as e:
        logger.error(f"❌ 注册智能体失败: {e}")
        return target

# 智能体工厂函数
def create_agent(agent_type: str, **kwargs) -> BaseAgent:
    """创建智能体实例"""
    from .questionnaire_designer import QuestionnaireDesignerAgent
    from .risk_assessor import RiskAssessorAgent
    from .data_analyzer import DataAnalyzerAgent
    from .report_generator import ReportGeneratorAgent
    
    agent_classes = {
        "questionnaire_designer": QuestionnaireDesignerAgent,
        "risk_assessor": RiskAssessorAgent,
        "data_analyzer": DataAnalyzerAgent,
        "report_generator": ReportGeneratorAgent
    }
    
    if agent_type not in agent_classes:
        raise ValueError(f"不支持的智能体类型: {agent_type}")
    
    agent_class = agent_classes[agent_type]
    return agent_class(**kwargs)

if __name__ == "__main__":
    # 测试智能体基类
    print("=== 智能体基类测试 ===")
    
    # 创建测试智能体
    class TestAgent(BaseAgent):
        async def process(self, input_data: Any) -> Any:
            return f"测试处理结果: {input_data}"
    
    test_agent = TestAgent("测试智能体", "用于测试的智能体", ["测试", "调试"])
    print(f"智能体创建成功: {test_agent}")
    
    # 测试状态获取
    status = test_agent.get_status()
    print(f"智能体状态: {status}")
    
    # 测试注册表
    agent_registry.register(test_agent)
    print(f"已注册智能体: {agent_registry.list_agents()}")
    
    print("✅ 智能体基类测试完成")
