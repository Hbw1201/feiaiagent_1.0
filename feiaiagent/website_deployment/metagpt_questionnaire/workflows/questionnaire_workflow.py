# -*- coding: utf-8 -*-
"""
问卷工作流协调器
协调各个智能体的工作流程，实现端到端的问卷分析
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from ..agents.base_agent import agent_registry
from ..models.questionnaire import Questionnaire, UserResponse, RiskAssessment, AnalysisReport
from ..config.metagpt_config import PROJECT_ROOT

logger = logging.getLogger(__name__)

class QuestionnaireWorkflow:
    """问卷工作流协调器"""
    
    def __init__(self):
        self.workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.agents = {}
        self.workflow_history: List[Dict[str, Any]] = []
        self._initialize_agents()
    
    def _initialize_agents(self):
        """初始化智能体"""
        try:
            # 获取已注册的智能体
            self.agents = {
                "designer": agent_registry.get_agent("问卷设计专家"),
                "assessor": agent_registry.get_agent("风险评估专家"),
                "analyzer": agent_registry.get_agent("数据分析专家"),
                "generator": agent_registry.get_agent("报告生成专家"),
                "question_selector": agent_registry.get_agent("智能问题选择专家")
            }
            
            # 检查智能体是否都已注册
            missing_agents = [name for name, agent in self.agents.items() if agent is None]
            if missing_agents:
                logger.warning(f"⚠️ 以下智能体未注册: {missing_agents}")
            
            logger.info(f"✅ 工作流初始化完成，智能体数量: {len([a for a in self.agents.values() if a])}")
            
        except Exception as e:
            logger.error(f"❌ 智能体初始化失败: {e}")
    
    async def run_complete_workflow(self, 
                                  questionnaire_data: Optional[Dict[str, Any]] = None,
                                  user_responses: Optional[List[UserResponse]] = None,
                                  user_profile: Optional[Dict[str, Any]] = None,
                                  workflow_type: str = "standard") -> Dict[str, Any]:
        """运行完整的工作流"""
        workflow_start = datetime.now()
        logger.info(f"🚀 开始执行工作流: {self.workflow_id}")
        
        try:
            workflow_result = {
                "workflow_id": self.workflow_id,
                "workflow_type": workflow_type,
                "start_time": workflow_start.isoformat(),
                "status": "running",
                "stages": [],
                "final_results": {},
                "error": None
            }
            
            # 阶段1: 问卷设计/加载
            questionnaire = await self._stage_questionnaire_design(questionnaire_data, workflow_result)
            
            # 阶段2: 风险评估
            risk_assessment = await self._stage_risk_assessment(user_responses, questionnaire, user_profile, workflow_result)
            
            # 阶段3: 数据分析
            analysis_result = await self._stage_data_analysis(user_responses, questionnaire, workflow_result)
            
            # 阶段4: 报告生成
            report = await self._stage_report_generation(analysis_result, risk_assessment, questionnaire, user_profile, workflow_result)
            
            # 完成工作流
            workflow_result["status"] = "completed"
            workflow_result["final_results"] = {
                "questionnaire": questionnaire.to_dict() if questionnaire else None,
                "risk_assessment": risk_assessment.to_dict() if risk_assessment else None,
                "analysis_result": analysis_result,
                "report": report.to_dict() if report else None
            }
            
            # 保存工作流历史
            self.workflow_history.append(workflow_result)
            
            logger.info(f"✅ 工作流执行完成: {self.workflow_id}")
            return workflow_result
            
        except Exception as e:
            error_msg = f"工作流执行失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            workflow_result["status"] = "failed"
            workflow_result["error"] = error_msg
            workflow_result["end_time"] = datetime.now().isoformat()
            
            # 保存失败的工作流历史
            self.workflow_history.append(workflow_result)
            
            return workflow_result
    
    async def _stage_questionnaire_design(self, questionnaire_data: Optional[Dict[str, Any]], 
                                        workflow_result: Dict[str, Any]) -> Optional[Questionnaire]:
        """问卷设计阶段"""
        stage_name = "问卷设计"
        stage_start = datetime.now()
        
        try:
            logger.info(f"📝 开始{stage_name}阶段")
            
            if questionnaire_data:
                # 如果提供了问卷数据，直接使用
                questionnaire = self._create_questionnaire_from_data(questionnaire_data)
                stage_result = {
                    "stage": stage_name,
                    "status": "completed",
                    "start_time": stage_start.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "result": "使用提供的问卷数据"
                }
            else:
                # 使用智能体设计问卷
                if self.agents.get("designer"):
                    requirements = {
                        "context": "设计一个肺癌早筛问卷",
                        "type": "健康评估",
                        "target_audience": "40-70岁人群",
                        "question_count": "20个",
                        "estimated_time": "15-20分钟",
                        "template_type": "lung_cancer"
                    }
                    
                    questionnaire = await self.agents["designer"].process(requirements)
                    stage_result = {
                        "stage": stage_name,
                        "status": "completed",
                        "start_time": stage_start.isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "result": f"智能体设计完成: {questionnaire.title}"
                    }
                else:
                    # 创建默认问卷
                    questionnaire = self._create_default_questionnaire()
                    stage_result = {
                        "stage": stage_name,
                        "status": "completed",
                        "start_time": stage_start.isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "result": "使用默认问卷模板"
                    }
            
            workflow_result["stages"].append(stage_result)
            logger.info(f"✅ {stage_name}阶段完成")
            return questionnaire
            
        except Exception as e:
            error_msg = f"{stage_name}阶段失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            stage_result = {
                "stage": stage_name,
                "status": "failed",
                "start_time": stage_start.isoformat(),
                "end_time": datetime.now().isoformat(),
                "error": error_msg
            }
            workflow_result["stages"].append(stage_result)
            
            # 返回默认问卷
            return self._create_default_questionnaire()
    
    async def _stage_risk_assessment(self, user_responses: Optional[List[UserResponse]], 
                                   questionnaire: Optional[Questionnaire],
                                   user_profile: Optional[Dict[str, Any]],
                                   workflow_result: Dict[str, Any]) -> Optional[RiskAssessment]:
        """风险评估阶段"""
        stage_name = "风险评估"
        stage_start = datetime.now()
        
        try:
            logger.info(f"🔍 开始{stage_name}阶段")
            
            if not user_responses:
                stage_result = {
                    "stage": stage_name,
                    "status": "skipped",
                    "start_time": stage_start.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "result": "无用户回答数据，跳过风险评估"
                }
                workflow_result["stages"].append(stage_result)
                return None
            
            # 使用风险评估智能体
            if self.agents.get("assessor"):
                risk_assessment = await self.agents["assessor"].process({
                    "responses": user_responses,
                    "questionnaire": questionnaire.to_dict() if questionnaire else None,
                    "user_profile": user_profile or {}
                })
                
                stage_result = {
                    "stage": stage_name,
                    "status": "completed",
                    "start_time": stage_start.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "result": f"风险评估完成: {risk_assessment.overall_risk.value}风险"
                }
            else:
                # 创建默认风险评估
                risk_assessment = self._create_default_risk_assessment()
                stage_result = {
                    "stage": stage_name,
                    "status": "completed",
                    "start_time": stage_start.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "result": "使用默认风险评估"
                }
            
            workflow_result["stages"].append(stage_result)
            logger.info(f"✅ {stage_name}阶段完成")
            return risk_assessment
            
        except Exception as e:
            error_msg = f"{stage_name}阶段失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            stage_result = {
                "stage": stage_name,
                "status": "failed",
                "start_time": stage_start.isoformat(),
                "end_time": datetime.now().isoformat(),
                "error": error_msg
            }
            workflow_result["stages"].append(stage_result)
            
            # 返回默认风险评估
            return self._create_default_risk_assessment()
    
    async def _stage_data_analysis(self, user_responses: Optional[List[UserResponse]], 
                                 questionnaire: Optional[Questionnaire],
                                 workflow_result: Dict[str, Any]) -> Dict[str, Any]:
        """数据分析阶段"""
        stage_name = "数据分析"
        stage_start = datetime.now()
        
        try:
            logger.info(f"📊 开始{stage_name}阶段")
            
            if not user_responses:
                stage_result = {
                    "stage": stage_name,
                    "status": "skipped",
                    "start_time": stage_start.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "result": "无用户回答数据，跳过数据分析"
                }
                workflow_result["stages"].append(stage_result)
                return {"responses_count": 0}
            
            # 使用数据分析智能体
            if self.agents.get("analyzer"):
                analysis_result = await self.agents["analyzer"].process({
                    "responses": user_responses,
                    "questionnaire": questionnaire.to_dict() if questionnaire else None,
                    "analysis_type": "comprehensive"
                })
                
                stage_result = {
                    "stage": stage_name,
                    "status": "completed",
                    "start_time": stage_start.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "result": f"数据分析完成: {len(analysis_result.get('insights', []))}个洞察"
                }
            else:
                # 创建默认分析结果
                analysis_result = self._create_default_analysis_result(user_responses)
                stage_result = {
                    "stage": stage_name,
                    "status": "completed",
                    "start_time": stage_start.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "result": "使用默认数据分析结果"
                }
            
            workflow_result["stages"].append(stage_result)
            logger.info(f"✅ {stage_name}阶段完成")
            return analysis_result
            
        except Exception as e:
            error_msg = f"{stage_name}阶段失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            stage_result = {
                "stage": stage_name,
                "status": "failed",
                "start_time": stage_start.isoformat(),
                "end_time": datetime.now().isoformat(),
                "error": error_msg
            }
            workflow_result["stages"].append(stage_result)
            
            # 返回默认分析结果
            return self._create_default_analysis_result(user_responses or [])
    
    async def _stage_report_generation(self, analysis_result: Dict[str, Any],
                                     risk_assessment: Optional[RiskAssessment],
                                     questionnaire: Optional[Questionnaire],
                                     user_profile: Optional[Dict[str, Any]],
                                     workflow_result: Dict[str, Any]) -> Optional[AnalysisReport]:
        """报告生成阶段"""
        stage_name = "报告生成"
        stage_start = datetime.now()
        
        try:
            logger.info(f"📝 开始{stage_name}阶段")
            
            # 使用报告生成智能体
            if self.agents.get("generator"):
                report = await self.agents["generator"].process({
                    "analysis_data": analysis_result,
                    "risk_assessment": risk_assessment,
                    "questionnaire": questionnaire,
                    "report_type": "comprehensive",
                    "user_profile": user_profile or {}
                })
                
                stage_result = {
                    "stage": stage_name,
                    "status": "completed",
                    "start_time": stage_start.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "result": f"报告生成完成: {report.title}"
                }
            else:
                # 创建默认报告
                report = self._create_default_report(analysis_result, risk_assessment)
                stage_result = {
                    "stage": stage_name,
                    "status": "completed",
                    "start_time": stage_start.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "result": "使用默认报告模板"
                }
            
            workflow_result["stages"].append(stage_result)
            logger.info(f"✅ {stage_name}阶段完成")
            return report
            
        except Exception as e:
            error_msg = f"{stage_name}阶段失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            stage_result = {
                "stage": stage_name,
                "status": "failed",
                "start_time": stage_start.isoformat(),
                "end_time": datetime.now().isoformat(),
                "error": error_msg
            }
            workflow_result["stages"].append(stage_result)
            
            # 返回默认报告
            return self._create_default_report(analysis_result, risk_assessment)
    
    def _create_questionnaire_from_data(self, data: Dict[str, Any]) -> Questionnaire:
        """从数据创建问卷"""
        from ..models.questionnaire import create_lung_cancer_questionnaire
        
        if data.get('type') == 'lung_cancer':
            return create_lung_cancer_questionnaire()
        else:
            # 创建通用问卷
            questionnaire = Questionnaire(
                id=data.get('id', f"questionnaire_{uuid.uuid4().hex[:8]}"),
                title=data.get('title', '健康评估问卷'),
                description=data.get('description', '基于用户需求定制的健康评估问卷'),
                version=data.get('version', '1.0'),
                estimated_time=data.get('estimated_time', '15-20分钟')
            )
            return questionnaire
    
    def _create_default_questionnaire(self) -> Questionnaire:
        """创建默认问卷"""
        from ..models.questionnaire import create_lung_cancer_questionnaire
        return create_lung_cancer_questionnaire()
    
    def _create_default_risk_assessment(self) -> RiskAssessment:
        """创建默认风险评估"""
        from ..models.questionnaire import RiskLevel
        
        return RiskAssessment(
            session_id="default",
            overall_risk=RiskLevel.MEDIUM,
            risk_score=3.0,
            risk_factors=[{
                "factor": "default",
                "name": "默认评估",
                "level": "moderate",
                "score": 3.0,
                "details": "风险评估数据不可用",
                "description": "建议进行专业医学评估"
            }],
            recommendations=[
                "建议进行专业医学评估",
                "定期进行健康检查",
                "保持健康生活方式"
            ]
        )
    
    def _create_default_analysis_result(self, responses: List[UserResponse]) -> Dict[str, Any]:
        """创建默认分析结果"""
        return {
            "analysis_id": f"default_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "responses_count": len(responses),
            "analysis_type": "default",
            "basic_statistics": {
                "total_responses": len(responses),
                "unique_questions": len(set(r.question_id for r in responses)) if responses else 0
            },
            "category_analysis": {},
            "pattern_analysis": {},
            "data_quality": {
                "overall_score": 0.7,
                "completeness": 0.8,
                "consistency": 0.7,
                "validity": 0.9,
                "timeliness": 0.5
            },
            "insights": [
                {
                    "title": "基础数据分析",
                    "description": "基于默认分析模板生成的基础洞察",
                    "significance": "medium"
                }
            ],
            "summary": {
                "key_findings": ["数据收集完成"],
                "recommendations": ["建议进行专业分析"],
                "next_steps": ["继续监控数据质量"]
            }
        }
    
    def _create_default_report(self, analysis_result: Dict[str, Any], 
                             risk_assessment: Optional[RiskAssessment]) -> AnalysisReport:
        """创建默认报告"""
        return AnalysisReport(
            session_id="default",
            title="默认分析报告",
            content="# 默认分析报告\n\n基于系统默认模板生成的报告。",
            risk_assessment=risk_assessment or self._create_default_risk_assessment(),
            data_insights=analysis_result.get('insights', []),
            generated_at=datetime.now()
        )
    
    async def run_custom_workflow(self, workflow_steps: List[str], 
                                workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """运行自定义工作流"""
        logger.info(f"🔧 开始执行自定义工作流: {workflow_steps}")
        
        workflow_result = {
            "workflow_id": f"custom_{self.workflow_id}",
            "workflow_type": "custom",
            "start_time": datetime.now().isoformat(),
            "status": "running",
            "stages": [],
            "final_results": {},
            "error": None
        }
        
        try:
            for step in workflow_steps:
                if step == "questionnaire_design":
                    questionnaire = await self._stage_questionnaire_design(
                        workflow_data.get('questionnaire_data'), workflow_result
                    )
                    workflow_result["final_results"]["questionnaire"] = questionnaire.to_dict() if questionnaire else None
                
                elif step == "risk_assessment":
                    risk_assessment = await self._stage_risk_assessment(
                        workflow_data.get('user_responses'),
                        workflow_result["final_results"].get("questionnaire"),
                        workflow_data.get('user_profile'),
                        workflow_result
                    )
                    workflow_result["final_results"]["risk_assessment"] = risk_assessment.to_dict() if risk_assessment else None
                
                elif step == "data_analysis":
                    analysis_result = await self._stage_data_analysis(
                        workflow_data.get('user_responses'),
                        workflow_result["final_results"].get("questionnaire"),
                        workflow_result
                    )
                    workflow_result["final_results"]["analysis_result"] = analysis_result
                
                elif step == "report_generation":
                    report = await self._stage_report_generation(
                        workflow_result["final_results"].get("analysis_result"),
                        workflow_result["final_results"].get("risk_assessment"),
                        workflow_result["final_results"].get("questionnaire"),
                        workflow_data.get('user_profile'),
                        workflow_result
                    )
                    workflow_result["final_results"]["report"] = report.to_dict() if report else None
            
            workflow_result["status"] = "completed"
            workflow_result["end_time"] = datetime.now().isoformat()
            
            # 保存工作流历史
            self.workflow_history.append(workflow_result)
            
            logger.info(f"✅ 自定义工作流执行完成")
            return workflow_result
            
        except Exception as e:
            error_msg = f"自定义工作流执行失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            workflow_result["status"] = "failed"
            workflow_result["error"] = error_msg
            workflow_result["end_time"] = datetime.now().isoformat()
            
            # 保存失败的工作流历史
            self.workflow_history.append(workflow_result)
            
            return workflow_result
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流状态"""
        for workflow in self.workflow_history:
            if workflow["workflow_id"] == workflow_id:
                return workflow
        return None
    
    def get_workflow_history(self) -> List[Dict[str, Any]]:
        """获取工作流历史"""
        return self.workflow_history
    
    def export_workflow_result(self, workflow_result: Dict[str, Any], 
                             output_dir: Optional[str] = None) -> str:
        """导出工作流结果"""
        if not output_dir:
            output_dir = PROJECT_ROOT / "outputs" / "workflows"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 生成输出文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"workflow_{workflow_result['workflow_id']}_{timestamp}.json"
        filepath = output_path / filename
        
        # 保存工作流结果
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(workflow_result, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"✅ 工作流结果已导出到: {filepath}")
        return str(filepath)
    
    async def run_intelligent_questionnaire_workflow(self,
                                                   questionnaire_data: Optional[Dict[str, Any]] = None,
                                                   user_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """运行智能问卷工作流 - 支持动态问题选择"""
        workflow_start = datetime.now()
        logger.info(f"🧠 开始执行智能问卷工作流: {self.workflow_id}")
        
        try:
            workflow_result = {
                "workflow_id": self.workflow_id,
                "workflow_type": "intelligent_questionnaire",
                "start_time": workflow_start.isoformat(),
                "status": "running",
                "stages": [],
                "final_results": {},
                "error": None,
                "questionnaire_session": {
                    "answered_questions": [],
                    "current_question": None,
                    "progress": 0,
                    "estimated_remaining": 0
                }
            }
            
            # 阶段1: 创建/加载问卷
            questionnaire = await self._stage_questionnaire_design(questionnaire_data, workflow_result)
            if not questionnaire:
                raise RuntimeError("问卷创建失败")
            
            # 初始化智能问题选择会话
            session_data = {
                "questionnaire": questionnaire,
                "answered_questions": [],
                "available_questions": questionnaire.questions.copy(),
                "conversation_history": [],
                "user_profile": user_profile or {}
            }
            
            workflow_result["questionnaire_session"]["total_questions"] = len(questionnaire.questions)
            workflow_result["final_results"]["questionnaire"] = questionnaire.to_dict()
            workflow_result["final_results"]["session_data"] = session_data
            
            logger.info(f"✅ 智能问卷工作流初始化完成: {questionnaire.title}")
            workflow_result["status"] = "initialized"
            
            return workflow_result
            
        except Exception as e:
            error_msg = f"智能问卷工作流初始化失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            workflow_result["status"] = "failed"
            workflow_result["error"] = error_msg
            workflow_result["end_time"] = datetime.now().isoformat()
            
            return workflow_result

    async def get_next_intelligent_question(self, 
                                          session_data: Dict[str, Any],
                                          new_response: Optional[UserResponse] = None) -> Dict[str, Any]:
        """获取下一个智能推荐问题"""
        try:
            # 如果有新回答，添加到会话数据
            if new_response:
                session_data["answered_questions"].append(new_response)
                session_data["conversation_history"].append({
                    "type": "user_response",
                    "question_id": new_response.question_id,
                    "answer": new_response.answer,
                    "timestamp": datetime.now().isoformat()
                })
                
                # 从可用问题中移除已回答的问题
                session_data["available_questions"] = [
                    q for q in session_data["available_questions"] 
                    if q.id != new_response.question_id
                ]
            
            # 使用智能问题选择器
            if self.agents.get("question_selector"):
                selection_result = await self.agents["question_selector"].process({
                    "answered_questions": session_data["answered_questions"],
                    "available_questions": session_data["available_questions"],
                    "conversation_history": session_data["conversation_history"],
                    "user_profile": session_data["user_profile"]
                })
                
                if selection_result["status"] == "completed":
                    # 问卷完成，进行分析和报告生成
                    analysis_result = await self._finalize_intelligent_questionnaire(session_data)
                    return {
                        "status": "completed",
                        "analysis_result": analysis_result,
                        "session_data": session_data
                    }
                elif selection_result["status"] == "next_question":
                    next_question_info = selection_result["next_question"]
                    session_data["current_question"] = next_question_info
                    
                    return {
                        "status": "next_question",
                        "question": next_question_info,
                        "progress": self._calculate_progress(session_data),
                        "alternatives": selection_result.get("alternatives", []),
                        "session_data": session_data
                    }
            
            # 降级到简单的顺序选择
            if session_data["available_questions"]:
                next_question = session_data["available_questions"][0]
                return {
                    "status": "next_question",
                    "question": {
                        "id": next_question.id,
                        "text": next_question.text,
                        "optimized_prompt": next_question.text,
                        "category": next_question.category,
                        "priority_score": 50,
                        "selection_reason": "顺序选择"
                    },
                    "progress": self._calculate_progress(session_data),
                    "session_data": session_data
                }
            else:
                # 问卷完成
                analysis_result = await self._finalize_intelligent_questionnaire(session_data)
                return {
                    "status": "completed",
                    "analysis_result": analysis_result,
                    "session_data": session_data
                }
                
        except Exception as e:
            logger.error(f"❌ 获取下一个智能问题失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "session_data": session_data
            }

    async def _finalize_intelligent_questionnaire(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """完成智能问卷并进行分析"""
        try:
            logger.info(f"🎯 完成智能问卷，开始最终分析")
            
            answered_questions = session_data["answered_questions"]
            questionnaire = session_data["questionnaire"]
            user_profile = session_data["user_profile"]
            
            # 风险评估
            risk_assessment = None
            if self.agents.get("assessor") and answered_questions:
                risk_assessment = await self.agents["assessor"].process({
                    "responses": answered_questions,
                    "questionnaire": questionnaire.to_dict() if questionnaire else None,
                    "user_profile": user_profile
                })
            
            # 数据分析
            analysis_result = None
            if self.agents.get("analyzer") and answered_questions:
                analysis_result = await self.agents["analyzer"].process({
                    "responses": answered_questions,
                    "questionnaire": questionnaire.to_dict() if questionnaire else None,
                    "analysis_type": "intelligent_questionnaire"
                })
            
            # 报告生成
            report = None
            if self.agents.get("generator"):
                report = await self.agents["generator"].process({
                    "analysis_data": analysis_result or {},
                    "risk_assessment": risk_assessment,
                    "questionnaire": questionnaire,
                    "report_type": "intelligent_assessment",
                    "user_profile": user_profile
                })
            
            return {
                "questionnaire": questionnaire.to_dict() if questionnaire else None,
                "risk_assessment": risk_assessment.to_dict() if risk_assessment else None,
                "analysis_result": analysis_result,
                "report": report.to_dict() if report else None,
                "total_questions_asked": len(answered_questions),
                "completion_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 智能问卷最终分析失败: {e}")
            return {
                "error": str(e),
                "total_questions_asked": len(session_data.get("answered_questions", [])),
                "completion_time": datetime.now().isoformat()
            }

    def _calculate_progress(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算问卷进度"""
        answered_count = len(session_data["answered_questions"])
        total_questions = session_data.get("total_questions", len(session_data.get("available_questions", [])) + answered_count)
        
        progress_percentage = (answered_count / total_questions * 100) if total_questions > 0 else 0
        
        return {
            "answered": answered_count,
            "total": total_questions,
            "percentage": round(progress_percentage, 1),
            "remaining": max(0, total_questions - answered_count)
        }

    def get_agent_status(self) -> Dict[str, Any]:
        """获取智能体状态"""
        return {
            "workflow_id": self.workflow_id,
            "agents": {name: agent.get_status() if agent else None 
                      for name, agent in self.agents.items()},
            "total_agents": len([a for a in self.agents.values() if a]),
            "workflow_history_count": len(self.workflow_history)
        }

# 工作流工厂函数
def create_workflow(workflow_type: str = "standard") -> QuestionnaireWorkflow:
    """创建工作流实例"""
    if workflow_type == "standard":
        return QuestionnaireWorkflow()
    else:
        raise ValueError(f"不支持的工作流类型: {workflow_type}")

if __name__ == "__main__":
    # 测试工作流协调器
    print("=== 工作流协调器测试 ===")
    
    # 创建工作流
    workflow = create_workflow("standard")
    print(f"工作流创建成功: {workflow.workflow_id}")
    
    # 测试智能体状态
    agent_status = workflow.get_agent_status()
    print(f"智能体状态: {agent_status}")
    
    # 测试完整工作流
    import asyncio
    
    async def test_workflow():
        # 模拟用户回答
        from ..models.questionnaire import UserResponse
        
        test_responses = [
            UserResponse("name", "张三"),
            UserResponse("age", "55"),
            UserResponse("smoking", "1"),
            UserResponse("occupational_exposure", "2"),
            UserResponse("family_history", "2")
        ]
        
        result = await workflow.run_complete_workflow(
            user_responses=test_responses,
            user_profile={"age": "55", "gender": "男"}
        )
        
        print(f"工作流执行结果: {result['status']}")
        print(f"执行阶段数: {len(result['stages'])}")
        
        if result['status'] == 'completed':
            print("✅ 工作流执行成功")
            # 导出结果
            output_file = workflow.export_workflow_result(result)
            print(f"结果已导出到: {output_file}")
        else:
            print(f"❌ 工作流执行失败: {result.get('error')}")
    
    # 运行测试
    asyncio.run(test_workflow())
    
    print("✅ 工作流协调器测试完成")
