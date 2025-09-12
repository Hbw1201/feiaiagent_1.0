# -*- coding: utf-8 -*-
"""
MetaGPT问卷系统主应用入口
提供命令行界面和API接口
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('metagpt_questionnaire.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 项目根目录（仅用于信息展示，不再修改 sys.path）
project_root = Path(__file__).parent

# 使用相对导入，避免与上层同名模块（如 config.py）冲突
from .config.metagpt_config import validate_config, get_llm_config
from .models.questionnaire import UserResponse, create_lung_cancer_questionnaire
from .workflows.questionnaire_workflow import create_workflow
from .agents.base_agent import agent_registry

class MetaGPTQuestionnaireApp:
    """MetaGPT问卷系统主应用"""
    
    def __init__(self):
        self.workflow = None
        self.config_validated = False
    
    def initialize(self) -> bool:
        """初始化应用"""
        try:
            logger.info("🚀 初始化MetaGPT问卷系统...")
            
            # 验证配置（允许降级运行）
            if not validate_config():
                logger.warning("⚠️ 配置验证失败，将以降级模式运行（使用默认问卷/分析/报告）")
                self.config_validated = False
            else:
                self.config_validated = True
                logger.info("✅ 配置验证通过")
            
            # 创建工作流
            self.workflow = create_workflow("standard")
            logger.info("✅ 工作流初始化完成")
            
            # 显示智能体状态
            self._show_agent_status()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 应用初始化失败: {e}")
            return False
    
    def _show_agent_status(self):
        """显示智能体状态"""
        if not self.workflow:
            return
        
        agent_status = self.workflow.get_agent_status()
        logger.info("🤖 智能体状态:")
        logger.info(f"  工作流ID: {agent_status['workflow_id']}")
        logger.info(f"  智能体数量: {agent_status['total_agents']}")
        
        for name, status in agent_status['agents'].items():
            if status:
                logger.info(f"  ✅ {name}: {status['name']}")
            else:
                logger.warning(f"  ⚠️ {name}: 未注册")
    
    async def run_demo_workflow(self) -> Dict[str, Any]:
        """运行演示工作流"""
        if not self.workflow:
            logger.error("❌ 工作流未初始化")
            return {"error": "工作流未初始化"}
        
        logger.info("🎯 开始运行演示工作流...")
        
        # 创建演示数据
        demo_responses = [
            UserResponse("name", "演示用户"),
            UserResponse("age", "55"),
            UserResponse("gender", "1"),  # 男
            UserResponse("height", "175"),
            UserResponse("weight", "70"),
            UserResponse("smoking", "1"),  # 有吸烟史
            UserResponse("smoking_years", "20"),
            UserResponse("daily_cigarettes", "20"),
            UserResponse("occupational_exposure", "2"),  # 无职业暴露
            UserResponse("family_history", "2"),  # 无家族史
            UserResponse("cough", "2"),  # 无咳嗽
            UserResponse("hemoptysis", "2"),  # 无痰中带血
            UserResponse("weight_loss", "2")  # 无消瘦
        ]
        
        demo_profile = {
            "age": "55",
            "gender": "男",
            "session_id": "demo_session_001"
        }
        
        # 运行完整工作流
        result = await self.workflow.run_complete_workflow(
            user_responses=demo_responses,
            user_profile=demo_profile
        )
        
        return result
    
    async def run_custom_workflow(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """运行自定义工作流"""
        if not self.workflow:
            logger.error("❌ 工作流未初始化")
            return {"error": "工作流未初始化"}
        
        logger.info("🔧 开始运行自定义工作流...")
        
        # 解析工作流配置
        workflow_steps = workflow_config.get('steps', ['questionnaire_design', 'risk_assessment', 'data_analysis', 'report_generation'])
        workflow_data = workflow_config.get('data', {})
        
        # 运行自定义工作流
        result = await self.workflow.run_custom_workflow(workflow_steps, workflow_data)
        
        return result
    
    def export_results(self, workflow_result: Dict[str, Any], output_dir: Optional[str] = None) -> str:
        """导出工作流结果"""
        if not self.workflow:
            return "工作流未初始化"
        
        try:
            output_file = self.workflow.export_workflow_result(workflow_result, output_dir)
            logger.info(f"✅ 结果已导出到: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"❌ 结果导出失败: {e}")
            return f"导出失败: {e}"
    
    def show_workflow_history(self):
        """显示工作流历史"""
        if not self.workflow:
            logger.error("❌ 工作流未初始化")
            return
        
        history = self.workflow.get_workflow_history()
        if not history:
            logger.info("📝 暂无工作流历史")
            return
        
        logger.info(f"📝 工作流历史 (共{len(history)}条):")
        for i, workflow in enumerate(history, 1):
            status_emoji = "✅" if workflow['status'] == 'completed' else "❌" if workflow['status'] == 'failed' else "🔄"
            logger.info(f"  {i}. {status_emoji} {workflow['workflow_id']} - {workflow['status']}")
            if workflow.get('error'):
                logger.info(f"     错误: {workflow['error']}")
    
    def show_available_templates(self):
        """显示可用的问卷模板"""
        try:
            from models.questionnaire import create_lung_cancer_questionnaire
            
            # 创建演示问卷
            questionnaire = create_lung_cancer_questionnaire()
            
            logger.info("📋 可用问卷模板:")
            logger.info(f"  🏥 {questionnaire.title}")
            logger.info(f"     描述: {questionnaire.description}")
            logger.info(f"     问题数量: {len(questionnaire.questions)}")
            logger.info(f"     分类: {', '.join(questionnaire.categories)}")
            logger.info(f"     预计时间: {questionnaire.estimated_time}")
            
        except Exception as e:
            logger.error(f"❌ 获取模板失败: {e}")
    
    def show_system_info(self):
        """显示系统信息"""
        logger.info("ℹ️ 系统信息:")
        logger.info(f"  项目根目录: {project_root}")
        logger.info(f"  Python版本: {sys.version}")
        logger.info(f"  配置状态: {'✅ 已验证' if self.config_validated else '⚠️ 未验证'}")
        
        if self.workflow:
            agent_status = self.workflow.get_agent_status()
            logger.info(f"  工作流状态: 已初始化")
            logger.info(f"  智能体数量: {agent_status['total_agents']}")
        else:
            logger.info(f"  工作流状态: 未初始化")

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MetaGPT问卷系统")
    parser.add_argument("--demo", action="store_true", help="运行演示工作流")
    parser.add_argument("--custom", type=str, help="运行自定义工作流配置文件")
    parser.add_argument("--export", type=str, help="导出结果到指定目录")
    parser.add_argument("--history", action="store_true", help="显示工作流历史")
    parser.add_argument("--templates", action="store_true", help="显示可用模板")
    parser.add_argument("--info", action="store_true", help="显示系统信息")
    parser.add_argument("--interactive", action="store_true", help="交互式模式")
    
    args = parser.parse_args()
    
    # 创建应用实例
    app = MetaGPTQuestionnaireApp()
    
    # 初始化应用
    if not app.initialize():
        logger.error("❌ 应用初始化失败，退出")
        return
    
    try:
        if args.demo:
            # 运行演示工作流
            logger.info("🎯 运行演示工作流...")
            result = await app.run_demo_workflow()
            
            if result.get('status') == 'completed':
                logger.info("✅ 演示工作流执行成功")
                
                # 导出结果
                if args.export:
                    output_file = app.export_results(result, args.export)
                    logger.info(f"📁 结果已导出到: {output_file}")
                else:
                    output_file = app.export_results(result)
                    logger.info(f"📁 结果已导出到: {output_file}")
                
                # 显示结果摘要
                logger.info("📊 结果摘要:")
                logger.info(f"  工作流ID: {result['workflow_id']}")
                logger.info(f"  执行阶段: {len(result['stages'])}")
                
                if result.get('final_results', {}).get('risk_assessment'):
                    risk_level = result['final_results']['risk_assessment']['overall_risk']
                    logger.info(f"  风险评估: {risk_level}")
                
            else:
                logger.error(f"❌ 演示工作流执行失败: {result.get('error')}")
        
        elif args.custom:
            # 运行自定义工作流
            try:
                with open(args.custom, 'r', encoding='utf-8') as f:
                    workflow_config = json.load(f)
                
                logger.info("🔧 运行自定义工作流...")
                result = await app.run_custom_workflow(workflow_config)
                
                if result.get('status') == 'completed':
                    logger.info("✅ 自定义工作流执行成功")
                    output_file = app.export_results(result)
                    logger.info(f"📁 结果已导出到: {output_file}")
                else:
                    logger.error(f"❌ 自定义工作流执行失败: {result.get('error')}")
                    
            except FileNotFoundError:
                logger.error(f"❌ 配置文件未找到: {args.custom}")
            except json.JSONDecodeError:
                logger.error(f"❌ 配置文件格式错误: {args.custom}")
        
        elif args.history:
            # 显示工作流历史
            app.show_workflow_history()
        
        elif args.templates:
            # 显示可用模板
            app.show_available_templates()
        
        elif args.info:
            # 显示系统信息
            app.show_system_info()
        
        elif args.interactive:
            # 交互式模式
            await interactive_mode(app)
        
        else:
            # 默认显示帮助信息
            parser.print_help()
            logger.info("\n💡 使用 --demo 运行演示工作流")
            logger.info("💡 使用 --interactive 进入交互式模式")
    
    except KeyboardInterrupt:
        logger.info("\n👋 用户中断，退出程序")
    except Exception as e:
        logger.error(f"❌ 程序执行失败: {e}")
        raise

async def interactive_mode(app: MetaGPTQuestionnaireApp):
    """交互式模式"""
    logger.info("🎮 进入交互式模式")
    logger.info("可用命令:")
    logger.info("  demo     - 运行演示工作流")
    logger.info("  history  - 显示工作流历史")
    logger.info("  templates - 显示可用模板")
    logger.info("  info     - 显示系统信息")
    logger.info("  quit     - 退出")
    
    while True:
        try:
            command = input("\n🤖 请输入命令: ").strip().lower()
            
            if command == 'quit' or command == 'exit':
                logger.info("👋 退出交互式模式")
                break
            
            elif command == 'demo':
                logger.info("🎯 运行演示工作流...")
                result = await app.run_demo_workflow()
                
                if result.get('status') == 'completed':
                    logger.info("✅ 演示工作流执行成功")
                    output_file = app.export_results(result)
                    logger.info(f"📁 结果已导出到: {output_file}")
                else:
                    logger.error(f"❌ 演示工作流执行失败: {result.get('error')}")
            
            elif command == 'history':
                app.show_workflow_history()
            
            elif command == 'templates':
                app.show_available_templates()
            
            elif command == 'info':
                app.show_system_info()
            
            elif command == '':
                continue
            
            else:
                logger.warning(f"⚠️ 未知命令: {command}")
                logger.info("可用命令: demo, history, templates, info, quit")
        
        except KeyboardInterrupt:
            logger.info("\n👋 退出交互式模式")
            break
        except Exception as e:
            logger.error(f"❌ 命令执行失败: {e}")

def create_sample_config():
    """创建示例配置文件"""
    config = {
        "steps": ["questionnaire_design", "risk_assessment", "data_analysis", "report_generation"],
        "data": {
            "questionnaire_data": {
                "type": "lung_cancer",
                "title": "肺癌早筛问卷",
                "description": "专业的肺癌风险评估问卷"
            },
            "user_profile": {
                "age": "50",
                "gender": "女",
                "session_id": "sample_session_001"
            }
        }
    }
    
    config_file = project_root / "sample_workflow_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    logger.info(f"📝 示例配置文件已创建: {config_file}")
    return str(config_file)

if __name__ == "__main__":
    # 检查是否需要创建示例配置
    if len(sys.argv) == 1:
        logger.info("🚀 MetaGPT问卷系统启动")
        logger.info("💡 使用 --help 查看帮助信息")
        logger.info("💡 使用 --demo 运行演示工作流")
        logger.info("💡 使用 --interactive 进入交互式模式")
        
        # 创建示例配置文件
        sample_config = create_sample_config()
        logger.info(f"📝 示例配置文件: {sample_config}")
    
    # 运行主程序
    asyncio.run(main())
