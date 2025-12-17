"""
AI Node Analyzer Backend Server
提供API接口供浏览器和Blender插件通信
"""
import json
import threading
import sys
import os

# 尝试导入并安装必要的库
try:
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS
except ImportError:
    print("正在安装Flask依赖...")
    import subprocess
    # 获取Blender的Python执行路径
    blender_python_path = sys.executable
    subprocess.check_call([blender_python_path, "-m", "pip", "install", "flask", "flask-cors"])
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS

import bpy

app = Flask(__name__)
CORS(app)  # 允许跨域请求，便于浏览器访问

# 存储Blender数据的全局变量
blender_data = {
    "nodes": [],
    "status": "disconnected",
    "current_operation": None
}

@app.route('/')
def index():
    """主页 - 提供测试页面"""
    addon_dir = os.path.dirname(os.path.dirname(__file__))  # 获取插件根目录
    frontend_path = os.path.join(addon_dir, 'frontend.html')
    try:
        with open(frontend_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except FileNotFoundError:
        return "<h1>AI Node Analyzer Backend</h1><p>Frontend file not found. Please ensure frontend.html is in the addon root directory.</p>"

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取当前Blender插件状态"""
    global blender_data
    return jsonify({
        "status": blender_data["status"],
        "connected": blender_data["status"] == "connected",
        "timestamp": str(bpy.context.view_layer if bpy.context else "No context")
    })

@app.route('/api/blender-data', methods=['GET'])
def get_blender_data():
    """获取当前Blender中的节点数据"""
    global blender_data
    return jsonify(blender_data)

@app.route('/api/blender-data', methods=['POST'])
def set_blender_data():
    """设置Blender数据（从浏览器接收数据）"""
    global blender_data
    try:
        data = request.json
        blender_data.update(data)
        return jsonify({"success": True, "message": "Data updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/execute-operation', methods=['POST'])
def execute_operation():
    """执行Blender操作"""
    try:
        data = request.json
        operation = data.get('operation')
        
        if not operation:
            return jsonify({"success": False, "error": "No operation specified"}), 400
            
        # 根据操作类型执行不同的Blender功能
        result = perform_blender_operation(operation, data.get('params', {}))
        
        return jsonify({
            "success": True,
            "operation": operation,
            "result": result
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def perform_blender_operation(operation, params):
    """执行具体的Blender操作"""
    # 安全地从Blender主进程中获取上下文
    try:
        import bpy
        if bpy.context and hasattr(bpy.context, 'selected_nodes'):
            # 简化版本 - 只处理基本操作
            if operation == "get_selected_nodes":
                # 获取选中节点数量
                selected_count = len(getattr(bpy.context, 'selected_nodes', []))
                active_node_name = getattr(bpy.context.active_node, 'name', 'None') if bpy.context.active_node else 'None'
                return {
                    "selected_nodes_count": selected_count,
                    "active_node": active_node_name
                }
            elif operation == "get_node_tree_info":
                # 获取当前节点树信息
                if bpy.context.space_data and hasattr(bpy.context.space_data, 'node_tree') and bpy.context.space_data.node_tree:
                    node_tree = bpy.context.space_data.node_tree
                    return {
                        "tree_name": node_tree.name,
                        "tree_type": bpy.context.space_data.tree_type,
                        "total_nodes": len(node_tree.nodes)
                    }
                else:
                    return {"error": "No active node tree"}
            elif operation == "simple_operation":
                # 执行简单操作并返回结果
                return {"result": f"Operation {operation} executed successfully", "params": params}
            else:
                return {"result": f"Unknown operation: {operation}", "params": params}
        else:
            # 如果在非Blender环境中运行，返回模拟数据
            if operation == "get_selected_nodes":
                return {
                    "selected_nodes_count": 0,
                    "active_node": "None"
                }
            elif operation == "get_node_tree_info":
                return {"error": "Not running in Blender context"}
    except ImportError:
        # 如果bpy不可用，返回模拟数据
        if operation == "get_selected_nodes":
            return {
                "selected_nodes_count": 0,
                "active_node": "None"
            }
        elif operation == "get_node_tree_info":
            return {"error": "bpy module not available (not in Blender context)"}

    if operation == "simple_operation":
        # 执行简单操作并返回结果
        return {"result": f"Operation {operation} executed successfully", "params": params}
    else:
        return {"result": f"Unknown operation: {operation}", "params": params}

# 存储浏览器发送的消息
browser_messages = []

@app.route('/api/test-connection', methods=['GET'])
def test_connection():
    """测试连接"""
    return jsonify({
        "message": "Connection to Blender backend successful!",
        "blender_version": f"{bpy.app.version[0]}.{bpy.app.version[1]}.{bpy.app.version[2] if len(bpy.app.version) > 2 else 0}",
        "addon_status": "active"
    })

@app.route('/api/send-message', methods=['POST'])
def send_message():
    """接收来自浏览器的消息"""
    try:
        data = request.json
        message = data.get('message', '')
        sender = data.get('sender', 'browser')

        # 将消息存储在全局变量中
        browser_messages.append({
            'message': message,
            'sender': sender,
            'timestamp': str(bpy.context.view_layer.name) if bpy.context.view_layer else 'unknown'
        })

        # 执行与消息相关的基本操作
        response_message = f"Blender收到消息: {message}"

        return jsonify({
            "success": True,
            "response": response_message,
            "messages_count": len(browser_messages)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/get-messages', methods=['GET'])
def get_messages():
    """获取所有消息"""
    return jsonify({
        "messages": browser_messages,
        "count": len(browser_messages)
    })

@app.route('/api/clear-messages', methods=['POST'])
def clear_messages():
    """清空消息列表"""
    global browser_messages
    count = len(browser_messages)
    browser_messages = []
    return jsonify({
        "success": True,
        "cleared_count": count
    })

class ServerManager:
    """服务器管理类"""
    def __init__(self):
        self.server_thread = None
        self.is_running = False
        self.host = '127.0.0.1'
        self.port = 5000
        self.app = app

    def start_server(self, port=None):
        """启动服务器（在后台线程中）"""
        if self.is_running:
            print("服务器已在运行中")
            return False

        if port is not None:
            self.port = port

        def run_server():
            print(f"Starting AI Node Analyzer backend server on {self.host}:{self.port}...")
            try:
                self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False, threaded=True)
            except Exception as e:
                print(f"服务器启动失败: {e}")
                import traceback
                traceback.print_exc()

        try:
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            self.is_running = True
            print(f"服务器线程已启动，地址: http://{self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"创建服务器线程失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def stop_server(self):
        """停止服务器"""
        if self.server_thread and self.server_thread.is_alive():
            # Flask的内置服务器不支持优雅关闭，这里只更新状态
            self.is_running = False
            print("服务器已停止")
            return True
        return False

# 全局服务器实例
server_manager = ServerManager()

def start_server(port=5000):
    """启动服务器"""
    server_manager.port = port
    return server_manager.start_server()

if __name__ == '__main__':
    start_server()