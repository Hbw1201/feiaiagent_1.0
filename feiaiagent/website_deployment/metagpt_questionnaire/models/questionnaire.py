# -*- coding: utf-8 -*-
"""
问卷数据模型
定义问卷、问题、答案等数据结构
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

class QuestionType(Enum):
    """问题类型枚举"""
    TEXT = "text"           # 文本输入
    SINGLE_CHOICE = "single_choice"  # 单选
    MULTIPLE_CHOICE = "multiple_choice"  # 多选
    NUMBER = "number"        # 数字输入
    DATE = "date"           # 日期输入
    SCALE = "scale"         # 量表评分

class RiskLevel(Enum):
    """风险等级枚举"""
    LOW = "low"             # 低风险
    MEDIUM = "medium"       # 中风险
    HIGH = "high"           # 高风险

@dataclass
class QuestionOption:
    """问题选项"""
    value: str
    label: str
    score: Optional[int] = None
    risk_factor: Optional[float] = None

@dataclass
class Question:
    """问题模型"""
    id: str
    text: str
    type: QuestionType
    category: str
    required: bool = True
    options: Optional[List[QuestionOption]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    help_text: Optional[str] = None
    risk_weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "text": self.text,
            "type": self.type.value,
            "category": self.category,
            "required": self.required,
            "options": [opt.__dict__ for opt in (self.options or [])],
            "validation_rules": self.validation_rules,
            "help_text": self.help_text,
            "risk_weight": self.risk_weight
        }

@dataclass
class Questionnaire:
    """问卷模型"""
    id: str
    title: str
    description: str
    version: str = "1.0"
    questions: List[Question] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    estimated_time: str = "15-20分钟"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_question(self, question: Question):
        """添加问题"""
        self.questions.append(question)
        if question.category not in self.categories:
            self.categories.append(question.category)
        self.updated_at = datetime.now()
    
    def get_questions_by_category(self, category: str) -> List[Question]:
        """按分类获取问题"""
        return [q for q in self.questions if q.category == category]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "questions": [q.to_dict() for q in self.questions],
            "categories": self.categories,
            "estimated_time": self.estimated_time,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    def save_to_file(self, filepath: str):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'Questionnaire':
        """从文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        questions = []
        for q_data in data.get('questions', []):
            q_type = QuestionType(q_data['type'])
            options = None
            if q_data.get('options'):
                options = [QuestionOption(**opt) for opt in q_data['options']]
            
            question = Question(
                id=q_data['id'],
                text=q_data['text'],
                type=q_type,
                category=q_data['category'],
                required=q_data.get('required', True),
                options=options,
                validation_rules=q_data.get('validation_rules'),
                help_text=q_data.get('help_text'),
                risk_weight=q_data.get('risk_weight', 1.0)
            )
            questions.append(question)
        
        return cls(
            id=data['id'],
            title=data['title'],
            description=data['description'],
            version=data.get('version', '1.0'),
            questions=questions,
            categories=data.get('categories', []),
            estimated_time=data.get('estimated_time', '15-20分钟'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at'])
        )

@dataclass
class UserResponse:
    """用户回答模型"""
    question_id: str
    answer: Union[str, int, float, List[str]]
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: Optional[float] = None  # 回答置信度
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "question_id": self.question_id,
            "answer": self.answer,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence
        }

@dataclass
class QuestionnaireSession:
    """问卷会话模型"""
    session_id: str
    questionnaire_id: str
    user_id: Optional[str] = None
    responses: List[UserResponse] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    status: str = "in_progress"  # in_progress, completed, abandoned
    
    def add_response(self, response: UserResponse):
        """添加回答"""
        self.responses.append(response)
    
    def get_response(self, question_id: str) -> Optional[UserResponse]:
        """获取特定问题的回答"""
        for response in self.responses:
            if response.question_id == question_id:
                return response
        return None
    
    def is_completed(self) -> bool:
        """检查是否完成"""
        return self.status == "completed"
    
    def complete(self):
        """标记为完成"""
        self.status = "completed"
        self.completed_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "questionnaire_id": self.questionnaire_id,
            "user_id": self.user_id,
            "responses": [r.to_dict() for r in self.responses],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status
        }

@dataclass
class RiskAssessment:
    """风险评估模型"""
    session_id: str
    overall_risk: RiskLevel
    risk_score: float
    risk_factors: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    assessed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "overall_risk": self.overall_risk.value,
            "risk_score": self.risk_score,
            "risk_factors": self.risk_factors,
            "recommendations": self.recommendations,
            "assessed_at": self.assessed_at.isoformat()
        }

