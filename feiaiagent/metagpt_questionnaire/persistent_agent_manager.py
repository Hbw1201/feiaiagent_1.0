# -*- coding: utf-8 -*-
"""
持久化智能体管理器
保持智能体常开，避免重复初始化，大幅提升问卷填写速度
"""

import logging
import asyncio
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from .agents.base_agent import agent_registry, BaseAgent

logger = logging.getLogger(__name__)

@dataclass
class AgentSession:
    """智能体会话信息"""
    agent: BaseAgent
    last_used: datetime
    usage_count: int
    is_active: bool = True

class PersistentAgentManager:
    """持久化智能体管理器"""
    
    def __init__(self):
        self.agent_sessions: Dict[str, AgentSession] = {}
        self.session_lock = threading.Lock()
        self.cleanup_interval = 300  # 5分钟清理一次
        self.max_idle_time = 1800  # 30分钟无使用则关闭
        self._cleanup_thread = None
        self._start_cleanup_thread()
        
    def _start_cleanup_thread(self):
        """启动清理线程"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
            
        def cleanup_worker():
            while True:
                try:
                    self._cleanup_idle_agents()
                    threading.Event().wait(self.cleanup_interval)
                except Exception as e:
                    logger.error(f"❌ 智能体清理线程错误: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        logger.info("🧹 智能体清理线程已启动")
    
    def get_or_create_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """获取或创建智能体（保持常开）"""
        with self.session_lock:
            # 检查是否已有活跃会话
            if agent_name in self.agent_sessions:
                session = self.agent_sessions[agent_name]
                if session.is_active:
                    session.last_used = datetime.now()
                    session.usage_count += 1
                    logger.debug(f"♻️ 复用智能体: {agent_name} (使用次数: {session.usage_count})")
                    return session.agent
            
            # 创建新的智能体会话
            try:
                agent = agent_registry.get_agent(agent_name)
                if not agent:
                    logger.error(f"❌ 无法获取智能体: {agent_name}")
                    return None
                
                # 创建会话
                session = AgentSession(
                    agent=agent,
                    last_used=datetime.now(),
                    usage_count=1,
                    is_active=True
                )
                
                self.agent_sessions[agent_name] = session
                logger.info(f"🆕 创建智能体会话: {agent_name}")
                return agent
                
            except Exception as e:
                logger.error(f"❌ 创建智能体会话失败: {agent_name}, {e}")
                return None
    
    async def process_with_agent(self, agent_name: str, input_data: Any) -> Any:
        """使用指定智能体处理数据"""
        agent = self.get_or_create_agent(agent_name)
        if not agent:
            raise RuntimeError(f"无法获取智能体: {agent_name}")
        
        try:
            start_time = datetime.now()
            result = await agent.process(input_data)
            process_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"⚡ 智能体处理完成: {agent_name} (耗时: {process_time:.2f}s)")
            return result
            
        except Exception as e:
            logger.error(f"❌ 智能体处理失败: {agent_name}, {e}")
            raise
    
    def _cleanup_idle_agents(self):
        """清理空闲的智能体"""
        with self.session_lock:
            now = datetime.now()
            to_remove = []
            
            for agent_name, session in self.agent_sessions.items():
                if not session.is_active:
                    continue
                    
                idle_time = (now - session.last_used).total_seconds()
                if idle_time > self.max_idle_time:
                    to_remove.append(agent_name)
                    logger.info(f"🧹 清理空闲智能体: {agent_name} (空闲时间: {idle_time:.0f}s)")
            
            for agent_name in to_remove:
                session = self.agent_sessions.pop(agent_name, None)
                if session:
                    session.is_active = False
                    logger.info(f"🔒 智能体已关闭: {agent_name}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        with self.session_lock:
            active_sessions = sum(1 for s in self.agent_sessions.values() if s.is_active)
            total_usage = sum(s.usage_count for s in self.agent_sessions.values())
            
            return {
                "total_sessions": len(self.agent_sessions),
                "active_sessions": active_sessions,
                "total_usage": total_usage,
                "agents": {
                    name: {
                        "usage_count": session.usage_count,
                        "last_used": session.last_used.isoformat(),
                        "is_active": session.is_active
                    }
                    for name, session in self.agent_sessions.items()
                }
            }
    
    def reset_agent(self, agent_name: str):
        """重置指定智能体"""
        with self.session_lock:
            if agent_name in self.agent_sessions:
                session = self.agent_sessions[agent_name]
                session.agent.reset()
                session.usage_count = 0
                session.last_used = datetime.now()
                logger.info(f"🔄 智能体已重置: {agent_name}")
    
    def close_all_agents(self):
        """关闭所有智能体"""
        with self.session_lock:
            for agent_name, session in self.agent_sessions.items():
                session.is_active = False
                logger.info(f"🔒 智能体已关闭: {agent_name}")
            
            self.agent_sessions.clear()
            logger.info("🔒 所有智能体已关闭")

# 全局持久化智能体管理器
_persistent_manager = None

def get_persistent_manager() -> PersistentAgentManager:
    """获取全局持久化智能体管理器"""
    global _persistent_manager
    if _persistent_manager is None:
        _persistent_manager = PersistentAgentManager()
        logger.info("🚀 持久化智能体管理器已初始化")
    return _persistent_manager

# 便捷函数
async def process_with_persistent_agent(agent_name: str, input_data: Any) -> Any:
    """使用持久化智能体处理数据"""
    manager = get_persistent_manager()
    return await manager.process_with_agent(agent_name, input_data)

def get_agent_session_stats() -> Dict[str, Any]:
    """获取智能体会话统计"""
    manager = get_persistent_manager()
    return manager.get_session_stats()
