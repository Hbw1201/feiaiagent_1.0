# -*- coding: utf-8 -*-
"""
智能问卷系统使用示例
演示如何使用基于local_questionnaire的动态问题选择功能
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from workflows.questionnaire_workflow import create_workflow
from models.questionnaire import UserResponse
from agents.base_agent import agent_registry

async def demo_intelligent_questionnaire():
    """演示智能问卷系统"""
    print("=" * 60)
    print("🧠 智能问卷系统演示")
    print("=" * 60)
    
    try:
        # 1. 创建工作流
        workflow = create_workflow("standard")
        print(f"✅ 工作流创建成功: {workflow.workflow_id}")
        
        # 2. 显示智能体状态
        agent_status = workflow.get_agent_status()
        print(f"\n🤖 智能体状态:")
        for name, status in agent_status['agents'].items():
            if status:
                print(f"  ✅ {name}: {status['name']}")
            else:
                print(f"  ⚠️ {name}: 未注册")
        
        # 3. 启动智能问卷工作流
        print(f"\n🚀 启动智能问卷工作流...")
        workflow_result = await workflow.run_intelligent_questionnaire_workflow(
            questionnaire_data={
                "source": "local",  # 使用本地问卷
                "template_type": "lung_cancer"
            },
            user_profile={
                "session_id": "demo_intelligent_001",
                "start_time": "2024-01-01 10:00:00"
            }
        )
        
        if workflow_result["status"] != "initialized":
            print(f"❌ 工作流初始化失败: {workflow_result.get('error')}")
            return
        
        print(f"✅ 智能问卷工作流初始化成功")
        session_data = workflow_result["final_results"]["session_data"]
        
        # 4. 模拟智能问答流程
        print(f"\n📝 开始智能问答流程...")
        
        # 模拟用户回答序列
        demo_answers = [
            ("name", "张三"),
            ("gender", "1"),  # 男
            ("birth_year", "1970"),
            ("height", "175"),
            ("weight", "75"),
            ("smoking_history", "1"),  # 有吸烟史 - 这会触发后续吸烟相关问题
            ("smoking_freq", "20"),
            ("smoking_years", "25"),
            ("smoking_quit", "2"),  # 未戒烟
            ("passive_smoking", "1"),  # 无被动吸烟
            ("occupation", "建筑工人"),
            ("occupation_exposure", "1"),  # 有职业暴露 - 会触发详情询问
            ("occupation_exposure_details", "石棉接触15年"),
            ("family_cancer_history", "2"),  # 无家族史
            ("recent_cough", "1"),  # 有持续咳嗽 - 高风险信号
            ("cough_duration", "2个月"),
            ("recent_weight_loss", "1"),  # 有消瘦 - 高风险信号
            ("weight_loss_amount", "5"),
            ("hemoptysis", "2"),  # 无痰血
            ("self_feeling", "3")  # 感觉不好
        ]
        
        question_count = 0
        max_questions = 15  # 限制演示问题数量
        
        for answer_id, answer_value in demo_answers:
            if question_count >= max_questions:
                break
                
            # 获取下一个智能推荐问题
            if question_count == 0:
                # 第一次获取问题
                next_result = await workflow.get_next_intelligent_question(session_data)
            else:
                # 提交上一个问题的回答，获取下一个问题
                user_response = UserResponse(question_id=current_question_id, answer=answer_value)
                next_result = await workflow.get_next_intelligent_question(session_data, user_response)
            
            if next_result["status"] == "completed":
                print(f"\n🎉 问卷完成!")
                break
            elif next_result["status"] == "error":
                print(f"\n❌ 错误: {next_result['error']}")
                break
            elif next_result["status"] == "next_question":
                question_info = next_result["question"]
                progress_info = next_result["progress"]
                
                # 检查是否是我们要回答的问题
                if question_info["id"] == answer_id:
                    current_question_id = question_info["id"]
                    
                    print(f"\n📋 问题 {question_count + 1}:")
                    print(f"   类别: {question_info['category']}")
                    print(f"   问题: {question_info['optimized_prompt']}")
                    print(f"   回答: {answer_value}")
                    print(f"   选择理由: {question_info['selection_reason']}")
                    print(f"   优先级评分: {question_info['priority_score']:.1f}")
                    print(f"   进度: {progress_info['answered']}/{progress_info['total']} ({progress_info['percentage']:.1f}%)")
                    
                    # 显示备选问题
                    if next_result.get("alternatives"):
                        print(f"   📚 备选问题:")
                        for alt in next_result["alternatives"][:3]:
                            print(f"      - {alt['category']}: {alt['text'][:50]}... (评分: {alt['score']:.1f})")
                    
                    question_count += 1
                else:
                    # 如果推荐的问题不在我们的演示回答中，跳过
                    print(f"\n⏭️ 跳过问题: {question_info['text'][:50]}...")
                    # 用默认回答
                    user_response = UserResponse(question_id=question_info["id"], answer="2")
                    session_data = next_result["session_data"]
                    continue
        
        # 5. 强制完成问卷并生成报告
        print(f"\n📊 生成最终分析报告...")
        final_analysis = await workflow._finalize_intelligent_questionnaire(session_data)
        
        print(f"\n📋 分析结果:")
        print(f"   ✅ 回答问题数: {final_analysis.get('total_questions_asked', 0)}")
        
        if final_analysis.get("risk_assessment"):
            risk_data = final_analysis["risk_assessment"]
            print(f"   🔍 风险等级: {risk_data.get('overall_risk', 'unknown')}")
            print(f"   📊 风险评分: {risk_data.get('risk_score', 0):.1f}")
            print(f"   ⚠️ 风险因素: {len(risk_data.get('risk_factors', []))}")
            print(f"   💡 建议数量: {len(risk_data.get('recommendations', []))}")
        
        if final_analysis.get("report"):
            report_data = final_analysis["report"]
            print(f"   📝 报告标题: {report_data.get('title', 'N/A')}")
            print(f"   📄 报告长度: {len(report_data.get('content', ''))} 字符")
        
        # 6. 导出结果
        print(f"\n💾 导出工作流结果...")
        workflow_result["final_results"].update(final_analysis)
        output_file = workflow.export_workflow_result(workflow_result)
        print(f"   ✅ 结果已导出: {output_file}")
        
        print(f"\n🎊 智能问卷系统演示完成!")
        
    except Exception as e:
        logger.error(f"❌ 演示过程中发生错误: {e}")
        raise

async def demo_comparison_workflow():
    """演示传统工作流 vs 智能工作流的对比"""
    print("\n" + "=" * 60)
    print("🔀 传统工作流 vs 智能工作流对比")
    print("=" * 60)
    
    try:
        workflow = create_workflow("standard")
        
        # 相同的测试数据
        test_responses = [
            UserResponse("name", "李四"),
            UserResponse("gender", "2"),  # 女
            UserResponse("birth_year", "1980"),
            UserResponse("height", "165"),
            UserResponse("weight", "55"),
            UserResponse("smoking_history", "2"),  # 无吸烟史
            UserResponse("passive_smoking", "2"),  # 有被动吸烟
            UserResponse("kitchen_fumes", "1"),  # 有厨房油烟接触
            UserResponse("family_cancer_history", "1"),  # 有家族史
            UserResponse("recent_symptoms", "2")  # 无症状
        ]
        
        user_profile = {
            "session_id": "comparison_demo",
            "age": "44",
            "gender": "女"
        }
        
        # 1. 传统工作流
        print(f"\n🔄 运行传统工作流...")
        traditional_start = asyncio.get_event_loop().time()
        
        traditional_result = await workflow.run_complete_workflow(
            user_responses=test_responses,
            user_profile=user_profile
        )
        
        traditional_time = asyncio.get_event_loop().time() - traditional_start
        
        print(f"   ⏱️ 执行时间: {traditional_time:.2f}秒")
        print(f"   📊 执行阶段: {len(traditional_result.get('stages', []))}")
        print(f"   📝 问题数量: {len(test_responses)}")
        
        # 2. 智能工作流（模拟）
        print(f"\n🧠 智能工作流特点:")
        print(f"   🎯 动态问题选择: 根据回答智能推荐下一题")
        print(f"   ⏭️ 智能跳题: 自动跳过不相关问题")
        print(f"   🔍 风险感知: 优先询问高风险相关问题")
        print(f"   💬 上下文理解: 基于对话历史优化问题")
        print(f"   📈 实时评估: 动态调整问题优先级")
        
        # 比较结果
        print(f"\n📊 对比总结:")
        print(f"   传统工作流: 固定问题顺序，全量问题")
        print(f"   智能工作流: 个性化问题路径，按需询问")
        print(f"   效率提升: 预计节省30-50%的问题数量")
        print(f"   准确性提升: 更精准的风险评估")
        
    except Exception as e:
        logger.error(f"❌ 对比演示失败: {e}")

if __name__ == "__main__":
    async def main():
        """主演示函数"""
        try:
            # 演示智能问卷系统
            await demo_intelligent_questionnaire()
            
            # 演示对比
            await demo_comparison_workflow()
            
        except KeyboardInterrupt:
            print("\n👋 演示被用户中断")
        except Exception as e:
            print(f"\n❌ 演示失败: {e}")
            raise
    
    # 运行演示
    print("🚀 启动智能问卷系统演示...")
    asyncio.run(main())