@dataclass
class AnalysisReport:
    """分析报告模型"""
    session_id: str
    title: str
    content: str
    risk_assessment: RiskAssessment
    data_insights: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "content": self.content,
            "risk_assessment": self.risk_assessment.to_dict(),
            "data_insights": self.data_insights,
            "generated_at": self.generated_at.isoformat()
        }
    
    def save_to_file(self, filepath: str):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

# 预定义的肺癌早筛问卷模板
def create_lung_cancer_questionnaire() -> Questionnaire:
    """创建肺癌早筛问卷模板"""
    questionnaire = Questionnaire(
        id="lung_cancer_screening_v1",
        title="肺癌早筛风险评估问卷",
        description="基于多维度因素的肺癌风险评估问卷，适用于40-70岁人群",
        version="1.0",
        estimated_time="15-20分钟"
    )
    
    # 基本信息类问题
    basic_questions = [
        Question("name", "姓名", QuestionType.TEXT, "基本信息", True),
        Question("gender", "性别", QuestionType.SINGLE_CHOICE, "基本信息", True,
                options=[
                    QuestionOption("1", "男", 0, 0.0),
                    QuestionOption("2", "女", 0, 0.0)
                ]),
        Question("age", "年龄", QuestionType.NUMBER, "基本信息", True,
                validation_rules={"min": 40, "max": 70}),
        Question("height", "身高(cm)", QuestionType.NUMBER, "基本信息", True,
                validation_rules={"min": 140, "max": 200}),
        Question("weight", "体重(kg)", QuestionType.NUMBER, "基本信息", True,
                validation_rules={"min": 40, "max": 150})
    ]
    
    # 吸烟史类问题
    smoking_questions = [
        Question("smoking_history", "是否有吸烟史", QuestionType.SINGLE_CHOICE, "吸烟史", True,
                options=[
                    QuestionOption("1", "是", 2, 2.0),
                    QuestionOption("2", "否", 0, 0.0)
                ]),
        Question("smoking_years", "累计吸烟年数", QuestionType.NUMBER, "吸烟史", False,
                validation_rules={"min": 0, "max": 60}),
        Question("daily_cigarettes", "每日吸烟支数", QuestionType.NUMBER, "吸烟史", False,
                validation_rules={"min": 0, "max": 100})
    ]
    
    # 职业暴露类问题
    occupational_questions = [
        Question("occupational_exposure", "是否接触职业致癌物质", QuestionType.SINGLE_CHOICE, "职业暴露", True,
                options=[
                    QuestionOption("1", "是", 2, 2.0),
                    QuestionOption("2", "否", 0, 0.0)
                ]),
        Question("exposure_years", "累计接触年数", QuestionType.NUMBER, "职业暴露", False,
                validation_rules={"min": 0, "max": 50})
    ]
    
    # 家族史类问题
    family_questions = [
        Question("family_history", "三代以内直系亲属是否有肺癌史", QuestionType.SINGLE_CHOICE, "家族史", True,
                options=[
                    QuestionOption("1", "是", 2, 2.0),
                    QuestionOption("2", "否", 0, 0.0)
                ])
    ]
    
    # 症状类问题
    symptom_questions = [
        Question("cough", "是否有持续性干咳", QuestionType.SINGLE_CHOICE, "症状", True,
                options=[
                    QuestionOption("1", "是", 3, 3.0),
                    QuestionOption("2", "否", 0, 0.0)
                ]),
        Question("hemoptysis", "是否有痰中带血", QuestionType.SINGLE_CHOICE, "症状", True,
                options=[
                    QuestionOption("1", "是", 3, 3.0),
                    QuestionOption("2", "否", 0, 0.0)
                ]),
        Question("weight_loss", "近半年是否有不明原因消瘦", QuestionType.SINGLE_CHOICE, "症状", True,
                options=[
                    QuestionOption("1", "是", 2, 2.0),
                    QuestionOption("2", "否", 0, 0.0)
                ])
    ]
    
    # 添加所有问题
    all_questions = (basic_questions + smoking_questions + 
                    occupational_questions + family_questions + symptom_questions)
    
    for question in all_questions:
        questionnaire.add_question(question)
    
    return questionnaire

if __name__ == "__main__":
    # 测试问卷创建
    questionnaire = create_lung_cancer_questionnaire()
    print(f"问卷创建成功: {questionnaire.title}")
    print(f"问题总数: {len(questionnaire.questions)}")
    print(f"问题分类: {questionnaire.categories}")
    
    # 保存到文件
    questionnaire.save_to_file("lung_cancer_questionnaire.json")
    print("问卷已保存到文件")
