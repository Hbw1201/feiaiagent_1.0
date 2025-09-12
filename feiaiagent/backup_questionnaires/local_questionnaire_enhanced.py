# -*- coding: utf-8 -*-
"""
增强版本地问卷管理模块
- 支持条件跳题逻辑
- 基于用户回答动态选择问题
- 智能问题流程控制
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# ========== 带跳题逻辑的问卷配置 ==========

QUESTIONS_STRUCTURED_ENHANCED = [
    # 基本信息 - 必答
    {"id": "name", "text": "姓名", "prompt": "请问怎么称呼您？", "category": "基本信息", "required": True},
    {"id": "gender", "text": "性别", "prompt": "您的性别是？", "category": "基本信息", "required": True},
    {"id": "birth_year", "text": "出生年份", "prompt": "请问您是哪一年出生的？", "category": "基本信息", "required": True},
    {"id": "id_card", "text": "身份证号", "prompt": "方便提供一下您的身份证号码吗？这个信息将严格保密。", "category": "基本信息", "required": False},
    {"id": "med_card", "text": "医保卡号(选填)", "prompt": "如果您方便的话，可以提供医保卡号吗？不提供也没关系。", "category": "基本信息", "required": False},
    
    # 身体指标
    {"id": "height", "text": "身高", "prompt": "您的身高是多少？", "category": "身体指标", "required": True},
    {"id": "weight", "text": "体重", "prompt": "您的体重是多少？", "category": "身体指标", "required": True},
    
    # 吸烟史 - 核心分支点
    {"id": "smoking_history", "text": "吸烟史", "prompt": "请问您有吸烟的习惯吗？", "category": "吸烟史", "required": True},
    
    # 吸烟史相关问题 - 仅在有吸烟史时询问
    {
        "id": "smoking_freq", 
        "text": "吸烟频率", 
        "prompt": "您平均每天大概抽多少支烟？", 
        "category": "吸烟史",
        "depends_on": {"id": "smoking_history", "value": "1"},
        "required": True
    },
    {
        "id": "smoking_years", 
        "text": "累计吸烟年数", 
        "prompt": "您总共吸了多少年烟呢？", 
        "category": "吸烟史",
        "depends_on": {"id": "smoking_history", "value": "1"},
        "required": True
    },
    {
        "id": "smoking_quit", 
        "text": "目前是否戒烟", 
        "prompt": "那您现在是否已经戒烟了？", 
        "category": "吸烟史",
        "depends_on": {"id": "smoking_history", "value": "1"},
        "required": True
    },
    {
        "id": "smoking_quit_years", 
        "text": "戒烟年数", 
        "prompt": "您戒烟有多少年了？", 
        "category": "吸烟史",
        "depends_on": {"id": "smoking_quit", "value": "1"},
        "required": True
    },
    
    # 被动吸烟 - 无吸烟史时重点询问
    {
        "id": "passive_smoking", 
        "text": "被动吸烟", 
        "prompt": "在您的生活或工作环境中，您会经常吸到二手烟吗？", 
        "category": "被动吸烟",
        "required": True
    },
    {
        "id": "passive_smoking_freq", 
        "text": "被动吸烟频率", 
        "prompt": "您大概每天会接触二手烟多长时间呢？", 
        "category": "被动吸烟",
        "depends_on": {"id": "passive_smoking", "value": "2"},
        "required": True
    },
    {
        "id": "passive_smoking_years", 
        "text": "累计被动吸烟年数", 
        "prompt": "这种情况大概持续多少年了？", 
        "category": "被动吸烟",
        "depends_on": {"id": "passive_smoking", "value": "2"},
        "required": True
    },
    
    # 厨房油烟 - 重点关注女性
    {
        "id": "kitchen_fumes", 
        "text": "长期厨房油烟接触", 
        "prompt": "您平时做饭多吗？会经常接触厨房油烟吗？", 
        "category": "厨房油烟",
        "required": True
    },
    {
        "id": "kitchen_fumes_years", 
        "text": "累计厨房油烟接触年数", 
        "prompt": "您接触厨房油烟有多少年了？", 
        "category": "厨房油烟",
        "depends_on": {"id": "kitchen_fumes", "value": "1"},
        "required": True
    },
    
    # 社会信息
    {"id": "occupation", "text": "职业", "prompt": "请问您目前从事什么职业？", "category": "社会信息", "required": True},
    
    # 职业暴露
    {
        "id": "occupation_exposure", 
        "text": "职业致癌物质接触(1有 2无)", 
        "prompt": "您的工作中有没有可能接触到石棉、煤焦油、放射性物质等有害物质？", 
        "category": "职业暴露",
        "required": True
    },
    {
        "id": "occupation_exposure_details", 
        "text": "致癌物类型及累计接触年数(如有)", 
        "prompt": "具体是哪种物质，大概接触了多少年？", 
        "category": "职业暴露",
        "depends_on": {"id": "occupation_exposure", "value": "1"},
        "required": True
    },
    
    # 肿瘤相关史
    {
        "id": "personal_tumor_history", 
        "text": "既往个人肿瘤史(1有 2无)", 
        "prompt": "请问您以前得过肿瘤吗？", 
        "category": "肿瘤相关史",
        "required": True
    },
    {
        "id": "personal_tumor_details", 
        "text": "肿瘤类型及确诊年份(如有)", 
        "prompt": "可以具体说说肿瘤的类型和确诊年份吗？", 
        "category": "肿瘤相关史",
        "depends_on": {"id": "personal_tumor_history", "value": "1"},
        "required": True
    },
    {
        "id": "family_cancer_history", 
        "text": "三代以内直系亲属肺癌家族史(1有 2无)", 
        "prompt": "您的父母、兄弟姐妹或子女中，有人得过肺癌吗？", 
        "category": "肿瘤相关史",
        "required": True
    },
    {
        "id": "family_cancer_details", 
        "text": "肿瘤类型及关系(如有)", 
        "prompt": "是哪位亲属，患的是哪种癌症呢？", 
        "category": "肿瘤相关史",
        "depends_on": {"id": "family_cancer_history", "value": "1"},
        "required": True
    },
    
    # 影像检查
    {
        "id": "chest_ct_last_year", 
        "text": "一年内胸部CT检查(1是 2否)", 
        "prompt": "在过去的一年里，您做过胸部CT检查吗？", 
        "category": "影像检查",
        "required": True
    },
    {
        "id": "chest_ct_results", 
        "text": "胸部CT检查结果", 
        "prompt": "那检查结果怎么样？有发现什么异常吗？", 
        "category": "影像检查",
        "depends_on": {"id": "chest_ct_last_year", "value": "1"},
        "required": False
    },
    
    # 呼吸系统疾病史
    {
        "id": "chronic_lung_disease", 
        "text": "慢性肺部疾病史(1有 2无)", 
        "prompt": "您是否被诊断出患有慢性支气管炎、肺气肿、肺结核或慢阻肺等肺部疾病？", 
        "category": "呼吸系统疾病史",
        "required": True
    },
    {
        "id": "lung_disease_details", 
        "text": "肺部疾病详情", 
        "prompt": "具体是什么疾病？确诊时间大概是什么时候？", 
        "category": "呼吸系统疾病史",
        "depends_on": {"id": "chronic_lung_disease", "value": "1"},
        "required": True
    },
    
    # 近期症状 - 重要风险指标
    {
        "id": "recent_weight_loss", 
        "text": "近半年不明原因消瘦(1有 2无)", 
        "prompt": "最近半年，您的体重有没有在没刻意减肥的情况下明显下降？", 
        "category": "近期症状",
        "required": True
    },
    {
        "id": "weight_loss_amount", 
        "text": "体重下降kg", 
        "prompt": "大概下降了多少公斤？", 
        "category": "近期症状",
        "depends_on": {"id": "recent_weight_loss", "value": "1"},
        "required": True
    },
    {
        "id": "recent_cough", 
        "text": "最近是否有持续性干咳(1有 2无)", 
        "prompt": "最近有没有出现持续的干咳？", 
        "category": "近期症状",
        "required": True
    },
    {
        "id": "cough_duration", 
        "text": "咳嗽持续时间", 
        "prompt": "这种咳嗽大概持续多长时间了？", 
        "category": "近期症状",
        "depends_on": {"id": "recent_cough", "value": "1"},
        "required": True
    },
    {
        "id": "hemoptysis", 
        "text": "痰中带血(1有 2无)", 
        "prompt": "有没有发现痰里带血的情况？", 
        "category": "近期症状",
        "required": True
    },
    {
        "id": "voice_hoarse", 
        "text": "声音嘶哑(1有 2无)", 
        "prompt": "最近声音有变嘶哑吗？", 
        "category": "近期症状",
        "required": True
    },
    
    # 健康自评
    {
        "id": "self_feeling", 
        "text": "最近自我感觉(1好 2一般 3不好)", 
        "prompt": "总的来说，您感觉最近身体状态怎么样？", 
        "category": "健康自评",
        "required": True
    }
]

# ========== 智能问题选择逻辑 ==========

class QuestionnaireLogicManager:
    """问卷逻辑管理器 - 处理跳题和问题选择"""
    
    def __init__(self):
        self.questions = QUESTIONS_STRUCTURED_ENHANCED
        self.questions_by_id = {q['id']: q for q in self.questions}
    
    def get_next_question_index(self, current_index: int, answers: Dict[str, str]) -> int:
        """
        基于当前回答获取下一个问题的索引
        Returns: 下一个问题的索引，如果问卷完成返回-1
        """
        next_index = current_index + 1
        
        while next_index < len(self.questions):
            question = self.questions[next_index]
            
            # 检查是否有依赖条件
            dependency = question.get("depends_on")
            if not dependency:
                # 无依赖条件，直接返回这个问题
                return next_index
            
            # 检查依赖条件是否满足
            if self._is_dependency_met(dependency, answers):
                return next_index
            else:
                # 依赖条件不满足，跳过此问题
                next_index += 1
        
        # 没有更多问题，问卷完成
        return -1
    
    def _is_dependency_met(self, dependency: Dict[str, str], answers: Dict[str, str]) -> bool:
        """检查依赖条件是否满足"""
        dependent_question_id = dependency.get("id")
        required_value = dependency.get("value")
        
        # 根据问题ID找到问题文本
        dependent_question = self.questions_by_id.get(dependent_question_id)
        if not dependent_question:
            return False
        
        dependent_question_text = dependent_question["text"]
        actual_answer = answers.get(dependent_question_text)
        
        return str(actual_answer) == str(required_value)
    
    def get_intelligent_next_question(self, answers: Dict[str, str], 
                                    conversation_context: str = "") -> Optional[Dict[str, Any]]:
        """
        智能选择下一个最相关的问题
        基于已有回答和对话上下文，选择最有价值的下一个问题
        """
        unanswered_questions = self._get_unanswered_questions(answers)
        
        if not unanswered_questions:
            return None
        
        # 优先级排序规则
        priority_questions = self._prioritize_questions(unanswered_questions, answers)
        
        return priority_questions[0] if priority_questions else None
    
    def _get_unanswered_questions(self, answers: Dict[str, str]) -> List[Dict[str, Any]]:
        """获取所有未回答的可问问题"""
        unanswered = []
        
        for question in self.questions:
            question_text = question["text"]
            
            # 如果已经回答过，跳过
            if question_text in answers:
                continue
            
            # 检查依赖条件
            dependency = question.get("depends_on")
            if dependency and not self._is_dependency_met(dependency, answers):
                continue
            
            unanswered.append(question)
        
        return unanswered
    
    def _prioritize_questions(self, questions: List[Dict[str, Any]], 
                            answers: Dict[str, str]) -> List[Dict[str, Any]]:
        """对问题进行优先级排序"""
        def get_priority_score(q: Dict[str, Any]) -> int:
            score = 0
            category = q.get("category", "")
            
            # 基本信息优先
            if category == "基本信息":
                score += 100
            
            # 风险因素相关问题高优先级
            risk_categories = ["吸烟史", "职业暴露", "肿瘤相关史", "近期症状"]
            if category in risk_categories:
                score += 80
            
            # 必答问题优先
            if q.get("required", False):
                score += 50
            
            # 有依赖关系的问题，在满足依赖时优先级较高
            if q.get("depends_on"):
                score += 30
            
            return score
        
        return sorted(questions, key=get_priority_score, reverse=True)
    
    def get_questionnaire_progress(self, answers: Dict[str, str]) -> Dict[str, Any]:
        """获取问卷进度信息"""
        total_applicable = len(self._get_all_applicable_questions(answers))
        answered = len(answers)
        
        return {
            "answered": answered,
            "total_applicable": total_applicable,
            "progress_percentage": (answered / total_applicable * 100) if total_applicable > 0 else 0,
            "estimated_remaining": max(0, total_applicable - answered)
        }
    
    def _get_all_applicable_questions(self, answers: Dict[str, str]) -> List[Dict[str, Any]]:
        """获取所有适用的问题（考虑依赖条件）"""
        applicable = []
        
        for question in self.questions:
            dependency = question.get("depends_on")
            if not dependency or self._is_dependency_met(dependency, answers):
                applicable.append(question)
        
        return applicable

# ========== 全局实例 ==========
questionnaire_logic = QuestionnaireLogicManager()

# ========== 兼容性接口 ==========
def get_next_question_index(current_index: int, answers: Dict[str, str]) -> int:
    """兼容原有接口"""
    return questionnaire_logic.get_next_question_index(current_index, answers)

def get_intelligent_next_question(answers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """获取智能推荐的下一个问题"""
    return questionnaire_logic.get_intelligent_next_question(answers)

# ========== 报告生成（增强版） ==========
def generate_enhanced_assessment_report(answers: Dict[str, str]) -> str:
    """
    基于增强版问卷生成更详细的风险评估报告
    """
    report = "肺癌早筛智能风险评估报告\n\n" + "=" * 60 + "\n\n"
    
    def get_answer_by_id(question_id: str) -> Optional[str]:
        """通过问题ID获取答案"""
        question = questionnaire_logic.questions_by_id.get(question_id)
        if not question:
            return None
        return answers.get(question["text"])
    
    # 基本信息
    report += "【基本信息】\n"
    name = get_answer_by_id('name')
    if name: 
        report += f"姓名：{name}\n"
    
    gender_ans = get_answer_by_id('gender')
    if gender_ans: 
        report += f"性别：{'男' if gender_ans == '1' else '女'}\n"
    
    birth_year = get_answer_by_id('birth_year')
    if birth_year: 
        try:
            age = 2024 - int(birth_year)
            report += f"出生年份：{birth_year}年（{age}岁）\n"
        except:
            report += f"出生年份：{birth_year}\n"
    
    # BMI计算
    height_ans = get_answer_by_id('height')
    weight_ans = get_answer_by_id('weight')
    if height_ans and weight_ans:
        try:
            height = float(height_ans)
            weight = float(weight_ans)
            bmi = weight / ((height / 100) ** 2)
            bmi_status = "正常" if 18.5 <= bmi <= 24.9 else ("偏瘦" if bmi < 18.5 else "超重")
            report += f"身高：{height}cm，体重：{weight}kg，BMI：{bmi:.1f}（{bmi_status}）\n"
        except:
            report += f"身高：{height_ans}cm，体重：{weight_ans}kg\n"
    
    # 风险评估
    report += "\n【智能风险评估】\n"
    risk_score = 0
    risk_factors = []
    
    # 吸烟史评估
    smoking_history = get_answer_by_id('smoking_history')
    if smoking_history == '1':
        smoking_years = get_answer_by_id('smoking_years')
        smoking_freq = get_answer_by_id('smoking_freq')
        smoking_quit = get_answer_by_id('smoking_quit')
        
        try:
            years = float(smoking_years or 0)
            daily = float(smoking_freq or 0)
            pack_years = (years * daily) / 20
            
            if pack_years > 30:
                risk_score += 4
                risk_level = "极高"
            elif pack_years > 20:
                risk_score += 3
                risk_level = "高"
            elif pack_years > 10:
                risk_score += 2
                risk_level = "中"
            else:
                risk_score += 1
                risk_level = "低"
            
            status = "已戒烟" if smoking_quit == '1' else "仍在吸烟"
            report += f"🚭 吸烟史：{status}，吸烟指数 {pack_years:.1f} 包年（{risk_level}风险）\n"
            risk_factors.append(f"吸烟史（{pack_years:.1f}包年）")
            
        except:
            risk_score += 2
            report += f"🚭 吸烟史：有吸烟史\n"
            risk_factors.append("吸烟史")
    
    # 被动吸烟评估
    passive_smoking = get_answer_by_id('passive_smoking')
    if passive_smoking == '2':
        passive_years = get_answer_by_id('passive_smoking_years')
        risk_score += 1
        report += f"💨 被动吸烟：长期接触二手烟"
        if passive_years:
            report += f"（{passive_years}年）"
        report += "\n"
        risk_factors.append("长期被动吸烟")
    
    # 职业暴露评估
    occupation_exposure = get_answer_by_id('occupation_exposure')
    if occupation_exposure == '1':
        exposure_details = get_answer_by_id('occupation_exposure_details')
        risk_score += 2
        report += f"⚠️ 职业暴露：接触致癌物质"
        if exposure_details:
            report += f"（{exposure_details}）"
        report += "\n"
        risk_factors.append("职业致癌物质暴露")
    
    # 家族史评估
    family_history = get_answer_by_id('family_cancer_history')
    if family_history == '1':
        family_details = get_answer_by_id('family_cancer_details')
        risk_score += 2
        report += f"👨‍👩‍👧‍👦 家族史：肺癌家族史"
        if family_details:
            report += f"（{family_details}）"
        report += "\n"
        risk_factors.append("肺癌家族史")
    
    # 个人肿瘤史
    personal_tumor = get_answer_by_id('personal_tumor_history')
    if personal_tumor == '1':
        tumor_details = get_answer_by_id('personal_tumor_details')
        risk_score += 3
        report += f"🏥 既往史：既往肿瘤史"
        if tumor_details:
            report += f"（{tumor_details}）"
        report += "\n"
        risk_factors.append("既往肿瘤史")
    
    # 症状评估
    symptoms = []
    if get_answer_by_id('recent_cough') == '1':
        duration = get_answer_by_id('cough_duration')
        symptoms.append(f"持续性干咳" + (f"（{duration}）" if duration else ""))
        risk_score += 2
    
    if get_answer_by_id('hemoptysis') == '1':
        symptoms.append("痰中带血")
        risk_score += 3
    
    if get_answer_by_id('voice_hoarse') == '1':
        symptoms.append("声音嘶哑")
        risk_score += 2
    
    if get_answer_by_id('recent_weight_loss') == '1':
        weight_loss = get_answer_by_id('weight_loss_amount')
        symptoms.append(f"不明原因消瘦" + (f"（{weight_loss}kg）" if weight_loss else ""))
        risk_score += 2
    
    if symptoms:
        report += f"🔴 重要症状：{' | '.join(symptoms)}\n"
        risk_factors.extend(symptoms)
    
    # 慢性肺病
    chronic_lung = get_answer_by_id('chronic_lung_disease')
    if chronic_lung == '1':
        lung_details = get_answer_by_id('lung_disease_details')
        risk_score += 1
        report += f"🫁 肺部疾病：慢性肺部疾病史"
        if lung_details:
            report += f"（{lung_details}）"
        report += "\n"
        risk_factors.append("慢性肺部疾病")
    
    # 总体评估
    report += "\n【综合风险评估】\n"
    
    if risk_score >= 8:
        risk_level = "极高风险"
        risk_color = "🔴🔴🔴"
        recommendation = "强烈建议立即就医！建议尽快到呼吸科或胸外科进行详细检查，包括低剂量螺旋CT、肿瘤标志物检测等。"
    elif risk_score >= 5:
        risk_level = "高风险"
        risk_color = "🔴🔴"
        recommendation = "建议尽快就医咨询专科医生，进行胸部CT检查和相关筛查。"
    elif risk_score >= 3:
        risk_level = "中等风险"
        risk_color = "🟡"
        recommendation = "建议定期体检，每年进行胸部影像学检查，必要时咨询呼吸科医生。"
    elif risk_score >= 1:
        risk_level = "低-中风险"
        risk_color = "🟢🟡"
        recommendation = "建议保持健康生活方式，定期体检，关注身体变化。"
    else:
        risk_level = "低风险"
        risk_color = "🟢"
        recommendation = "继续保持健康的生活方式，定期进行健康检查。"
    
    report += f"{risk_color} 风险等级：{risk_level}（评分：{risk_score}分）\n\n"
    
    if risk_factors:
        report += f"主要风险因素：{' | '.join(risk_factors)}\n\n"
    
    report += f"📋 专业建议：{recommendation}\n\n"
    
    # 健康指导
    report += "【健康生活建议】\n"
    report += "• 戒烟限酒，避免被动吸烟\n"
    report += "• 保持室内通风，减少油烟接触\n"
    report += "• 适量运动，增强体质\n"
    report += "• 均衡饮食，多吃新鲜蔬果\n"
    report += "• 注意职业防护，定期体检\n"
    report += "• 关注身体变化，及时就医\n\n"
    
    # 随访建议
    if risk_score >= 3:
        report += "【随访建议】\n"
        if risk_score >= 5:
            report += "• 3-6个月复查一次胸部CT\n"
            report += "• 定期检测肿瘤标志物\n"
        else:
            report += "• 6-12个月复查一次胸部影像\n"
        report += "• 如出现新症状立即就医\n"
        report += "• 保持与医生的定期沟通\n\n"
    
    report += "=" * 60 + "\n"
    report += f"报告生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += "注：本报告仅供参考，不能替代医生的专业诊断，如有疑虑请及时就医。\n"
    
    return report

# ========== 导出接口 ==========
questions_structured = QUESTIONS_STRUCTURED_ENHANCED
questions = [q['text'] for q in QUESTIONS_STRUCTURED_ENHANCED]  # 兼容性

def get_questionnaire_summary() -> Dict[str, Any]:
    """获取问卷概要信息"""
    return {
        "title": "肺癌早筛智能风险评估问卷",
        "description": "基于人工智能的肺癌早期筛查风险评估问卷，支持智能跳题和个性化问题推荐",
        "version": "2.0",
        "total_questions": len(QUESTIONS_STRUCTURED_ENHANCED),
        "categories": list(set(q.get("category", "其他") for q in QUESTIONS_STRUCTURED_ENHANCED)),
        "estimated_time": "10-20分钟（根据个人情况动态调整）",
        "features": [
            "智能跳题逻辑",
            "个性化问题推荐", 
            "实时风险评估",
            "详细分析报告"
        ]
    }

if __name__ == "__main__":
    # 测试智能问卷逻辑
    print("=== 增强版问卷逻辑测试 ===")
    
    # 测试样本回答
    test_answers = {
        "姓名": "张三",
        "性别(1男 2女)": "1",
        "出生年份": "1970",
        "身高(cm)": "175",
        "体重(kg)": "70",
        "吸烟史(1是 2否)": "1",  # 有吸烟史
    }
    
    # 测试下一个问题推荐
    next_question = get_intelligent_next_question(test_answers)
    if next_question:
        print(f"智能推荐下一题：{next_question['prompt']}")
    
    # 测试进度信息
    progress = questionnaire_logic.get_questionnaire_progress(test_answers)
    print(f"问卷进度：{progress}")
    
    print("✅ 增强版问卷逻辑测试完成")
