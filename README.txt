肺癌早筛智能体语音问答系统
============================

项目简介
--------
这是一个基于人工智能的肺癌早筛语音问答系统，集成了智谱AI大语言模型、讯飞语音识别(ASR)和语音合成(TTS)技术，为用户提供智能化的肺癌风险评估服务。

系统架构
--------
├── app.py                 # Flask主应用服务器
├── zhipu_agent.py        # 智谱AI智能体接口
├── xfyun_asr.py          # 讯飞语音识别模块
├── xfyun_tts.py          # 讯飞语音合成模块
├── config.py              # 配置文件
├── requirements.txt       # Python依赖包
├── static/                # 前端静态文件
│   ├── index.html        # 主页面
│   ├── script.js         # 前端JavaScript逻辑
│   ├── style.css         # 样式文件
│   ├── beep.wav          # 音频占位文件
│   └── tts/              # TTS音频输出目录
└── .venv/                # Python虚拟环境

核心功能
--------
1. 智能问答：基于智谱AI的肺癌早筛问卷系统
2. 本地问卷：内置完整的肺癌早筛问卷，支持离线使用
3. 语音交互：支持语音输入和AI语音回复
4. 实时对话：多轮对话，智能风险评估
5. 语音识别：将用户语音转换为文字
6. 语音合成：将AI回复转换为语音

技术特点
--------
- 使用智谱智能体进行问卷搭建
- 集成讯飞开放平台的ASR和TTS服务
- 支持多种音频格式转换（WebM、MP3、WAV等）
- 实时语音流处理和音频可视化
- 响应式Web界面，支持移动端访问

API接口
--------
POST /api/agent/start      # 启动智谱AI对话会话
POST /api/agent/reply      # 提交智谱AI对话回答
POST /api/local_questionnaire/start      # 启动本地问卷
POST /api/local_questionnaire/reply      # 提交本地问卷回答
GET  /api/local_questionnaire/status/<session_id>  # 获取本地问卷状态
POST /api/asr              # 语音转文字
GET  /api/health           # 健康检查
GET  /api/questionnaire_status  # 获取问卷系统状态

环境要求
--------
- Python 3.7+
- FFmpeg（音频格式转换）
- 智谱AI API密钥
- 讯飞开放平台账号

安装部署
--------
1. 克隆项目到本地
2. 创建Python虚拟环境：python -m venv .venv
3. 激活虚拟环境：
   - Windows: .venv\Scripts\activate
   - Linux/Mac: source .venv/bin/activate
4. 安装依赖：pip install -r requirements.txt
5. 配置环境变量（见env_template.env）
6. 运行应用：python app.py

环境变量配置
------------
ZHIPU_APP_ID=1952963926488719360
ZHIPU_API_KEY=232e17d40eb44d358597dbac3e75db03.bBgenNRnmYEFgRAi
XFYUN_APPID=3536bab1
XFYUN_APIKEY=fe9c6565d02d77ca53d1129df1222e37
XFYUN_APISECRET=YTRlMjU3MDAyOGIxM2FhNTA0OTFjYjM1

使用方法
--------
1. 启动系统后访问 http://localhost:8080
2. 选择问卷模式：
   - 点击"开始对话"按钮启动智谱AI智能对话
   - 点击"本地问卷"按钮启动内置问卷
3. 使用"开始录音"按钮进行语音回答
4. 系统会自动识别语音并生成下一问题
5. 本地问卷会显示问题分类和格式要求
6. 问卷完成后自动生成风险评估报告



注意事项
--------
- 确保FFmpeg已正确安装并添加到系统PATH
- 智谱AI和讯飞API需要有效的密钥配置
- 音频文件会临时存储在static/tts目录
- 建议在生产环境中使用HTTPS

故障排除
--------
- 如果ASR失败，检查讯飞API配置和网络连接
- 如果TTS失败，检查音频输出目录权限
- 如果智谱AI调用失败，检查API密钥和网络状态

语言识别（方言）
-------------
普通话
zh_cn
mandarin
已开通
-
-
英语
en_us
mandarin
已开通
-
-
上海话
zh_cn
shanghainese
已开通
2025-08-23 00:00
河南话
zh_cn
henanese
已开通
2025-08-26 00:00
客家话
zh_cn
hakkanese
已开通
2025-08-26 00:00
闽南话
zh_cn
minnanese
已开通
2025-08-26 00:00
合肥话
zh_cn
hefeinese
已开通
2025-08-26 00:00