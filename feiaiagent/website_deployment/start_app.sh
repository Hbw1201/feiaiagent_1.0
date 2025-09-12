#!/bin/bash
# MetaGPT应用启动脚本

echo "🚀 启动MetaGPT应用..."

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
pip install -r requirements.txt

# 设置权限
echo "🔐 设置权限..."
chmod 755 app.py
chmod -R 755 static/
chmod -R 755 metagpt_questionnaire/

# 启动应用
echo "🚀 启动应用..."
nohup python3 app.py > app.log 2>&1 &

# 等待启动
echo "⏳ 等待应用启动..."
sleep 5

# 检查状态
echo "🔍 检查应用状态..."
if curl -f http://localhost:5000/api/health > /dev/null 2>&1; then
    echo "✅ 应用启动成功"
    echo "📊 查看日志: tail -f app.log"
    echo "🌐 访问地址: http://localhost:5000"
else
    echo "❌ 应用启动失败"
    echo "📊 查看日志: cat app.log"
    exit 1
fi
