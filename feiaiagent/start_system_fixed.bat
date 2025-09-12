@echo off
echo 启动肺癌早筛智能体系统...
echo.

REM 设置环境变量
set ZHIPU_APP_ID=1952963926488719360
set ZHIPU_API_KEY=232e17d40eb44d358597dbac3e75db03.bBgenNRnmYEFgRAi
set ZHIPU_API_MODE=open_app_v3
set XFYUN_APPID=3536bab1
set XFYUN_APIKEY=fe9c6565d02d77ca53d1129df1222e37
set XFYUN_APISECRET=YTRlMjU3MDAyOGIxM2FhNTA0OTFjYjM1
set FLASK_ENV=development
set FLASK_DEBUG=true

echo 环境变量已设置
echo.

REM 直接使用虚拟环境中的Python
echo 启动Flask服务器...
.venv\Scripts\python.exe app.py

pause
