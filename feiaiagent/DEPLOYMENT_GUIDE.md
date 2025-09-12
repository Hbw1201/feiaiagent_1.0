# MetaGPT部署指南

## 问题诊断
如果MetaGPT在部署环境中无法正常工作，请按以下步骤检查：

### 1. 环境变量检查
确保以下环境变量已正确设置：
```bash
DEEPSEEK_API_KEY=your-actual-deepseek-api-key
ZHIPU_APP_ID=your-zhipu-app-id
ZHIPU_API_KEY=your-zhipu-api-key
XFYUN_APPID=your-xfyun-appid
XFYUN_APIKEY=your-xfyun-apikey
XFYUN_APISECRET=your-xfyun-apisecret
```

### 2. 文件结构检查
确保以下文件/目录存在：
- app.py
- config.py
- local_questionnaire.py
- metagpt_questionnaire/ (目录)
- .env (环境变量文件)

### 3. 依赖包检查
确保安装了所有必要的Python包：
```bash
pip install -r requirements.txt
```

### 4. 路径问题
如果MetaGPT目录找不到，检查：
- 当前工作目录是否正确
- metagpt_questionnaire目录是否在正确位置
- Python路径是否包含项目根目录

### 5. 权限问题
确保应用有读取所有必要文件的权限。

## 修复步骤

### 步骤1: 运行诊断脚本
```bash
python deploy_metagpt_fix.py
```

### 步骤2: 根据诊断结果修复问题
- 如果环境变量缺失，创建.env文件
- 如果文件缺失，检查部署包是否完整
- 如果路径问题，调整工作目录或文件位置

### 步骤3: 重新测试
```bash
python final_test.py
```

## 常见问题

### Q: MetaGPT初始化失败
A: 检查DEEPSEEK_API_KEY是否正确设置

### Q: 路由404错误
A: 检查Flask应用是否正确加载了所有路由

### Q: 模块导入失败
A: 检查Python路径和文件结构

### Q: 权限错误
A: 检查文件权限和用户权限
