# -*- coding: utf-8 -*-
"""
问卷设计智能体
负责设计问卷结构、优化问题、组织分类等
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import os
import importlib.util
import re

from .base_agent import BaseAgent, register_agent
from ..models.questionnaire import Questionnaire, Question, QuestionType, QuestionOption
from ..prompts.design_prompts import DesignPrompts

logger = logging.getLogger(__name__)

@register_agent
class QuestionnaireDesignerAgent(BaseAgent):
    """问卷设计智能体"""
    
    def __init__(self):
        super().__init__(
            name="问卷设计专家",
            description="专业设计医学问卷的智能体，擅长问卷结构设计和问题优化",
            expertise=["问卷设计", "医学知识", "用户体验", "问题优化"]
        )
        self.design_templates = self._load_design_templates()
    
    def _load_design_templates(self) -> Dict[str, Any]:
        """加载设计模板"""
        return {
            "lung_cancer": {
                "title": "肺癌早筛风险评估问卷",
                "description": "基于多维度因素的肺癌风险评估问卷",
                "categories": ["基本信息", "生活习惯", "职业暴露", "家族史", "症状评估"],
                "target_audience": "40-70岁人群",
                "estimated_time": "15-20分钟"
            },
            "general_health": {
                "title": "一般健康评估问卷",
                "description": "全面的健康风险评估问卷",
                "categories": ["基本信息", "生活方式", "既往病史", "家族史", "当前症状"],
                "target_audience": "18岁以上人群",
                "estimated_time": "10-15分钟"
            },
            "custom": {
                "title": "自定义健康问卷",
                "description": "根据需求定制的健康评估问卷",
                "categories": [],
                "target_audience": "根据需求确定",
                "estimated_time": "根据问题数量确定"
            }
        }
    
    async def process(self, input_data: Any) -> Any:
        """处理问卷设计请求"""
        if isinstance(input_data, str):
            # 如果是字符串，尝试解析为设计需求
            return await self.design_questionnaire_from_text(input_data)
        elif isinstance(input_data, dict):
            # 如果是字典，直接使用
            return await self.design_questionnaire(input_data)
        else:
            raise ValueError(f"不支持的输入类型: {type(input_data)}")
    
    async def design_questionnaire(self, requirements: Dict[str, Any]) -> Questionnaire:
        """设计问卷 - 基于医院本地问卷"""
        logger.info(f"🎨 {self.name} 开始设计问卷: {requirements}")

        # 优先使用医院本地问卷
        try:
            local_path = requirements.get('local_questionnaire_path')
            questionnaire = self._create_from_local_questionnaire(local_path)
            self._validate_questionnaire(questionnaire)
            logger.info(f"✅ {self.name} 已根据医院本地问卷生成: {questionnaire.title}")
            return questionnaire
        except Exception as e:
            logger.error(f"❌ 加载医院本地问卷失败: {e}")
            raise RuntimeError(f"无法加载医院问卷: {e}")
    
    async def design_questionnaire_from_text(self, text: str) -> Questionnaire:
        """从文本描述设计问卷"""
        requirements = {
            'context': text,
            'type': '健康评估问卷',
            'target_audience': '一般人群',
            'question_count': '15-20个',
            'estimated_time': '10-15分钟',
            'focus_areas': '健康风险评估'
        }
        return await self.design_questionnaire(requirements)
    
    def _create_from_local_questionnaire(self, local_path: Optional[str] = None) -> Questionnaire:
        """从医院本地问卷构建问卷"""
        # 解析本地模块
        if not local_path:
            local_path = self._find_local_questionnaire_path()
        if not local_path or not os.path.exists(local_path):
            raise FileNotFoundError(f"未找到医院问卷文件，路径: {local_path}")

        module = self._import_local_questionnaire(local_path)

        # 读取医院问卷定义
        questions_structured = getattr(module, 'QUESTIONS_STRUCTURED', None)
        if not questions_structured:
            raise ValueError("医院问卷文件中未定义 QUESTIONS_STRUCTURED")

        # 读取问卷参考信息（可选）
        reference = getattr(module, 'questionnaire_reference', None) or getattr(module, 'QUESTIONNAIRE_REFERENCE', None) or {}

        # 创建问卷对象
        questionnaire = Questionnaire(
            id=f"hospital_questionnaire_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            title="肺癌早筛风险评估问卷",
            description="基于医院专业问卷的智能调研系统",
            version='1.0',
            estimated_time="15-20分钟"
        )

        # 构造快速索引：问题 -> (分类, 格式提示)
        q2meta: Dict[str, Tuple[str, Optional[str]]] = {}
        for category, qdict in reference.items():
            for q_text, fmt in qdict.items():
                # 只记录首个匹配分类，避免重复键覆盖
                if q_text not in q2meta:
                    q2meta[q_text] = (category, fmt)

        # 逐题构建
        for idx, q_data in enumerate(questions_structured, start=1):
            original_text = q_data.get('text', '')
            prompt_text = q_data.get('prompt', original_text)  # 优先使用优化后的prompt
            category = q_data.get('category', '其他')
            qid = q_data.get('id', f"q{idx:03d}")

            # 推断逻辑依然使用包含格式提示的 original_text
            _inferred_category, fmt = q2meta.get(original_text, (category, None))
            qtype, options, validation_rules, required, help_text = self._infer_question_type_and_options(original_text, fmt)

            # 将跳题依赖信息 'depends_on' 注入 validation_rules
            dependency = q_data.get('depends_on')
            if dependency:
                if validation_rules is None:
                    validation_rules = {}
                validation_rules['depends_on'] = dependency

            question = Question(
                id=qid,
                text=original_text,  # 关键修复：使用原始文本以确保后端分析兼容性
                type=qtype,
                category=category,
                required=required,
                options=[QuestionOption(str(v), lbl) for v, lbl in options] if options else None,
                validation_rules=validation_rules,
                help_text=prompt_text,  # 将对用户友好的提示放在这里，供前端或对话Agent使用
                risk_weight=1.0
            )
            questionnaire.add_question(question)

        return questionnaire

    def _find_local_questionnaire_path(self) -> Optional[str]:
        """尝试在工程内查找 local_questionnaire.py"""
        # 环境变量优先
        env_path = os.environ.get('LOCAL_QUESTIONNAIRE_PATH')
        if env_path and os.path.exists(env_path):
            return env_path
        # 从当前目录向下递归查找
        root = os.getcwd()
        for dirpath, _dirnames, filenames in os.walk(root):
            if 'local_questionnaire.py' in filenames:
                return os.path.join(dirpath, 'local_questionnaire.py')
        return None

    def _import_local_questionnaire(self, path: str):
        spec = importlib.util.spec_from_file_location("local_questionnaire", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载模块: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore
        return module

    def _infer_question_type_and_options(self, q_text: str, fmt: Optional[str]) -> Tuple[QuestionType, Optional[List[Tuple[int, str]]], Optional[Dict[str, Any]], bool, Optional[str]]:
        """基于题面与格式提示推断题型、选项、校验、是否必填、帮助文案"""
        help_text = None
        if fmt:
            help_text = fmt
        required = not self._is_optional(q_text, fmt)

        # 优先从题面括号内解析枚举选项
        options = None
        paren_match = re.search(r"\(([^)]*)\)", q_text)
        if paren_match:
            inside = paren_match.group(1).strip()
            # 过滤非选项提示词
            if not any(tag in inside for tag in ["选填", "如有"]):
                pairs = []
                for m in re.finditer(r"(\d+)\s*([^\d]+?)(?=(\d+\s*[^\d]|$))", inside):
                    val = int(m.group(1))
                    label = m.group(2).strip()
                    pairs.append((val, label))
                if pairs:
                    # 枚举选择题
                    validation_rules = {"allowed_values": [str(v) for v, _ in pairs]}
                    return QuestionType.SINGLE_CHOICE, pairs, validation_rules, required, help_text

        # 无显式选项时，依据题面与格式提示推断数值题
        numeric_keywords = ["cm", "kg", "年数", "频率", "出生年份", "体重下降kg", "支/天"]
        if any(kw in q_text for kw in numeric_keywords) or (fmt and re.search(r"\d+\s*~\s*\d+", fmt)):
            validation_rules = self._extract_min_max(fmt)
            # 出生年份限定四位数字
            if "出生年份" in q_text:
                validation_rules = validation_rules or {}
                validation_rules.setdefault("digits", 4)
                # 合理的年份范围（可选）
                validation_rules.setdefault("min", 1900)
                validation_rules.setdefault("max", 2100)
            return QuestionType.NUMBER, None, validation_rules, required, help_text

        # 二元是/否类但无括号提示时（极少）
        if fmt and ("1 或 2" in fmt or re.search(r"1\s*或\s*2", fmt)):
            pairs = [(1, "是"), (2, "否")]
            validation_rules = {"allowed_values": ["1", "2"]}
            return QuestionType.SINGLE_CHOICE, pairs, validation_rules, required, help_text

        # 默认文本题
        return QuestionType.TEXT, None, None, required, help_text

    def _extract_min_max(self, fmt: Optional[str]) -> Optional[Dict[str, Any]]:
        if not fmt:
            return None
        # 匹配 X~Y 或者 0~80 等
        m = re.search(r"(\d+)\s*~\s*(\d+)", fmt)
        if m:
            return {"min": float(m.group(1)), "max": float(m.group(2))}
        # 匹配 1~3 之间整数（特殊描述）
        m2 = re.search(r"(\d+)~(\d+)之间?整?数?", fmt)
        if m2:
            return {"min": float(m2.group(1)), "max": float(m2.group(2)), "integer": True}
        return None

    def _is_optional(self, q_text: str, fmt: Optional[str]) -> bool:
        text = (q_text or "") + " " + (fmt or "")
        return ("选填" in text) or ("如有" in text)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 尝试提取JSON部分
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # 如果没有找到JSON，返回结构化数据
                return self._extract_structured_data(response)
                
        except json.JSONDecodeError as e:
            logger.warning(f"LLM响应JSON解析失败: {e}")
            return self._extract_structured_data(response)
    
    def _extract_structured_data(self, response: str) -> Dict[str, Any]:
        """从文本响应中提取结构化数据"""
        # 简单的文本解析逻辑
        data = {
            "title": "智能生成的健康问卷",
            "description": "基于AI分析生成的健康评估问卷",
            "categories": ["基本信息", "健康评估", "风险评估"],
            "questions": []
        }
        
        # 提取问题（这里简化处理）
        lines = response.split('\n')
        question_id = 1
        for line in lines:
            if '?' in line or '？' in line:
                question_text = line.strip()
                if question_text:
                    data["questions"].append({
                        "id": f"q{question_id}",
                        "text": question_text,
                        "type": "single_choice",
                        "category": "健康评估",
                        "options": [
                            {"value": "1", "label": "是"},
                            {"value": "2", "label": "否"}
                        ]
                    })
                    question_id += 1
        
        return data
    
    def _create_questionnaire_from_data(self, data: Dict[str, Any]) -> Questionnaire:
        """从数据创建问卷对象"""
        # 创建问卷
        questionnaire = Questionnaire(
            id=data.get('id', f"questionnaire_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
            title=data.get('title', '智能生成的问卷'),
            description=data.get('description', '基于AI分析生成的问卷'),
            version=data.get('version', '1.0'),
            estimated_time=data.get('estimated_time', '15-20分钟')
        )
        
        # 添加问题
        for q_data in data.get('questions', []):
            question = self._create_question_from_data(q_data)
            questionnaire.add_question(question)
        
        return questionnaire
    
    def _create_question_from_data(self, q_data: Dict[str, Any]) -> Question:
        """从数据创建问题对象"""
        # 确定问题类型
        q_type_str = q_data.get('type', 'single_choice')
        try:
            q_type = QuestionType(q_type_str)
        except ValueError:
            q_type = QuestionType.SINGLE_CHOICE
        
        # 创建选项
        options = None
        if q_data.get('options'):
            options = []
            for opt_data in q_data['options']:
                option = QuestionOption(
                    value=opt_data.get('value', ''),
                    label=opt_data.get('label', ''),
                    score=opt_data.get('score'),
                    risk_factor=opt_data.get('risk_factor')
                )
                options.append(option)
        
        # 创建问题
        question = Question(
            id=q_data.get('id', ''),
            text=q_data.get('text', ''),
            type=q_type,
            category=q_data.get('category', '其他'),
            required=q_data.get('required', True),
            options=options,
            validation_rules=q_data.get('validation_rules'),
            help_text=q_data.get('help_text'),
            risk_weight=q_data.get('risk_weight', 1.0)
        )
        
        return question
    
    def _create_template_questionnaire(self, requirements: Dict[str, Any]) -> Questionnaire:
        """使用模板创建问卷"""
        template_type = requirements.get('template_type', 'lung_cancer')
        template = self.design_templates.get(template_type, self.design_templates['custom'])
        
        questionnaire = Questionnaire(
            id=f"{template_type}_template_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            title=template['title'],
            description=template['description'],
            version='1.0',
            estimated_time=template['estimated_time']
        )
        
        # 添加模板问题
        if template_type == 'lung_cancer':
            self._add_lung_cancer_questions(questionnaire)
        elif template_type == 'general_health':
            self._add_general_health_questions(questionnaire)
        
        return questionnaire
    
    def _add_lung_cancer_questions(self, questionnaire: Questionnaire):
        """添加肺癌早筛问题"""
        # 基本信息
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
        
        # 生活习惯
        lifestyle_questions = [
            Question("smoking", "是否有吸烟史", QuestionType.SINGLE_CHOICE, "生活习惯", True,
                    options=[
                        QuestionOption("1", "是", 2, 2.0),
                        QuestionOption("2", "否", 0, 0.0)
                    ]),
            Question("smoking_years", "累计吸烟年数", QuestionType.NUMBER, "生活习惯", False,
                    validation_rules={"min": 0, "max": 60}),
            Question("daily_cigarettes", "每日吸烟支数", QuestionType.NUMBER, "生活习惯", False,
                    validation_rules={"min": 0, "max": 100})
        ]
        
        # 职业暴露
        occupational_questions = [
            Question("occupational_exposure", "是否接触职业致癌物质", QuestionType.SINGLE_CHOICE, "职业暴露", True,
                    options=[
                        QuestionOption("1", "是", 2, 2.0),
                        QuestionOption("2", "否", 0, 0.0)
                    ])
        ]
        
        # 家族史
        family_questions = [
            Question("family_history", "三代以内直系亲属是否有肺癌史", QuestionType.SINGLE_CHOICE, "家族史", True,
                    options=[
                        QuestionOption("1", "是", 2, 2.0),
                        QuestionOption("2", "否", 0, 0.0)
                    ])
        ]
        
        # 症状评估
        symptom_questions = [
            Question("cough", "是否有持续性干咳", QuestionType.SINGLE_CHOICE, "症状评估", True,
                    options=[
                        QuestionOption("1", "是", 3, 3.0),
                        QuestionOption("2", "否", 0, 0.0)
                    ]),
            Question("hemoptysis", "是否有痰中带血", QuestionType.SINGLE_CHOICE, "症状评估", True,
                    options=[
                        QuestionOption("1", "是", 3, 3.0),
                        QuestionOption("2", "否", 0, 0.0)
                    ]),
            Question("weight_loss", "近半年是否有不明原因消瘦", QuestionType.SINGLE_CHOICE, "症状评估", True,
                    options=[
                        QuestionOption("1", "是", 2, 2.0),
                        QuestionOption("2", "否", 0, 0.0)
                    ])
        ]
        
        # 添加所有问题
        all_questions = (basic_questions + lifestyle_questions + 
                        occupational_questions + family_questions + symptom_questions)
        
        for question in all_questions:
            questionnaire.add_question(question)
    
    def _add_general_health_questions(self, questionnaire: Questionnaire):
        """添加一般健康问题"""
        # 基本信息
        basic_questions = [
            Question("name", "姓名", QuestionType.TEXT, "基本信息", True),
            Question("age", "年龄", QuestionType.NUMBER, "基本信息", True,
                    validation_rules={"min": 18, "max": 100}),
            Question("gender", "性别", QuestionType.SINGLE_CHOICE, "基本信息", True,
                    options=[
                        QuestionOption("1", "男", 0, 0.0),
                        QuestionOption("2", "女", 0, 0.0)
                    ])
        ]
        
        # 生活方式
        lifestyle_questions = [
            Question("exercise", "每周运动频率", QuestionType.SINGLE_CHOICE, "生活方式", True,
                    options=[
                        QuestionOption("1", "从不运动", 2, 1.5),
                        QuestionOption("2", "偶尔运动", 1, 1.0),
                        QuestionOption("3", "经常运动", 0, 0.0)
                    ]),
            Question("diet", "饮食习惯", QuestionType.SINGLE_CHOICE, "生活方式", True,
                    options=[
                        QuestionOption("1", "不规律", 2, 1.5),
                        QuestionOption("2", "一般", 1, 1.0),
                        QuestionOption("3", "健康", 0, 0.0)
                    ])
        ]
        
        # 既往病史
        medical_questions = [
            Question("chronic_disease", "是否有慢性疾病", QuestionType.SINGLE_CHOICE, "既往病史", True,
                    options=[
                        QuestionOption("1", "是", 2, 2.0),
                        QuestionOption("2", "否", 0, 0.0)
                    ])
        ]
        
        # 添加问题
        all_questions = basic_questions + lifestyle_questions + medical_questions
        for question in all_questions:
            questionnaire.add_question(question)
    
    def _validate_questionnaire(self, questionnaire: Questionnaire):
        """验证问卷完整性"""
        if not questionnaire.questions:
            raise ValueError("问卷不能为空问题")
        
        if not questionnaire.title or not questionnaire.description:
            raise ValueError("问卷必须包含标题和描述")
        
        # 检查问题ID唯一性
        question_ids = [q.id for q in questionnaire.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("问题ID必须唯一")
        
        logger.info(f"✅ 问卷验证通过: {len(questionnaire.questions)} 个问题")
    
    async def optimize_question(self, question: Question, feedback: str) -> Question:
        """优化问题"""
        logger.info(f"🔧 {self.name} 开始优化问题: {question.text[:30]}...")
        
        prompt = DesignPrompts.question_optimization_prompt(question.text, feedback)
        
        try:
            llm_response = await self.call_llm(prompt)
            
            # 解析优化建议
            optimized_text = self._extract_optimized_text(llm_response)
            
            if optimized_text:
                # 创建优化后的问题
                optimized_question = Question(
                    id=question.id,
                    text=optimized_text,
                    type=question.type,
                    category=question.category,
                    required=question.required,
                    options=question.options,
                    validation_rules=question.validation_rules,
                    help_text=question.help_text,
                    risk_weight=question.risk_weight
                )
                
                logger.info(f"✅ 问题优化完成")
                return optimized_question
            else:
                logger.warning("⚠️ 无法提取优化后的问题文本，返回原问题")
                return question
                
        except Exception as e:
            logger.error(f"❌ 问题优化失败: {e}")
            return question
    
    def _extract_optimized_text(self, response: str) -> Optional[str]:
        """提取优化后的问题文本"""
        # 简单的文本提取逻辑
        lines = response.split('\n')
        for line in lines:
            if '优化后的问题' in line or '优化后的问题文本' in line:
                # 提取冒号后的内容
                if ':' in line:
                    return line.split(':', 1)[1].strip()
                elif '：' in line:
                    return line.split('：', 1)[1].strip()
        
        # 如果没有找到明确标记，返回第一行非空内容
        for line in lines:
            if line.strip() and len(line.strip()) > 10:
                return line.strip()
        
        return None
    
    async def organize_categories(self, questions: List[Question]) -> Dict[str, List[Question]]:
        """组织问题分类"""
        logger.info(f"📂 {self.name} 开始组织问题分类")
        
        # 按现有分类组织
        categories = {}
        for question in questions:
            category = question.category
            if category not in categories:
                categories[category] = []
            categories[category].append(question)
        
        # 如果分类过多，尝试合并相似分类
        if len(categories) > 6:
            categories = self._merge_similar_categories(categories)
        
        logger.info(f"✅ 问题分类完成: {len(categories)} 个分类")
        return categories
    
    def _merge_similar_categories(self, categories: Dict[str, List[Question]]) -> Dict[str, List[Question]]:
        """合并相似分类"""
        # 简单的分类合并逻辑
        merged_categories = {}
        
        # 定义分类映射
        category_mapping = {
            "基本信息": ["基本信息", "个人资料", "基础资料"],
            "生活习惯": ["生活习惯", "生活方式", "日常行为"],
            "健康状况": ["健康状况", "健康状态", "身体状况"],
            "风险评估": ["风险评估", "风险因素", "风险分析"],
            "其他": ["其他", "其他信息", "补充信息"]
        }
        
        for category, questions in categories.items():
            # 找到匹配的分类
            target_category = "其他"
            for target, aliases in category_mapping.items():
                if category in aliases or any(alias in category for alias in aliases):
                    target_category = target
                    break
            
            if target_category not in merged_categories:
                merged_categories[target_category] = []
            merged_categories[target_category].extend(questions)
        
        return merged_categories
    
    def get_design_templates(self) -> Dict[str, Any]:
        """获取可用的设计模板"""
        return self.design_templates
    
    def create_custom_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建自定义模板"""
        template_id = f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        template_data['id'] = template_id
        template_data['created_at'] = datetime.now().isoformat()
        
        self.design_templates[template_id] = template_data
        logger.info(f"✅ 自定义模板创建成功: {template_id}")
        
        return template_data

if __name__ == "__main__":
    # 测试问卷设计智能体
    print("=== 问卷设计智能体测试 ===")
    
    # 创建智能体
    designer = QuestionnaireDesignerAgent()
    print(f"智能体创建成功: {designer}")
    
    # 测试模板获取
    templates = designer.get_design_templates()
    print(f"可用模板: {list(templates.keys())}")
    
    # 测试问卷创建
    import asyncio
    
    async def test_design():
        requirements = {
            'context': '设计一个简单的健康问卷',
            'type': '健康评估',
            'target_audience': '成年人',
            'question_count': '10个',
            'estimated_time': '10分钟'
        }
        
        questionnaire = await designer.design_questionnaire(requirements)
        print(f"问卷设计成功: {questionnaire.title}")
        print(f"问题数量: {len(questionnaire.questions)}")
        print(f"问题分类: {questionnaire.categories}")
    
    # 运行测试
    asyncio.run(test_design())
    
    print("✅ 问卷设计智能体测试完成")
