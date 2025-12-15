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
    bl_label = "AI节点分析器"
    bl_idname = "NODE_PT_ai_analyzer"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AI Node Analyzer"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ain_settings = scene.ainode_analyzer_settings

        # 状态行和设置按钮
        top_row = layout.row()
        top_row.label(text=f"状态: {ain_settings.current_status}")
        top_row.separator()
        top_row.operator("node.settings_popup", text="", icon='PREFERENCES')

        # 分析框架按钮
        row = layout.row()
        row.operator("node.create_analysis_frame", text="确定分析范围")

        # 对话功能
        box = layout.box()
        box.label(text="交互式问答", icon='QUESTION')
        row = box.row(align=True)
        row.prop(ain_settings, "user_input", text="")

        # 第二行：默认、清除、刷新按钮
        row = box.row(align=True)
        row.operator("node.set_default_question", text="默认", icon='FILE_REFRESH')
        row.operator("node.clear_question", text="清除", icon='X')
        row.operator("node.refresh_to_text", text="刷新", icon='FILE_TEXT')

        # 第三行：提问按钮单独一行
        row = box.row()
        row.scale_y = 1.2
        row.operator("node.ask_ai", text="提问", icon='SPEAKER')

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

# 添加对话历史记录属性
class AINodeAnalyzerSettings(PropertyGroup):
    """插件设置属性组"""

    # AI服务商选择
    ai_provider: EnumProperty(
        name="AI服务提供商",
        description="选择AI服务提供商",
        items=[
            ('DEEPSEEK', "DeepSeek", "DeepSeek AI服务"),
            ('OLLAMA', "Ollama", "Ollama本地AI服务"),
        ],
        default='DEEPSEEK'
    )

    # DeepSeek设置
    deepseek_api_key: StringProperty(
        name="DeepSeek API密钥",
        description="DeepSeek API密钥用于模型访问",
        subtype='PASSWORD',
        default=""
    )

    deepseek_model: EnumProperty(
        name="DeepSeek模型",
        description="选择要使用的DeepSeek模型",
        items=[
            ('deepseek-chat', "DeepSeek Chat", "DeepSeek聊天模型"),
            ('deepseek-coder', "DeepSeek Coder", "DeepSeek代码模型"),
        ],
        default='deepseek-chat'
    )

    # Ollama设置
    ollama_url: StringProperty(
        name="Ollama服务地址",
        description="Ollama服务的URL地址",
        default="http://localhost:11434",
        maxlen=2048
    )

    ollama_model: StringProperty(
        name="Ollama模型",
        description="Ollama模型名称 (例如: llama2, mistral)",
        default="llama2",
        maxlen=256
    )

    # 系统提示
    system_prompt: StringProperty(
        name="系统提示",
        description="AI助手的系统提示信息",
        default="您是Blender节点的专家。分析以下节点结构并提供见解、优化或解释。",
        maxlen=2048
    )

    # 联网检索相关设置
    enable_web_search: BoolProperty(
        name="启用网络搜索",
        description="启用网络搜索功能以增强分析",
        default=False
    )

    search_api: EnumProperty(
        name="搜索API",
        description="选择搜索API服务",
        items=[
            ('TAVILY', "Tavily", "Tavily搜索API"),
            ('NONE', "无", "无搜索API"),
        ],
        default='NONE'
    )

    tavily_api_key: StringProperty(
        name="Tavily API密钥",
        description="Tavily搜索API密钥",
        subtype='PASSWORD',
        default=""
    )

    # 新增对话功能相关属性
    conversation_history: StringProperty(
        name="对话历史",
        description="内部存储的对话历史记录",
        default="",
        maxlen=65536  # 增加容量以存储多轮对话
    )

    # 用户输入文本
    user_input: StringProperty(
        name="您的问题",
        description="输入关于节点的问题",
        default="",
        maxlen=2048
    )

    # 显示给AI的提示内容
    preview_content: StringProperty(
        name="预览内容",
        description="将要发送给AI的内容预览",
        default="",
        maxlen=65536
    )

    # 当前状态
    current_status: StringProperty(
        name="当前状态",
        description="插件当前运行状态",
        default="就绪"
    )

    # 默认问题
    default_question: StringProperty(
        name="默认问题",
        description="默认的节点分析问题",
        default="请分析这些节点的功能和优化建议"
    )

    # 分析框架相关 - 记录节点名称
    analysis_frame_node_names: StringProperty(
        name="分析框架节点名称",
        description="记录分析框架中包含的节点名称，用逗号分隔",
        default=""
    )

