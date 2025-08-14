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

# 科大讯飞配置
XFYUN_APPID=your_appid
XFYUN_APIKEY=your_apikey
XFYUN_APISECRET=your_apisecret

# 可选配置
LOG_LEVEL=INFO
FFMPEG_PATH=/path/to/ffmpeg
```

### 4. 安装FFmpeg
- **Windows**: 下载FFmpeg并添加到系统PATH
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg` 或 `sudo yum install ffmpeg`

## 🚀 启动系统

### Windows
```bash
start_system.bat
```

### Linux/macOS
```bash
chmod +x start_system.sh
./start_system.sh
```

### 手动启动
```bash
python app.py
```

系统启动后，访问 `http://localhost:5000` 即可使用。

## 📱 使用方法

### 1. 开始对话
- 点击"开始对话"按钮
- 系统会询问您的姓名并开始问卷

### 2. 回答问题
- 可以通过语音或文字回答系统问题
- 系统会根据您的回答智能调整问题

### 3. 获取报告
- 完成所有问题后，系统自动生成风险评估报告
- 报告包含详细的健康建议和风险评估

## 🔍 API接口

### 开始对话
```http
POST /api/agent/start
Content-Type: application/json

{
    "session_id": "unique_session_id"
}
```

### 继续对话
```http
POST /api/agent/reply
Content-Type: application/json

{
    "session_id": "session_id",
    "answer": "用户回答内容"
}
```

## 📁 项目结构

```
feiaiagent_1.0/
├── app.py                 # Flask主应用
├── config.py              # 配置文件
├── requirements.txt        # Python依赖
├── zhipu_agent.py         # 智谱AI代理模块
├── xfyun_asr.py          # 科大讯飞语音识别
├── xfyun_tts.py          # 科大讯飞语音合成
├── static/                # 静态资源
│   ├── index.html         # 主页面
│   ├── style.css          # 样式文件
│   ├── script.js          # 前端逻辑
│   ├── beep.wav           # 提示音
│   └── tts/               # TTS音频输出目录
├── start_system.bat       # Windows启动脚本
└── start_system.sh        # Linux/macOS启动脚本
```

## ⚙️ 配置说明

### 智谱AI配置
- `ZHIPU_API_MODE`: 支持 `agents` 和 `open_app_v3` 两种模式
- `ZHIPU_MOCK`: 启用模拟模式，用于测试

### 科大讯飞配置
- 需要申请科大讯飞开放平台账号
- 创建语音识别和语音合成应用

### 音频配置
- `TTS_OUT_DIR`: TTS音频文件输出目录
- `FFMPEG_PATH`: FFmpeg可执行文件路径

## 🐛 故障排除

### 常见问题

1. **智谱AI调用失败**
   - 检查API密钥是否正确
   - 确认网络连接正常
   - 查看日志中的错误信息

2. **语音识别失败**
   - 检查科大讯飞配置
   - 确认音频文件格式正确
   - 查看ASR模块日志

3. **FFmpeg相关错误**
   - 确认FFmpeg已正确安装
   - 检查FFMPEG_PATH环境变量
   - 验证FFmpeg版本兼容性

### 日志查看
系统运行时会输出详细的日志信息，包括：
- API调用状态
- 语音处理进度
- 错误和异常信息

## 📄 许可证

本项目仅供学习和研究使用。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进项目。

## 📞 支持

如有问题，请查看日志文件或提交Issue。

---

**注意**: 使用前请确保已正确配置所有API密钥，并遵守相关服务的使用条款。
