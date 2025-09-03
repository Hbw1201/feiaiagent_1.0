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

# ========== 问卷配置 ==========

# 肺癌早筛问卷问题列表
QUESTIONS = [
    "姓名", "性别(1男 2女)", "出生年份", "身份证号", "医保卡号(选填)",
    "家庭医生", "问卷调查人(楼栋负责人)", "身高(cm)", "体重(kg)",
    "职业", "文化程度(1小学 2初中 3中专 4高中 5大专 6大学 7硕士 8博士 9博士后)",
    "家庭地址", "联系电话1(住宅)", "联系电话2(手机)", "联系电话3(家属)",
    "吸烟史(1是 2否)", "吸烟频率(支/天)", "累计吸烟年数", "目前是否戒烟(1是 2否)", "戒烟年数",
    "被动吸烟(1否 2是)", "被动吸烟频率(1≤1小时/天 2 1-2小时/天 3>2小时/天)", "累计被动吸烟年数",
    "长期厨房油烟接触(1每周<1次 2每周1-3次 3每周>3次 4每天)", "累计厨房油烟接触年数",
    "职业致癌物质接触(1有 2无)", "致癌物类型及累计接触年数(如有)",
    "既往个人肿瘤史(1有 2无)", "肿瘤类型及确诊年份(如有)",
    "三代以内直系亲属肺癌家族史(1有 2无)", "肿瘤类型及关系(如有)",
    "一年内胸部CT检查(1是 2否)",
    "慢性支气管炎(1是 2否)", "患病年数", "肺气肿(1是 2否)", "患病年数",
    "肺结核(1是 2否)", "患病年数", "慢性阻塞性肺病(1是 2否)", "患病年数",
    "肺间质纤维化(1是 2否)", "患病年数",
    "近半年不明原因消瘦(1有 2无)", "体重下降kg(如有)",
    "最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)", "具体症状(如有)",
    "最近自我感觉(1好 2一般 3不好)"
]

# 问卷问题分类和格式要求参考
QUESTIONNAIRE_REFERENCE = {
    "基本信息": {
        "姓名": "2~4个汉字",
        "性别(1男 2女)": "1 或 2",
        "出生年份": "四位数字，如 1950~2010",
        "身份证号": "18位，最后一位可能是 X",
        "医保卡号(选填)": "10~20位字母或数字，可为空",
        "家庭医生": "2~4个字",
        "问卷调查人(楼栋负责人)": "2~4个字"
    },
    "身体指标": {
        "身高(cm)": "数值，100~250",
        "体重(kg)": "数值，30~200"
    },
    "社会信息": {
        "职业": "自由文本，如工人、教师",
        "文化程度(1小学 2初中 3中专 4高中 5大专 6大学 7硕士 8博士 9博士后)": "1~9之间整数"
    },
    "联系方式": {
        "家庭地址": "不少于10个字的详细地址",
        "联系电话1(住宅)": "区号+号码，如 010-12345678",
        "联系电话2(手机)": "11位手机号",
        "联系电话3(家属)": "可为固话或手机号"
    },
    "吸烟史": {
        "吸烟史(1是 2否)": "1 或 2",
        "吸烟频率(支/天)": "0~100",
        "累计吸烟年数": "0~80",
        "目前是否戒烟(1是 2否)": "1 或 2",
        "戒烟年数": "0~80（如已戒烟）"
    },
    "被动吸烟": {
        "被动吸烟(1否 2是)": "1 或 2",
        "被动吸烟频率(1≤1小时/天 2 1-2小时/天 3>2小时/天)": "1~3",
        "累计被动吸烟年数": "0~80"
    },
    "厨房油烟": {
        "长期厨房油烟接触(1每周<1次 2每周1-3次 3每周>3次 4每天)": "1~4",
        "累计厨房油烟接触年数": "0~80"
    },
    "职业暴露": {
        "职业致癌物质接触(1有 2无)": "1 或 2",
        "致癌物类型及累计接触年数(如有)": "如石棉10年，无可为空或无"
    },
    "肿瘤相关史": {
        "既往个人肿瘤史(1有 2无)": "1 或 2",
        "肿瘤类型及确诊年份(如有)": "如肺癌2010年，无可为空",
        "三代以内直系亲属肺癌家族史(1有 2无)": "1 或 2",
        "肿瘤类型及关系(如有)": "如父亲肺癌，无可为空"
    },
    "影像检查": {
        "一年内胸部CT检查(1是 2否)": "1 或 2"
    },
    "呼吸系统疾病史": {
        "慢性支气管炎(1是 2否)": "1 或 2",
        "患病年数": "0~80",
        "肺气肿(1是 2否)": "1 或 2",
        "患病年数": "0~80",
        "肺结核(1是 2否)": "1 或 2",
        "患病年数": "0~80",
        "慢性阻塞性肺病(1是 2否)": "1 或 2",
        "患病年数": "0~80",
        "肺间质纤维化(1是 2否)": "1 或 2",
        "患病年数": "0~80"
    },
    "近期症状": {
        "近半年不明原因消瘦(1有 2无)": "1 或 2",
        "体重下降kg(如有)": "0~30",
        "最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)": "1 或 2",
        "具体症状(如有)": "自由描述，或填无"
    },
    "健康自评": {
        "最近自我感觉(1好 2一般 3不好)": "1~3"
    }
}

