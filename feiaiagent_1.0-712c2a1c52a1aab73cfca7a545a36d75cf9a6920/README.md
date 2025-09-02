# 肺癌早筛智能体（Zhipu + iFlytek）
版本：对外为1.0   内部文件编码为2.0
下个版本迭代内部编码为2.1


基于智谱AI与科大讯飞（ASR/TTS）的肺癌早筛问卷系统。当前版本默认禁用“数字人生成”，采用预录视频 + 讯飞TTS 实时播报；支持自动生成与保存评估报告、网页查看历史报告。

## 功能特性

- 智谱AI对话：按问卷逐题提问，完成后输出评估报告
- 语音识别：iFlytek IAT WebSocket，前端自动录音与静音检测
- 语音合成：iFlytek TTS WebSocket，WAV→MP3（优先）
- 报告保存与浏览：报告自动保存至 `report/`，网页可列出/查看/下载
- 一键清理：开始新问卷时自动清空 `static/tts` 旧音频（保留 warmup/beep）
- 健康检查：`/api/asr/health` 输出 ffmpeg/speexdec/讯飞配置状态

## 版本与路线

- 对外版本：1.0（对演示/用户展示）
- 内部版本：2.0（当前代码实现）
- 计划迭代：2.1（路线图见文末）

## 运行环境

- Python 3.9+（推荐）
- FFmpeg（用于录音格式转 16k/mono PCM 与 WAV→MP3）
- 可访问外网（Zhipu 与 iFlytek）

### 环境准备建议

- Windows：
  - 安装 FFmpeg，并将 `FFMPEG_PATH` 指向 `ffmpeg.exe`；或将 FFmpeg `bin/` 加入 PATH
  - PowerShell 临时设置示例：`$env:FFMPEG_PATH="C:\\ffmpeg\\bin\\ffmpeg.exe"`
- macOS：`brew install ffmpeg`
- Linux：`sudo apt-get install ffmpeg` 或 `sudo yum install ffmpeg`

## 安装与启动

1) 安装依赖
```bash
pip install -r requirements.txt
```

2) 配置环境（可用 `.env` 或系统环境变量）
```env
# Zhipu
ZHIPU_APP_ID=your_app_id
ZHIPU_API_KEY=your_api_key
ZHIPU_API_MODE=open_app_v3

# iFlytek
XFYUN_APPID=your_appid
XFYUN_APIKEY=your_apikey
XFYUN_APISECRET=your_apisecret

# 可选
FFMPEG_PATH=C:\\ffmpeg\\bin\\ffmpeg.exe   # Windows 建议显式设置
LOG_LEVEL=INFO
```

3) 启动
```bash
python app.py
```
启动后访问 `http://localhost:8080`。

## 使用说明

- “开始对话”：使用智谱AI流程问卷；每题播报TTS，播报结束自动开始录音；识别后继续下一题
- “本地问卷”：不调用智谱，按内置 `config.questions` 提问并本地生成报告
- “历史报告”：页面底部可刷新列表、查看内容、下载文件

### 前端交互流程（自动化细节）

1. 点击“开始对话”或“本地问卷”后：
   - 后端先清理 `static/tts/` 旧音频（保留 `warmup.wav/beep.wav`）
   - 后端返回第一题与 `tts_url`、`video_url`（预录视频静音播放）
2. 前端同时播放 TTS 音频与静音视频；TTS 播放结束后自动开始录音
3. 前端录音支持 6 秒静音自动停止并上传
4. 后端将音频转为 16k/16bit/mono PCM WAV → 讯飞 IAT 识别 → 返回文本
5. 提交回答后获取下一题（或最终报告）；历史报告模块可随时查看已保存报告

## 主要接口

- POST `/api/agent/start`：启动智谱问卷
- POST `/api/agent/reply`：提交回答，返回下一题或最终报告
- POST `/api/local_questionnaire/start`：启动本地问卷
- POST `/api/local_questionnaire/reply`：提交回答
- GET `/api/reports`：报告列表与统计
- GET `/api/reports/content/<filename>`：读取报告文本
- GET `/api/reports/download/<filename>`：下载报告
- GET `/api/asr/health`：ASR健康状态

返回字段含 `question`（问题或报告全文）、`tts_url`（音频）、`video_url`（预录视频）、`is_complete`（完成标记）。

### 报告接口响应示例

