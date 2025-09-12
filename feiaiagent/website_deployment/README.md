# MetaGPT网站部署包

## 快速部署

### 1. 上传文件
将所有文件上传到服务器

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
检查 .env 文件中的API密钥是否正确

### 4. 启动应用
```bash
python app.py
```

### 5. 测试功能
```bash
python test_deployment.py
```

## 文件说明

- `app.py` - 主应用文件（包含MetaGPT修复）
- `metagpt_questionnaire/` - MetaGPT模块目录
- `static/` - 静态文件目录
- `.env` - 环境变量文件
- `requirements.txt` - Python依赖
- `start_app.sh` - 启动脚本
- `test_deployment.py` - 测试脚本

## 重要提醒

1. 确保 `metagpt_questionnaire/` 目录完整上传
2. 确保 `.env` 文件包含正确的API密钥
3. 确保有足够的文件权限
4. 检查服务器日志以排查问题

## 故障排除

如果MetaGPT接口返回404：
- 检查 `metagpt_questionnaire/` 目录是否存在
- 检查文件权限
- 检查Python路径

如果初始化失败：
- 检查 `DEEPSEEK_API_KEY` 是否正确
- 检查依赖包是否安装
- 查看应用日志
