"""
AI Node Analyzer Blender Add-on

This addon allows users to analyze selected nodes in Blender's node editors
(Geometry Nodes, Shader Nodes, Compositor Nodes) with AI assistance.
"""
import bpy
import bmesh
import threading
import json
import requests
from bpy.props import (
    StringProperty,
    EnumProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty,
    PointerProperty
)
from bpy.types import (
    Panel,
    Operator,
    AddonPreferences,
    PropertyGroup,
    Text
)
from mathutils import Vector
import os
import tempfile
from urllib.parse import urlparse

# 插件基本信息
bl_info = {
    "name": "AI Node Analyzer",
    "author": "Assistant",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "Node Editor > Sidebar > AI Node Analyzer",
    "description": "Analyze selected nodes with AI assistance",
    "category": "Node",
    "doc_url": "https://github.com/your-repo/ainode-analyzer",
}

# 配置选项
class AINodeAnalyzerSettings(PropertyGroup):
    """插件设置属性组"""
    
    # AI服务商选择
    ai_provider: EnumProperty(
        name="AI Provider",
        description="Select AI service provider",
        items=[
            ('DEEPSEEK', "DeepSeek", "DeepSeek AI service"),
            ('OLLAMA', "Ollama", "Ollama local AI service"),
        ],
        default='DEEPSEEK'
    )

    # DeepSeek设置
    deepseek_api_key: StringProperty(
        name="DeepSeek API Key",
        description="DeepSeek API Key for model access",
        subtype='PASSWORD',
        default=""
    )

    deepseek_model: EnumProperty(
        name="DeepSeek Model",
        description="Select DeepSeek model to use",
        items=[
            ('deepseek-chat', "DeepSeek Chat", "DeepSeek Chat model"),
            ('deepseek-coder', "DeepSeek Coder", "DeepSeek Coder model"),
        ],
        default='deepseek-chat'
    )

    # Ollama设置
    ollama_url: StringProperty(
        name="Ollama URL",
        description="URL for Ollama service",
        default="http://localhost:11434",
        maxlen=2048
    )

    ollama_model: StringProperty(
        name="Ollama Model",
        description="Ollama model name (e.g., llama2, mistral)",
        default="llama2",
        maxlen=256
    )

    # 系统提示
    system_prompt: StringProperty(
        name="System Prompt",
        description="Custom system prompt for AI",
        default="You are an expert in Blender nodes. Analyze the following node structure and provide insights, optimizations, or explanations.",
        maxlen=2048
    )

    # 联网检索相关设置
    enable_web_search: BoolProperty(
        name="Enable Web Search",
        description="Enable web search functionality for enhanced analysis",
        default=False
    )

    search_api: EnumProperty(
        name="Search API",
        description="Select search API service",
        items=[
            ('TAVILY', "Tavily", "Tavily search API"),
            ('NONE', "None", "No search API"),
        ],
        default='NONE'
    )

    tavily_api_key: StringProperty(
        name="Tavily API Key",
        description="Tavily API Key for web search",
        subtype='PASSWORD',
        default=""
    )

# 插件偏好设置面板
class AINodeAnalyzerPreferences(AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="AI Node Analyzer Preferences")
        col.separator()

