"""
检查Blender的Python环境是否可以安装Flask
"""
import sys
import os

print(f"Python可执行文件路径: {sys.executable}")
print(f"Python版本: {sys.version}")

try:
    import bpy
    print(f"在Blender中运行，Blender版本: {bpy.app.version}")
except ImportError:
    print("不在Blender环境中运行")

# 尝试安装Flask
try:
    import flask
    print(f"Flask已安装，版本: {flask.__version__}")
except ImportError:
    print("Flask未安装，正在尝试安装...")
    import subprocess
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", "flask", "flask-cors"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("Flask安装成功")
            import flask
            print(f"Flask版本: {flask.__version__}")
        else:
            print(f"Flask安装失败: {result.stderr}")
    except Exception as e:
        print(f"安装Flask时出错: {e}")