# 设置弹窗面板
class AINodeAnalyzerSettingsPopup(bpy.types.Operator):
    bl_idname = "node.settings_popup"
    bl_label = "AI节点分析器设置"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=500)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ain_settings = scene.ainode_analyzer_settings

        # 显示当前Blender版本和节点类型
        row = layout.row()
        row.label(text=f"Blender版本: {bpy.app.version_string}")

        # 确定当前节点类型
        node_type = "未知"
        if context.space_data and hasattr(context.space_data, 'tree_type'):
            tree_type = context.space_data.tree_type
            if tree_type == 'GeometryNodeTree':
                node_type = "几何节点"
            elif tree_type == 'ShaderNodeTree':
                node_type = "材质节点"
            elif tree_type == 'CompositorNodeTree':
                node_type = "合成节点"
            elif tree_type == 'TextureNodeTree':
                node_type = "纹理节点"
            elif tree_type == 'WorldNodeTree':
                node_type = "环境节点"

        row = layout.row()
        row.label(text=f"当前节点类型: {node_type}")

        # AI服务提供商设置
        box = layout.box()
        box.label(text="AI服务提供商设置", icon='WORLD_DATA')
        box.prop(ain_settings, "ai_provider")

        if ain_settings.ai_provider == 'DEEPSEEK':
            box.prop(ain_settings, "deepseek_api_key")
            box.prop(ain_settings, "deepseek_model")
        elif ain_settings.ai_provider == 'OLLAMA':
            box.prop(ain_settings, "ollama_url")
            box.prop(ain_settings, "ollama_model")

        # 系统提示
        box = layout.box()
        box.label(text="系统提示", icon='WORDWRAP_ON')
        box.prop(ain_settings, "system_prompt", text="")

        # 联网检索设置
        box = layout.box()
        box.label(text="网络搜索设置", icon='URL')
        box.prop(ain_settings, "enable_web_search")
        if ain_settings.enable_web_search:
            box.prop(ain_settings, "search_api")

            if ain_settings.search_api == 'TAVILY':
                box.prop(ain_settings, "tavily_api_key")

        # 交互式问答设置
        box = layout.box()
        box.label(text="交互式问答设置", icon='QUESTION')
        box.prop(ain_settings, "default_question", text="默认问题")

        # 重置按钮
        row = layout.row()
        row.operator("node.reset_settings", text="重置为默认设置", icon='LOOP_BACK')

# 重置设置运算符
class NODE_OT_reset_settings(bpy.types.Operator):
    bl_idname = "node.reset_settings"
    bl_label = "重置设置"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings

        # 重置所有设置为默认值
        ain_settings.ai_provider = 'DEEPSEEK'
        ain_settings.deepseek_api_key = ""
        ain_settings.deepseek_model = 'deepseek-chat'
        ain_settings.ollama_url = "http://localhost:11434"
        ain_settings.ollama_model = "llama2"
        ain_settings.system_prompt = "您是Blender节点的专家。分析以下节点结构并提供见解、优化或解释。"
        ain_settings.enable_web_search = False
        ain_settings.search_api = 'NONE'
        ain_settings.tavily_api_key = ""
        ain_settings.user_input = ""
        ain_settings.default_question = "请分析这些节点的功能和优化建议"

        self.report({'INFO'}, "设置已重置为默认值")
        return {'FINISHED'}

