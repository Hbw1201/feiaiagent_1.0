# -*- coding: utf-8 -*-
"""
问卷设计提示词模板
定义各种智能体使用的提示词
"""

from typing import Dict, Any

class DesignPrompts:
    """问卷设计提示词类"""
    
    @staticmethod
    def questionnaire_design_prompt(context: str, requirements: Dict[str, Any]) -> str:
        """问卷设计提示词"""
        return f"""
        你是一位专业的医学问卷设计专家，请基于以下要求设计一个专业的问卷：

        设计背景：{context}

        具体要求：
        - 问卷类型：{requirements.get('type', '健康评估问卷')}
        - 目标人群：{requirements.get('target_audience', '一般人群')}
        - 问题数量：{requirements.get('question_count', '15-20个')}
        - 完成时间：{requirements.get('estimated_time', '10-15分钟')}
        - 重点关注：{requirements.get('focus_areas', '健康风险评估')}

        设计原则：
        1. 问题逻辑清晰，从基本信息到专业问题逐步深入
        2. 问题表述简洁明了，避免歧义
        3. 考虑用户隐私和敏感信息处理
        4. 包含必要的验证和帮助信息
        5. 问题类型多样化（单选、多选、文本、数字等）

        请输出：
        1. 问卷标题和描述
        2. 问题分类结构
        3. 具体问题列表（包含问题ID、文本、类型、选项、验证规则）
        4. 风险评估逻辑说明

        请以JSON格式输出，确保结构清晰，便于程序处理。
        """
    
    @staticmethod
    def question_optimization_prompt(question: str, feedback: str) -> str:
        """问题优化提示词"""
        return f"""
        你是一位问卷优化专家，请基于用户反馈优化以下问题：

        原始问题：{question}
        用户反馈：{feedback}

        优化要求：
        1. 保持问题核心含义不变
        2. 提高问题清晰度和易理解性
        3. 优化问题表述，减少歧义
        4. 考虑用户心理感受
        5. 确保问题符合问卷设计最佳实践

        请提供：
        1. 优化后的问题文本
        2. 优化理由说明
        3. 相关建议（如需要添加帮助文本、调整选项等）
        """
    
    @staticmethod
    def category_organization_prompt(questions: list) -> str:
        """问题分类组织提示词"""
        return f"""
        你是一位问卷结构专家，请帮助组织以下问题的最佳分类结构：

        问题列表：{questions}

        分类要求：
        1. 逻辑清晰，从基础到专业逐步深入
        2. 分类数量适中（建议4-6个分类）
        3. 每个分类包含相关问题，数量均衡
        4. 分类名称简洁明了
        5. 考虑用户填写流程的流畅性

        请提供：
        1. 建议的分类结构
        2. 每个分类的问题分配
        3. 分类顺序建议
        4. 分类说明和填写指导
        """

class AnalysisPrompts:
    """数据分析提示词类"""
    
    @staticmethod
    def data_analysis_prompt(responses: Dict[str, Any], questionnaire: Dict[str, Any]) -> str:
        """数据分析提示词"""
        return f"""
        你是一位专业的数据分析专家，请分析以下问卷回答数据：

        问卷信息：{questionnaire}
        用户回答：{responses}

        分析要求：
        1. 识别回答模式和趋势
        2. 发现异常或值得关注的数据点
        3. 分析不同分类问题的回答质量
        4. 提供数据洞察和建议
        5. 识别潜在的数据质量问题

        请提供：
        1. 数据概览和统计摘要
        2. 关键发现和洞察
        3. 数据质量评估
        4. 改进建议
        5. 可视化建议
        """
    
    @staticmethod
    def pattern_recognition_prompt(responses: list) -> str:
        """模式识别提示词"""
        return f"""
        你是一位模式识别专家，请分析以下问卷回答中的模式：

        回答数据：{responses}

        识别要求：
        1. 发现回答的时间模式
        2. 识别回答的一致性模式
        3. 发现潜在的响应偏差
        4. 分析用户行为模式
        5. 识别异常回答模式

        请提供：
        1. 识别的主要模式
        2. 模式的意义和解释
        3. 异常模式分析
        4. 对问卷设计的启示
        """

