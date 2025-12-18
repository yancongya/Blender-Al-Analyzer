"""
Blender插件与后端服务器的通信接口
此模块提供函数供Blender插件调用，以推送数据到后端服务器
"""
import json
import requests
from threading import Thread

class BlenderDataPusher:
    """用于从Blender向后端服务器推送数据的类"""
    
    def __init__(self, server_manager):
        self.server_manager = server_manager
        self.base_url = None
    
    def update_base_url(self):
        """更新基础URL"""
        if self.server_manager and self.server_manager.is_running:
            self.base_url = f"http://127.0.0.1:{self.server_manager.port}"
            return True
        return False
    
    def push_blender_data(self, data):
        """推送Blender数据到后端服务器"""
        if not self.update_base_url() or not self.base_url:
            print("服务器未运行或URL未设置")
            return False
        
        try:
            response = requests.post(
                f"{self.base_url}/api/blender-data",
                json=data,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"推送数据失败: {e}")
            return False
    
    def get_blender_content(self):
        """从后端服务器获取Blender内容"""
        if not self.update_base_url() or not self.base_url:
            print("服务器未运行或URL未设置")
            return None
        
        try:
            response = requests.get(
                f"{self.base_url}/api/blender-data",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取数据失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"获取数据失败: {e}")
            return None

# 全局推送器实例
blender_data_pusher = None

def initialize_pusher(server_manager):
    """初始化推送器"""
    global blender_data_pusher
    blender_data_pusher = BlenderDataPusher(server_manager)
    return blender_data_pusher