# 设置默认问题运算符
class NODE_OT_set_default_question(bpy.types.Operator):
    bl_idname = "node.set_default_question"
    bl_label = "设置默认问题"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        ain_settings.user_input = ain_settings.default_question
        self.report({'INFO'}, "已设置默认问题")
        return {'FINISHED'}

# 清除问题运算符
class NODE_OT_clear_question(bpy.types.Operator):
    bl_idname = "node.clear_question"
    bl_label = "清除问题"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        ain_settings.user_input = ""
        self.report({'INFO'}, "问题已清除")
        return {'FINISHED'}

# 创建分析框架运算符
class NODE_OT_create_analysis_frame(bpy.types.Operator):
    bl_idname = "node.create_analysis_frame"
    bl_label = "创建分析框架"
    bl_description = "将选中的节点加入框架以便确定分析范围"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        # 首先检查当前上下文是否有有效的节点编辑器
        if not context.space_data or not hasattr(context.space_data, 'node_tree') or not context.space_data.node_tree:
            self.report({'ERROR'}, "未找到活动的节点树")
            return {'CANCELLED'}

        node_tree = context.space_data.node_tree

        # 检查是否已经有框架节点
        frame_node = None
        for node in node_tree.nodes:
            if node.type == 'FRAME' and node.label == "将要分析":
                frame_node = node
                break

        if frame_node:
            # 如果已经存在框架，则移除它并记录节点名称
            # 记录框架中的节点名称
            node_names = []
            nodes_in_frame = []
            for node in node_tree.nodes:
                if node.parent == frame_node:
                    node_names.append(node.name)
                    nodes_in_frame.append(node)
                    node.parent = None  # 将节点从框架中移出
            ain_settings.analysis_frame_node_names = ','.join(node_names)
            node_tree.nodes.remove(frame_node)

            # 选择从框架中移出的节点
            for node in node_tree.nodes:
                node.select = False  # 先取消所有选择
            for node in nodes_in_frame:
                node.select = True  # 选择刚从框架中移出的节点

            self.report({'INFO'}, "已移除分析框架")
        else:
            # 如果不存在框架，优先使用当前选中的节点，如果当前没有选择节点才恢复之前的节点
            selected_nodes = []

            # 检查当前是否选择了节点
            current_selected = []
            # 检查 context.selected_nodes
            if hasattr(context, 'selected_nodes'):
                current_selected = list(context.selected_nodes)

            # 如果没有选中的节点，使用活动节点
            if not current_selected and hasattr(context, 'active_node') and context.active_node:
                current_selected = [context.active_node]

            # 如果还是没有，尝试从当前节点树获取
            if not current_selected:
                for node in node_tree.nodes:
                    if getattr(node, 'select', False):  # 使用getattr确保属性存在
                        current_selected.append(node)

            if current_selected:
                # 如果当前有选中的节点，使用当前选中的节点
                selected_nodes = current_selected
            elif ain_settings.analysis_frame_node_names:
                # 只有在当前没有选中节点时才恢复之前的节点
                node_names = ain_settings.analysis_frame_node_names.split(',')
                for node_name in node_names:
                    if node_name in node_tree.nodes:
                        selected_nodes.append(node_tree.nodes[node_name])
            else:
                self.report({'WARNING'}, "没有选择要分析的节点")
                return {'CANCELLED'}

            # 将节点名称记录到设置中（更新为当前实际使用的节点）
            node_names = [node.name for node in selected_nodes]
            ain_settings.analysis_frame_node_names = ','.join(node_names)

            # 创建框架并加入选中的节点
            try:
                # 选择要加入框架的节点
                for node in node_tree.nodes:
                    node.select = False  # 先取消所有选择
                for node in selected_nodes:
                    node.select = True  # 选择指定节点

                # 使用join操作将选中的节点加入框架
                bpy.ops.node.join()  # 这会将选中的节点加入到一个框架中

                # 确保新创建的框架被找到并设置标签
                frame_found = None
                for node in node_tree.nodes:
                    if node.type == 'FRAME' and node.select:
                        node.label = "将要分析"
                        frame_found = node
                        break

                # 框架创建后，重新选择框架内的节点
                for node in node_tree.nodes:
                    node.select = False  # 先取消所有选择
                for node in selected_nodes:
                    node.select = True  # 重新选择原始节点
                if frame_found:
                    frame_found.select = False  # 不选择框架本身，只选择内部的节点

                self.report({'INFO'}, f"已将 {len(selected_nodes)} 个节点加入分析框架")
            except Exception as e:
                # 如果join操作失败，手动创建框架
                frame_node = node_tree.nodes.new(type='NodeFrame')
                frame_node.label = "将要分析"
                # 设置框架位置和大小
                min_x = min([node.location.x for node in selected_nodes])
                max_x = max([node.location.x + node.width for node in selected_nodes])
                min_y = min([node.location.y - node.height for node in selected_nodes])
                max_y = max([node.location.y for node in selected_nodes])

                frame_node.location = (min_x - 20, max_y + 20)
                frame_node.width = max_x - min_x + 40
                frame_node.height = max_y - min_y + 40

                # 将选中节点移到框架内
                for node in selected_nodes:
                    node.parent = frame_node

                # 重新选择节点（因为创建框架后，节点仍然被选中）
                for node in node_tree.nodes:
                    node.select = False  # 先取消所有选择
                for node in selected_nodes:
                    node.select = True  # 选择这些节点

                print(f"Error during join operation: {e}")  # 输出错误信息用于调试

                self.report({'INFO'}, f"已将 {len(selected_nodes)} 个节点加入分析框架")

        return {'FINISHED'}