# 主要面板
class NODE_PT_ai_analyzer(Panel):
    bl_label = "AI Node Analyzer"
    bl_idname = "NODE_PT_ai_analyzer"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AI Node Analyzer"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ain_settings = scene.ainode_analyzer_settings

        # AI服务商选择
        box = layout.box()
        box.label(text="AI Provider", icon='WORLD_DATA')
        box.prop(ain_settings, "ai_provider")

        # 根据选择的AI服务商显示不同的设置
        if ain_settings.ai_provider == 'DEEPSEEK':
            box.prop(ain_settings, "deepseek_api_key")
            box.prop(ain_settings, "deepseek_model")
        elif ain_settings.ai_provider == 'OLLAMA':
            box.prop(ain_settings, "ollama_url")
            box.prop(ain_settings, "ollama_model")

        # 系统提示
        box = layout.box()
        box.label(text="System Prompt", icon='WORDWRAP_ON')
        box.prop(ain_settings, "system_prompt", text="")

        # 联网检索设置
        box = layout.box()
        box.label(text="Web Search", icon='URL')
        box.prop(ain_settings, "enable_web_search")
        if ain_settings.enable_web_search:
            box.prop(ain_settings, "search_api")
            
            if ain_settings.search_api == 'TAVILY':
                box.prop(ain_settings, "tavily_api_key")
            elif ain_settings.search_api == 'EXA':
                box.prop(ain_settings, "exa_api_key")
            elif ain_settings.search_api == 'BRAVE':
                box.prop(ain_settings, "brave_api_key")

        # 知识库设置 - 暂时隐藏，后续实现
        # box = layout.box()
        # box.label(text="Knowledge Base", icon='INFO')
        # box.prop(ain_settings, "custom_knowledge", text="")
        # box.prop(ain_settings, "knowledge_file_path", text="Knowledge File")
        # box.prop(ain_settings, "knowledge_urls", text="Knowledge URLs")

        # 分析按钮
        layout.separator()
        row = layout.row()
        row.scale_y = 1.5
        row.operator("node.analyze_with_ai", text="Analyze Selected Nodes with AI", icon='PLAY')

# 实现节点解析功能
def parse_node_tree_recursive(node_tree, depth=0, max_depth=10):
    """
    递归解析节点树
    :param node_tree: 要解析的节点树
    :param depth: 当前递归深度
    :param max_depth: 最大递归深度，防止无限递归
    :return: 解析结果的字典
    """
    if depth >= max_depth:
        return {"error": f"Max recursion depth ({max_depth}) reached"}

    result = {
        "tree_type": node_tree.bl_idname if hasattr(node_tree, 'bl_idname') else "Unknown",
        "nodes": [],
        "groups": {},
        "links": []
    }

    # 解析节点
    for node in node_tree.nodes:
        node_info = {
            "name": node.name,
            "label": node.label,
            "type": node.bl_idname,
            "location": (node.location.x, node.location.y),
            "width": node.width,
            "height": node.height,
            "color": node.color[:],
            "use_custom_color": node.use_custom_color,
            "inputs": [],
            "outputs": [],
        }

        # 解析输入端口
        for input_idx, input_socket in enumerate(node.inputs):
            input_info = {
                "name": input_socket.name,
                "type": input_socket.type,
                "identifier": input_socket.identifier,
                "enabled": input_socket.enabled,
                "hide": input_socket.hide,
                "hide_value": input_socket.hide_value,
            }
            # 添加默认值（如果适用）
            if hasattr(input_socket, 'default_value'):
                try:
                    # 处理不同类型的默认值
                    val = input_socket.default_value
                    if isinstance(val, (int, float, str, bool)):
                        input_info["default_value"] = val
                    elif hasattr(val, '__len__') and len(val) <= 10:  # 处理向量等序列
                        input_info["default_value"] = list(val)
                    else:
                        input_info["default_value"] = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                except:
                    input_info["default_value"] = "N/A"

            # 检查输入是否连接
            connected = False
            for link in node_tree.links:
                if link.to_socket == input_socket:
                    input_info["connected_from"] = {
                        "node": link.from_node.name,
                        "socket": link.from_socket.name
                    }
                    connected = True
                    break
            input_info["is_connected"] = connected

            node_info["inputs"].append(input_info)

        # 解析输出端口
        for output_idx, output_socket in enumerate(node.outputs):
            output_info = {
                "name": output_socket.name,
                "type": output_socket.type,
                "identifier": output_socket.identifier,
                "enabled": output_socket.enabled,
                "hide": output_socket.hide,
            }
            # 添加默认值（如果适用）
            if hasattr(output_socket, 'default_value'):
                try:
                    val = output_socket.default_value
                    if isinstance(val, (int, float, str, bool)):
                        output_info["default_value"] = val
                    elif hasattr(val, '__len__') and len(val) <= 10:  # 处理向量等序列
                        output_info["default_value"] = list(val)
                    else:
                        output_info["default_value"] = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                except:
                    output_info["default_value"] = "N/A"

            # 检查输出是否连接
            connected = False
            output_info["connected_to"] = []
            for link in node_tree.links:
                if link.from_socket == output_socket:
                    output_info["connected_to"].append({
                        "node": link.to_node.name,
                        "socket": link.to_socket.name
                    })
                    connected = True
            output_info["is_connected"] = connected

            node_info["outputs"].append(output_info)

        # 如果是节点组，递归解析其内容
        if node.type == 'GROUP' and node.node_tree:
            node_info["group_content"] = parse_node_tree_recursive(node.node_tree, depth + 1, max_depth)
            result["groups"][node.name] = node_info["group_content"]

        result["nodes"].append(node_info)

    # 解析连接
    for link in node_tree.links:
        link_info = {
            "from_node": link.from_node.name,
            "from_socket": link.from_socket.name,
            "to_node": link.to_node.name,
            "to_socket": link.to_socket.name,
        }
        result["links"].append(link_info)

    return result

