#!/bin/bash

echo "启动肺癌早筛智能体语音问答系统..."
echo

echo "检查Python环境..."
python3 --version
if [ $? -ne 0 ]; then
    echo "错误：未找到Python3，请先安装Python 3.7+"
    exit 1
fi

echo
echo "检查依赖包..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "警告：依赖包安装失败，可能影响系统运行"
fi

echo
echo "启动Flask服务器..."
echo "访问地址: http://localhost:8080"
echo "按 Ctrl+C 停止服务器"
echo

python3 app.py
