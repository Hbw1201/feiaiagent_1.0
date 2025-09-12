#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
依赖安装脚本
尝试多种方法安装MetaGPT问卷系统所需的依赖包
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """运行命令并处理结果"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            print(f"✅ {description} 成功")
            return True
        else:
            print(f"❌ {description} 失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} 异常: {e}")
        return False

def install_with_pip(package, description=None):
    """使用pip安装包"""
    if description is None:
        description = f"安装 {package}"
    
    # 尝试多种安装方法
    methods = [
        f"pip install {package}",
        f"pip install {package} --trusted-host pypi.org",
        f"pip install {package} --trusted-host pypi.python.org",
        f"python -m pip install {package}",
    ]
    
    for method in methods:
        if run_command(method, description):
            return True
    
    return False

def install_with_alternative_sources(package, description=None):
    """使用替代源安装包"""
    if description is None:
        description = f"使用替代源安装 {package}"
    
    sources = [
        f"pip install {package} -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn",
        f"pip install {package} -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com",
        f"pip install {package} -i https://pypi.douban.com/simple/ --trusted-host pypi.douban.com",
    ]
    
    for source in sources:
        if run_command(source, description):
            return True
    
    return False

def check_package_installed(package):
    """检查包是否已安装"""
    try:
        __import__(package)
        return True
    except ImportError:
        return False

def main():
    """主安装流程"""
    print("🚀 MetaGPT问卷系统依赖安装脚本")
    print("=" * 50)
    
    # 检查Python版本
    print(f"🐍 Python版本: {sys.version}")
    
    # 检查pip
    if not run_command("pip --version", "检查pip"):
        print("❌ pip不可用，请先安装pip")
        return
    
    # 核心依赖包列表
    core_packages = [
        "openai",
        "anthropic", 
        "pandas",
        "numpy",
        "aiohttp",
        "python-dotenv",
        "pydantic",
        "pytest"
    ]
    
    # 已安装的包
    installed_packages = []
    failed_packages = []
    
    print("\n📦 开始安装依赖包...")
    
    for package in core_packages:
        print(f"\n--- 处理 {package} ---")
        
        # 检查是否已安装
        if check_package_installed(package):
            print(f"✅ {package} 已安装")
            installed_packages.append(package)
            continue
        
        # 尝试安装
        success = False
        
        # 方法1: 直接pip安装
        if install_with_pip(package):
            success = True
        # 方法2: 使用替代源
        elif install_with_alternative_sources(package):
            success = True
        # 方法3: 尝试不同版本
        elif install_with_pip(f"{package}>=0.0.1", f"安装 {package} (最低版本)"):
            success = True
        
        if success:
            installed_packages.append(package)
        else:
            failed_packages.append(package)
    
    # 安装结果总结
    print("\n" + "=" * 50)
    print("📊 安装结果总结:")
    print(f"✅ 成功安装: {len(installed_packages)} 个包")
    print(f"❌ 安装失败: {len(failed_packages)} 个包")
    
    if installed_packages:
        print(f"\n✅ 已安装的包:")
        for pkg in installed_packages:
            print(f"  - {pkg}")
    
    if failed_packages:
        print(f"\n❌ 安装失败的包:")
        for pkg in failed_packages:
            print(f"  - {pkg}")
        print(f"\n💡 建议:")
        print("  1. 检查网络连接")
        print("  2. 尝试手动安装失败的包")
        print("  3. 使用离线安装包")
    
    # 创建环境检查脚本
    create_environment_check_script()
    
    print(f"\n🎯 安装完成！")
    print(f"💡 使用 'python check_env.py' 检查环境")

def create_environment_check_script():
    """创建环境检查脚本"""
    script_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境检查脚本
检查MetaGPT问卷系统的运行环境
"""

import sys
import importlib

def check_package(package_name, display_name=None):
    """检查包是否可用"""
    if display_name is None:
        display_name = package_name
    
    try:
        importlib.import_module(package_name)
        print(f"✅ {display_name}: 可用")
        return True
    except ImportError:
        print(f"❌ {display_name}: 不可用")
        return False

def main():
    """主检查流程"""
    print("🔍 MetaGPT问卷系统环境检查")
    print("=" * 40)
    
    # 检查Python版本
    print(f"🐍 Python版本: {sys.version}")
    
    # 核心依赖检查
    core_packages = [
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic"),
        ("pandas", "Pandas"),
        ("numpy", "NumPy"),
        ("aiohttp", "aiohttp"),
        ("dotenv", "python-dotenv"),
        ("pydantic", "Pydantic"),
        ("pytest", "Pytest")
    ]
    
    available_count = 0
    total_count = len(core_packages)
    
    for package, display_name in core_packages:
        if check_package(package, display_name):
            available_count += 1
    
    print("\\n" + "=" * 40)
    print(f"📊 环境检查结果: {available_count}/{total_count} 个包可用")
    
    if available_count == total_count:
        print("🎉 环境配置完整，可以运行MetaGPT问卷系统！")
    else:
        print("⚠️  部分依赖缺失，某些功能可能不可用")
        print("💡 建议运行安装脚本补充缺失的依赖")

if __name__ == "__main__":
    main()
'''
    
    with open("check_env.py", "w", encoding="utf-8") as f:
        f.write(script_content)
    
    print("📝 环境检查脚本已创建: check_env.py")

if __name__ == "__main__":
    main()