def get_selected_nodes_description(context):
    """
    获取选中节点的描述
    :param context: Blender上下文
    :return: 包含节点描述的字符串
    """
    space = context.space_data

    if not hasattr(space, 'node_tree') or not space.node_tree:
        return "No active node tree found."

    node_tree = space.node_tree
    selected_nodes = context.selected_nodes

    if not selected_nodes:
        if hasattr(context, 'active_node') and context.active_node:
            selected_nodes = [context.active_node]
        else:
            return "No selected or active nodes to analyze."

    result = {
        "node_tree_type": space.tree_type,
        "selected_nodes_count": len(selected_nodes),
        "selected_nodes": []
    }

    for node in selected_nodes:
        node_info = {
            "name": node.name,
            "label": node.label,
            "type": node.bl_idname,
            "location": (node.location.x, node.location.y),
            "width": node.width,
            "height": node.height,
            "color": node.color[:],
            "use_custom_color": node.use_custom_color,
            "inputs": [],
            "outputs": [],
        }

        # 解析输入端口
        for input_idx, input_socket in enumerate(node.inputs):
            input_info = {
                "name": input_socket.name,
                "type": input_socket.type,
                "identifier": input_socket.identifier,
                "enabled": input_socket.enabled,
                "hide": input_socket.hide,
                "hide_value": input_socket.hide_value,
            }
            if hasattr(input_socket, 'default_value'):
                try:
                    val = input_socket.default_value
                    if isinstance(val, (int, float, str, bool)):
                        input_info["default_value"] = val
                    elif hasattr(val, '__len__') and len(val) <= 10:  # 处理向量等序列
                        input_info["default_value"] = list(val)
                    else:
                        input_info["default_value"] = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                except:
                    input_info["default_value"] = "N/A"

            # 检查输入是否连接
            connected = False
            for link in node_tree.links:
                if link.to_socket == input_socket:
                    input_info["connected_from"] = {
                        "node": link.from_node.name,
                        "socket": link.from_socket.name
                    }
                    connected = True
                    break
            input_info["is_connected"] = connected

            node_info["inputs"].append(input_info)

        # 解析输出端口
        for output_idx, output_socket in enumerate(node.outputs):
            output_info = {
                "name": output_socket.name,
                "type": output_socket.type,
                "identifier": output_socket.identifier,
                "enabled": output_socket.enabled,
                "hide": output_socket.hide,
            }
            if hasattr(output_socket, 'default_value'):
                try:
                    val = output_socket.default_value
                    if isinstance(val, (int, float, str, bool)):
                        output_info["default_value"] = val
                    elif hasattr(val, '__len__') and len(val) <= 10:  # 处理向量等序列
                        output_info["default_value"] = list(val)
                    else:
                        output_info["default_value"] = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                except:
                    output_info["default_value"] = "N/A"

            # 检查输出是否连接
            connected = False
            output_info["connected_to"] = []
            for link in node_tree.links:
                if link.from_socket == output_socket:
                    output_info["connected_to"].append({
                        "node": link.to_node.name,
                        "socket": link.to_socket.name
                    })
                    connected = True
            output_info["is_connected"] = connected

            node_info["outputs"].append(output_info)

        # 如果是节点组，递归解析其内容
        if node.type == 'GROUP' and node.node_tree:
            node_info["group_content"] = parse_node_tree_recursive(node.node_tree)

        result["selected_nodes"].append(node_info)

    # 添加连接信息
    if hasattr(node_tree, 'links'):
        connections = []
        for link in node_tree.links:
            if link.from_node in selected_nodes or link.to_node in selected_nodes:
                connection_info = {
                    "from_node": link.from_node.name,
                    "from_socket": link.from_socket.name,
                    "to_node": link.to_node.name,
                    "to_socket": link.to_socket.name,
                }
                connections.append(connection_info)
        result["connections"] = connections

    return json.dumps(result, indent=2)