# ========== 问卷会话管理 ==========

class QuestionnaireSession:
    """本地问卷会话管理类"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_question_index = 0
        self.answers = {}
        self.start_time = time.time()
        self.completed = False
        self.report = None
    
    def get_current_question(self) -> str:
        """获取当前问题"""
        if self.current_question_index < len(QUESTIONS):
            return QUESTIONS[self.current_question_index]
        return None
    
    def get_progress(self) -> str:
        """获取进度信息"""
        return f"{self.current_question_index + 1}/{len(QUESTIONS)}"
    
    def submit_answer(self, answer: str) -> bool:
        """提交答案"""
        current_question = self.get_current_question()
        if current_question:
            self.answers[current_question] = answer
            return True
        return False
    
    def move_to_next(self) -> bool:
        """移动到下一题"""
        if self.current_question_index < len(QUESTIONS) - 1:
            self.current_question_index += 1
            return True
        return False
    
    def is_completed(self) -> bool:
        """检查是否完成"""
        return self.current_question_index >= len(QUESTIONS) - 1
    
    def get_question_info(self) -> Optional[Dict[str, Any]]:
        """获取当前问题信息"""
        if self.current_question_index >= len(QUESTIONS):
            return None
        
        question = QUESTIONS[self.current_question_index]
        for category, questions_dict in QUESTIONNAIRE_REFERENCE.items():
            if question in questions_dict:
                return {
                    "category": category,
                    "question": question,
                    "format": questions_dict[question],
                    "question_index": self.current_question_index + 1,
                    "total_questions": len(QUESTIONS)
                }
        
        return {
            "category": "其他",
            "question": question,
            "format": "自由回答",
            "question_index": self.current_question_index + 1,
            "total_questions": len(QUESTIONS)
        }

# ========== 报告生成 ==========

def generate_assessment_report(answers: Dict[str, str]) -> str:
    """
    根据用户答案生成肺癌早筛风险评估报告
    
    Args:
        answers: 用户答案字典
        
    Returns:
        格式化的评估报告文本
    """
    report = "肺癌早筛风险评估报告\n\n" + "=" * 50 + "\n\n"
    
    # 基本信息
    report += "【基本信息】\n"
    if "姓名" in answers:
        report += f"姓名：{answers['姓名']}\n"
    if "性别(1男 2女)" in answers:
        gender = "男" if answers["性别(1男 2女)"] == "1" else "女"
        report += f"性别：{gender}\n"
    if "出生年份" in answers:
        report += f"出生年份：{answers['出生年份']}\n"
    if "身高(cm)" in answers and "体重(kg)" in answers:
        try:
            height = float(answers["身高(cm)"])
            weight = float(answers["体重(kg)"])
            bmi = weight / ((height / 100) ** 2)
            report += f"身高：{height}cm，体重：{weight}kg，BMI：{bmi:.1f}\n"
        except:
            report += f"身高：{answers['身高(cm)']}cm，体重：{answers['体重(kg)']}kg\n"
    
    # 风险评估
    report += "\n【风险评估】\n"
    risk_score = 0
    
    # 吸烟史评估
    if answers.get("吸烟史(1是 2否)") == "1":
        report += "⚠️ 吸烟史：有吸烟史，增加肺癌风险\n"
        try:
            years = float(answers.get("累计吸烟年数", "0"))
            daily = float(answers.get("吸烟频率(支/天)", "0"))
            pack_years = (years * daily) / 20
            if pack_years > 30:
                report += f"   重度吸烟：{pack_years:.1f}包年，高风险\n"
                risk_score += 3
            elif pack_years > 20:
                report += f"   中度吸烟：{pack_years:.1f}包年，中风险\n"
                risk_score += 2
            else:
                report += f"   轻度吸烟：{pack_years:.1f}包年，低风险\n"
                risk_score += 1
        except:
            report += "   吸烟情况：需进一步评估\n"
            risk_score += 2
    
    # 被动吸烟
    if answers.get("被动吸烟(1否 2是)") == "2":
        report += "⚠️ 被动吸烟：存在被动吸烟情况\n"
        risk_score += 1
    
    # 职业暴露
    if answers.get("职业致癌物质接触(1有 2无)") == "1":
        report += "⚠️ 职业暴露：存在职业致癌物质接触\n"
        risk_score += 2
    
    # 家族史
    if answers.get("三代以内直系亲属肺癌家族史(1有 2无)") == "1":
        report += "⚠️ 家族史：存在肺癌家族史，遗传风险增加\n"
        risk_score += 2
    
    # 症状评估
    if answers.get("最近是否有持续性干咳、痰中带血、声音嘶哑、反复同部位肺炎(1有 2无)") == "1":
        report += "⚠️ 症状：存在可疑症状，建议及时就医\n"
        risk_score += 3
    
    # CT检查建议
    if answers.get("一年内胸部CT检查(1是 2否)") == "2":
        report += "📋 建议：建议进行胸部CT检查\n"
    
    # 总体评估
    report += "\n【总体评估】\n"
    if risk_score >= 6:
        report += "🔴 高风险：建议立即就医，进行详细检查\n"
    elif risk_score >= 3:
        report += "🟡 中风险：建议定期体检，关注症状变化\n"
    else:
        report += "🟢 低风险：保持健康生活方式，定期体检\n"
    
    # 建议措施
    report += "\n【建议措施】\n"
    report += "1. 戒烟限酒，避免二手烟\n"
    report += "2. 保持室内通风，减少油烟接触\n"
    report += "3. 定期体检，关注肺部健康\n"
    report += "4. 如有异常症状，及时就医\n"
    report += "5. 保持健康生活方式，适量运动\n"
    
    report += "\n" + "=" * 50 + "\n"
    report += f"报告生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return report

# ========== 工具函数 ==========

def get_question_info(question_index: int) -> Optional[Dict[str, Any]]:
    """
    获取指定索引的问题信息
    
    Args:
        question_index: 问题索引
        
    Returns:
        问题信息字典
    """
    if question_index >= len(QUESTIONS):
        return None
    
    question = QUESTIONS[question_index]
    for category, questions_dict in QUESTIONNAIRE_REFERENCE.items():
        if question in questions_dict:
            return {
                "category": category,
                "question": question,
                "format": questions_dict[question],
                "question_index": question_index + 1,
                "total_questions": len(QUESTIONS)
            }
    
    return {
        "category": "其他",
        "question": question,
        "format": "自由回答",
        "question_index": question_index + 1,
        "total_questions": len(QUESTIONS)
    }

def validate_answer(question: str, answer: str) -> Tuple[bool, str]:
    """
    验证答案格式是否正确
    
    Args:
        question: 问题文本
        answer: 用户答案
        
    Returns:
        (是否有效, 错误信息)
    """
    if not answer or not answer.strip():
        return False, "答案不能为空"
    
    # 根据问题类型进行验证
    if "性别" in question:
        if answer not in ["1", "2"]:
            return False, "请选择1(男)或2(女)"
    
    elif "文化程度" in question:
        try:
            level = int(answer)
            if level < 1 or level > 9:
                return False, "请选择1-9之间的数字"
        except ValueError:
            return False, "请输入1-9之间的数字"
    
    elif "身高" in question:
        try:
            height = float(answer)
            if height < 100 or height > 250:
                return False, "身高应在100-250cm之间"
        except ValueError:
            return False, "请输入有效的数字"
    
    elif "体重" in question:
        try:
            weight = float(answer)
            if weight < 30 or weight > 200:
                return False, "体重应在30-200kg之间"
        except ValueError:
            return False, "请输入有效的数字"
    
    elif "吸烟频率" in question:
        try:
            freq = float(answer)
            if freq < 0 or freq > 100:
                return False, "吸烟频率应在0-100支/天之间"
        except ValueError:
            return False, "请输入有效的数字"
    
    elif "年数" in question:
        try:
            years = float(answer)
            if years < 0 or years > 80:
                return False, "年数应在0-80年之间"
        except ValueError:
            return False, "请输入有效的数字"
    
    return True, ""

def get_questionnaire_summary() -> Dict[str, Any]:
    """
    获取问卷概览信息
    
    Returns:
        问卷概览字典
    """
    return {
        "total_questions": len(QUESTIONS),
        "categories": list(QUESTIONNAIRE_REFERENCE.keys()),
        "estimated_time": "约15-20分钟",
        "description": "肺癌早筛风险评估问卷，包含基本信息、生活习惯、病史、症状等多个维度的评估"
    }

# ========== 导出配置 ==========

# 为了保持向后兼容，导出主要变量
questions = QUESTIONS
questionnaire_reference = QUESTIONNAIRE_REFERENCE

if __name__ == "__main__":
    # 测试代码
    print("=== 本地问卷模块测试 ===")
    print(f"总问题数: {len(QUESTIONS)}")
    print(f"问题分类: {list(QUESTIONNAIRE_REFERENCE.keys())}")
    
    # 测试会话管理
    session = QuestionnaireSession("test_session")
    print(f"\n当前问题: {session.get_current_question()}")
    print(f"进度: {session.get_progress()}")
    
    # 测试报告生成
    test_answers = {
        "姓名": "张三",
        "性别(1男 2女)": "1",
        "出生年份": "1980",
        "身高(cm)": "175",
        "体重(kg)": "70",
        "吸烟史(1是 2否)": "1",
        "吸烟频率(支/天)": "20",
        "累计吸烟年数": "15"
    }
    
    report = generate_assessment_report(test_answers)
    print(f"\n生成的报告长度: {len(report)} 字符")
    print("报告预览:")
    print(report[:500] + "...")
