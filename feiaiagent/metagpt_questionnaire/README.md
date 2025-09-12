# MetaGPT问卷系统 🚀

基于MetaGPT架构的智能问卷填写和分析系统，专为医学健康评估设计。

## ✨ 系统特性

- **🤖 多智能体协作**: 问卷设计、风险评估、数据分析、报告生成四大智能体
- **🏥 专业医学问卷**: 内置肺癌早筛等专业问卷模板
- **📊 智能数据分析**: AI驱动的数据洞察和模式识别
- **📝 自动报告生成**: 多种格式的专业分析报告
- **🔄 灵活工作流**: 支持自定义工作流程和配置
- **🌐 多LLM支持**: OpenAI、Anthropic、智谱AI等多种大模型

## 🏗️ 系统架构

```
用户输入 → 工作流协调器 → 智能体协作 → 结果输出
                ↓
         ┌─────────────────┐
         │ 问卷设计智能体  │
         │ 风险评估智能体  │
         │ 数据分析智能体  │
         │ 报告生成智能体  │
         └─────────────────┘
                ↓
        智能体协作工作流
                ↓
        问卷分析结果 → 用户
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 支持的操作系统: Windows, macOS, Linux

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd metagpt_questionnaire
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
# 复制环境变量模板
cp env_template.env .env

# 编辑 .env 文件，填入您的API密钥
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
ZHIPU_APP_ID=your-zhipu-app-id
ZHIPU_API_KEY=your-zhipu-api-key
```

4. **运行演示**
```bash
python main.py --demo
```

## 📖 使用指南

### 命令行使用

```bash
# 运行演示工作流
python main.py --demo

# 交互式模式
python main.py --interactive

# 自定义工作流
python main.py --custom config.json

# 显示系统信息
python main.py --info

# 显示可用模板
python main.py --templates

# 显示工作流历史
python main.py --history
```

### 交互式模式

进入交互式模式后，可以使用以下命令：

- `demo` - 运行演示工作流
- `history` - 显示工作流历史
- `templates` - 显示可用模板
- `info` - 显示系统信息
- `quit` - 退出

### 自定义工作流

创建配置文件 `workflow_config.json`:

```json
{
  "steps": [
    "questionnaire_design",
    "risk_assessment", 
    "data_analysis",
    "report_generation"
  ],
  "data": {
    "questionnaire_data": {
      "type": "lung_cancer",
      "title": "肺癌早筛问卷",
      "description": "专业的肺癌风险评估问卷"
    },
    "user_profile": {
      "age": "50",
      "gender": "女",
      "session_id": "custom_session_001"
    }
  }
}
```

运行自定义工作流：
```bash
python main.py --custom workflow_config.json
```

## 🏥 问卷模板

### 肺癌早筛问卷

- **基本信息**: 姓名、年龄、性别、身高、体重
- **生活习惯**: 吸烟史、吸烟年数、每日吸烟量
- **职业暴露**: 职业致癌物质接触情况
- **家族史**: 三代以内直系亲属肺癌史
- **症状评估**: 持续性干咳、痰中带血、不明原因消瘦

### 一般健康问卷

- **基本信息**: 个人基础资料
- **生活方式**: 运动频率、饮食习惯
- **既往病史**: 慢性疾病情况
- **家族史**: 遗传疾病史
- **当前症状**: 身体不适症状

## 🤖 智能体介绍

### 1. 问卷设计智能体
- **职责**: 设计问卷结构、优化问题、组织分类
- **专长**: 问卷设计、医学知识、用户体验
- **功能**: 
  - 智能问卷设计
  - 问题优化建议
  - 分类结构组织

### 2. 风险评估智能体
- **职责**: 分析用户回答、评估健康风险
- **专长**: 医学诊断、风险评估、预防医学
- **功能**:
  - 多维度风险评估
  - 风险因素分析
  - 个性化建议生成

### 3. 数据分析智能体
- **职责**: 分析问卷数据、识别模式、提供洞察
- **专长**: 数据分析、统计学、模式识别
- **功能**:
  - 数据质量评估
  - 模式识别分析
  - 洞察发现

### 4. 报告生成智能体
- **职责**: 生成专业分析报告和可视化内容
- **专长**: 报告写作、医学写作、数据可视化
- **功能**:
  - 多种报告模板
  - 自动内容生成
  - 多格式导出

## 🔧 配置说明