# 实现AI分析运算符
class NODE_OT_analyze_with_ai(Operator):
    bl_idname = "node.analyze_with_ai"
    bl_label = "Analyze Selected Nodes with AI"
    bl_description = "Send selected nodes to AI for analysis"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 直接在主线程中执行，获取当前节点信息
        # 首先检查当前上下文是否有有效的节点编辑器
        if not context.space_data or not hasattr(context.space_data, 'node_tree') or not context.space_data.node_tree:
            self.report({'ERROR'}, "No active node tree found")
            return {'CANCELLED'}

        # 检查是否选择了节点
        # 尝试多种方式获取选中的节点
        selected_nodes = []

        # 方法1: 检查 context.selected_nodes
        if hasattr(context, 'selected_nodes'):
            selected_nodes = list(context.selected_nodes)

        # 如果没有选中的节点，使用活动节点
        if not selected_nodes and hasattr(context, 'active_node') and context.active_node:
            selected_nodes = [context.active_node]

        # 如果还是没有，尝试从当前节点树获取
        if not selected_nodes:
            node_tree = context.space_data.node_tree
            for node in node_tree.nodes:
                if getattr(node, 'select', False):  # 使用getattr确保属性存在
                    selected_nodes.append(node)

        if not selected_nodes:
            self.report({'ERROR'}, "No nodes selected to analyze")
            return {'CANCELLED'}

        # 在后台线程中运行，以避免阻塞UI
        import threading
        # 保存当前的上下文信息
        self.current_space_data = context.space_data
        self.selected_nodes = selected_nodes
        self.active_node = selected_nodes[0] if selected_nodes else None
        thread = threading.Thread(target=self.run_analysis)
        thread.start()
        self.report({'INFO'}, "Starting AI analysis in background...")
        return {'FINISHED'}

    def run_analysis(self):
        """在后台线程中运行AI分析"""
        import bpy
        try:
            # 首先检查当前上下文是否有有效的节点编辑器
            if not self.current_space_data or not hasattr(self.current_space_data, 'node_tree') or not self.current_space_data.node_tree:
                self.report({'ERROR'}, "No active node tree found")
                return {'CANCELLED'}

            # 使用保存的节点信息
            selected_nodes = self.selected_nodes

            if not selected_nodes:
                self.report({'ERROR'}, "No nodes selected to analyze")
                return {'CANCELLED'}

            # 获取节点描述
            # 由于在后台线程中，我们不能直接使用context，需要使用当前空间数据
            # 创建一个简化上下文用于节点描述函数
            fake_context = type('FakeContext', (), {
                'space_data': self.current_space_data,
                'selected_nodes': selected_nodes,
                'active_node': self.active_node
            })()

            node_description = get_selected_nodes_description(fake_context)

            # 创建AI分析请求
            ain_settings = bpy.context.scene.ainode_analyzer_settings

            # 创建文本块以显示结果
            text_block_name = "AINodeAnalysisResult"
            if text_block_name in bpy.data.texts:
                text_block = bpy.data.texts[text_block_name]
                text_block.clear()
            else:
                text_block = bpy.data.texts.new(name=text_block_name)

            text_block.write(f"AI Node Analysis Result\n")
            text_block.write(f"Generated on: {bpy.app.version_string}\n")
            text_block.write("="*50 + "\n\n")
            text_block.write("Node structure:\n")
            text_block.write(node_description)

            # 根据AI提供商显示相关信息
            text_block.write(f"\n\nAI Provider: {ain_settings.ai_provider}\n")
            if ain_settings.ai_provider == 'DEEPSEEK':
                text_block.write(f"Model: {ain_settings.deepseek_model}\n")
            elif ain_settings.ai_provider == 'OLLAMA':
                text_block.write(f"Model: {ain_settings.ollama_model}\n")
                text_block.write(f"URL: {ain_settings.ollama_url}\n")

            # 生成分析结果
            analysis_result = self.perform_analysis(node_description, ain_settings)
            if analysis_result:
                text_block.write(f"\n\nAnalysis Result:\n")
                text_block.write(analysis_result)
                self.report({'INFO'}, f"Node analysis complete. See '{text_block_name}' text block for results.")
            else:
                text_block.write(f"\n\nNo analysis result (API key may be missing or API is not implemented yet)\n")
                self.report({'WARNING'}, f"Node structure shown. See '{text_block_name}' text block for results.")

        except Exception as e:
            self.report({'ERROR'}, f"Error during AI analysis: {str(e)}")

    def perform_analysis(self, node_description, settings):
        """执行AI分析"""
        try:
            # 根据AI提供商调用相应的API
            if settings.ai_provider == 'DEEPSEEK':
                return self.call_deepseek_api(node_description, settings)
            elif settings.ai_provider == 'OLLAMA':
                return self.call_ollama_api(node_description, settings)
            else:
                return None
        except Exception as e:
            print(f"Error in perform_analysis: {str(e)}")
            return None

    def call_deepseek_api(self, node_description, settings):
        """调用DeepSeek API"""
        if not settings.deepseek_api_key.strip():
            return "DeepSeek API Key is required."

        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.deepseek_api_key}'
            }

            system_message = settings.system_prompt
            user_message = f"Analyze the following Blender node structure and provide insights, optimizations, or explanations:\n\n{node_description}"

            data = {
                "model": settings.deepseek_model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }

            import requests
            response = requests.post(
                'https://api.deepseek.com/chat/completions',
                headers=headers,
                json=data,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0]['message']['content']
                else:
                    return f"Unexpected API response format: {result}"
            else:
                return f"DeepSeek API error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error calling DeepSeek API: {str(e)}"

    def call_ollama_api(self, node_description, settings):
        """调用Ollama API"""
        try:
            import requests

            # 构建Ollama API URL
            url = f"{settings.ollama_url}/api/generate"

            system_message = settings.system_prompt
            prompt = f"System: {system_message}\n\nUser: Analyze the following Blender node structure and provide insights, optimizations, or explanations:\n\n{node_description}\n\nAssistant:"

            data = {
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7
                }
            }

            response = requests.post(url, json=data, timeout=60)

            if response.status_code == 200:
                result = response.json()
                if 'response' in result:
                    return result['response']
                else:
                    return f"Unexpected API response format: {result}"
            else:
                return f"Ollama API error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error calling Ollama API: {str(e)}"

# 注册函数
def register():
    # 注册设置属性
    bpy.utils.register_class(AINodeAnalyzerSettings)
    bpy.types.Scene.ainode_analyzer_settings = PointerProperty(type=AINodeAnalyzerSettings)
    
    # 注册偏好设置
    bpy.utils.register_class(AINodeAnalyzerPreferences)
    
    # 注册面板
    bpy.utils.register_class(NODE_PT_ai_analyzer)
    
    # 注册运算符
    bpy.utils.register_class(NODE_OT_analyze_with_ai)


# 注销函数
def unregister():
    # 注销运算符
    bpy.utils.unregister_class(NODE_OT_analyze_with_ai)
    
    # 注销面板
    bpy.utils.unregister_class(NODE_PT_ai_analyzer)
    
    # 注销偏好设置
    bpy.utils.unregister_class(AINodeAnalyzerPreferences)
    
    # 删除设置属性
    del bpy.types.Scene.ainode_analyzer_settings
    bpy.utils.unregister_class(AINodeAnalyzerSettings)


if __name__ == "__main__":
    register()