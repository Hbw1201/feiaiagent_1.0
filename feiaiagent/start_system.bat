@echo off
echo 启动肺癌早筛智能体语音问答系统...
echo.

echo 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo 错误：未找到Python，请先安装Python 3.7+
    pause
    exit /b 1
)

echo.
echo 检查依赖包...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo 警告：依赖包安装失败，可能影响系统运行
    pause
)

echo.
echo 启动Flask服务器...
echo 访问地址: http://localhost:8080
echo 按 Ctrl+C 停止服务器
echo.

python app.py

pause
