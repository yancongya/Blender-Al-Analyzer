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

# 获取插件的根目录，然后确定前端静态文件的路径
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_folder_path = os.path.join(addon_dir, 'frontend', 'src')

app = Flask(__name__, static_folder=static_folder_path, static_url_path='')
CORS(app)  # 允许跨域请求，便于浏览器访问

# 存储Blender数据的全局变量
blender_data = {
    "nodes": "",
    "status": "disconnected",
    "current_operation": None,
    "type": "initial"
}

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取当前Blender插件状态"""
    global blender_data
    return jsonify({
        "status": blender_data["status"],
        "connected": blender_data["status"] == "connected",
        "timestamp": "unknown"
    })

@app.route('/api/blender-data', methods=['GET'])
def get_blender_data():
    """获取当前Blender中的节点数据"""
    global blender_data
    try:
        import bpy
        # 尝试从Blender获取AINodeRefreshContent文本块的内容
        if 'AINodeRefreshContent' in bpy.data.texts:
            text_block = bpy.data.texts['AINodeRefreshContent']
            content = text_block.as_string()
            return jsonify({
                "nodes": content,
                "timestamp": "unknown"  # 移除对bpy.context的访问
            })
        else:
            # 如果没有AINodeRefreshContent，返回默认信息
            return jsonify({"nodes": "No data available"})
    except Exception as e:
        return jsonify({"nodes": f"Error retrieving data: {str(e)}"})

@app.route('/api/blender-data', methods=['POST'])
def set_blender_data():
    """设置Blender数据（从Blender插件推送数据）"""
    global blender_data
    try:
        data = request.json
        # 只更新nodes相关字段
        if "nodes" in data:
            blender_data["nodes"] = data["nodes"]
        if "type" in data:
            blender_data["type"] = data["type"]
        if "timestamp" in data:
            blender_data["timestamp"] = data["timestamp"]

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

@app.route('/api/stream-ai-response', methods=['POST'])
def stream_ai_response():
    from flask import Response, stream_with_context
    import json
    import time

    payload = request.get_json(force=True) or {}
    question = payload.get('question', 'No question provided')
    content = payload.get('content', 'No content provided')

    response_parts = [
        "根据您提供的节点信息，",
        "我分析了节点的连接关系和属性设置。",
        "主要包含以下几个部分：",
        "1. 输入节点：几何信息节点，提供位置、法线等数据。",
        "2. 处理节点：包含变换、计算等操作。",
        "3. 输出节点：最终结果输出。",
        "优化建议：...",
        "这是模拟的AI响应，实际实现中会连接到AI服务。"
    ]

    def generate():
        try:
            yield "data: " + json.dumps({'type': 'start', 'message': '开始处理请求...'}) + "\n\n"
            time.sleep(0.5)
            yield "data: " + json.dumps({'type': 'progress', 'message': '正在分析节点数据...'}) + "\n\n"
            full = []
            for i, part in enumerate(response_parts):
                time.sleep(0.3)
                full.append(part)
                yield "data: " + json.dumps({'type': 'chunk', 'content': part, 'index': i}) + "\n\n"
            yield "data: " + json.dumps({'type': 'complete', 'message': 'AI分析完成'}) + "\n\n"
            analysis_result_store['question'] = question
            analysis_result_store['result'] = ''.join(full)
            browser_messages.append({'message': question, 'response': ''.join(full), 'sender': 'ai', 'timestamp': 'unknown'})
        except GeneratorExit:
            pass
        except Exception as e:
            yield "data: " + json.dumps({'type': 'error', 'message': f'Error: {str(e)}'}) + "\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

def perform_blender_operation(operation, params):
    """执行具体的Blender操作"""
    # 安全地从Blender主进程中获取上下文
    try:
        import bpy
        # 在Flask环境中直接访问bpy.context可能会导致问题
        # 所以我们只返回模拟数据，实际的Blender数据访问需要通过其他方式处理
        if operation == "get_selected_nodes":
            return {
                "selected_nodes_count": 0,
                "active_node": "Simulated data"
            }
        elif operation == "get_node_tree_info":
            return {"tree_name": "Simulated tree", "tree_type": "Simulated type", "total_nodes": 0}
        elif operation == "simple_operation":
            return {"result": f"Operation {operation} executed successfully", "params": params}
        else:
            return {"result": f"Unknown operation: {operation}", "params": params}
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

@app.route('/api/ai-response', methods=['POST'])
def ai_response():
    import time
    data = request.get_json(force=True) or {}
    question = data.get('question', 'No question provided')
    content = data.get('content', 'No content provided')
    parts = [
        "根据您提供的节点信息，",
        "我分析了节点的连接关系和属性设置。",
        "主要包含以下几个部分：",
        "1. 输入节点：几何信息节点，提供位置、法线等数据。",
        "2. 处理节点：包含变换、计算等操作。",
        "3. 输出节点：最终结果输出。",
        "优化建议：...",
        "这是模拟的AI响应，实际实现中会连接到AI服务。"
    ]
    time.sleep(0.5)
    result = ''.join(parts)
    analysis_result_store['question'] = question
    analysis_result_store['result'] = result
    browser_messages.append({'message': question, 'response': result, 'sender': 'ai', 'timestamp': 'unknown'})
    return jsonify({"result": result})

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

# 用于存储前端触发的刷新请求
refresh_request_flag = {"requested": False}

@app.route('/api/trigger-blender-refresh', methods=['POST'])
def trigger_blender_refresh():
    """触发Blender中的节点刷新操作"""
    global refresh_request_flag
    try:
        # 设置刷新请求标志，Blender插件会定期检查这个标志
        refresh_request_flag["requested"] = True

        return jsonify({
            "success": True,
            "message": "刷新请求已发送到Blender"
        })
    except Exception as e:
        print(f"触发Blender刷新时出错: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# 用于存储前端触发的刷新请求
refresh_request_flag = {"requested": False}
# 用于存储从Web推送到Blender的内容
web_to_blender_content = {"content": "", "question": ""}
analysis_result_store = {"question": "", "result": ""}

@app.route('/api/check-refresh-request', methods=['GET'])
def check_refresh_request():
    """检查是否有来自前端的刷新请求"""
    global refresh_request_flag
    try:
        requested = refresh_request_flag["requested"]
        if requested:
            # 重置标志，确保只处理一次
            refresh_request_flag["requested"] = False
            return jsonify({
                "requested": True,
                "message": "需要刷新节点数据"
            })
        else:
            return jsonify({
                "requested": False,
                "message": "无刷新请求"
            })
    except Exception as e:
        print(f"检查刷新请求时出错: {e}")
        return jsonify({"requested": False, "error": str(e)}), 500

@app.route('/api/push-web-content', methods=['POST'])
def push_web_content():
    """接收来自Web的内容并存储以供Blender使用"""
    global web_to_blender_content
    try:
        data = request.json
        content = data.get('content', '')
        question = data.get('question', '')

        # 存储内容供Blender使用
        web_to_blender_content["content"] = content
        web_to_blender_content["question"] = question

        return jsonify({
            "success": True,
            "message": "内容已接收并存储"
        })
    except Exception as e:
        print(f"接收Web内容时出错: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/get-web-content', methods=['GET'])
def get_web_content():
    """获取存储的Web内容供Blender使用"""
    global web_to_blender_content
    try:
        content = web_to_blender_content["content"]
        question = web_to_blender_content["question"]

        # 重置内容，确保Blender获取后不会重复使用
        web_to_blender_content["content"] = ""
        web_to_blender_content["question"] = ""

        return jsonify({
            "content": content,
            "question": question,
            "has_content": bool(content or question)
        })
    except Exception as e:
        print(f"获取Web内容时出错: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/get-analysis-result', methods=['GET'])
def get_analysis_result():
    q = analysis_result_store.get('question', '')
    r = analysis_result_store.get('result', '')
    return jsonify({
        "question": q,
        "result": r,
        "has_content": bool(q or r)
    })

@app.route('/api/clear-analysis-result', methods=['POST'])
def clear_analysis_result():
    analysis_result_store['question'] = ''
    analysis_result_store['result'] = ''
    return jsonify({"success": True})

@app.route('/api/set-analysis-result', methods=['POST'])
def set_analysis_result():
    data = request.get_json(force=True) or {}
    q = data.get('question', '')
    r = data.get('result', '')
    analysis_result_store['question'] = q
    analysis_result_store['result'] = r
    browser_messages.append({'message': q, 'response': r, 'sender': 'ai', 'timestamp': 'unknown'})
    return jsonify({"success": True})

# ===== 统一 AI 分析 API（供 Web/Blender 共用） =====
def _get_ai_settings():
    try:
        s = bpy.context.scene.ainode_analyzer_settings
        return {
            'provider': getattr(s, 'ai_provider', ''),
            'system_prompt': getattr(s, 'system_prompt', ''),
            'deepseek_api_key': getattr(s, 'deepseek_api_key', ''),
            'deepseek_model': getattr(s, 'deepseek_model', ''),
            'ollama_url': getattr(s, 'ollama_url', ''),
            'ollama_model': getattr(s, 'ollama_model', ''),
        }
    except Exception:
        return {'provider': ''}

def _call_deepseek(node_description, question, settings):
    import requests
    api_key = (settings.get('deepseek_api_key') or '').strip()
    model = (settings.get('deepseek_model') or 'deepseek-chat').strip()
    if not api_key:
        return "未配置 DeepSeek API Key"
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    system_message = settings.get('system_prompt', '')
    user_message = f"Analyze Blender nodes:\n\n{node_description}\n\nQuestion: {question}"
    data = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_message},
            {'role': 'user', 'content': user_message}
        ],
        'temperature': 0.7,
        'max_tokens': 2000
    }
    try:
        r = requests.post('https://api.deepseek.com/chat/completions', headers=headers, json=data, timeout=60)
        if r.status_code == 200:
            j = r.json()
            if 'choices' in j and j['choices']:
                return j['choices'][0]['message']['content']
            return f"Unexpected API response format: {j}"
        return f"DeepSeek API error: {r.status_code} - {r.text}"
    except Exception as e:
        return f"Error calling DeepSeek API: {str(e)}"

def _call_ollama(node_description, question, settings):
    import requests
    url = (settings.get('ollama_url') or '').rstrip('/') + '/api/generate'
    model = settings.get('ollama_model') or 'llama3.1'
    system_message = settings.get('system_prompt', '')
    prompt = (
        f"System: {system_message}\n\n"
        f"User: Analyze Blender nodes and answer the question.\n\n{node_description}\n\nQuestion: {question}\n\nAssistant:"
    )
    data = {'model': model, 'prompt': prompt, 'stream': False, 'options': {'temperature': 0.7}}
    try:
        r = requests.post(url, json=data, timeout=60)
        if r.status_code == 200:
            j = r.json()
            if 'response' in j:
                return j['response']
            return f"Unexpected API response format: {j}"
        return f"Ollama API error: {r.status_code} - {r.text}"
    except Exception as e:
        return f"Error calling Ollama API: {str(e)}"

def _analyze(node_description, question):
    settings = _get_ai_settings()
    provider = (settings.get('provider') or '').upper()
    if provider == 'DEEPSEEK':
        return _call_deepseek(node_description, question, settings)
    if provider == 'OLLAMA':
        return _call_ollama(node_description, question, settings)
    return "未配置 AI 提供商或密钥"

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.get_json(force=True) or {}
    question = data.get('question', '')
    node_desc = data.get('content', '') or data.get('node_description', '')
    result = _analyze(node_desc, question)
    analysis_result_store['question'] = question
    analysis_result_store['result'] = result
    browser_messages.append({'message': question, 'response': result, 'sender': 'ai', 'timestamp': 'unknown'})
    return jsonify({'result': result})

@app.route('/api/stream-analyze', methods=['POST'])
def stream_analyze():
    from flask import Response, stream_with_context
    import json, re
    data = request.get_json(force=True) or {}
    question = data.get('question', '')
    node_desc = data.get('content', '') or data.get('node_description', '')
    answer = _analyze(node_desc, question)
    parts = [p for p in re.split(r"(?<=[。！？]|\n)\s+", answer) if p]

    def generate():
        try:
            yield "data: " + json.dumps({'type': 'start', 'message': '开始处理请求...'}) + "\n\n"
            yield "data: " + json.dumps({'type': 'progress', 'message': '正在分析节点数据...'}) + "\n\n"
            full = []
            for i, part in enumerate(parts):
                yield "data: " + json.dumps({'type': 'chunk', 'content': part, 'index': i}) + "\n\n"
                full.append(part)
            yield "data: " + json.dumps({'type': 'complete', 'message': 'AI分析完成'}) + "\n\n"
            final = ''.join(full)
            analysis_result_store['question'] = question
            analysis_result_store['result'] = final
            browser_messages.append({'message': question, 'response': final, 'sender': 'ai', 'timestamp': 'unknown'})
        except Exception as e:
            yield "data: " + json.dumps({'type': 'error', 'message': f'Error: {str(e)}'}) + "\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/')
def index():
    """主页 - 提供前端页面"""
    return app.send_static_file('index.html')

class ServerManager:
    """服务器管理类"""
    def __init__(self):
        self.server_thread = None
        self.is_running = False
        self.host = '127.0.0.1'
        self.port = 5000
        self.app = app
        self.context = None  # 保存Blender上下文

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
