# -*- coding: utf-8 -*-
"""
智能动态问卷管理器
- 支持基础问题预生成 + 动态问题生成
- 实现智能跳转和问题依赖关系
- 根据用户回答动态调整问卷流程
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class QuestionType(Enum):
    """问题类型枚举"""
    BASIC = "basic"           # 基础问题（预生成）
    DYNAMIC = "dynamic"       # 动态问题（根据回答生成）
    FOLLOW_UP = "follow_up"   # 跟进问题（基于特定回答）

@dataclass
class Question:
    """问题数据结构"""
    id: str
    text: str
    prompt: str
    category: str
    question_type: QuestionType
    depends_on: Optional[Dict] = None
    auto_fill_value: Optional[str] = None
    dynamic_conditions: Optional[List[Dict]] = None  # 动态生成条件
    priority: int = 0  # 优先级，数字越小优先级越高

@dataclass
class UserResponse:
    """用户回答数据结构"""
    question_id: str
    answer: str
    timestamp: float
    confidence: float = 1.0  # 回答可信度

class IntelligentQuestionnaireManager:
    """智能动态问卷管理器"""
    
    def __init__(self):
        self.basic_questions: List[Question] = []
        self.dynamic_questions: List[Question] = []
        self.user_responses: List[UserResponse] = []
        self.current_question_index: int = 0
        self.questionnaire_completed: bool = False
        self.conversation_history: List[Dict] = []
        
        # 动态问题生成规则
        self.dynamic_rules = self._init_dynamic_rules()
        
        # 初始化基础问题
        self._init_basic_questions()
    
    def _init_dynamic_rules(self) -> Dict[str, List[Dict]]:
        """初始化动态问题生成规则"""
        return {
            "smoking_history": [
                {
                    "condition": {"value": "是", "values": ["是", "有", "吸烟", "抽过", "以前抽", "曾经抽"]},
                    "questions": [
                        {
                            "id": "smoking_freq_dynamic",
                            "text": "吸烟频率",
                            "prompt": "您平均每天大概抽多少支烟？",
                            "category": "吸烟史",
                            "priority": 1
                        },
                        {
                            "id": "smoking_years_dynamic", 
                            "text": "累计吸烟年数",
                            "prompt": "您总共吸了多少年烟呢？",
                            "category": "吸烟史",
                            "priority": 2
                        },
                        {
                            "id": "smoking_quit_dynamic",
                            "text": "目前是否戒烟",
                            "prompt": "那您现在是否已经戒烟了？",
                            "category": "吸烟史",
                            "priority": 3
                        }
                    ]
                }
            ],
            "smoking_quit": [
                {
                    "condition": {"value": "是", "values": ["是", "有", "戒了", "已经戒", "现在不抽"]},
                    "questions": [
                        {
                            "id": "smoking_quit_years_dynamic",
                            "text": "戒烟年数",
                            "prompt": "您戒烟有多少年了？",
                            "category": "吸烟史",
                            "priority": 1
                        }
                    ]
                }
            ],
            "passive_smoking": [
                {
                    "condition": {"value": "是", "values": ["是", "有", "经常", "会", "接触", "吸到"]},
                    "questions": [
                        {
                            "id": "passive_smoking_freq_dynamic",
                            "text": "被动吸烟频率",
                            "prompt": "您大概每天会接触二手烟多长时间呢？",
                            "category": "被动吸烟",
                            "priority": 1
                        },
                        {
                            "id": "passive_smoking_years_dynamic",
                            "text": "累计被动吸烟年数",
                            "prompt": "这种情况大概持续多少年了？",
                            "category": "被动吸烟",
                            "priority": 2
                        }
                    ]
                }
            ],
            "kitchen_fumes": [
                {
                    "condition": {"value": "是", "values": ["是", "有", "经常", "会", "接触"]},
                    "questions": [
                        {
                            "id": "kitchen_fumes_years_dynamic",
                            "text": "累计厨房油烟接触年数",
                            "prompt": "您接触厨房油烟有多少年了？",
                            "category": "厨房油烟",
                            "priority": 1
                        }
                    ]
                }
            ],
            "occupation_exposure": [
                {
                    "condition": {"value": "是", "values": ["是", "有", "接触", "会接触"]},
                    "questions": [
                        {
                            "id": "occupation_exposure_details_dynamic",
                            "text": "致癌物类型及累计接触年数",
                            "prompt": "具体是哪种物质，大概接触了多少年？",
                            "category": "职业暴露",
                            "priority": 1
                        }
                    ]
                }
            ],
            "personal_tumor_history": [
                {
                    "condition": {"value": "是", "values": ["是", "有", "得过", "患过"]},
                    "questions": [
                        {
                            "id": "personal_tumor_details_dynamic",
                            "text": "肿瘤类型及确诊年份",
                            "prompt": "可以具体说说肿瘤的类型和确诊年份吗？",
                            "category": "肿瘤相关史",
                            "priority": 1
                        }
                    ]
                }
            ],
            "family_cancer_history": [
                {
                    "condition": {"value": "是", "values": ["是", "有", "得过", "患过"]},
                    "questions": [
                        {
                            "id": "family_cancer_details_dynamic",
                            "text": "肿瘤类型及关系",
                            "prompt": "是哪位亲属，患的是哪种癌症呢？",
                            "category": "肿瘤相关史",
                            "priority": 1
                        }
                    ]
                }
            ],
            "recent_symptoms": [
                {
                    "condition": {"value": "是", "values": ["是", "有", "出现", "发生"]},
                    "questions": [
                        {
                            "id": "recent_symptoms_details_dynamic",
                            "text": "具体症状",
                            "prompt": "能具体描述一下是什么症状吗？",
                            "category": "近期症状",
                            "priority": 1
                        }
                    ]
                }
            ]
        }
    
    def _init_basic_questions(self):
        """初始化基础问题（预生成）"""
        basic_questions_data = [
            # 基本信息
            {"id": "name", "text": "姓名", "prompt": "请问怎么称呼您？", "category": "基本信息", "priority": 1},
            {"id": "gender", "text": "性别", "prompt": "您的性别是？", "category": "基本信息", "priority": 2},
            {"id": "birth_year", "text": "出生年份", "prompt": "请问您是哪一年出生的？", "category": "基本信息", "priority": 3},
            {"id": "height", "text": "身高(cm)", "prompt": "您的身高是多少厘米？", "category": "身体指标", "priority": 4},
            {"id": "weight", "text": "体重(kg)", "prompt": "您的体重是多少公斤呢？", "category": "身体指标", "priority": 5},
            
            # 核心风险因素
            {"id": "smoking_history", "text": "吸烟史", "prompt": "请问您有吸烟的习惯吗？", "category": "吸烟史", "priority": 6},
            {"id": "passive_smoking", "text": "被动吸烟", "prompt": "在您的生活或工作环境中，您会经常吸到二手烟吗？", "category": "被动吸烟", "priority": 7},
            {"id": "kitchen_fumes", "text": "长期厨房油烟接触", "prompt": "您平时做饭多吗？会经常接触厨房油烟吗？", "category": "厨房油烟", "priority": 8},
            {"id": "occupation", "text": "职业", "prompt": "请问您目前从事什么职业？", "category": "社会信息", "priority": 9},
            {"id": "occupation_exposure", "text": "职业致癌物质接触", "prompt": "您的工作中有没有可能接触到石棉、煤焦油、放射性物质等有害物质？", "category": "职业暴露", "priority": 10},
            
            # 病史相关
            {"id": "personal_tumor_history", "text": "既往个人肿瘤史", "prompt": "请问您以前得过肿瘤吗？", "category": "肿瘤相关史", "priority": 11},
            {"id": "family_cancer_history", "text": "三代以内直系亲属肺癌家族史", "prompt": "您的父母、兄弟姐妹或子女中，有人得过肺癌吗？", "category": "肿瘤相关史", "priority": 12},
            
            # 检查史
            {"id": "chest_ct_last_year", "text": "一年内胸部CT检查", "prompt": "在过去的一年里，您做过胸部CT检查吗？", "category": "影像检查", "priority": 13},
            {"id": "chronic_lung_disease", "text": "慢性肺部疾病史", "prompt": "您是否被诊断出患有慢性支气管炎、肺气肿、肺结核或慢阻肺等肺部疾病？", "category": "呼吸系统疾病史", "priority": 14},
            
            # 症状相关
            {"id": "recent_weight_loss", "text": "近半年不明原因消瘦", "prompt": "最近半年，您的体重有没有在没刻意减肥的情况下明显下降？", "category": "近期症状", "priority": 15},
            {"id": "recent_symptoms", "text": "最近是否有持续性干咳、痰中带血、声音嘶哑等", "prompt": "那最近有没有出现持续干咳、痰里带血、或者声音嘶哑这些情况呢？", "category": "近期症状", "priority": 16},
            
            # 健康自评
            {"id": "self_feeling", "text": "最近自我感觉", "prompt": "总的来说，您感觉最近身体状态怎么样？", "category": "健康自评", "priority": 17}
        ]
        
        for q_data in basic_questions_data:
            question = Question(
                id=q_data["id"],
                text=q_data["text"],
                prompt=q_data["prompt"],
                category=q_data["category"],
                question_type=QuestionType.BASIC,
                priority=q_data["priority"]
            )
            self.basic_questions.append(question)
    
    def get_next_question(self, user_answer: Optional[str] = None) -> Dict[str, Any]:
        """获取下一个问题（支持动态生成）"""
        try:
            # 处理用户回答
            if user_answer and self.current_question_index > 0:
                # 获取当前问题（索引已经递增，所以需要减1）
                current_question_index = self.current_question_index - 1
                if current_question_index < len(self.basic_questions):
                    current_question = self.basic_questions[current_question_index]
                    self._process_user_answer(current_question.id, user_answer)
                    
                    # 根据回答生成动态问题
                    self._generate_dynamic_questions(current_question.id, user_answer)
            
            # 获取下一个问题
            next_question = self._get_next_question()
            
            if next_question:
                return {
                    "status": "next_question",
                    "question": next_question.prompt,
                    "question_id": next_question.id,
                    "category": next_question.category,
                    "question_type": next_question.question_type.value,
                    "progress": f"{self.current_question_index}/{len(self.basic_questions) + len(self.dynamic_questions)}",
                    "total_questions": len(self.basic_questions) + len(self.dynamic_questions)
                }
            else:
                # 问卷完成
                return self._complete_questionnaire()
                
        except Exception as e:
            logger.error(f"获取下一个问题失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def _process_user_answer(self, question_id: str, answer: str):
        """处理用户回答"""
        response = UserResponse(
            question_id=question_id,
            answer=answer,
            timestamp=time.time()
        )
        self.user_responses.append(response)
        
        # 记录对话历史
        self.conversation_history.append({
            "question_id": question_id,
            "answer": answer,
            "timestamp": response.timestamp
        })
        
        logger.info(f"记录用户回答: {question_id} -> {answer}")
    
    def _generate_dynamic_questions(self, question_id: str, answer: str):
        """根据用户回答生成动态问题"""
        if question_id not in self.dynamic_rules:
            return
        
        rules = self.dynamic_rules[question_id]
        
        for rule in rules:
            condition = rule["condition"]
            if self._check_condition(answer, condition):
                # 生成动态问题
                for q_data in rule["questions"]:
                    # 检查是否已经存在相同的问题
                    if not self._question_exists(q_data["id"]):
                        question = Question(
                            id=q_data["id"],
                            text=q_data["text"],
                            prompt=q_data["prompt"],
                            category=q_data["category"],
                            question_type=QuestionType.DYNAMIC,
                            priority=q_data["priority"],
                            depends_on={"id": question_id, "value": answer}
                        )
                        self.dynamic_questions.append(question)
                        logger.info(f"生成动态问题: {q_data['id']} - {q_data['text']}")
    
    def _check_condition(self, answer: str, condition: Dict) -> bool:
        """检查回答是否满足条件"""
        answer_lower = answer.lower().strip()
        
        # 检查是否匹配任何可能的值
        if "values" in condition:
            for value in condition["values"]:
                if value.lower() in answer_lower:
                    return True
        
        # 检查精确匹配
        if "value" in condition:
            if condition["value"].lower() in answer_lower:
                return True
        
        return False
    
    def _question_exists(self, question_id: str) -> bool:
        """检查问题是否已存在"""
        # 检查基础问题
        for q in self.basic_questions:
            if q.id == question_id:
                return True
        
        # 检查动态问题
        for q in self.dynamic_questions:
            if q.id == question_id:
                return True
        
        return False
    
    def _get_next_question(self) -> Optional[Question]:
        """获取下一个问题"""
        # 首先处理基础问题
        if self.current_question_index < len(self.basic_questions):
            question = self.basic_questions[self.current_question_index]
            self.current_question_index += 1
            return question
        
        # 然后处理动态问题
        dynamic_index = self.current_question_index - len(self.basic_questions)
        if dynamic_index < len(self.dynamic_questions):
            # 按优先级排序动态问题
            sorted_dynamic = sorted(self.dynamic_questions, key=lambda x: x.priority)
            question = sorted_dynamic[dynamic_index]
            self.current_question_index += 1
            return question
        
        return None
    
    def _complete_questionnaire(self) -> Dict[str, Any]:
        """完成问卷"""
        self.questionnaire_completed = True
        
        # 生成报告
        report = self._generate_report()
        
        return {
            "status": "completed",
            "is_complete": True,
            "report": report,
            "total_questions": len(self.basic_questions) + len(self.dynamic_questions),
            "answered_questions": len(self.user_responses),
            "basic_questions": len(self.basic_questions),
            "dynamic_questions": len(self.dynamic_questions)
        }
    
    def _generate_report(self) -> str:
        """生成评估报告"""
        report = "肺癌早筛风险评估报告（智能动态问卷）\n\n" + "=" * 60 + "\n\n"
        
        # 基本信息
        report += "【基本信息】\n"
        for response in self.user_responses:
            if response.question_id in ["name", "gender", "birth_year", "height", "weight"]:
                question_text = self._get_question_text(response.question_id)
                report += f"{question_text}: {response.answer}\n"
        
        # 风险评估
        report += "\n【风险评估】\n"
        risk_score = self._calculate_risk_score()
        
        # 根据风险分数确定风险等级
        if risk_score >= 8:
            risk_level = "高风险"
            risk_desc = "🔴 高风险：强烈建议立即咨询呼吸科或胸外科医生，并进行低剂量螺旋CT筛查。"
        elif risk_score >= 4:
            risk_level = "中风险"
            risk_desc = "🟡 中风险：建议定期体检，并与医生讨论是否需要进行肺癌筛查。"
        else:
            risk_level = "低风险"
            risk_desc = "🟢 低风险：建议保持健康生活方式，远离烟草，并保持对身体变化的警觉。"
        
        report += f"风险等级: {risk_level}\n"
        report += f"风险分数: {risk_score}/10\n"
        report += f"建议: {risk_desc}\n"
        
        # 问卷统计
        report += f"\n【问卷统计】\n"
        report += f"基础问题: {len(self.basic_questions)} 个\n"
        report += f"动态问题: {len(self.dynamic_questions)} 个\n"
        report += f"总问题数: {len(self.basic_questions) + len(self.dynamic_questions)} 个\n"
        report += f"已回答数: {len(self.user_responses)} 个\n"
        
        report += "\n" + "=" * 60 + "\n"
        report += f"报告生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return report
    
    def _get_question_text(self, question_id: str) -> str:
        """获取问题文本"""
        for q in self.basic_questions + self.dynamic_questions:
            if q.id == question_id:
                return q.text
        return question_id
    
    def _calculate_risk_score(self) -> int:
        """计算风险分数"""
        risk_score = 0
        
        # 将回答转换为字典便于查找
        answers = {r.question_id: r.answer for r in self.user_responses}
        
        # 吸烟史评分
        if answers.get("smoking_history", "").lower() in ["是", "有", "吸烟", "抽过"]:
            risk_score += 3
            # 如果有吸烟频率和年数，进一步评分
            if "smoking_freq_dynamic" in answers and "smoking_years_dynamic" in answers:
                try:
                    freq = float(answers["smoking_freq_dynamic"])
                    years = float(answers["smoking_years_dynamic"])
                    pack_years = (freq * years) / 20
                    if pack_years > 30:
                        risk_score += 2
                    elif pack_years > 20:
                        risk_score += 1
                except (ValueError, TypeError):
                    pass
        
        # 被动吸烟评分
        if answers.get("passive_smoking", "").lower() in ["是", "有", "经常", "会"]:
            risk_score += 1
        
        # 职业暴露评分
        if answers.get("occupation_exposure", "").lower() in ["是", "有", "接触"]:
            risk_score += 2
        
        # 家族史评分
        if answers.get("family_cancer_history", "").lower() in ["是", "有", "得过"]:
            risk_score += 2
        
        # 症状评分
        if answers.get("recent_symptoms", "").lower() in ["是", "有", "出现"]:
            risk_score += 3
        
        return min(risk_score, 10)  # 最高10分
    
    def get_questionnaire_stats(self) -> Dict[str, Any]:
        """获取问卷统计信息"""
        return {
            "basic_questions": len(self.basic_questions),
            "dynamic_questions": len(self.dynamic_questions),
            "total_questions": len(self.basic_questions) + len(self.dynamic_questions),
            "answered_questions": len(self.user_responses),
            "completion_rate": len(self.user_responses) / (len(self.basic_questions) + len(self.dynamic_questions)) * 100,
            "questionnaire_completed": self.questionnaire_completed
        }
    
    def reset_questionnaire(self):
        """重置问卷"""
        self.dynamic_questions.clear()
        self.user_responses.clear()
        self.current_question_index = 0
        self.questionnaire_completed = False
        self.conversation_history.clear()
        logger.info("问卷已重置")
