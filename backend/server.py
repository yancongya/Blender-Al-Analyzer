import json
import threading
import sys
import os
import uuid
import time
import requests

# 尝试导入并安装必要的库
try:
    from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
    from flask_cors import CORS
except ImportError:
    print("正在安装Flask依赖...")
    import subprocess
    # 获取Blender的Python执行路径
    blender_python_path = sys.executable
    subprocess.check_call([blender_python_path, "-m", "pip", "install", "flask", "flask-cors", "requests"])
    from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
    from flask_cors import CORS

import bpy

# 获取插件的根目录，然后确定前端静态文件的路径
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_folder_path = os.path.join(addon_dir, 'chatgpt-web', 'dist')

app = Flask(__name__, static_folder=static_folder_path, static_url_path='')
CORS(app)  # 允许跨域请求，便于浏览器访问

# 存储Blender数据的全局变量
blender_data = {
    "nodes": "",
    "status": "disconnected",
    "current_operation": None,
    "type": "initial",
    "filename": "Unknown",
    "version": "",
    "node_type": "",
    "tokens": 0
}

# Sync flags
pending_updates = {}
refresh_flag = False

# 存储对话历史
# Format: { 'conversation_id': [ {role, content}, ... ] }
conversations = {}
current_conversation_id = None

def get_settings():
    """从Blender获取设置"""
    settings = {}
    try:
        import bpy
        # 尝试获取当前场景
        scene = None
        if hasattr(bpy, 'context') and hasattr(bpy.context, 'scene'):
            scene = bpy.context.scene
        
        # 如果上下文不可用（例如在后台线程），尝试获取第一个场景
        if not scene and hasattr(bpy, 'data') and hasattr(bpy.data, 'scenes') and len(bpy.data.scenes) > 0:
            scene = bpy.data.scenes[0]
        
        if scene and hasattr(scene, 'ainode_analyzer_settings'):
            s = scene.ainode_analyzer_settings
            settings['deepseek_api_key'] = s.deepseek_api_key
            settings['deepseek_model'] = s.deepseek_model
            settings['ollama_url'] = s.ollama_url
            settings['ollama_model'] = s.ollama_model
            settings['system_prompt'] = s.system_prompt
            settings['ai_provider'] = s.ai_provider
            if hasattr(s, 'enable_web_search'):
                settings['enable_web_search'] = s.enable_web_search
            if hasattr(s, 'search_api'):
                settings['search_api'] = s.search_api
            if hasattr(s, 'tavily_api_key'):
                settings['tavily_api_key'] = s.tavily_api_key
            # 联网复合开关
            if hasattr(s, 'enable_networking'):
                settings['networking_enabled'] = bool(s.enable_networking)
            # Add default_question
            if hasattr(s, 'default_question'):
                settings['default_question'] = s.default_question
        # 从配置文件合并设置
        try:
            config_path = os.path.join(addon_dir, 'config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    ai = cfg.get('ai', {})
                    if 'provider' in ai: settings['ai_provider'] = ai.get('provider', settings.get('ai_provider'))
                    ds = ai.get('deepseek', {})
                    if 'api_key' in ds: settings['deepseek_api_key'] = ds.get('api_key', settings.get('deepseek_api_key'))
                    if 'model' in ds: settings['deepseek_model'] = ds.get('model', settings.get('deepseek_model'))
                    ol = ai.get('ollama', {})
                    if 'url' in ol: settings['ollama_url'] = ol.get('url', settings.get('ollama_url'))
                    if 'model' in ol: settings['ollama_model'] = ol.get('model', settings.get('ollama_model'))
                    if 'system_prompt' in ai: settings['system_prompt'] = ai.get('system_prompt', settings.get('system_prompt'))
                    if 'temperature' in ai: settings['temperature'] = ai.get('temperature')
                    if 'top_p' in ai: settings['top_p'] = ai.get('top_p')
                    thinking = ai.get('thinking', {})
                    if isinstance(thinking, dict) and 'enabled' in thinking:
                        settings['thinking_enabled'] = bool(thinking.get('enabled'))
                    # networking = ai.get('networking', {})
                    # if isinstance(networking, dict) and 'enabled' in networking:
                    #    settings['networking_enabled'] = bool(networking.get('enabled'))
                    
                    # Web Search
                    web_search = ai.get('web_search', {})
                    if isinstance(web_search, dict):
                         if 'enabled' in web_search: settings['enable_web_search'] = bool(web_search.get('enabled'))
                         if 'provider' in web_search: settings['search_api'] = web_search.get('provider')
                         if 'tavily_api_key' in web_search: settings['tavily_api_key'] = web_search.get('tavily_api_key')
        except Exception:
            pass
    except Exception as e:
        print(f"Error getting settings from Blender: {e}")
    return settings

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        response = send_from_directory(app.static_folder, path)
    else:
        response = send_from_directory(app.static_folder, 'index.html')
    
    # Disable caching for index.html and ensure revalidation for others
    if path == "" or path == "index.html" or path.endswith('.html'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    else:
        # For assets, we can allow caching but prefer revalidation if version changes
        # But given the issues, let's be safe for now
        # response.headers['Cache-Control'] = 'no-cache'
        pass
        
    return response

def success_response(data=None, message=""):
    return jsonify({
        "status": "Success",
        "message": message,
        "data": data
    })

def error_response(message="Error", code=400):
    return jsonify({
        "status": "Fail",
        "message": message,
        "data": None
    }), code

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取当前Blender插件状态"""
    global blender_data
    return success_response({
        "status": blender_data["status"],
        "connected": blender_data["status"] == "connected",
        "timestamp": "unknown"
    })

@app.route('/api/session', methods=['POST'])
def session():
    return success_response({
        "auth": False,
        "model": "ChatGPTAPI"
    })

@app.route('/api/verify', methods=['POST'])
def verify():
    return success_response(None, "Verify successfully")

@app.route('/api/config', methods=['POST'])
def config():
    global current_conversation_id, conversations
    settings = get_settings()
    thinking_enabled = bool(settings.get('thinking_enabled'))
    web_search_enabled = bool(settings.get('enable_web_search', False))
    # Calculate rounds for current conversation (assistant message count)
    rounds = 0
    cid = current_conversation_id
    if cid and cid in conversations:
        try:
            msgs = conversations.get(cid, [])
            rounds = len([m for m in msgs if m.get('role') == 'assistant'])
        except Exception:
            rounds = 0
    return success_response({
        "timeoutMs": 100000,
        "reverseProxy": "-",
        "thinkingEnabled": thinking_enabled,
        "webSearchEnabled": web_search_enabled,
        "conversationId": cid or "",
        "conversationRounds": rounds
    })

@app.route('/api/ui-config', methods=['GET'])
def get_ui_config():
    """Get unified configuration from local JSON"""
    config_path = os.path.join(addon_dir, 'config.json')
    # Default fallback
    config = {
        "port": 5000,
        "title": "Blender AI Assistant",
        "icon": "favicon.ico",
        "theme": "light",
        "language": "en-US",
        "user": {
            "name": "User",
            "avatar": "",
            "description": ""
        },
        "assistant": {
            "name": "AI Assistant",
            "avatar": "",
            "description": ""
        },
        "default_questions": [],
        "system_message_presets": [
            { "label": "Default", "value": "您是Blender节点的专家。分析以下节点结构并提供见解、优化或解释。您可以使用网络搜索或提供的知识库来准确回答。" },
            { "label": "Python Expert", "value": "You are an expert Python developer specialized in Blender API (bpy)." }
        ],
        "default_question_presets": [
            { "label": "Analyze Nodes", "value": "请分析这些节点的功能和优化建议" },
            { "label": "Explain Nodes", "value": "Explain what these nodes do in simple terms." }
        ],
        "ai": {
            "provider": "DEEPSEEK",
            "deepseek": {"api_key": "", "model": "deepseek-chat"},
            "ollama": {"url": "http://localhost:11434", "model": "llama2"},
            "system_prompt": "You are an expert in Blender nodes.",
            "temperature": 0.7,
            "top_p": 1.0,
            "thinking": {"enabled": False},
            "web_search": {"enabled": False, "provider": "tavily", "tavily_api_key": ""}
        }
    }
    
    # Load from file
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                # Deep merge could be better, but simple update for now
                deep_update(config, file_config)
        except Exception as e:
            print(f"Error reading config.json: {e}")

    # Smart Fallbacks for Simplified Config
    # 1. If default_questions is empty, populate from presets
    if not config.get('default_questions') and config.get('default_question_presets'):
        config['default_questions'] = [p['value'] for p in config['default_question_presets']]
    
    # 2. If system_prompt is default (English) and presets exist, use first preset (likely Localized)
    ai_config = config.get('ai', {})
    default_prompt = "You are an expert in Blender nodes."
    if ai_config.get('system_prompt') == default_prompt and config.get('system_message_presets'):
         ai_config['system_prompt'] = config['system_message_presets'][0]['value']

    # Optionally sync CURRENT Blender settings into this if they are more recent?
    # For now, let's respect the file as the source of truth as requested.
    
    return success_response(config)

def deep_update(source, overrides):
    """Recursively update a dictionary."""
    for key, value in overrides.items():
        if isinstance(value, dict) and value:
            returned = deep_update(source.get(key, {}), value)
            source[key] = returned
        else:
            source[key] = overrides[key]
    return source

@app.route('/api/save-ui-config', methods=['POST'])
def save_ui_config():
    """Save configuration to config.json"""
    try:
        data = request.json
        
        # Normalize root-level temperature/top_p into ai section for backward compatibility
        if isinstance(data, dict):
            ai = data.get('ai', {})
            if 'temperature' in data and 'temperature' not in ai:
                ai['temperature'] = data['temperature']
                # remove root field to avoid duplication
                try:
                    del data['temperature']
                except Exception:
                    pass
            if 'top_p' in data and 'top_p' not in ai:
                ai['top_p'] = data['top_p']
                try:
                    del data['top_p']
                except Exception:
                    pass
            if ai:
                data['ai'] = ai
        
        config_path = os.path.join(addon_dir, 'config.json')
        
        # Read existing to preserve fields not in request
        existing_config = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
        
        # Deep Merge
        deep_update(existing_config, data)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, indent=4, ensure_ascii=False)
            
        # Trigger Blender to reload these settings
        global pending_updates
        pending_updates['reload_config'] = True
            
        return success_response(None, "Configuration saved")
    except Exception as e:
        return error_response(f"Error saving config: {e}")


@app.route('/api/check-refresh-request', methods=['GET'])
def check_refresh_request():
    global refresh_flag, pending_updates
    response = {
        "requested": refresh_flag,
        "updates": pending_updates
    }
    # Reset flags
    # We create a copy to return and clear the global ones
    # But for simplicity, we just clear them here. 
    # Note: potential race condition if multiple checks happen, but unlikely given single threaded Blender timer.
    if refresh_flag:
        refresh_flag = False
    if pending_updates:
        # Create a new dict instead of clearing to avoid reference issues if returned directly (though we return a copy in response dict)
        # Actually response['updates'] is a reference if we just assigned it.
        # But pending_updates is a dict.
        # Let's do it safely.
        pass # Cleared below by reassigning
        
    # Re-construct response to be safe
    current_updates = pending_updates.copy()
    pending_updates = {}
    
    return success_response({
        "requested": response["requested"],
        "updates": current_updates
    })

@app.route('/api/trigger-refresh', methods=['POST'])
def trigger_refresh():
    global refresh_flag
    refresh_flag = True
    return success_response(None, "Refresh triggered")

@app.route('/api/update-settings', methods=['POST'])
def update_settings():
    global pending_updates
    data = request.json
    # Store updates to be applied by Blender main thread
    if 'system_prompt' in data:
        pending_updates['system_prompt'] = data['system_prompt']
    # Also handle 'default_questions' array from web, taking the first one
    if 'default_questions' in data and isinstance(data['default_questions'], list) and len(data['default_questions']) > 0:
        pending_updates['default_question'] = data['default_questions'][0]
    elif 'default_question' in data:
        pending_updates['default_question'] = data['default_question']
    
    # Sync to config.json
    try:
        config_path = os.path.join(addon_dir, 'config.json')
        existing_config = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
        
        updated = False
        # Support deep 'ai' partial updates from web
        if 'ai' in data and isinstance(data['ai'], dict):
            if 'ai' not in existing_config: existing_config['ai'] = {}
            deep_update(existing_config['ai'], data['ai'])
            updated = True
        if 'system_prompt' in data:
            if 'ai' not in existing_config: existing_config['ai'] = {}
            existing_config['ai']['system_prompt'] = data['system_prompt']
            updated = True
            
        if 'default_questions' in data:
            existing_config['default_questions'] = data['default_questions']
            updated = True
            
        if 'temperature' in data:
            if 'ai' not in existing_config: existing_config['ai'] = {}
            existing_config['ai']['temperature'] = data['temperature']
            updated = True
            
        if 'top_p' in data:
            if 'ai' not in existing_config: existing_config['ai'] = {}
            existing_config['ai']['top_p'] = data['top_p']
            updated = True

        if updated:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, indent=4, ensure_ascii=False)
            # Trigger reload flag so Blender re-reads the file if needed
            pending_updates['reload_config'] = True
            
    except Exception as e:
        print(f"Failed to sync update to file: {e}")
    
    return success_response(None, "Settings update queued")

@app.route('/api/set-analysis-result', methods=['POST'])
def set_analysis_result():
    # Placeholder for future use, maybe store in history
    return success_response(None, "Result received")

def clean_node_data(content):
    """Clean redundant metadata from Blender content"""
    if not content: return ""
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        # Stop processing if we hit the separator line (usually followed by settings/prompt)
        if "==================================================" in line:
            break
        # Skip metadata header lines
        if "AI节点分析器刷新内容" in line: continue
        if "Blender版本:" in line: continue
        if "当前节点类型:" in line: continue
        if "选中节点数量:" in line: continue
        
        cleaned_lines.append(line)
    
    result = '\n'.join(cleaned_lines).strip()
    return result

@app.route('/api/blender-data', methods=['GET'])
def get_blender_data():
    """获取当前Blender中的节点数据"""
    global blender_data
    try:
        import bpy
        # Default to cached data
        content = blender_data.get("nodes", "")
        
        # 尝试从Blender获取AINodeRefreshContent文本块的内容
        if 'AINodeRefreshContent' in bpy.data.texts:
            text_block = bpy.data.texts['AINodeRefreshContent']
            content = text_block.as_string()
            
        # Clean the content
        content = clean_node_data(content)
        
        # 实时获取一些元数据
        filename = blender_data.get("filename", "Unknown")
        version = blender_data.get("version", "")
        tokens = blender_data.get("tokens", 0)
        
        # 如果缓存中是默认值，尝试从bpy获取
        if filename == "Unknown" and bpy.data.filepath:
            filename = bpy.path.basename(bpy.data.filepath)
        if not version:
             version = bpy.app.version_string
        
        # Calculate tokens if 0 and content exists
        if tokens == 0 and content:
            tokens = len(content) // 4
             
        # 更新缓存中的这些值（可选）
        blender_data["filename"] = filename
        blender_data["version"] = version
        blender_data["tokens"] = tokens

        return success_response({
            "nodes": content,
            "timestamp": blender_data.get("timestamp", "unknown"),
            "filename": filename,
            "version": version,
            "node_type": blender_data.get("node_type", ""),
            "tokens": tokens
        })
    except Exception as e:
        return success_response({"nodes": f"Error retrieving data: {str(e)}"})

@app.route('/api/blender-data', methods=['POST'])
def set_blender_data():
    """设置Blender数据（从Blender插件推送数据）"""
    global blender_data
    try:
        data = request.json
        # Update all fields
        for key in ["nodes", "type", "timestamp", "filename", "version", "node_type", "tokens"]:
            if key in data:
                blender_data[key] = data[key]

        return success_response(None, "Data updated successfully")
    except Exception as e:
        return error_response(str(e))

# DeepSeek Call
def _call_deepseek(messages, settings):
    if not bool(settings.get('networking_enabled', True)):
        yield "Error: 联网已关闭，无法调用在线模型。请启用联网。"
        return
    api_key = (settings.get('deepseek_api_key') or '').strip()
    model = (settings.get('deepseek_model') or 'deepseek-chat').strip()
    
    if not api_key:
        yield "Error: 未配置 DeepSeek API Key。请在 Blender 插件设置中配置。"
        return

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    data = {
        'model': model,
        'messages': messages,
        'temperature': 0.7,
        'max_tokens': 2000,
        'stream': True
    }
    thinking_enabled = bool(settings.get('thinking_enabled'))
    if thinking_enabled and model != 'deepseek-reasoner':
        data['thinking'] = {'type': 'enabled'}
    
    try:
        with requests.post('https://api.deepseek.com/chat/completions', headers=headers, json=data, timeout=60, stream=True) as r:
            if r.status_code != 200:
                yield f"DeepSeek API error: {r.status_code} - {r.text}"
                return

            for line in r.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        if line == 'data: [DONE]':
                            break
                        try:
                            json_str = line[6:]
                            j = json.loads(json_str)
                            if 'choices' in j and j['choices']:
                                delta = j['choices'][0].get('delta', {})
                                if 'reasoning_content' in delta and delta['reasoning_content']:
                                    yield json.dumps({'kind': 'thinking', 'content': delta.get('reasoning_content')})
                                if 'content' in delta and delta['content']:
                                    yield json.dumps({'kind': 'chunk', 'content': delta['content']})
                        except Exception:
                            pass
    except Exception as e:
        yield f"Error calling DeepSeek API: {str(e)}"

# Ollama Call
def _call_ollama(messages, settings):
    base_url = (settings.get('ollama_url') or 'http://localhost:11434').rstrip('/')
    model = (settings.get('ollama_model') or 'llama2').strip()
    
    url = f"{base_url}/api/chat"
    
    data = {
        'model': model,
        'messages': messages,
        'stream': True
    }
    
    try:
        with requests.post(url, json=data, timeout=60, stream=True) as r:
            if r.status_code != 200:
                yield f"Ollama API error: {r.status_code} - {r.text}"
                return

            for line in r.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    try:
                        j = json.loads(line)
                        if 'message' in j and 'content' in j['message']:
                            yield j['message']['content']
                        if j.get('done', False):
                            break
                    except Exception:
                        pass
    except Exception as e:
        yield f"Error calling Ollama API: {str(e)}"

@app.route('/api/stream-analyze', methods=['POST'])
def stream_analyze():
    payload = request.get_json(force=True) or {}
    question = payload.get('question', '')
    node_content = payload.get('content', '')
    conversation_id = payload.get('conversationId')
    
    # 获取设置
    settings = get_settings()
    # 若关闭联网，直接返回错误信息，避免任何外部请求
    if not bool(settings.get('networking_enabled', True)):
        return Response("data: " + json.dumps({"type": "error", "content": "联网已关闭，请在设置中启用"}) + "\n\n", mimetype='text/event-stream')
    provider = settings.get('ai_provider', 'DEEPSEEK')
    system_prompt = settings.get('system_prompt', 'You are an expert in Blender nodes.')

    # 管理对话历史
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
    
    if conversation_id not in conversations:
        conversations[conversation_id] = []
        # 如果是新对话，添加系统提示和初始节点上下文
        if node_content:
            context_msg = f"Current Blender Node Data:\n{node_content}\n\nPlease analyze this when asked."
            conversations[conversation_id].append({'role': 'system', 'content': f"{system_prompt}\n\n{context_msg}"})
        else:
            conversations[conversation_id].append({'role': 'system', 'content': system_prompt})

    # 添加用户消息
    # Check for {{Current Node Data}} variable and replace it with actual content
    final_question = question
    # Priority 1: Check for explicit variable with braces
    if "{{Current Node Data}}" in final_question:
        if node_content:
            # Clean metadata first
            cleaned_content = clean_node_data(node_content)
            # Replace with explicit XML-like tag block for clear separation
            replacement = f"\n<Node Data>\n{cleaned_content}\n</Node Data>\n"
            final_question = final_question.replace("{{Current Node Data}}", replacement)
        else:
            final_question = final_question.replace("{{Current Node Data}}", "[No Node Data Available]")
    # Priority 2: Check for variable name without braces (common user case)
    elif "Current Node Data" in final_question:
        if node_content:
            cleaned_content = clean_node_data(node_content)
            replacement = f"\n<Node Data>\n{cleaned_content}\n</Node Data>\n"
            final_question = final_question.replace("Current Node Data", replacement)
        else:
            final_question = final_question.replace("Current Node Data", "[No Node Data Available]")

    conversations[conversation_id].append({'role': 'user', 'content': final_question})

    def generate():
        full_response = ""
        try:
            yield "data: " + json.dumps({'type': 'start', 'conversationId': conversation_id}) + "\n\n"
            global current_conversation_id
            current_conversation_id = conversation_id
            
            generator = None
            if provider == 'OLLAMA':
                generator = _call_ollama(conversations[conversation_id], settings)
            else:
                generator = _call_deepseek(conversations[conversation_id], settings)
            
            for chunk in generator:
                try:
                    # Try to parse as JSON first (for DeepSeek wrapper)
                    try:
                        j = json.loads(chunk)
                        kind = j.get('kind')
                        content = j.get('content') or ''
                        
                        if kind == 'thinking':
                            yield "data: " + json.dumps({'type': 'thinking', 'content': content}) + "\n\n"
                        elif kind == 'chunk':
                            full_response += content
                            yield "data: " + json.dumps({'type': 'chunk', 'content': content}) + "\n\n"
                        else:
                            # Not our wrapper format, maybe direct JSON? treat as string
                            raise ValueError("Unknown kind")
                    except (json.JSONDecodeError, ValueError, TypeError):
                        # If parsing fails or structure doesn't match, treat as raw string (for Ollama or errors)
                        s_chunk = str(chunk)
                        full_response += s_chunk
                        yield "data: " + json.dumps({'type': 'chunk', 'content': s_chunk}) + "\n\n"
                except Exception as e:
                    print(f"Error processing chunk: {e}")

            
            # Save assistant response to history
            conversations[conversation_id].append({'role': 'assistant', 'content': full_response})

            yield "data: " + json.dumps({'type': 'complete', 'conversationId': conversation_id}) + "\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            yield "data: " + json.dumps({'type': 'error', 'message': str(e), 'conversationId': conversation_id}) + "\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/get-messages', methods=['GET'])
def get_messages():
    """获取所有对话历史列表 (For sidebar)"""
    chat_list = []
    for cid, msgs in conversations.items():
        user_msg = next((m['content'] for m in msgs if m['role'] == 'user'), "New Chat")
        last_resp = next((m['content'] for m in reversed(msgs) if m['role'] == 'assistant'), "")
        
        chat_list.append({
            'conversationId': cid,
            'message': user_msg[:50] + "..." if len(user_msg) > 50 else user_msg,
            'response': last_resp[:50] + "...", 
            'timestamp': 'unknown'
        })
    
    return jsonify({'messages': chat_list})

@app.route('/api/prompt-templates', methods=['GET'])
def get_prompt_templates():
    """获取提示词模板"""
    try:
        prompt_templates_path = os.path.join(addon_dir, 'prompt_templates.json')
        if os.path.exists(prompt_templates_path):
            with open(prompt_templates_path, 'r', encoding='utf-8') as f:
                prompt_templates = json.load(f)
                return success_response(prompt_templates)
        else:
            # 如果提示词文件不存在，返回空数组
            return success_response([])
    except Exception as e:
        return error_response(f"Error reading prompt templates: {e}")

@app.route('/api/save-prompt-templates', methods=['POST'])
def save_prompt_templates():
    """保存提示词模板"""
    try:
        data = request.json
        prompt_templates = data.get('promptList', data) if isinstance(data, dict) else data

        prompt_templates_path = os.path.join(addon_dir, 'prompt_templates.json')

        # 保存到提示词文件
        with open(prompt_templates_path, 'w', encoding='utf-8') as f:
            json.dump(prompt_templates, f, indent=4, ensure_ascii=False)

        return success_response(None, "Prompt templates saved successfully")
    except Exception as e:
        return error_response(f"Error saving prompt templates: {e}")

@app.route('/api/import-prompt-templates', methods=['POST'])
def import_prompt_templates():
    """从在线URL导入提示词模板"""
    try:
        data = request.json
        url = data.get('url')

        if not url:
            return error_response("URL is required for importing prompt templates")

        # 从URL获取提示词数据
        response = requests.get(url)
        if response.status_code != 200:
            return error_response(f"Failed to fetch data from URL: {response.status_code}")

        imported_data = response.json()

        # 验证数据格式
        if not isinstance(imported_data, list):
            return error_response("Imported data must be an array of prompts")

        # 验证每个提示词的格式
        for item in imported_data:
            if not isinstance(item, dict) or 'key' not in item or 'value' not in item:
                return error_response("Each prompt must have 'key' and 'value' fields")

        # 添加创建时间戳
        for item in imported_data:
            if 'createdAt' not in item:
                item['createdAt'] = int(time.time() * 1000)  # 毫秒时间戳

        # 保存到提示词文件
        prompt_templates_path = os.path.join(addon_dir, 'prompt_templates.json')

        # 如果文件存在，读取现有数据并与新数据合并
        existing_data = []
        if os.path.exists(prompt_templates_path):
            with open(prompt_templates_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

        # 合并数据，避免重复
        existing_keys = {item['key'] for item in existing_data}
        unique_imported = [item for item in imported_data if item['key'] not in existing_keys]
        merged_data = existing_data + unique_imported

        with open(prompt_templates_path, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=4, ensure_ascii=False)

        return success_response({
            "imported_count": len(unique_imported),
            "total_count": len(merged_data)
        }, f"Successfully imported {len(unique_imported)} new prompt templates")
    except Exception as e:
        return error_response(f"Error importing prompt templates: {e}")

@app.route('/api/default-prompt-templates', methods=['GET'])
def get_default_prompt_templates():
    """获取默认提示词模板（从config.json）"""
    try:
        config_path = os.path.join(addon_dir, 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 从配置文件中获取默认提示词模板
                default_prompt_templates = config.get('default_prompt_templates', [])
                return success_response(default_prompt_templates)
        else:
            # 如果配置文件不存在，返回空数组
            return success_response([])
    except Exception as e:
        return error_response(f"Error reading default prompt templates: {e}")

@app.route('/api/test-connection', methods=['GET'])
def test_connection():
    """测试连接"""
    return jsonify({
        "message": "Connection to Blender backend successful!",
        "blender_version": f"{bpy.app.version[0]}.{bpy.app.version[1]}.{bpy.app.version[2] if len(bpy.app.version) > 2 else 0}",
        "addon_status": "active"
    })

@app.route('/api/execute-operation', methods=['POST'])
def execute_operation():
    return jsonify({"success": False, "error": "Not implemented in this version"}), 501

class ServerManager:
    """管理Flask服务器线程"""
    def __init__(self):
        self.thread = None
        self.port = 5000
        self.is_running = False

    def start_server(self, port=5000):
        if self.is_running:
            return True
        self.port = port
        self.is_running = True
        try:
            self.thread = threading.Thread(target=self.run_server)
            self.thread.daemon = True
            self.thread.start()
            print(f"AI Node Server started on port {self.port}")
            return True
        except Exception as e:
            print(f"Failed to start server: {e}")
            self.is_running = False
            return False

    def run_server(self):
        # Disable Flask banner
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        try:
            app.run(host='127.0.0.1', port=self.port, debug=False, use_reloader=False)
        except Exception as e:
            print(f"Server error: {e}")
            self.is_running = False

    def stop_server(self):
        self.is_running = False
        # Flask server is hard to stop gracefully in a thread
        pass

# 全局服务器管理器实例
server_manager = ServerManager()

if __name__ == '__main__':
    port = 5000
    config_path = os.path.join(addon_dir, 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'port' in config:
                    port = config['port']
        except Exception as e:
            print(f"Error reading config for port: {e}")
            
    app.run(port=port)