# 刷新内容到文本编辑器运算符
class NODE_OT_refresh_to_text(bpy.types.Operator):
    bl_idname = "node.refresh_to_text"
    bl_label = "刷新到文本编辑器"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings

        # 检查当前上下文是否有有效的节点编辑器
        if not context.space_data or not hasattr(context.space_data, 'node_tree') or not context.space_data.node_tree:
            self.report({'ERROR'}, "未找到活动的节点树")
            return {'CANCELLED'}

        # 检查是否选择了节点
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
            # 如果没有选中节点，但有用户问题，也允许刷新
            if not ain_settings.user_input:
                self.report({'WARNING'}, "没有选择要分析的节点，也没有输入问题")
                return {'CANCELLED'}

        # 创建或更新文本块以显示完整内容
        text_block_name = "AINodeRefreshContent"
        if text_block_name in bpy.data.texts:
            text_block = bpy.data.texts[text_block_name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(name=text_block_name)

        # 获取当前节点类型
        node_type = "未知"
        if context.space_data and hasattr(context.space_data, 'tree_type'):
            tree_type = context.space_data.tree_type
            if tree_type == 'GeometryNodeTree':
                node_type = "几何节点"
            elif tree_type == 'ShaderNodeTree':
                node_type = "材质节点"
            elif tree_type == 'CompositorNodeTree':
                node_type = "合成节点"
            elif tree_type == 'TextureNodeTree':
                node_type = "纹理节点"
            elif tree_type == 'WorldNodeTree':
                node_type = "环境节点"

        # 写入内容
        text_block.write(f"AI节点分析器刷新内容\n")
        text_block.write(f"Blender版本: {bpy.app.version_string}\n")
        text_block.write(f"当前节点类型: {node_type}\n")
        text_block.write(f"选中节点数量: {len(selected_nodes)}\n")
        text_block.write("="*50 + "\n\n")

        # 获取当前选中节点的描述（直接从当前上下文获取，而不是使用预览内容）
        if selected_nodes:
            fake_context = type('FakeContext', (), {
                'space_data': context.space_data,
                'selected_nodes': selected_nodes,
                'active_node': selected_nodes[0] if selected_nodes else None
            })()

            node_description = get_selected_nodes_description(fake_context)
            text_block.write("当前选中节点信息:\n")
            text_block.write(node_description)
            text_block.write("\n\n")

        # 写入当前设置信息
        text_block.write("当前设置:\n")
        text_block.write(f"AI服务提供商: {ain_settings.ai_provider}\n")
        if ain_settings.ai_provider == 'DEEPSEEK':
            text_block.write(f"DeepSeek模型: {ain_settings.deepseek_model}\n")
        elif ain_settings.ai_provider == 'OLLAMA':
            text_block.write(f"Ollama模型: {ain_settings.ollama_model}\n")
            text_block.write(f"Ollama地址: {ain_settings.ollama_url}\n")

        text_block.write(f"系统提示: {ain_settings.system_prompt}\n")
        text_block.write(f"用户问题: {ain_settings.user_input}\n")

        self.report({'INFO'}, f"内容已刷新到文本块 '{text_block_name}'")
        return {'FINISHED'}

# 显示完整预览内容运算符
class NODE_OT_show_full_preview(bpy.types.Operator):
    bl_idname = "node.show_full_preview"
    bl_label = "在文本编辑器中显示完整预览"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings

        if ain_settings.preview_content:
            # 创建或更新文本块以显示完整预览
            text_block_name = "AINodeFullPreview"
            if text_block_name in bpy.data.texts:
                text_block = bpy.data.texts[text_block_name]
                text_block.clear()
            else:
                text_block = bpy.data.texts.new(name=text_block_name)

            # 获取当前节点类型和Blender版本
            node_type = "未知"
            if context.space_data and hasattr(context.space_data, 'tree_type'):
                tree_type = context.space_data.tree_type
                if tree_type == 'GeometryNodeTree':
                    node_type = "几何节点"
                elif tree_type == 'ShaderNodeTree':
                    node_type = "材质节点"
                elif tree_type == 'CompositorNodeTree':
                    node_type = "合成节点"
                elif tree_type == 'TextureNodeTree':
                    node_type = "纹理节点"
                elif tree_type == 'WorldNodeTree':
                    node_type = "环境节点"

            text_block.write(f"AI节点分析器完整内容预览\n")
            text_block.write(f"Blender版本: {bpy.app.version_string}\n")
            text_block.write(f"当前节点类型: {node_type}\n")
            text_block.write("="*50 + "\n\n")
            text_block.write(ain_settings.preview_content)

            self.report({'INFO'}, f"完整预览已保存到文本块 '{text_block_name}'")
        else:
            self.report({'WARNING'}, "没有预览内容可显示")

        return {'FINISHED'}

# AI分析基类
class AIBaseOperator:
    """AI分析基类，包含通用的API调用方法"""

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
            return "DeepSeek API Key是必需的。"

        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.deepseek_api_key}'
            }

            system_message = settings.system_prompt
            user_message = f"分析以下Blender节点结构并提供见解、优化或解释:\n\n{node_description}"

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
                    return f"意外的API响应格式: {result}"
            else:
                return f"DeepSeek API错误: {response.status_code} - {response.text}"
        except Exception as e:
            return f"调用DeepSeek API时出错: {str(e)}"

    def call_ollama_api(self, node_description, settings):
        """调用Ollama API"""
        try:
            import requests

            # 构建Ollama API URL
            url = f"{settings.ollama_url}/api/generate"

            system_message = settings.system_prompt
            prompt = f"System: {system_message}\n\nUser: 分析以下Blender节点结构并提供见解、优化或解释:\n\n{node_description}\n\nAssistant:"

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
                    return f"意外的API响应格式: {result}"
            else:
                return f"Ollama API错误: {response.status_code} - {response.text}"
        except Exception as e:
            return f"调用Ollama API时出错: {str(e)}"

