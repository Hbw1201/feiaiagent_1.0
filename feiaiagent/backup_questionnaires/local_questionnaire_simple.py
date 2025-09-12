# -*- coding: utf-8 -*-
"""
简化版本地问卷
直接在本地书写问卷，便于控制和修改
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any

# ========== 问卷问题定义 ==========

QUESTIONS = [
    # 基本信息
    {
        "id": "name",
        "text": "姓名",
        "prompt": "请问怎么称呼您？",
        "category": "基本信息",
        "required": True,
        "validation": "姓名不能为空，请输入真实姓名"
    },
    {
        "id": "gender", 
        "text": "性别",
        "prompt": "您的性别是？",
        "category": "基本信息",
        "required": True,
        "options": ["男", "女"],
        "validation": "请选择性别"
    },
    {
        "id": "age",
        "text": "年龄", 
        "prompt": "请问您今年多少岁？",
        "category": "基本信息",
        "required": True,
        "validation": "请输入有效的年龄数字"
    },
    {
        "id": "phone",
        "text": "联系电话",
        "prompt": "方便留个联系电话吗？",
        "category": "基本信息", 
        "required": False,
        "validation": "请输入有效的手机号码"
    },
    
    # 身体指标
    {
        "id": "height",
        "text": "身高",
        "prompt": "您的身高是多少？",
        "category": "身体指标",
        "required": True,
        "validation": "请输入有效的身高数字"
    },
    {
        "id": "weight", 
        "text": "体重",
        "prompt": "您的体重是多少？",
        "category": "身体指标",
        "required": True,
        "validation": "请输入有效的体重数字"
    },
    
    # 吸烟史
    {
        "id": "smoking_history",
        "text": "是否有吸烟史",
        "prompt": "请问您有吸烟的习惯吗？",
        "category": "吸烟史",
        "required": True,
        "options": ["是", "否"],
        "validation": "请选择是否有吸烟史"
    },
    {
        "id": "smoking_freq",
        "text": "吸烟频率",
        "prompt": "您平均每天抽多少支烟？",
        "category": "吸烟史", 
        "required": False,
        "depends_on": {"id": "smoking_history", "value": "是"},
        "validation": "请输入每天吸烟的支数"
    },
    {
        "id": "smoking_years",
        "text": "累计吸烟年数",
        "prompt": "您总共吸了多少年烟？",
        "category": "吸烟史",
        "required": False,
        "depends_on": {"id": "smoking_history", "value": "是"},
        "validation": "请输入吸烟的年数"
    },
    {
        "id": "smoking_quit",
        "text": "是否已戒烟",
        "prompt": "您现在已经戒烟了吗？",
        "category": "吸烟史",
        "required": False,
        "depends_on": {"id": "smoking_history", "value": "是"},
        "options": ["是", "否"],
        "validation": "请选择是否已戒烟"
    },
    {
        "id": "smoking_quit_years",
        "text": "戒烟年数",
        "prompt": "您戒烟多少年了？",
        "category": "吸烟史",
        "required": False,
        "depends_on": {"id": "smoking_quit", "value": "是"},
        "validation": "请输入戒烟的年数"
    },
    
    # 家族史
    {
        "id": "family_cancer",
        "text": "家族肺癌史",
        "prompt": "您的直系亲属中有人患过肺癌吗？",
        "category": "家族史",
        "required": True,
        "options": ["有", "无"],
        "validation": "请选择是否有家族肺癌史"
    },
    {
        "id": "family_cancer_details",
        "text": "家族肺癌详情",
        "prompt": "请具体说明哪位亲属患过肺癌？",
        "category": "家族史",
        "required": False,
        "depends_on": {"id": "family_cancer", "value": "有"},
        "validation": "请详细说明家族肺癌情况"
    },
    
    # 职业暴露
    {
        "id": "occupation",
        "text": "职业",
        "prompt": "请问您从事什么职业？",
        "category": "职业信息",
        "required": True,
        "validation": "请输入您的职业"
    },
    
    # 症状评估
    {
        "id": "recent_symptoms",
        "text": "近期症状",
        "prompt": "最近是否有持续咳嗽、痰中带血、声音嘶哑等症状？",
        "category": "症状评估",
        "required": True,
        "options": ["有", "无"],
        "validation": "请选择是否有近期症状"
    },
    {
        "id": "symptoms_details",
        "text": "症状详情",
        "prompt": "请详细描述具体症状？",
        "category": "症状评估",
        "required": False,
        "depends_on": {"id": "recent_symptoms", "value": "有"},
        "validation": "请详细描述症状"
    },
    
    # 健康自评
    {
        "id": "self_health",
        "text": "自我健康评价",
        "prompt": "您觉得自己的整体健康状况如何？",
        "category": "健康自评",
        "required": True,
        "options": ["很好", "一般", "较差"],
        "validation": "请选择自我健康评价"
    }
]

# ========== 问卷配置 ==========

QUESTIONNAIRE_CONFIG = {
    "title": "肺癌早筛风险评估问卷",
    "description": "基于医学专业知识的肺癌风险评估问卷",
    "version": "1.0",
    "estimated_time": "10-15分钟",
    "total_questions": len(QUESTIONS)
}

# ========== 辅助函数 ==========

def get_question_by_id(question_id: str) -> dict:
    """根据ID获取问题"""
    for question in QUESTIONS:
        if question["id"] == question_id:
            return question
    return None

def get_questions_by_category(category: str) -> list:
    """根据分类获取问题"""
    return [q for q in QUESTIONS if q["category"] == category]

def get_next_question_index(current_index: int, answers: dict) -> int:
    """获取下一个问题的索引，考虑依赖关系"""
    next_index = current_index + 1
    
    while next_index < len(QUESTIONS):
        question = QUESTIONS[next_index]
        
        # 检查依赖条件
        if "depends_on" in question:
            depends_on = question["depends_on"]
            dependent_question_id = depends_on["id"]
            required_value = depends_on["value"]
            
            # 检查依赖问题的答案
            dependent_answer = answers.get(dependent_question_id, "")
            if dependent_answer != required_value:
                # 依赖条件不满足，跳过此问题
                next_index += 1
                continue
        
        # 依赖条件满足或无依赖，返回此问题
        return next_index
    
    # 没有更多问题
    return -1

def validate_answer(question_id: str, answer: str) -> Tuple[bool, str]:
    """验证答案"""
    question = get_question_by_id(question_id)
    if not question:
        return False, "问题不存在"
    
    if not answer or answer.strip() == "":
        if question.get("required", False):
            return False, question.get("validation", "此问题为必答题")
        return True, "答案有效"
    
    # 基本长度检查
    if len(answer.strip()) < 1:
        return False, "回答太短，请提供更详细的信息"
    
    # 选项检查
    if "options" in question:
        if answer not in question["options"]:
            return False, f"请从以下选项中选择：{', '.join(question['options'])}"
    
    return True, "答案有效"

def generate_simple_report(answers: dict) -> str:
    """生成简单报告 - 基础版本，职业致癌物接触风险由智能体判断"""
    report = "肺癌早筛风险评估报告\n\n" + "=" * 50 + "\n\n"
    
    # 基本信息
    report += "【基本信息】\n"
    report += f"姓名：{answers.get('name', '未填写')}\n"
    report += f"性别：{answers.get('gender', '未填写')}\n"
    report += f"年龄：{answers.get('age', '未填写')}\n"
    report += f"联系电话：{answers.get('phone', '未填写')}\n"
    report += f"职业：{answers.get('occupation', '未填写')}\n\n"
    
    # 身体指标
    height = answers.get('height', '')
    weight = answers.get('weight', '')
    if height and weight:
        try:
            bmi = float(weight) / ((float(height) / 100) ** 2)
            report += f"身高：{height}cm，体重：{weight}kg，BMI：{bmi:.1f}\n\n"
        except:
            report += f"身高：{height}cm，体重：{weight}kg\n\n"
    
    # 基础风险评估（不包含职业致癌物接触，由智能体判断）
    report += "【基础风险评估】\n"
    basic_risk_factors = []
    
    if answers.get('smoking_history') == '是':
        basic_risk_factors.append("吸烟史")
    
    if answers.get('family_cancer') == '有':
        basic_risk_factors.append("家族肺癌史")
    
    if answers.get('recent_symptoms') == '有':
        basic_risk_factors.append("近期症状")
    
    if basic_risk_factors:
        report += f"识别到的基础风险因素：{', '.join(basic_risk_factors)}\n"
    else:
        report += "未识别到明显基础风险因素\n"
    
    # 职业致癌物接触风险将由智能体在报告生成时进行专业分析
    report += "\n【AI智能分析】\n"
    report += "职业致癌物接触风险将由AI智能体基于您的职业信息进行专业分析\n"
    report += "请查看完整的智能分析报告获取详细评估结果\n"
    
    # 基础建议
    report += "\n【基础医学建议】\n"
    if len(basic_risk_factors) >= 2:
        report += "1. 建议定期体检\n"
        report += "2. 注意生活方式改善\n"
        report += "3. 如有症状及时就医\n"
    else:
        report += "1. 保持良好的生活习惯\n"
        report += "2. 定期体检\n"
        report += "3. 注意健康监测\n"
    
    report += "\n注意：完整的风险评估报告将由AI智能体生成，包含职业致癌物接触的专业分析\n"
    
    return report