class RiskAssessmentPrompts:
    """风险评估提示词类"""
    
    @staticmethod
    def risk_assessment_prompt(responses: Dict[str, Any], risk_factors: Dict[str, Any]) -> str:
        """风险评估提示词"""
        return f"""
        你是一位专业的医学风险评估专家，请基于以下信息进行风险评估：

        用户回答：{responses}
        风险因素定义：{risk_factors}

        评估要求：
        1. 基于科学证据进行风险评估
        2. 考虑多个风险因素的交互作用
        3. 提供量化的风险评分
        4. 给出风险等级分类
        5. 提供个性化的预防建议

        请提供：
        1. 总体风险评估结果
        2. 各风险因素分析
        3. 风险评分和等级
        4. 具体预防建议
        5. 后续监测建议
        """
    
    @staticmethod
    def personalized_recommendation_prompt(risk_assessment: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
        """个性化建议提示词"""
        return f"""
        你是一位健康管理专家，请基于风险评估结果提供个性化建议：

        风险评估结果：{risk_assessment}
        用户档案：{user_profile}

        建议要求：
        1. 基于风险等级提供相应建议
        2. 考虑用户年龄、性别、职业等个人因素
        3. 提供具体可执行的行动建议
        4. 包含生活方式改善建议
        5. 给出后续监测和复查建议

        请提供：
        1. 总体健康管理建议
        2. 具体行动方案
        3. 生活方式改善建议
        4. 监测和复查计划
        5. 紧急情况处理建议
        """

class ReportGenerationPrompts:
    """报告生成提示词类"""
    
    @staticmethod
    def report_generation_prompt(analysis_data: Dict[str, Any], report_type: str) -> str:
        """报告生成提示词"""
        return f"""
        你是一位专业的报告写作专家，请基于以下数据生成{report_type}报告：

        分析数据：{analysis_data}

        报告要求：
        1. 结构清晰，逻辑性强
        2. 语言专业但易懂
        3. 包含关键数据和洞察
        4. 提供具体建议和行动方案
        5. 格式规范，便于阅读

        请生成：
        1. 执行摘要
        2. 详细分析内容
        3. 关键发现
        4. 建议和行动方案
        5. 附录和参考资料
        """
    
    @staticmethod
    def executive_summary_prompt(report_content: str) -> str:
        """执行摘要提示词"""
        return f"""
        你是一位执行摘要专家，请为以下报告生成简洁的执行摘要：

        报告内容：{report_content}

        摘要要求：
        1. 长度控制在300字以内
        2. 突出关键信息和结论
        3. 包含主要建议
        4. 语言简洁明了
        5. 便于决策者快速理解

        请生成：
        1. 核心发现摘要
        2. 关键结论
        3. 主要建议
        4. 后续行动要点
        """

class InterviewPrompts:
    """Prompts for conversational interviews."""

    @staticmethod
    def rephrase_question_prompt(context: str, history_summary: str, question_text: str, question_category: str) -> str:
        """Prompt to rephrase a formal question into a conversational one."""
        return f"""
        {context}

        Here is a summary of the last interaction:
        {history_summary}

        Based on this, please rephrase the following formal question from the '{question_category}' category into a natural, conversational question. Just provide the rephrased question, nothing else.

        Formal Question: "{question_text}"
        """
    
    @staticmethod
    def intelligent_question_selection_prompt(history: str, inferred_facts: str, candidate_questions: str) -> str:
        """Prompt for intelligent question selection based on conversation history."""
        return f"""
        你是一位经验丰富的全科医生，正在进行肺癌早筛问卷调查。请根据已有的对话历史和推断的事实，从候选问题中选择一个最合适、最符合逻辑的下一个问题。

        **对话历史：**
        {history}

        **已推断的事实：**
        {inferred_facts}

        **候选问题列表：**
        {candidate_questions}

        **选择要求：**
        1. 必须从候选问题列表中选择一个问题
        2. 选择的问题应该基于已有信息，符合医学逻辑
        3. 优先选择能够获得关键健康信息的问题
        4. 考虑问题的重要性和紧急性
        5. 确保问诊流程自然、符合医生问诊习惯

        **输出格式：**
        严格按照以下JSON格式输出，不要包含任何其他文字：
        {{"next_question_id": "选择的问题ID"}}

        如果没有合适的问题可选，返回：
        {{"next_question_id": "none"}}
        """

# 提示词模板使用示例
def get_prompt_template(prompt_type: str, **kwargs) -> str:
    """获取提示词模板"""
    if prompt_type == "questionnaire_design":
        return DesignPrompts.questionnaire_design_prompt(
            kwargs.get('context', ''),
            kwargs.get('requirements', {})
        )
    elif prompt_type == "risk_assessment":
        return RiskAssessmentPrompts.risk_assessment_prompt(
            kwargs.get('responses', {}),
            kwargs.get('risk_factors', {})
        )
    elif prompt_type == "report_generation":
        return ReportGenerationPrompts.report_generation_prompt(
            kwargs.get('analysis_data', {}),
            kwargs.get('report_type', '分析报告')
        )
    elif prompt_type == "rephrase_question":
        return InterviewPrompts.rephrase_question_prompt(
            kwargs.get('context', ''),
            kwargs.get('history_summary', ''),
            kwargs.get('question_text', ''),
            kwargs.get('question_category', '')
        )
    elif prompt_type == "intelligent_question_selection":
        return InterviewPrompts.intelligent_question_selection_prompt(
            kwargs.get('history', ''),
            kwargs.get('inferred_facts', ''),
            kwargs.get('candidate_questions', '')
        )
    else:
        return "未找到对应的提示词模板"

if __name__ == "__main__":
    # 测试提示词模板
    print("=== 提示词模板测试 ===")
    
    # 测试问卷设计提示词
    design_prompt = DesignPrompts.questionnaire_design_prompt(
        "设计一个肺癌早筛问卷",
        {"type": "健康评估", "target_audience": "40-70岁人群", "question_count": "20个"}
    )
    print("问卷设计提示词:")
    print(design_prompt[:200] + "...")
    
    # 测试风险评估提示词
    risk_prompt = RiskAssessmentPrompts.risk_assessment_prompt(
        {"age": 50, "smoking": "yes"},
        {"smoking": {"weight": 2.0, "description": "吸烟史"}}
    )
    print("\n风险评估提示词:")
    print(risk_prompt[:200] + "...")
