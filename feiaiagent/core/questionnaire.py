# local_questionnaire.py
# -*- coding: utf-8 -*-
"""
本地问卷管理模块
- 集中管理本地问卷的配置、问题和逻辑
- 提供问卷启动、回答处理、报告生成等功能
- 支持问卷进度跟踪和状态管理
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# ========== 问卷配置（优化版） ==========

QUESTIONS_STRUCTURED = [
    # 基本信息
    {"id": "name", "text": "姓名", "prompt": "请问怎么称呼您？", "category": "基本信息"},
    {"id": "gender", "text": "性别", "prompt": "您的性别是？", "category": "基本信息"},
    {"id": "birth_year", "text": "出生年份", "prompt": "请问您是哪一年出生的？", "category": "基本信息"},
    {"id": "height", "text": "身高", "prompt": "您的身高是多少？", "category": "身体指标"},
    {"id": "weight", "text": "体重", "prompt": "您的体重是多少？", "category": "身体指标"},
    {"id": "smoking_history", "text": "吸烟史", "prompt": "请问您有吸烟的习惯吗？", "category": "吸烟史"},
    {"id": "smoking_freq", "text": "吸烟频率", "prompt": "您平均每天大概抽多少支烟？", "category": "吸烟史"},
    {"id": "smoking_years", "text": "累计吸烟年数", "prompt": "您总共吸了多少年烟呢？", "category": "吸烟史"},
    {"id": "smoking_quit", "text": "目前是否戒烟", "prompt": "那您现在是否已经戒烟了？", "category": "吸烟史"},
    {"id": "smoking_quit_years", "text": "戒烟年数", "prompt": "您戒烟有多少年了？", "category": "吸烟史"},
    {"id": "passive_smoking", "text": "被动吸烟", "prompt": "在您的生活或工作环境中，您会经常吸到二手烟吗？", "category": "被动吸烟"},
    {"id": "passive_smoking_freq", "text": "被动吸烟频率", "prompt": "您大概每天会接触二手烟多长时间呢？", "category": "被动吸烟"},
    {"id": "passive_smoking_years", "text": "累计被动吸烟年数", "prompt": "这种情况大概持续多少年了？", "category": "被动吸烟"},
    {"id": "kitchen_fumes", "text": "长期厨房油烟接触", "prompt": "您平时做饭多吗？会经常接触厨房油烟吗？", "category": "厨房油烟"},
    {"id": "kitchen_fumes_years", "text": "累计厨房油烟接触年数", "prompt": "您接触厨房油烟有多少年了？", "category": "厨房油烟"},
    {"id": "occupation", "text": "职业", "prompt": "请问您目前从事什么职业？", "category": "社会信息"},
    {"id": "occupation_exposure", "text": "职业致癌物质接触", "prompt": "您的工作中有没有可能接触到石棉、煤焦油、放射性物质等有害物质？", "category": "职业暴露"},
    {"id": "occupation_exposure_details", "text": "致癌物类型及累计接触年数(如有)", "prompt": "具体是哪种物质，大概接触了多少年？", "category": "职业暴露"},
    {"id": "personal_tumor_history", "text": "既往个人肿瘤史", "prompt": "请问您以前得过肿瘤吗？", "category": "肿瘤相关史"},
    {"id": "personal_tumor_details", "text": "肿瘤类型及确诊年份", "prompt": "可以具体说说肿瘤的类型和确诊年份吗？", "category": "肿瘤相关史"},
    {"id": "family_cancer_history", "text": "三代以内直系亲属肺癌家族史", "prompt": "您的父母、兄弟姐妹或子女中，有人得过肺癌吗？", "category": "肿瘤相关史"},
    {"id": "family_cancer_details", "text": "肿瘤类型及关系(如有)", "prompt": "是哪位亲属，患的是哪种癌症呢？", "category": "肿瘤相关史"},
    {"id": "chest_ct_last_year", "text": "一年内胸部CT检查", "prompt": "在过去的一年里，您做过胸部CT检查吗？", "category": "影像检查"},
    {"id": "chronic_lung_disease", "text": "慢性肺部疾病史", "prompt": "您是否被诊断出患有慢性支气管炎、肺气肿、肺结核或慢阻肺等肺部疾病？", "category": "呼吸系统疾病史"},
    {"id": "recent_weight_loss", "text": "近半年不明原因消瘦", "prompt": "最近半年，您的体重有没有在没刻意减肥的情况下明显下降？", "category": "近期症状"},
    {"id": "recent_symptoms", "text": "最近是否有持续性干咳、痰中带血、声音嘶哑等", "prompt": "那最近有没有出现持续干咳、痰里带血、或者声音嘶哑这些情况呢？", "category": "近期症状"},
    {"id": "recent_symptoms_details", "text": "具体症状(如有)", "prompt": "能具体描述一下是什么症状吗？", "category": "近期症状"},
    {"id": "self_feeling", "text": "最近自我感觉", "prompt": "总的来说，您感觉最近身体状态怎么样？", "category": "健康自评"}
]

# 为了完全兼容，生成一个从ID到问题的映射
QUESTIONS_BY_ID = {q['id']: q for q in QUESTIONS_STRUCTURED}

# 旧的兼容性变量
questions = [q['text'] for q in QUESTIONS_STRUCTURED]
questionnaire_reference = {}

# ========== 报告生成（重构版） ==========
def generate_assessment_report(answers: Dict[str, str]) -> str:
    """
    根据用户答案生成肺癌早筛风险评估报告 (已重构)
    使用DeepSeek报告生成智能体判断风险等级
    """
    report = "肺癌早筛风险评估报告\n\n" + "=" * 50 + "\n\n"

    def get_answer(question_id: str) -> Optional[str]:
        """通过问题ID安全地获取答案"""
        question_text = QUESTIONS_BY_ID.get(question_id, {}).get('text')
        return answers.get(question_text)

    # 基本信息
    report += "【基本信息】\n"
    name = get_answer('name')
    if name: report += f"姓名：{name}\n"
    
    gender_ans = get_answer('gender')
    if gender_ans: report += f"性别：{'男' if gender_ans == '1' else '女'}\n"

    birth_year = get_answer('birth_year')
    if birth_year: report += f"出生年份：{birth_year}\n"

    height_ans = get_answer('height')
    weight_ans = get_answer('weight')
    if height_ans and weight_ans:
        try:
            height = float(height_ans)
            weight = float(weight_ans)
            bmi = weight / ((height / 100) ** 2)
            report += f"身高：{height}cm，体重：{weight}kg，BMI：{bmi:.1f}\n"
        except (ValueError, TypeError):
            report += f"身高：{height_ans}cm，体重：{weight_ans}kg\n"

    # 风险评估
    report += "\n【风险评估】\n"
    risk_score = 0

    if get_answer('smoking_history') == '1':
        report += "⚠️ 吸烟史：有吸烟史，增加肺癌风险\n"
        try:
            years = float(get_answer('smoking_years') or 0)
            daily = float(get_answer('smoking_freq') or 0)
            pack_years = (years * daily) / 20
            if pack_years > 30: risk_score += 3
            elif pack_years > 20: risk_score += 2
            else: risk_score += 1
            report += f"   吸烟指数：{pack_years:.1f} 包年\n"
        except (ValueError, TypeError):
            risk_score += 2

    if get_answer('passive_smoking') == '2':
        report += "⚠️ 被动吸烟：存在被动吸烟情况\n"
        risk_score += 1

    if get_answer('occupation_exposure') == '1':
        report += "⚠️ 职业暴露：存在职业致癌物质接触\n"
        risk_score += 2

    if get_answer('family_cancer_history') == '1':
        report += "⚠️ 家族史：存在肺癌家族史，遗传风险增加\n"
        risk_score += 2

    if get_answer('recent_symptoms') == '1':
        report += "⚠️ 症状：存在可疑症状，建议及时就医\n"
        risk_score += 3

    if get_answer('chest_ct_last_year') == '2':
        report += "📋 建议：近期未进行胸部CT检查，建议根据风险评估结果咨询医生。\n"

    # 使用DeepSeek报告生成智能体判断风险等级
    risk_level, risk_analysis = _get_risk_level_from_deepseek(answers, risk_score)
    
    # 总体评估
    report += "\n【总体评估】\n"
    if risk_level == "高风险":
        report += "🔴 高风险：综合评估为高风险，强烈建议您立即咨询呼吸科或胸外科医生，并进行低剂量螺旋CT筛查。\n"
    elif risk_level == "中风险":
        report += "🟡 中风险：综合评估为中等风险，建议您定期体检，并与医生讨论是否需要进行肺癌筛查。\n"
    else:
        report += "🟢 低风险：综合评估为低风险，但仍建议您保持健康生活方式，远离烟草，并保持对身体变化的警觉。\n"
    
    # 添加DeepSeek的详细分析
    if risk_analysis:
        report += f"\n【AI智能分析】\n{risk_analysis}\n"

    report += "\n" + "=" * 50 + "\n"
    report += f"报告生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    return report

def _get_risk_level_from_deepseek(answers: Dict[str, str], risk_score: int) -> Tuple[str, str]:
    """
    使用DeepSeek报告生成智能体判断风险等级
    返回 (风险等级, 详细分析)
    """
    try:
        # 构建问答数据
        qa_data = []
        for question_id, question_data in QUESTIONS_BY_ID.items():
            question_text = question_data['text']
            answer = answers.get(question_text, '未回答')
            qa_data.append(f"问题：{question_text}\n回答：{answer}")
        
        qa_text = "\n\n".join(qa_data)
        
        # 构建提示词
        prompt = f"""你是一位专业的医学专家，需要基于患者的问卷回答判断肺癌早筛风险等级。