# 实现AI分析运算符
class NODE_OT_analyze_with_ai(AIBaseOperator, Operator):
    bl_idname = "node.analyze_with_ai"
    bl_label = "使用AI分析选中的节点"
    bl_description = "将选中的节点发送给AI进行分析"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings

        # 更新状态
        ain_settings.current_status = "正在分析节点..."

        # 直接在主线程中执行，获取当前节点信息
        # 首先检查当前上下文是否有有效的节点编辑器
        if not context.space_data or not hasattr(context.space_data, 'node_tree') or not context.space_data.node_tree:
            self.report({'ERROR'}, "未找到活动的节点树")
            ain_settings.current_status = "错误：未找到活动的节点树"
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
            self.report({'ERROR'}, "没有选择要分析的节点")
            ain_settings.current_status = "错误：没有选择要分析的节点"
            return {'CANCELLED'}

        # 创建预览内容（实时创建最新的节点信息）
        fake_context = type('FakeContext', (), {
            'space_data': context.space_data,
            'selected_nodes': selected_nodes,
            'active_node': selected_nodes[0] if selected_nodes else None
        })()

        node_description = get_selected_nodes_description(fake_context)
        preview_content = f"节点结构:\n{node_description}\n\n系统提示: {ain_settings.system_prompt}"
        ain_settings.preview_content = preview_content  # 更新预览内容

        # 在后台线程中运行，以避免阻塞UI
        import threading
        # 保存当前的上下文信息
        self.current_space_data = context.space_data
        self.selected_nodes = selected_nodes
        self.active_node = selected_nodes[0] if selected_nodes else None
        thread = threading.Thread(target=self.run_analysis)
        thread.start()
        return {'FINISHED'}

    def run_analysis(self):
        """在后台线程中运行AI分析"""
        import bpy
        try:
            # 首先检查当前上下文是否有有效的节点编辑器
            if not self.current_space_data or not hasattr(self.current_space_data, 'node_tree') or not self.current_space_data.node_tree:
                self.report({'ERROR'}, "未找到活动的节点树")
                ain_settings = bpy.context.scene.ainode_analyzer_settings
                ain_settings.current_status = "错误：未找到活动的节点树"
                return {'CANCELLED'}

            # 使用保存的节点信息
            selected_nodes = self.selected_nodes

            if not selected_nodes:
                self.report({'ERROR'}, "没有选择要分析的节点")
                ain_settings = bpy.context.scene.ainode_analyzer_settings
                ain_settings.current_status = "错误：没有选择要分析的节点"
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

            # 确定当前节点类型
            node_type = "未知"
            tree_type = self.current_space_data.tree_type
            if tree_type == 'GeometryNodeTree':
                node_type = "几何节点"
            elif tree_type == 'ShaderNodeTree':
                node_type = "材质节点"
            elif tree_type == 'CompositorNodeTree':
                node_type = "合成节点"
            elif tree_type == 'TextureNodeTree':
                node_type = "纹理节点"
            elif tree_type == 'WorldNodeTree':
                node_type = "环境节点"

            text_block.write(f"AI节点分析结果\n")
            text_block.write(f"Blender版本: {bpy.app.version_string}\n")
            text_block.write(f"节点类型: {node_type}\n")
            text_block.write("="*50 + "\n\n")
            text_block.write("节点结构:\n")
            text_block.write(node_description)

            # 根据AI提供商显示相关信息
            text_block.write(f"\n\nAI服务提供商: {ain_settings.ai_provider}\n")
            if ain_settings.ai_provider == 'DEEPSEEK':
                text_block.write(f"模型: {ain_settings.deepseek_model}\n")
            elif ain_settings.ai_provider == 'OLLAMA':
                text_block.write(f"模型: {ain_settings.ollama_model}\n")
                text_block.write(f"地址: {ain_settings.ollama_url}\n")

            # 生成分析结果
            analysis_result = self.perform_analysis(node_description, ain_settings)
            if analysis_result:
                text_block.write(f"\n\n分析结果:\n")
                text_block.write(analysis_result)
                ain_settings.current_status = "完成"
                self.report({'INFO'}, f"节点分析完成。请在'{text_block_name}'文本块中查看结果。")
            else:
                text_block.write(f"\n\n没有分析结果 (可能API密钥缺失或API未实现)\n")
                ain_settings.current_status = "完成（无结果）"
                self.report({'WARNING'}, f"节点结构已显示。请在'{text_block_name}'文本块中查看结果。")

        except Exception as e:
            self.report({'ERROR'}, f"AI分析过程中出现错误: {str(e)}")
            ain_settings = bpy.context.scene.ainode_analyzer_settings
            ain_settings.current_status = f"错误: {str(e)}"

