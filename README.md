# 肺癌早筛AI代理系统

一个基于智谱AI和科大讯飞语音技术的智能肺癌早筛问卷系统，通过自然语言对话完成风险评估。

## 🚀 功能特性

- **智能对话**: 基于智谱AI大模型，支持自然语言交互
- **语音识别**: 集成科大讯飞ASR，支持语音输入
- **语音合成**: 集成科大讯飞TTS，提供语音播报
- **风险评估**: 自动生成肺癌早筛风险评估报告
- **Web界面**: 简洁易用的Web操作界面
- **会话管理**: 支持多会话并发处理

## 🛠️ 技术架构

- **后端**: Flask + Python
- **AI模型**: 智谱AI (ZhipuAI)
- **语音识别**: 科大讯飞ASR
- **语音合成**: 科大讯飞TTS
- **前端**: HTML + CSS + JavaScript
- **音频处理**: FFmpeg

## 📋 系统要求

- Python 3.7+
- FFmpeg (用于音频处理)
- 网络连接 (访问智谱AI和科大讯飞API)

## 🔧 安装步骤

### 1. 克隆项目
```bash
git clone <项目地址>
cd feiaiagent_1.0
```

### 2. 安装Python依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
创建 `.env` 文件并配置以下参数：

```env
# 智谱AI配置
ZHIPU_APP_ID=your_app_id
ZHIPU_API_KEY=your_api_key
ZHIPU_API_MODE=open_app_v3