### 环境变量配置

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `OPENAI_API_KEY` | OpenAI API密钥 | `sk-...` |
| `OPENAI_BASE_URL` | OpenAI API地址 | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | OpenAI模型名称 | `gpt-4` |
| `ANTHROPIC_API_KEY` | Anthropic API密钥 | `sk-ant-...` |
| `ANTHROPIC_MODEL` | Anthropic模型名称 | `claude-3-sonnet` |
| `ZHIPU_APP_ID` | 智谱AI应用ID | `1952963926488719360` |
| `ZHIPU_API_KEY` | 智谱AI API密钥 | `...` |
| `XFYUN_APPID` | 科大讯飞应用ID | `3536bab1` |

### 系统配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `MAX_TOKENS` | 最大Token数 | `4000` |
| `TEMPERATURE` | 生成温度 | `0.7` |

## 📁 项目结构

```
metagpt_questionnaire/
├── agents/                 # 智能体定义
│   ├── base_agent.py      # 智能体基类
│   ├── questionnaire_designer.py  # 问卷设计智能体
│   ├── risk_assessor.py   # 风险评估智能体
│   ├── data_analyzer.py   # 数据分析智能体
│   └── report_generator.py # 报告生成智能体
├── config/                 # 配置文件
│   └── metagpt_config.py  # 系统配置
├── models/                 # 数据模型
│   └── questionnaire.py   # 问卷数据模型
├── prompts/                # 提示词模板
│   └── design_prompts.py  # 设计提示词
├── workflows/              # 工作流定义
│   └── questionnaire_workflow.py  # 问卷工作流
├── main.py                 # 主应用入口
├── requirements.txt        # 依赖包列表
└── README.md              # 项目说明
```

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_agents.py

# 运行异步测试
pytest --asyncio-mode=auto
```

### 测试覆盖率

```bash
# 安装覆盖率工具
pip install pytest-cov

# 运行测试并生成覆盖率报告
pytest --cov=metagpt_questionnaire --cov-report=html
```

## 📊 性能优化

### 异步处理
- 所有智能体操作都支持异步执行
- 工作流并行处理提高效率
- 支持并发请求处理

### 缓存机制
- 智能体对话历史缓存
- 工作流结果缓存
- 配置信息缓存

### 资源管理
- 智能连接池管理
- 内存使用优化
- 异常处理和恢复

## 🔒 安全特性

- **API密钥管理**: 环境变量安全存储
- **数据隐私**: 用户信息加密处理
- **访问控制**: 智能体权限管理
- **审计日志**: 完整操作记录

## 🚀 部署指南

### 本地部署

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **配置环境变量**
```bash
cp env_template.env .env
# 编辑 .env 文件
```

3. **运行应用**
```bash
python main.py --demo
```

### Docker部署

1. **构建镜像**
```bash
docker build -t metagpt-questionnaire .
```

2. **运行容器**
```bash
docker run -p 8000:8000 metagpt-questionnaire
```

### 云服务部署

支持部署到以下云平台：
- AWS Lambda
- Google Cloud Functions
- Azure Functions
- 阿里云函数计算

## 🤝 贡献指南

### 开发环境设置

1. **Fork项目**
2. **创建特性分支**
3. **提交更改**
4. **创建Pull Request**

### 代码规范

- 使用Black进行代码格式化
- 遵循PEP 8编码规范
- 添加适当的类型注解
- 编写单元测试

### 提交规范

```
feat: 添加新功能
fix: 修复bug
docs: 更新文档
style: 代码格式调整
refactor: 代码重构
test: 添加测试
chore: 构建过程或辅助工具的变动
```

## 📞 技术支持

### 常见问题

1. **配置问题**
   - 检查环境变量是否正确设置
   - 验证API密钥是否有效
   - 确认网络连接正常

2. **性能问题**
   - 检查系统资源使用情况
   - 优化工作流配置
   - 调整并发参数

3. **功能问题**
   - 查看日志文件
   - 检查智能体状态
   - 验证数据格式

### 联系方式

- **项目Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **技术支持**: support@example.com
- **开发讨论**: [Discord](https://discord.gg/your-server)

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

感谢以下开源项目的支持：
- [MetaGPT](https://github.com/geekan/MetaGPT) - 多智能体框架
- [OpenAI](https://openai.com/) - GPT模型服务
- [Anthropic](https://www.anthropic.com/) - Claude模型服务
- [智谱AI](https://open.bigmodel.cn/) - 中文大模型服务

---

**⭐ 如果这个项目对您有帮助，请给我们一个Star！**