# 新增对话功能运算符
class NODE_OT_ask_ai(AIBaseOperator, Operator):
    bl_idname = "node.ask_ai"
    bl_label = "向AI询问节点问题"
    bl_description = "关于选中节点提出具体问题"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        user_question = ain_settings.user_input.strip()

        if not user_question:
            self.report({'WARNING'}, "请输入问题")
            return {'CANCELLED'}

        # 更新状态
        ain_settings.current_status = "正在向AI提问..."

        # 直接在主线程中执行，获取当前节点信息
        # 首先检查当前上下文是否有有效的节点编辑器
        if not context.space_data or not hasattr(context.space_data, 'node_tree') or not context.space_data.node_tree:
            self.report({'ERROR'}, "未找到活动的节点树")
            ain_settings.current_status = "错误：未找到活动的节点树"
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
            self.report({'ERROR'}, "没有选择要分析的节点")
            ain_settings.current_status = "错误：没有选择要分析的节点"
            return {'CANCELLED'}

        # 创建预览内容（实时创建最新的节点信息）
        fake_context = type('FakeContext', (), {
            'space_data': context.space_data,
            'selected_nodes': selected_nodes,
            'active_node': selected_nodes[0] if selected_nodes else None
        })()

        node_description = get_selected_nodes_description(fake_context)
        preview_content = f"节点结构:\n{node_description}\n\n问题: {user_question}\n\n系统提示: {ain_settings.system_prompt}"
        ain_settings.preview_content = preview_content  # 更新预览内容

        # 在后台线程中运行，以避免阻塞UI
        import threading
        # 保存当前的上下文信息
        self.current_space_data = context.space_data
        self.selected_nodes = selected_nodes
        self.active_node = selected_nodes[0] if selected_nodes else None
        self.user_question = user_question
        thread = threading.Thread(target=self.run_ask_analysis)
        thread.start()
        return {'FINISHED'}

    def run_ask_analysis(self):
        """在后台线程中运行AI问答"""
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

            # 在问题中包含节点描述
            full_question = f"Node structure:\n{node_description}\n\nQuestion: {self.user_question}"

            # 生成分析结果
            analysis_result = self.perform_analysis(full_question, ain_settings)
            if analysis_result:
                # 创建文本块以显示结果
                text_block_name = "AINodeAnalysisResult"
                if text_block_name in bpy.data.texts:
                    text_block = bpy.data.texts[text_block_name]
                else:
                    text_block = bpy.data.texts.new(name=text_block_name)

                # 添加问答记录到文本块
                text_block.write(f"\n\n{'='*50}\n")
                text_block.write(f"Question: {self.user_question}\n")
                text_block.write(f"Answer: {analysis_result}\n")
                text_block.write(f"Asked on: {bpy.app.version_string}\n")

                self.report({'INFO'}, f"Question answered. See '{text_block_name}' text block for details.")
            else:
                self.report({'WARNING'}, "未收到AI的回复")

        except Exception as e:
            self.report({'ERROR'}, f"AI分析过程中出现错误: {str(e)}")
            ain_settings = bpy.context.scene.ainode_analyzer_settings
            ain_settings.current_status = f"错误: {str(e)}"

    def run_ask_analysis(self):
        """在后台线程中运行AI问答"""
        import bpy
        try:
            # 首先检查当前上下文是否有有效的节点编辑器
            if not self.current_space_data or not hasattr(self.current_space_data, 'node_tree') or not self.current_space_data.node_tree:
                self.report({'ERROR'}, "未找到活动的节点树")
                ain_settings = bpy.context.scene.ainode_analyzer_settings
                ain_settings.current_status = "错误：未找到活动的节点树"
                return {'CANCELLED'}

            # 使用保存的节点信息
            selected_nodes = self.selected_nodes

            if not selected_nodes:
                self.report({'ERROR'}, "没有选择要分析的节点")
                ain_settings = bpy.context.scene.ainode_analyzer_settings
                ain_settings.current_status = "错误：没有选择要分析的节点"
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

            # 在问题中包含节点描述
            full_question = f"节点结构:\n{node_description}\n\n问题: {self.user_question}"

            # 生成分析结果
            analysis_result = self.perform_analysis(full_question, ain_settings)
            if analysis_result:
                # 创建文本块以显示结果
                text_block_name = "AINodeAnalysisResult"
                if text_block_name in bpy.data.texts:
                    text_block = bpy.data.texts[text_block_name]
                else:
                    text_block = bpy.data.texts.new(name=text_block_name)

                # 获取当前节点类型
                node_type = "未知"
                tree_type = self.current_space_data.tree_type
                if tree_type == 'GeometryNodeTree':
                    node_type = "几何节点"
                elif tree_type == 'ShaderNodeTree':
                    node_type = "材质节点"
                elif tree_type == 'CompositorNodeTree':
                    node_type = "合成节点"
                elif tree_type == 'TextureNodeTree':
                    node_type = "纹理节点"
                elif tree_type == 'WorldNodeTree':
                    node_type = "环境节点"

                # 添加问答记录到文本块
                text_block.write(f"\n\n{'='*50}\n")
                text_block.write(f"节点类型: {node_type}\n")
                text_block.write(f"提问: {self.user_question}\n")
                text_block.write(f"回答: {analysis_result}\n")
                text_block.write(f"提问时间: {bpy.app.version_string}\n")

                ain_settings.current_status = "完成"
                self.report({'INFO'}, f"问题已回答。请在'{text_block_name}'文本块中查看详细信息。")
            else:
                ain_settings.current_status = "完成（无结果）"
                self.report({'WARNING'}, "未收到AI的回复")

        except Exception as e:
            self.report({'ERROR'}, f"AI分析过程中出现错误: {str(e)}")
            ain_settings = bpy.context.scene.ainode_analyzer_settings
            ain_settings.current_status = f"错误: {str(e)}"

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
    bpy.utils.register_class(NODE_OT_ask_ai)
    bpy.utils.register_class(AINodeAnalyzerSettingsPopup)
    bpy.utils.register_class(NODE_OT_reset_settings)
    bpy.utils.register_class(NODE_OT_show_full_preview)
    bpy.utils.register_class(NODE_OT_set_default_question)
    bpy.utils.register_class(NODE_OT_clear_question)
    bpy.utils.register_class(NODE_OT_refresh_to_text)
    bpy.utils.register_class(NODE_OT_create_analysis_frame)


# 注销函数
def unregister():
    # 注销运算符
    bpy.utils.unregister_class(NODE_OT_create_analysis_frame)
    bpy.utils.unregister_class(NODE_OT_refresh_to_text)
    bpy.utils.unregister_class(NODE_OT_clear_question)
    bpy.utils.unregister_class(NODE_OT_set_default_question)
    bpy.utils.unregister_class(NODE_OT_show_full_preview)
    bpy.utils.unregister_class(NODE_OT_reset_settings)
    bpy.utils.unregister_class(AINodeAnalyzerSettingsPopup)
    bpy.utils.unregister_class(NODE_OT_ask_ai)
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