患者回答：
{qa_text}

当前风险评分：{risk_score}分

请根据以下标准判断风险等级：
- 低风险：无明显风险因素，建议定期体检
- 中风险：存在一些风险因素，建议定期监测
- 高风险：存在多个风险因素或严重症状，建议立即就医

请按以下格式回复：
风险等级：[低风险/中风险/高风险]
详细分析：[基于医学知识的详细分析，包括主要风险因素、建议措施等]

要求：
- 基于医学专业知识进行分析
- 考虑所有风险因素的综合影响
- 提供具体的医学建议
- 语言专业但易懂

请直接输出结果，不要添加其他说明。"""

        # 调用DeepSeek API
        import requests
        import json
        import os
        
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            logger.warning("DEEPSEEK_API_KEY未设置，使用默认风险等级")
            return _get_default_risk_level(risk_score), "AI分析不可用，使用传统评分方法"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            # 解析结果
            lines = content.split('\n')
            risk_level = "低风险"
            analysis = content
            
            for line in lines:
                if line.startswith('风险等级：'):
                    risk_level = line.replace('风险等级：', '').strip()
                elif line.startswith('详细分析：'):
                    analysis = line.replace('详细分析：', '').strip()
            
            logger.info(f"DeepSeek风险等级判断：{risk_level}")
            return risk_level, analysis
        else:
            logger.error(f"DeepSeek API调用失败：{response.status_code}")
            return _get_default_risk_level(risk_score), "AI分析失败，使用传统评分方法"
            
    except Exception as e:
        logger.error(f"DeepSeek风险等级判断失败：{e}")
        return _get_default_risk_level(risk_score), f"AI分析异常：{str(e)}"

def _get_default_risk_level(risk_score: int) -> str:
    """获取默认风险等级（基于传统评分）"""
    if risk_score >= 6:
        return "高风险"
    elif risk_score >= 3:
        return "中风险"
    else:
        return "低风险"

# ========== 工具函数（重构版） ==========
def get_question_info(question_index: int) -> Optional[Dict[str, Any]]:
    if not 0 <= question_index < len(QUESTIONS_STRUCTURED):
        return None
    q_data = QUESTIONS_STRUCTURED[question_index]
    return {
        "category": q_data.get("category", "其他"),
        "question": q_data['prompt'],
        "original_question": q_data['text'],
        "question_index": question_index + 1,
        "total_questions": len(QUESTIONS_STRUCTURED)
    }

# ========== 导出配置 ==========
questions_structured = QUESTIONS_STRUCTURED