列表：
```json
{
  "reports": [
    {
      "filename": "张三_13800138000_20250902_153000.txt",
      "path": "D:/.../report/张三_13800138000_20250902_153000.txt",
      "size": 10240,
      "created": "2025-09-02 15:30:00",
      "modified": "2025-09-02 15:30:00"
    }
  ],
  "stats": {
    "total_reports": 1,
    "total_size": 10240,
    "total_size_mb": 0.01,
    "reports_dir": "D:/.../report",
    "latest_report": "2025-09-02 15:30:00"
  }
}
```

## 项目结构（核心）

```
feiaiagent_1.0-.../
├── app.py                 # Flask 应用与API路由
├── config.py              # 配置/问卷题库/工具路径解析
├── zhipu_agent.py         # 智谱会话封装（v2创建会话 + v3调用）
├── xfyun_asr.py           # 讯飞ASR（IAT）WebSocket实现
├── xfyun_tts.py           # 讯飞TTS WebSocket实现（WAV→MP3）
├── report_manager.py      # 报告保存/读取/下载/统计
├── static/
│   ├── index.html         # 前端页面（含“历史报告”模块）
│   ├── script.js          # 自动播放TTS→自动录音、报告UI、可视化
│   ├── style.css          # 医疗主题样式
│   ├── video/human.mp4    # 预录视频（静音播放，增强观感）
│   └── tts/               # TTS 音频输出目录
└── report/                # 评估报告输出目录（运行后自动创建）
```

> 注：数字人生成功能仍保留在 `digital_human.py`，当前默认不启用；如需启用，可参考代码内注释恢复相关导入与调用。

## 关键行为与注意事项

- 启动清理：`/api/agent/start` 与 `/api/local_questionnaire/start` 会先清空 `static/tts` 下旧音频（保留 warmup/beep）
- ASR稳定性：已避免结束帧后主动 `close()`，减少“Connection is already closed”；如需更强纠错，可在 `xfyun_asr.py` 开启 `dwa: wpgs`
- Windows 下建议设置 `FFMPEG_PATH` 指向 `ffmpeg.exe`

### 文件命名与保存规则（报告）

- 命名：`姓名_手机号_YYYYMMDD_HHMMSS.txt`（若无手机号则省略手机号段）
- 存放：项目根目录下 `report/`
- 同步生成：同时保存 `.txt` 与 `.json`（包含用户答案与会话信息）

### 音频目录策略（TTS）

- 目录：`static/tts/`
- 清理：每次开始新问卷时自动清理旧音频（保留 `warmup.wav` 与 `beep.wav`）
- 浏览器兼容：优先生成 MP3；若转换失败则回退 WAV

## 故障排查

- TTS/ASR失败：检查 iFlytek 三项配置与网络；看终端日志
- 音频无法播放：确认生成了 MP3，或浏览器支持的格式；查看 `/static/tts`
- 端口与地址：本应用监听 `0.0.0.0:8080`

### ASR 无法识别/结果为空 常见原因

1. 录音音量过低或持续静音（前端 6 秒静音自动停止）
2. 转码异常：确保 FFmpeg 可用，输入音频被转为 16k/16bit/mono PCM WAV
3. 连接中断：已调整为不主动关闭 IAT WebSocket；必要时检查网络与防火墙
4. 可选增强：在 `xfyun_asr.py` 的 `BusinessArgs` 开启 `"dwa": "wpgs"` 提升长语音纠错

### Windows FFmpeg 日志 GBK 解码报错（不影响结果）

- 现象：`UnicodeDecodeError: 'gbk' codec can't decode byte ...` 出现在子线程读取 FFmpeg 输出时
- 原因：FFmpeg 标准输出包含非 GBK 可解码字节
- 影响：不影响 MP3 生成与功能；可忽略

## 安全与合规

- 请将 API Key 置于环境变量/`.env`，避免提交到仓库
- 仅用于内部演示与研究，使用外部 API 时遵守对应服务条款

## 变更日志（要点）

- 2.0：
  - 默认禁用数字人；改为预录视频 + 讯飞 TTS
  - 新增报告保存（TXT/JSON）与网页查看/下载
  - 新增启动自动清理旧 TTS 音频
  - 优化 ASR 连接关闭时机，减少断连
  - 新增 `/api/asr/health` 健康检查

## 路线图（2.1）

- 报告筛选（姓名/手机号/日期）与删除接口
- ASR wpgs 增量字幕与前端展示
- 可选 TTS 音色/语速配置（前后端参数化）


