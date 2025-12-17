"""
测试脚本，用于验证后端服务器是否正常运行
"""
import sys
import os
import time

# 添加插件目录到Python路径
addon_dir = os.path.dirname(__file__)
sys.path.insert(0, addon_dir)

try:
    from backend.server import server_manager, start_server
    print("成功导入后端服务器模块")
    
    # 启动服务器
    if start_server(5000):
        print("服务器启动成功")
        
        # 等待几秒让服务器完全启动
        time.sleep(2)
        
        # 测试连接
        try:
            import requests
            response = requests.get('http://127.0.0.1:5000/api/test-connection', timeout=5)
            if response.status_code == 200:
                print("连接测试成功:", response.json())
            else:
                print("连接测试失败:", response.status_code)
        except Exception as e:
            print("请求测试失败:", e)
            
    else:
        print("服务器启动失败")
        
except ImportError as e:
    print(f"导入后端服务器模块失败: {e}")
except Exception as e:
    print(f"启动服务器时出错: {e}")

# 保持服务器运行
input("按Enter键停止服务器...")
if server_manager:
    server_manager.stop_server()