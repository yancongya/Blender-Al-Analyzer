"""
AI Node Analyzer Blender Add-on

This addon allows users to analyze selected nodes in Blender's node editors
(Geometry Nodes, Shader Nodes, Compositor Nodes) with AI assistance.
It also includes a backend server to enable communication with external applications.
"""
import bpy
import bmesh
import threading
import json
import requests
import socket
import time
import traceback
import io
from contextlib import redirect_stdout
from bpy.app.translations import pgettext_iface
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
import sys
from urllib.parse import urlparse

# 动态导入后端服务器
server_manager = None

system_message_presets_cache = []
default_question_presets_cache = []
provider_configs_cache = {}

def get_output_detail_instruction(settings):
    try:
        lvl = getattr(settings, 'output_detail_level', 'medium')
        if lvl == 'simple':
            return getattr(settings, 'prompt_simple', '') or ''
        if lvl == 'medium':
            return getattr(settings, 'prompt_medium', '') or ''
        if lvl == 'detailed':
            return getattr(settings, 'prompt_detailed', '') or ''
        return ''
    except Exception:
        return ''

def clean_markdown(text):
    try:
        import re
        s = text
        s = s.replace('\r\n', '\n').replace('\r', '\n')
        s = re.sub(r'[ \t]+\n', '\n', s)          # 行尾空白
        s = re.sub(r'\n{3,}', '\n\n', s)          # 过多空行
        s = re.sub(r'^[ \t]+', '', s, flags=re.MULTILINE)  # 行首空白
        s = re.sub(r'```+\s*', '```', s)          # 多余反引号
        s = re.sub(r'(#){2,}\s*', r'## ', s)      # 多级标题规范化为二级
        return s
    except Exception:
        return text

def get_text_items(self, context):
    try:
        import bpy
        items = []
        names = [t.name for t in bpy.data.texts]
        for n in names:
            items.append((n, n, n))
        if not items:
            items = [('AINodeAnalysisResult', 'AINodeAnalysisResult', 'AINodeAnalysisResult')]
        return items
    except Exception:
        return [('AINodeAnalysisResult', 'AINodeAnalysisResult', 'AINodeAnalysisResult')]

def get_identity_items(self, context):
    items = []
    for idx, it in enumerate(system_message_presets_cache):
        label = it.get('label', f'Preset {idx+1}')
        key = f"preset_{idx}"
        items.append((key, label, label))
    if not items:
        items = [('default', "默认助手", "默认助手")]
    return items

def get_provider_items(self, context):
    items = []
    if isinstance(provider_configs_cache, dict) and provider_configs_cache:
        for k in provider_configs_cache.keys():
            items.append((k, k.title(), k))
    if not items:
        items = [('DEEPSEEK', "DeepSeek", "DeepSeek"), ('OLLAMA', "Ollama", "Ollama")]
    return items

def _on_provider_update(self, context):
    """当AI提供商更改时，更新模型列表"""
    try:
        # 更新当前模型字段
        ain_settings = context.scene.ainode_analyzer_settings
        if ain_settings.ai_provider == 'DEEPSEEK':
            ain_settings.current_model = ain_settings.deepseek_model
            # 更新available_models为当前DeepSeek模型
            ain_settings.available_models = ain_settings.deepseek_model
        elif ain_settings.ai_provider == 'OLLAMA':
            ain_settings.current_model = ain_settings.ollama_model
            # 更新available_models为当前Ollama模型
            ain_settings.available_models = ain_settings.ollama_model
        elif ain_settings.ai_provider == 'BIGMODEL':
            ain_settings.current_model = ain_settings.bigmodel_model
            # 更新available_models为当前BigModel模型
            ain_settings.available_models = ain_settings.bigmodel_model
        else:
            ain_settings.current_model = ain_settings.generic_model
            # 更新available_models为当前Generic模型
            ain_settings.available_models = ain_settings.generic_model

        # 强制刷新模型列表
        if hasattr(bpy.context, 'window_manager'):
            # 触发界面更新
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'NODE_EDITOR':
                        for region in area.regions:
                            if region.type == 'UI':
                                region.tag_redraw()
                                break
                        break
    except Exception as e:
        print(f"更新提供商时出错: {e}")
        pass

def get_default_question_items(self, context):
    items = []
    for idx, it in enumerate(default_question_presets_cache):
        label = it.get('label', f'问题 {idx+1}')
        key = f"q_{idx}"
        items.append((key, label, label))
    if not items:
        items = [('none', "无预设", "无预设")]
    return items

def get_model_items(self, context):
    items = []
    try:
        # 获取所有服务商的模型列表
        all_models = set()  # 使用集合避免重复

        # 添加DeepSeek模型
        for model in deepseek_models_cache:
            all_models.add((model, model, f"DeepSeek: {model}"))

        # 添加Ollama模型
        for model in ollama_models_cache:
            all_models.add((model, model, f"Ollama: {model}"))

        # 添加BigModel模型
        for model in bigmodel_models_cache:
            # 根据模型ID确定分类
            if model.startswith('glm-4.7'):
                category = "GLM-4.7"
            elif model.startswith('glm-4'):
                category = "GLM-4"
            elif model.startswith('glm-3'):
                category = "GLM-3"
            else:
                category = "BigModel"
            all_models.add((model, model, f"{category}: {model}"))

        # 添加通用模型
        for model in generic_models_cache:
            all_models.add((model, model, f"通用: {model}"))

        # 将集合转换为列表并添加到items
        items.extend(list(all_models))

        # 如果没有可用模型，添加当前设置的模型
        if not items:
            current_model = ""
            if self.ai_provider == 'DEEPSEEK':
                current_model = self.deepseek_model
            elif self.ai_provider == 'OLLAMA':
                current_model = self.ollama_model
            elif self.ai_provider == 'BIGMODEL':
                current_model = self.bigmodel_model
            else:
                current_model = self.generic_model
            if current_model:
                items.append((current_model, current_model, current_model))
    except Exception as e:
        # 如果出错，返回空列表
        print(f"获取模型列表时出错: {e}")
        pass

    if not items:
        items = [('未找到模型', "未找到模型", "未找到可用模型")]
    return items

def copy_to_clipboard(text):
    """复制文本到剪贴板"""
    try:
        bpy.context.window_manager.clipboard = text
        return True
    except Exception as e:
        print(f"复制到剪贴板失败: {e}")
        return False

def get_response_detail_items(self, context):
    """获取回答精细度选项，悬浮提示显示实际的prompt内容"""
    items = []

    # 直接使用当前实例的属性值，这些值在加载配置文件时已经被更新
    simple_prompt = getattr(self, 'prompt_simple', '请简要说明，不需要使用markdown格式，简单描述即可。')
    medium_prompt = getattr(self, 'prompt_medium', '请按常规方式回答，使用适当的markdown格式来组织内容。')
    detailed_prompt = getattr(self, 'prompt_detailed', '请详细说明，使用图表、列表、代码块等markdown格式来清晰地表达内容。')

    items.append(('0', "简约", f"简约 - 实际提示: {simple_prompt}"))
    items.append(('1', "适中", f"适中 - 实际提示: {medium_prompt}"))
    items.append(('2', "详细", f"详细 - 实际提示: {detailed_prompt}"))

    return items

def _on_identity_update(self, context):
    try:
        idx = 0
        if self.identity_key.startswith("preset_"):
            idx = int(self.identity_key.split("_")[1])
        if 0 <= idx < len(system_message_presets_cache):
            val = system_message_presets_cache[idx].get('value', '')
            self.identity_text = val
            if val:
                self.system_prompt = val
    except Exception:
        pass

def _on_default_question_preset_update(self, context):
    try:
        idx = -1
        if self.default_question_preset.startswith("q_"):
            idx = int(self.default_question_preset.split("_")[1])
        if 0 <= idx < len(default_question_presets_cache):
            val = default_question_presets_cache[idx].get('value', '')
            if val:
                self.user_input = val
    except Exception:
        pass

def _on_model_change_update(self):
    """
    当模型选择更改时更新对应的模型字段
    """
    try:
        selected_model = self.available_models

        # 检查所选模型是否在当前提供商的模型列表中
        if self.ai_provider == 'DEEPSEEK':
            if selected_model in deepseek_models_cache:
                # 模型属于当前提供商
                self.deepseek_model = selected_model
            else:
                # 检查模型是否属于其他提供商，如果是则更新提供商
                if selected_model in ollama_models_cache:
                    self.ai_provider = 'OLLAMA'
                    self.ollama_model = selected_model
                elif selected_model in bigmodel_models_cache:
                    self.ai_provider = 'BIGMODEL'
                    self.bigmodel_model = selected_model
                elif selected_model in generic_models_cache:
                    # 设置为通用提供商
                    # 注意：这里需要根据实际配置来决定如何处理
                    self.generic_model = selected_model
        elif self.ai_provider == 'OLLAMA':
            if selected_model in ollama_models_cache:
                # 模型属于当前提供商
                self.ollama_model = selected_model
            else:
                # 检查模型是否属于其他提供商
                if selected_model in deepseek_models_cache:
                    self.ai_provider = 'DEEPSEEK'
                    self.deepseek_model = selected_model
                elif selected_model in bigmodel_models_cache:
                    self.ai_provider = 'BIGMODEL'
                    self.bigmodel_model = selected_model
                elif selected_model in generic_models_cache:
                    # 设置为通用提供商
                    self.generic_model = selected_model
        elif self.ai_provider == 'BIGMODEL':
            if selected_model in bigmodel_models_cache:
                # 模型属于当前提供商
                self.bigmodel_model = selected_model
            else:
                # 检查模型是否属于其他提供商
                if selected_model in deepseek_models_cache:
                    self.ai_provider = 'DEEPSEEK'
                    self.deepseek_model = selected_model
                elif selected_model in ollama_models_cache:
                    self.ai_provider = 'OLLAMA'
                    self.ollama_model = selected_model
                elif selected_model in generic_models_cache:
                    # 设置为通用提供商
                    self.generic_model = selected_model
        else:  # generic provider
            if selected_model in generic_models_cache:
                self.generic_model = selected_model
            else:
                # 检查模型是否属于其他提供商
                if selected_model in deepseek_models_cache:
                    self.ai_provider = 'DEEPSEEK'
                    self.deepseek_model = selected_model
                elif selected_model in ollama_models_cache:
                    self.ai_provider = 'OLLAMA'
                    self.ollama_model = selected_model
                elif selected_model in bigmodel_models_cache:
                    self.ai_provider = 'BIGMODEL'
                    self.bigmodel_model = selected_model

        # 同时更新current_model
        self.current_model = selected_model
    except Exception as e:
        print(f"更新模型时出错: {e}")

def get_auto_identity_for_node_type(tree_type):
    """
    根据节点类型获取对应的身份预设
    :param tree_type: 节点树类型 (如 'GeometryNodeTree', 'ShaderNodeTree' 等)
    :return: 对应的身份预设索引，如果没有找到则返回None
    """
    # 定义节点类型到身份关键词的映射
    node_type_keywords = {
        'GeometryNodeTree': ['几何', 'geometry', 'Geometry'],
        'ShaderNodeTree': ['材质', 'shader', 'Shader', '表面', 'Surface'],
        'CompositorNodeTree': ['合成', 'compositor', 'Compositor', 'Composite'],
        'TextureNodeTree': ['纹理', 'texture', 'Texture'],
        'WorldNodeTree': ['环境', 'world', 'World']
    }

    keywords = node_type_keywords.get(tree_type, [])
    if not keywords:
        return None

    # 在系统消息预设中查找包含关键词的预设
    for idx, preset in enumerate(system_message_presets_cache):
        preset_value = preset.get('value', '').lower()
        preset_label = preset.get('label', '').lower()
        # 检查预设值或标签中是否包含关键词
        for keyword in keywords:
            if keyword.lower() in preset_value or keyword.lower() in preset_label:
                return idx

    return None

# 模型列表缓存
deepseek_models_cache = []
ollama_models_cache = []
bigmodel_models_cache = []
generic_models_cache = []


def _on_model_update(self, context):
    try:
        if self.ai_provider == 'DEEPSEEK':
            self.current_model = self.deepseek_model
        elif self.ai_provider == 'OLLAMA':
            self.current_model = self.ollama_model
        elif self.ai_provider == 'BIGMODEL':
            self.current_model = self.bigmodel_model
    except Exception:
        pass

def filter_node_description(text, level):
    try:
        data = json.loads(text)
    except Exception:
        if level == 'ULTRA_LITE':
            return "节点结构已采集"
        elif level == 'LITE' or level == 'STANDARD':
            return text[:1000]
        else:
            return text
    if level == 'FULL':
        return text
    is_selected_shape = 'selected_nodes' in data or 'connections' in data
    def clean_node(node):
        node.pop('location', None)
        node.pop('width', None)
        node.pop('height', None)
        node.pop('color', None)
        node.pop('use_custom_color', None)
        node.pop('select', None)
        if level == 'ULTRA_LITE':
            minimal_name = node.get('name')
            minimal_type = node.get('type')
            node.clear()
            node['name'] = minimal_name
            node['type'] = minimal_type
            return
        if level == 'LITE':
            if isinstance(node.get('inputs'), list):
                for i in node['inputs']:
                    i.pop('identifier', None)
                node['inputs'] = [i for i in node['inputs'] if i.get('is_connected') or (i.get('default_value') is not None and i.get('default_value') != 'N/A')]
            if isinstance(node.get('outputs'), list):
                for o in node['outputs']:
                    o.pop('identifier', None)
        if node.get('group_content') and isinstance(node['group_content'].get('nodes'), list):
            for sub in node['group_content']['nodes']:
                clean_node(sub)
    nodes_array = data.get('selected_nodes') or data.get('nodes')
    if isinstance(nodes_array, list):
        for n in nodes_array:
            clean_node(n)
    if level in ('ULTRA_LITE', 'LITE'):
        for k in ('blender_version', 'addon_version', 'selected_nodes_count', 'node_tree_type'):
            data.pop(k, None)
    filtered_str = json.dumps(data, ensure_ascii=False, indent=2)
    return filtered_str

def initialize_backend():
    """初始化后端服务器"""
    global server_manager
    try:
        # 添加当前插件目录到Python路径
        addon_dir = os.path.dirname(__file__)
        backend_dir = os.path.join(addon_dir, 'backend')

        if backend_dir not in sys.path:
            sys.path.append(backend_dir)

        # 导入后端服务器 - 使用相对导入
        from .backend import server
        server_manager = server.server_manager
        print("后端服务器模块加载成功")
        return True
    except ImportError as e:
        print(f"无法导入后端服务器模块: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"初始化后端服务器时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_to_backend(endpoint, data=None, method='GET'):
    """向后端发送请求"""
    global server_manager
    if not server_manager or not server_manager.is_running:
        print("后端服务器未运行")
        return None

    try:
        import requests

        url = f"http://127.0.0.1:{server_manager.port}{endpoint}"

        if method == 'POST':
            response = requests.post(url, json=data, timeout=5)
        else:
            response = requests.get(url, timeout=5)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"请求失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"发送请求到后端时出错: {e}")
        return None

def push_blender_content_to_server(context=None):
    """将Blender中的节点数据推送到后端服务器（优先推送原始数据，不过滤）"""
    global server_manager
    if not server_manager or not server_manager.is_running:
        print("后端服务器未运行")
        return False

    try:
        # 使用传入的上下文或全局上下文
        ctx = context if context else bpy.context

        # 优先获取00-原始节点数据文本块的内容（不过滤）
        import bpy
        content = ""
        if '00-原始节点数据' in bpy.data.texts:
            text_block = bpy.data.texts['00-原始节点数据']
            content = text_block.as_string()
        elif '04-节点数据' in bpy.data.texts:
            # 兼容：如果没有原始数据，使用过滤后的数据
            text_block = bpy.data.texts['04-节点数据']
            content = text_block.as_string()
        elif 'AINodeRawNodeData' in bpy.data.texts:
            # 兼容旧的文本块名称
            text_block = bpy.data.texts['AINodeRawNodeData']
            content = text_block.as_string()
        elif 'AINodeRefreshContent' in bpy.data.texts:
            text_block = bpy.data.texts['AINodeRefreshContent']
            content = text_block.as_string()
            # 如果是完整消息格式，需要提取JSON
            if "节点结构:" in content:
                json_start = content.find("{", content.find("节点结构:"))
                if json_start != -1:
                    content = content[json_start:].strip()

        if not content:
            print("没有可推送的节点数据")
            return False

        # Get metadata
        filename = bpy.path.basename(bpy.data.filepath) if bpy.data.filepath else "Untitled"
        version = bpy.app.version_string
        
        # Get node type
        node_type = "Node Tree"
        # Try to infer from content header or context
        # Simple heuristic: check context or default
        try:
            if hasattr(ctx, 'space_data') and hasattr(ctx.space_data, 'tree_type'):
                 node_type = ctx.space_data.tree_type
            else:
                # Fallback: check all areas using global context (safest for window iteration)
                wm = getattr(ctx, 'window_manager', bpy.context.window_manager)
                for win in wm.windows:
                    for area in win.screen.areas:
                        if area.type == 'NODE_EDITOR':
                            for space in area.spaces:
                                if space.type == 'NODE_EDITOR' and space.node_tree:
                                    node_type = space.tree_type
                                    break
        except Exception:
            pass
        
        # Beautify node type
        if 'Shader' in node_type: node_type = 'Shader Nodes'
        elif 'Geometry' in node_type: node_type = 'Geometry Nodes'
        elif 'Compositor' in node_type: node_type = 'Compositor Nodes'
        elif 'Texture' in node_type: node_type = 'Texture Nodes'

        # Calculate tokens
        tokens = len(content) // 4

        # Get timestamp safely
        timestamp = 'unknown'
        try:
            if hasattr(ctx, 'view_layer') and ctx.view_layer:
                timestamp = str(ctx.view_layer.name)
        except Exception:
            pass

        # 发送内容到后端
        success = send_to_backend('/api/blender-data', {
            "nodes": content,
            "type": "refresh_content",
            "timestamp": timestamp,
            "filename": filename,
            "version": version,
            "node_type": node_type,
            "tokens": tokens
        }, method='POST')

        if success:
            print("成功推送节点数据到后端服务器")
            return True
        else:
            print("推送内容到后端服务器失败")
            return False
    except Exception as e:
        print(f"推送内容时出错: {e}")
        return False

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

def _save_ai_params_to_config_from_context(context):
    try:
        ain_settings = context.scene.ainode_analyzer_settings
    except Exception:
        if bpy.data.scenes:
            ain_settings = bpy.data.scenes[0].ainode_analyzer_settings
        else:
            return
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    existing_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
        except Exception:
            existing_config = {}
    if 'ai' not in existing_config:
        existing_config['ai'] = {}
    existing_config['ai']['temperature'] = ain_settings.temperature
    existing_config['ai']['top_p'] = ain_settings.top_p
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

def _on_temperature_update(self, context):
    _save_ai_params_to_config_from_context(context)

def _on_top_p_update(self, context):
    _save_ai_params_to_config_from_context(context)

 

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

        # 顶部状态信息行 - 使用更整齐的布局
        top_row = layout.row(align=True)
        node_type_display = "未知"
        current_tree_type = None
        if context.space_data and hasattr(context.space_data, 'tree_type'):
            current_tree_type = context.space_data.tree_type
            if current_tree_type == 'GeometryNodeTree':
                node_type_display = "几何节点"
            elif current_tree_type == 'ShaderNodeTree':
                node_type_display = "材质节点"
            elif current_tree_type == 'CompositorNodeTree':
                node_type_display = "合成节点"
            elif current_tree_type == 'TextureNodeTree':
                node_type_display = "纹理节点"
            elif current_tree_type == 'WorldNodeTree':
                node_type_display = "环境节点"

        # 显示当前节点类型
        top_row.label(text=f"节点: {node_type_display}")

        # 添加一个分隔符，将节点类型与身份预设分开
        top_row.separator(factor=1.0)

        # 将身份设置下拉菜单添加到状态信息行
        top_row.prop(ain_settings, "identity_key", text="", icon='USER')

        # 添加一个分隔符，将身份预设与UI控制按钮分开
        top_row.separator(factor=1.0)

        # 添加简化UI复选按钮
        top_row.prop(ain_settings, "simplified_ui", text="", icon='HIDE_OFF' if ain_settings.simplified_ui else 'HIDE_ON')
        # 添加帮助提示开关
        top_row.prop(ain_settings, "show_help_text", text="", icon='QUESTION' if ain_settings.show_help_text else 'INFO')

        # 添加一个分隔符，将UI控制按钮与操作按钮分开
        top_row.separator(factor=1.0)

        # 操作按钮区域
        top_row.operator("node.load_config_from_file", text="", icon='FILE_REFRESH')
        top_row.operator("node.settings_popup", text="", icon='SETTINGS')

        # 顶部后端服务器行
        backend_box = layout.box()
        backend_box.label(text="后端服务器", icon='WORLD')

        # 服务器控制按钮 - 一行显示三个按钮：[启动/停止] [端口] [网页]
        server_row = backend_box.row(align=True)
        server_row.operator("node.toggle_backend_server", text="", icon='PLAY' if not (server_manager and server_manager.is_running) else 'PAUSE')
        server_row.prop(ain_settings, "backend_port", text="端口")
        server_row.operator("node.open_backend_webpage", text="", icon='URL')


        # 底部交互式文档面板组+提问按钮
        bottom_box = layout.box()

        # 简化模式：只显示问题输入框和提问按钮
        if ain_settings.simplified_ui:
            # 问题输入行 - 包含输入框和右侧的操作按钮
            input_row = bottom_box.row(align=True)
            input_row.prop(ain_settings, "user_input", text="")
            # 在输入框右侧添加清除和刷新按钮
            input_row.operator("node.clear_question", text="", icon='TRASH')
            input_row.operator("node.refresh_to_text", text="", icon='FILE_REFRESH')

            # 提问按钮单独一行，使用更大尺寸，根据状态显示不同按钮
            ask_row = bottom_box.row()
            ask_row.scale_y = 1.5

            # 根据当前状态显示不同的按钮
            if ain_settings.ai_question_status == 'PROCESSING':
                # 显示终止按钮
                ask_row.operator("node.stop_ai_request", text="终止回答", icon='X')
            else:
                # 显示提问按钮
                ask_row.operator("node.ask_ai", text="提问", icon='PLAY')

            # 显示当前状态
            status_text = {
                'IDLE': "就绪",
                'PROCESSING': "正在回答...",
                'STOPPED': "已终止",
                'ERROR': "错误"
            }.get(ain_settings.ai_question_status, "未知状态")

            status_row = bottom_box.row()
            status_row.label(text=f"状态: {status_text}")
        else:
            # 标准模式：显示所有功能
            # 标题行包含标签、分析框架按钮和复合开关
            title_row = bottom_box.row()
            title_row.label(text="交互式问答", icon='QUESTION')
            title_row.operator("node.create_analysis_frame", text="", icon='FRAME_NEXT')  # 使用更合适的图标

            # 问题输入行 - 包含输入框和右侧的操作按钮
            input_row = bottom_box.row(align=True)
            input_row.prop(ain_settings, "user_input", text="")
            # 在输入框右侧添加清除和刷新按钮
            input_row.operator("node.clear_question", text="", icon='TRASH')
            input_row.operator("node.refresh_to_text", text="", icon='FILE_REFRESH')

            # 默认问题下拉菜单 - 移到问题输入行下方
            preset_row = bottom_box.row()
            preset_row.prop(ain_settings, "default_question_preset", text="默认问题")

            # 精度控制行 - 节点精细度和回答精细度放在同一行
            detail_row = bottom_box.row(align=True)
            # 节点精细度
            node_detail_enum = ain_settings.node_detail_level
            node_detail_labels = ["极简", "简化", "常规", "完整"]
            current_node_label = node_detail_labels[node_detail_enum] if 0 <= node_detail_enum < len(node_detail_labels) else "未知"

            # 创建一个包含节点精细度和复制功能的子行
            node_detail_subrow = detail_row.row(align=True)
            node_detail_subrow.prop(ain_settings, "node_detail_level", text=f"节点精细度({current_node_label})")
            # 添加一个按钮用于复制节点信息到剪贴板（普通点击复制选中，Alt+点击复制全部）
            copy_btn = node_detail_subrow.operator("node.copy_nodes_to_clipboard", text="", icon='COPY_ID')

            # 回答精细度
            response_detail_enum = ain_settings.response_detail_level
            response_detail_labels = ["简约", "适中", "详细"]
            current_label = response_detail_labels[response_detail_enum] if 0 <= response_detail_enum < len(response_detail_labels) else "未知"
            # 获取当前级别的实际prompt（使用output_detail_presets变量）
            prompt_texts = [
                ain_settings.prompt_simple,
                ain_settings.prompt_medium,
                ain_settings.prompt_detailed
            ]
            current_prompt = prompt_texts[response_detail_enum] if 0 <= response_detail_enum < len(prompt_texts) else "未设置"
            # 截取提示文本的前10个字符作为补充显示
            preview_text = current_prompt[:10] + "..." if len(current_prompt) > 10 else current_prompt
            detail_row.prop(ain_settings, "response_detail_level", text=f"回答精细度({current_label}) - {preview_text}")

            # 模型选择下拉菜单 - 移动到提问按钮上方
            model_row = bottom_box.row()
            model_row.prop(ain_settings, "available_models", text="模型")

            # 第三行：提问按钮单独一行，根据状态显示不同按钮
            ask_row = bottom_box.row()
            ask_row.scale_y = 1.5

            # 根据当前状态显示不同的按钮
            if ain_settings.ai_question_status == 'PROCESSING':
                # 显示终止按钮
                ask_row.operator("node.stop_ai_request", text="终止回答", icon='X')
            else:
                # 显示提问按钮
                ask_row.operator("node.ask_ai", text="提问", icon='PLAY')

            # 显示当前状态
            status_text = {
                'IDLE': "就绪",
                'PROCESSING': "正在回答...",
                'STOPPED': "已终止",
                'ERROR': "错误"
            }.get(ain_settings.ai_question_status, "未知状态")

            status_row = bottom_box.row()
            status_row.label(text=f"状态: {status_text}")

            # 帮助提示信息 - 可折叠
            if ain_settings.show_help_text:
                help_box = bottom_box.box()
                help_col = help_box.column(align=True)
                help_col.label(text="💡 使用提示:", icon='INFO')
                help_col.label(text="• 选择节点后点击'提问'向AI询问")
                help_col.label(text="• 使用'分析框架'确定分析范围")
                help_col.label(text="• 可通过'简化UI'按钮隐藏非必要元素")

# 快速复制面板
class NODE_PT_quick_copy(Panel):
    bl_label = "快速复制"
    bl_idname = "NODE_PT_quick_copy"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AI Node Analyzer"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        ain_settings = context.scene.ainode_analyzer_settings

        # 显示4个部分的图标+文本按钮 - 平均排布
        # 使用2x2网格布局
        col = layout.column(align=True)
        
        # 检查每个部分是否被选中
        selected_parts = {item.part_name for item in ain_settings.selected_text_parts}
        
        # 第一行：输出详细程度 + 系统提示词
        row1 = col.row(align=True)
        row1.scale_x = 1.0
        row1.scale_y = 1.2
        
        # 输出详细程度提示词
        op1 = row1.operator("node.copy_text_part", text="输出", icon='OUTPUT', depress=('output_detail' in selected_parts))
        op1.part = 'output_detail'
        
        # 系统提示词
        op2 = row1.operator("node.copy_text_part", text="用户", icon='USER', depress=('system_prompt' in selected_parts))
        op2.part = 'system_prompt'
        
        # 第二行：用户问题 + 节点数据
        row2 = col.row(align=True)
        row2.scale_x = 1.0
        row2.scale_y = 1.2
        
        # 用户问题
        op3 = row2.operator("node.copy_text_part", text="问题", icon='QUESTION', depress=('user_question' in selected_parts))
        op3.part = 'user_question'
        
        # 节点数据
        op4 = row2.operator("node.copy_text_part", text="节点", icon='NODETREE', depress=('node_data' in selected_parts))
        op4.part = 'node_data'

        # 复制按钮
        layout.separator()
        copy_row = layout.row()
        copy_row.alignment = 'CENTER'
        copy_row.scale_y = 1.2
        copy_row.operator("node.copy_active_text", text="复制选中部分", icon='COPY_ID')
        
        # 显示当前选中的部分数量
        selected_count = len(ain_settings.selected_text_parts)
        if selected_count > 0:
            layout.separator()
            info_row = layout.row()
            info_row.alignment = 'CENTER'
            info_row.label(text=f"已选中 {selected_count} 个部分")

# MCP 面板
class BLENDERMCP_PT_Panel(bpy.types.Panel):
    bl_label = "AI Node MCP"
    bl_idname = "BLENDERMCP_PT_Panel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AI Node Analyzer"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 服务器控制
        box = layout.box()
        box.label(text="MCP 服务器", icon='PREFERENCES')
        
        row = box.row()
        row.prop(scene, "blendermcp_port")
        
        if not scene.blendermcp_server_running:
            box.operator("blendermcp.start_server", text="启动服务器", icon='PLAY')
        else:
            box.operator("blendermcp.stop_server", text="停止服务器", icon='CANCEL')
            box.label(text=f"运行在端口 {scene.blendermcp_port}", icon='CHECKMARK')
        
        # 可用工具
        box.separator()
        box.label(text="可用工具:", icon='INFO')
        col = box.column(align=True)
        col.label(text="• get_scene_info - 获取场景信息")
        col.label(text="• get_object_info - 获取对象信息")
        col.label(text="• get_viewport_screenshot - 获取视口截图")
        col.label(text="• execute_code - 执行代码")

# MCP 运算符
class BLENDERMCP_OT_StartServer(bpy.types.Operator):
    bl_idname = "blendermcp.start_server"
    bl_label = "启动服务器"
    bl_description = "启动 BlenderMCP 服务器"

    def execute(self, context):
        scene = context.scene

        # Create a new server instance
        if not hasattr(bpy.types, "blendermcp_server") or not bpy.types.blendermcp_server:
            bpy.types.blendermcp_server = BlenderMCPServer(port=scene.blendermcp_port)

        # Start the server
        bpy.types.blendermcp_server.start()
        scene.blendermcp_server_running = True

        return {'FINISHED'}

class BLENDERMCP_OT_StopServer(bpy.types.Operator):
    bl_idname = "blendermcp.stop_server"
    bl_label = "停止服务器"
    bl_description = "停止 BlenderMCP 服务器"

    def execute(self, context):
        scene = context.scene

        # Stop the server if it exists
        if hasattr(bpy.types, "blendermcp_server") and bpy.types.blendermcp_server:
            bpy.types.blendermcp_server.stop()
            del bpy.types.blendermcp_server

        scene.blendermcp_server_running = False

        return {'FINISHED'}

class BLENDERMCP_OT_OpenTerms(bpy.types.Operator):
    bl_idname = "blendermcp.open_terms"
    bl_label = "查看条款和条件"
    bl_description = "打开条款和条件文档"

    def execute(self, context):
        # Open the Terms and Conditions on GitHub
        terms_url = "https://github.com/ahujasid/blender-mcp/blob/main/TERMS_AND_CONDITIONS.md"
        try:
            import webbrowser
            webbrowser.open(terms_url)
            self.report({'INFO'}, "条款和条件已在浏览器中打开")
        except Exception as e:
            self.report({'ERROR'}, f"无法打开条款和条件：{str(e)}")
        
        return {'FINISHED'}

# BlenderMCP Server 类
class BlenderMCPServer:
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.server_thread = None

    def start(self):
        if self.running:
            print("Server is already running")
            return

        self.running = True

        try:
            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)

            # Start server thread
            self.server_thread = threading.Thread(target=self._server_loop)
            self.server_thread.daemon = True
            self.server_thread.start()

            print(f"BlenderMCP server started on {self.host}:{self.port}")
        except Exception as e:
            print(f"Failed to start server: {str(e)}")
            self.stop()

    def stop(self):
        self.running = False

        # Close socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        # Wait for thread to finish
        if self.server_thread:
            try:
                if self.server_thread.is_alive():
                    self.server_thread.join(timeout=1.0)
            except:
                pass
            self.server_thread = None

        print("BlenderMCP server stopped")

    def _server_loop(self):
        """Main server loop in a separate thread"""
        print("Server thread started")
        self.socket.settimeout(1.0)  # Timeout to allow for stopping

        while self.running:
            try:
                # Accept new connection
                try:
                    client, address = self.socket.accept()
                    print(f"Connected to client: {address}")

                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    # Just check running condition
                    continue
                except Exception as e:
                    print(f"Error accepting connection: {str(e)}")
                    time.sleep(0.5)
            except Exception as e:
                print(f"Error in server loop: {str(e)}")
                if not self.running:
                    break
                time.sleep(0.5)

        print("Server thread stopped")

    def _handle_client(self, client):
        """Handle connected client"""
        print("Client handler started")
        client.settimeout(None)  # No timeout
        buffer = b''

        try:
            while self.running:
                # Receive data
                try:
                    data = client.recv(8192)
                    if not data:
                        print("Client disconnected")
                        break

                    buffer += data
                    try:
                        # Try to parse command
                        command = json.loads(buffer.decode('utf-8'))
                        buffer = b''

                        # Execute command in Blender's main thread
                        def execute_wrapper():
                            try:
                                response = self.execute_command(command)
                                response_json = json.dumps(response)
                                try:
                                    client.sendall(response_json.encode('utf-8'))
                                except:
                                    print("Failed to send response - client disconnected")
                            except Exception as e:
                                print(f"Error executing command: {str(e)}")
                                traceback.print_exc()
                                try:
                                    error_response = {
                                        "status": "error",
                                        "message": str(e)
                                    }
                                    client.sendall(json.dumps(error_response).encode('utf-8'))
                                except:
                                    pass
                            return None

                        # Schedule execution in main thread
                        bpy.app.timers.register(execute_wrapper, first_interval=0.0)
                    except json.JSONDecodeError:
                        # Incomplete data, wait for more
                        pass
                except Exception as e:
                    print(f"Error receiving data: {str(e)}")
                    break
        except Exception as e:
            print(f"Error in client handler: {str(e)}")
        finally:
            try:
                client.close()
            except:
                pass
            print("Client handler stopped")

    def execute_command(self, command):
        """Execute a command in the main Blender thread"""
        try:
            return self._execute_command_internal(command)

        except Exception as e:
            print(f"Error executing command: {str(e)}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _execute_command_internal(self, command):
        """Internal command execution with proper context"""
        cmd_type = command.get("type")
        params = command.get("params", {})

        # Base handlers that are always available
        handlers = {
            "get_scene_info": self.get_scene_info,
            "get_object_info": self.get_object_info,
            "get_viewport_screenshot": self.get_viewport_screenshot,
            "execute_code": self.execute_code,
            "get_selected_nodes_info": self.get_selected_nodes_info,
            "get_all_nodes_info": self.get_all_nodes_info,
            "create_analysis_frame": self.create_analysis_frame,
            "remove_analysis_frame": self.remove_analysis_frame,
            "get_analysis_frame_nodes": self.get_analysis_frame_nodes,
            "get_config_variable": self.get_config_variable,
            "get_all_config_variables": self.get_all_config_variables,
            "create_text_note": self.create_text_note,
            "update_text_note": self.update_text_note,
            "get_text_note": self.get_text_note,
            "delete_text_note": self.delete_text_note,
            "filter_nodes_info": self.filter_nodes_info,
            "get_nodes_info_with_filter": self.get_nodes_info_with_filter,
            "clean_markdown_text": self.clean_markdown_text,
            "get_tools_list": self.get_tools_list,
        }

        handler = handlers.get(cmd_type)
        if handler:
            try:
                print(f"Executing handler for {cmd_type}")
                result = handler(**params)
                print(f"Handler execution complete")
                
                # 检查结果是否包含错误
                if isinstance(result, dict) and "error" in result:
                    return {"status": "error", "message": result["error"]}
                
                return {"status": "success", "result": result}
            except Exception as e:
                print(f"Error in handler: {str(e)}")
                traceback.print_exc()
                return {"status": "error", "message": str(e)}
        else:
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}

    def get_scene_info(self):
        """Get information about the current Blender scene"""
        try:
            print("Getting scene info...")
            # Simplify the scene info to reduce data size
            scene_info = {
                "name": bpy.context.scene.name,
                "object_count": len(bpy.context.scene.objects),
                "objects": [],
                "materials_count": len(bpy.data.materials),
            }

            # Collect minimal object information (limit to first 10 objects)
            for i, obj in enumerate(bpy.context.scene.objects):
                if i >= 10:  # Reduced from 20 to 10
                    break

                obj_info = {
                    "name": obj.name,
                    "type": obj.type,
                    # Only include basic location data
                    "location": [round(float(obj.location.x), 2),
                                round(float(obj.location.y), 2),
                                round(float(obj.location.z), 2)],
                }
                scene_info["objects"].append(obj_info)

            print(f"Scene info collected: {len(scene_info['objects'])} objects")
            return scene_info
        except Exception as e:
            print(f"Error in get_scene_info: {str(e)}")
            traceback.print_exc()
            return {"error": str(e)}

    def get_object_info(self, name):
        """Get detailed information about a specific object"""
        from mathutils import Vector
        obj = bpy.data.objects.get(name)
        if not obj:
            raise ValueError(f"Object not found: {name}")

        # Basic object info
        obj_info = {
            "name": obj.name,
            "type": obj.type,
            "location": [obj.location.x, obj.location.y, obj.location.z],
            "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
            "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            "visible": obj.visible_get(),
            "materials": [],
        }

        # Add material slots
        for slot in obj.material_slots:
            if slot.material:
                obj_info["materials"].append(slot.material.name)

        # Add mesh data if applicable
        if obj.type == 'MESH' and obj.data:
            mesh = obj.data
            obj_info["mesh"] = {
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
            }

        return obj_info

    def get_viewport_screenshot(self, max_size=800, filepath=None, format="png"):
        """
        Capture a screenshot of the current 3D viewport and save it to the specified path.

        Parameters:
        - max_size: Maximum size in pixels for the largest dimension of the image
        - filepath: Path where to save the screenshot file
        - format: Image format (png, jpg, etc.)

        Returns success/error status
        """
        try:
            if not filepath:
                return {"error": "No filepath provided"}

            # Find the active 3D viewport
            area = None
            for a in bpy.context.screen.areas:
                if a.type == 'VIEW_3D':
                    area = a
                    break

            if not area:
                return {"error": "No 3D viewport found"}

            # Take screenshot with proper context override
            with bpy.context.temp_override(area=area):
                bpy.ops.screen.screenshot_area(filepath=filepath)

            # Load and resize if needed
            img = bpy.data.images.load(filepath)
            width, height = img.size

            if max(width, height) > max_size:
                scale = max_size / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img.scale(new_width, new_height)

                # Set format and save
                img.file_format = format.upper()
                img.save()
                width, height = new_width, new_height

            # Cleanup Blender image data
            bpy.data.images.remove(img)

            return {
                "success": True,
                "width": width,
                "height": height,
                "filepath": filepath
            }

        except Exception as e:
            return {"error": str(e)}

    def execute_code(self, code):
        """Execute arbitrary Blender Python code"""
        # This is powerful but potentially dangerous - use with caution
        try:
            # Create a local namespace for execution
            namespace = {"bpy": bpy}

            # Capture stdout during execution, and return it as result
            capture_buffer = io.StringIO()
            with redirect_stdout(capture_buffer):
                exec(code, namespace)

            captured_output = capture_buffer.getvalue()
            return {"executed": True, "result": captured_output}
        except Exception as e:
            raise Exception(f"Code execution error: {str(e)}")

    def get_selected_nodes_info(self):
        """获取当前选中节点的详细信息"""
        import json
        try:
            # 查找节点编辑器区域
            node_space = None
            node_area = None
            
            # 遍历所有区域，找到节点编辑器
            for area in bpy.context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for space in area.spaces:
                        if space.type == 'NODE_EDITOR':
                            node_space = space
                            node_area = area
                            break
                    if node_space:
                        break
            
            if not node_space or not node_space.node_tree:
                return {"error": "No active node tree found. Please open a node tree in the Node Editor."}
            
            node_tree = node_space.node_tree
            
            # 尝试多种方式获取选中节点
            selected_nodes = []
            
            # 方法 1: 从节点树直接获取（遍历所有节点检查 select 属性）
            selected_nodes = [node for node in node_tree.nodes if node.select]
            
            # 方法 2: 如果方法 1 失败，尝试从上下文获取（使用覆盖上下文）
            if not selected_nodes:
                try:
                    override = bpy.context.copy()
                    override['area'] = node_area
                    override['space_data'] = node_space
                    override['node_tree'] = node_tree
                    with bpy.context.temp_override(**override):
                        if hasattr(bpy.context, 'selected_nodes') and bpy.context.selected_nodes:
                            selected_nodes = list(bpy.context.selected_nodes)
                except:
                    pass
            
            # 方法 3: 使用活动节点
            if not selected_nodes and hasattr(node_tree, 'nodes'):
                for node in node_tree.nodes:
                    if getattr(node, 'select', False):
                        selected_nodes.append(node)
                        break
                if not selected_nodes and node_tree.nodes.active:
                    selected_nodes = [node_tree.nodes.active]
            
            if not selected_nodes:
                return {"error": "No selected nodes. Please select at least one node."}
            
            # 构建结果
            result = {
                "node_tree_type": node_space.tree_type,
                "selected_nodes_count": len(selected_nodes),
                "selected_nodes": []
            }
            
            for node in selected_nodes:
                node_info = {
                    "name": node.name,
                    "name_localized": pgettext_iface(node.name),
                    "label": node.label,
                    "label_localized": pgettext_iface(node.label or node.name),
                    "type": node.bl_idname,
                    "location": (node.location.x, node.location.y),
                    "width": node.width,
                    "height": node.height,
                    "color": node.color[:] if hasattr(node, 'color') else [0, 0, 0],
                    "use_custom_color": getattr(node, 'use_custom_color', False),
                    "inputs": [],
                    "outputs": [],
                }
                
                # 解析输入端口
                for input_socket in node.inputs:
                    input_info = {
                        "name": input_socket.name,
                        "name_localized": pgettext_iface(input_socket.name),
                        "type": input_socket.type,
                        "identifier": input_socket.identifier,
                        "enabled": input_socket.enabled,
                        "hide": input_socket.hide,
                        "hide_value": getattr(input_socket, 'hide_value', False),
                    }
                    if hasattr(input_socket, 'default_value'):
                        try:
                            val = input_socket.default_value
                            if isinstance(val, (int, float, str, bool)):
                                input_info["default_value"] = val
                            elif hasattr(val, '__len__') and len(val) <= 10:
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
                                "node_localized": pgettext_iface(link.from_node.name),
                                "socket": link.from_socket.name,
                                "socket_localized": pgettext_iface(link.from_socket.name)
                            }
                            connected = True
                            break
                    input_info["is_connected"] = connected
                    node_info["inputs"].append(input_info)
                
                # 解析输出端口
                for output_socket in node.outputs:
                    output_info = {
                        "name": output_socket.name,
                        "name_localized": pgettext_iface(output_socket.name),
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
                            elif hasattr(val, '__len__') and len(val) <= 10:
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
                                "node_localized": pgettext_iface(link.to_node.name),
                                "socket": link.to_socket.name,
                                "socket_localized": pgettext_iface(link.to_socket.name)
                            })
                            connected = True
                    output_info["is_connected"] = connected
                    node_info["outputs"].append(output_info)
                
                result["selected_nodes"].append(node_info)
            
            # 添加连接信息
            if hasattr(node_tree, 'links'):
                connections = []
                for link in node_tree.links:
                    if link.from_node in selected_nodes or link.to_node in selected_nodes:
                        connection_info = {
                            "from_node": link.from_node.name,
                            "from_node_localized": pgettext_iface(link.from_node.name),
                            "from_socket": link.from_socket.name,
                            "from_socket_localized": pgettext_iface(link.from_socket.name),
                            "to_node": link.to_node.name,
                            "to_node_localized": pgettext_iface(link.to_node.name),
                            "to_socket": link.to_socket.name,
                            "to_socket_localized": pgettext_iface(link.to_socket.name),
                        }
                        connections.append(connection_info)
                result["connections"] = connections
            
            return result
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

    def get_all_nodes_info(self):
        """获取当前节点树中的所有节点信息"""
        try:
            # 查找节点编辑器区域
            node_space = None
            node_area = None
            
            # 遍历所有区域，找到节点编辑器
            for area in bpy.context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for space in area.spaces:
                        if space.type == 'NODE_EDITOR':
                            node_space = space
                            node_area = area
                            break
                    if node_space:
                        break
            
            if not node_space:
                return {"error": "Not in Node Editor. Please switch to Node Editor view."}
            
            if not node_space.node_tree:
                return {"error": "No active node tree found. Please open or create a node tree."}
            
            node_tree = node_space.node_tree
            result = parse_node_tree_recursive(node_tree)
            return result
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

    def create_analysis_frame(self):
        """创建分析框架，将选中的节点加入框架"""
        try:
            bpy.ops.node.create_analysis_frame()
            ain_settings = bpy.context.scene.ainode_analyzer_settings
            return {
                "status": "success",
                "frame_node_names": ain_settings.analysis_frame_node_names
            }
        except Exception as e:
            return {"error": str(e)}

    def remove_analysis_frame(self):
        """移除分析框架"""
        try:
            ain_settings = bpy.context.scene.ainode_analyzer_settings
            node_tree = bpy.context.space_data.node_tree
            
            # 检查是否有框架
            frame_node = None
            for node in node_tree.nodes:
                if node.type == 'FRAME' and node.label == "将要分析":
                    frame_node = node
                    break
            
            if frame_node:
                # 移除框架
                node_names = []
                nodes_in_frame = []
                for node in node_tree.nodes:
                    if node.parent == frame_node:
                        node_names.append(node.name)
                        nodes_in_frame.append(node)
                        node.parent = None
                ain_settings.analysis_frame_node_names = ','.join(node_names)
                node_tree.nodes.remove(frame_node)
                
                return {
                    "status": "success",
                    "frame_node_names": ain_settings.analysis_frame_node_names
                }
            else:
                return {"error": "No analysis frame found"}
        except Exception as e:
            return {"error": str(e)}

    def get_analysis_frame_nodes(self):
        """获取分析框架中的节点信息"""
        try:
            # 查找节点编辑器区域
            node_space = None
            node_area = None
            
            # 遍历所有区域，找到节点编辑器
            for area in bpy.context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for space in area.spaces:
                        if space.type == 'NODE_EDITOR':
                            node_space = space
                            node_area = area
                            break
                    if node_space:
                        break
            
            if not node_space or not node_space.node_tree:
                return {"error": "No active node tree found."}
            
            node_tree = node_space.node_tree
            
            # 查找分析框架
            frame_node = None
            for node in node_tree.nodes:
                if node.type == 'FRAME' and node.label == "将要分析":
                    frame_node = node
                    break
            
            if not frame_node:
                return {"error": "No analysis frame found. Please create one first."}
            
            # 获取框架中的节点
            frame_nodes = []
            for node in node_tree.nodes:
                if node.parent == frame_node:
                    frame_nodes.append({
                        "name": node.name,
                        "type": node.bl_idname,
                        "label": node.label,
                        "location": (node.location.x, node.location.y)
                    })
            
            return {
                "status": "success",
                "frame_label": frame_node.label,
                "node_count": len(frame_nodes),
                "nodes": frame_nodes
            }
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

    def get_config_variable(self, variable_name):
        """读取配置文件中的指定变量"""
        try:
            import json
            import os
            
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if not os.path.exists(config_path):
                return {"error": "Config file not found"}
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 根据变量名返回对应的值
            if variable_name == "identity_presets":
                return config.get("system_message_presets", [])
            elif variable_name == "default_questions":
                return config.get("default_question_presets", [])
            elif variable_name == "output_detail_presets":
                return config.get("output_detail_presets", {})
            elif variable_name == "system_prompt":
                return config.get("ai", {}).get("system_prompt", "")
            elif variable_name == "output_detail_level":
                return config.get("output_detail_level", "medium")
            else:
                return {"error": f"Unknown variable: {variable_name}"}
        except Exception as e:
            return {"error": str(e)}

    def get_all_config_variables(self):
        """获取所有配置变量"""
        try:
            import json
            import os
            
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if not os.path.exists(config_path):
                return {"error": "Config file not found"}
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            return {
                "identity_presets": config.get("system_message_presets", []),
                "default_questions": config.get("default_question_presets", []),
                "output_detail_presets": config.get("output_detail_presets", {}),
                "system_prompt": config.get("ai", {}).get("system_prompt", ""),
                "output_detail_level": config.get("output_detail_level", "medium")
            }
        except Exception as e:
            return {"error": str(e)}

    def create_text_note(self, text):
        """创建文本注记节点"""
        try:
            from backend.ai_note import create_note
            
            success = create_note(text)
            
            if success:
                return {"status": "success", "message": "Text note created"}
            else:
                return {"error": "Failed to create text note"}
        except Exception as e:
            return {"error": str(e)}

    def update_text_note(self, text):
        """更新当前激活的文本注记节点"""
        try:
            from backend.ai_note import update_active
            
            success = update_active(text)
            
            if success:
                return {"status": "success", "message": "Text note updated"}
            else:
                return {"error": "Failed to update text note"}
        except Exception as e:
            return {"error": str(e)}

    def get_text_note(self):
        """获取当前激活的文本注记节点内容"""
        try:
            from backend.ai_note import get_active_note
            
            content = get_active_note()
            
            if content is not None:
                return {"status": "success", "content": content}
            else:
                return {"error": "No active text note found"}
        except Exception as e:
            return {"error": str(e)}

    def delete_text_note(self):
        """删除当前激活的文本注记节点"""
        try:
            from backend.ai_note import delete_active_note
            
            success = delete_active_note()
            
            if success:
                return {"status": "success", "message": "Text note deleted"}
            else:
                return {"error": "Failed to delete text note"}
        except Exception as e:
            return {"error": str(e)}

    def filter_nodes_info(self, node_info, level):
        """根据精细度过滤节点信息"""
        try:
            level_map = {
                "ULTRA_LITE": 0,
                "LITE": 1,
                "STANDARD": 2,
                "FULL": 3
            }
            
            level_value = level_map.get(level, 2)
            filtered = filter_node_description(node_info, level_value)
            
            return {
                "status": "success",
                "level": level,
                "filtered_info": filtered
            }
        except Exception as e:
            return {"error": str(e)}

    def get_nodes_info_with_filter(self, level):
        """获取节点信息并应用过滤"""
        try:
            level = level or "STANDARD"
            
            # 查找节点编辑器区域
            node_space = None
            node_area = None
            
            # 遍历所有区域，找到节点编辑器
            for area in bpy.context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for space in area.spaces:
                        if space.type == 'NODE_EDITOR':
                            node_space = space
                            node_area = area
                            break
                    if node_space:
                        break
            
            if not node_space:
                return {"error": "Not in Node Editor. Please switch to Node Editor view."}
            
            if not node_space.node_tree:
                return {"error": "No active node tree found. Please open or create a node tree."}
            
            # 创建覆盖上下文
            override = bpy.context.copy()
            override['area'] = node_area
            override['space_data'] = node_space
            override['node_tree'] = node_space.node_tree
            
            node_tree = node_space.node_tree
            selected_nodes = []
            
            # 尝试多种方式获取选中节点
            if hasattr(override, 'selected_nodes'):
                selected_nodes = list(override.selected_nodes)
            
            if not selected_nodes:
                selected_nodes = [node for node in node_tree.nodes if node.select]
            
            if not selected_nodes and hasattr(override, 'active_node') and override.active_node:
                selected_nodes = [override.active_node]
            
            if not selected_nodes:
                return {"error": "No selected nodes. Please select at least one node."}
            
            # 获取节点描述
            result = {
                "node_tree_type": node_space.tree_type,
                "selected_nodes_count": len(selected_nodes),
                "selected_nodes": []
            }
            
            for node in selected_nodes:
                node_info = {
                    "name": node.name,
                    "label": node.label,
                    "type": node.bl_idname,
                    "location": (node.location.x, node.location.y),
                    "inputs": [],
                    "outputs": [],
                }
                
                for input_socket in node.inputs:
                    node_info["inputs"].append({
                        "name": input_socket.name,
                        "type": input_socket.type,
                        "identifier": input_socket.identifier,
                    })
                
                for output_socket in node.outputs:
                    node_info["outputs"].append({
                        "name": output_socket.name,
                        "type": output_socket.type,
                        "identifier": output_socket.identifier,
                    })
                
                result["selected_nodes"].append(node_info)
            
            # 转换为 JSON 字符串
            node_info_json = json.dumps(result, indent=2)
            
            # 应用过滤
            level_map = {
                "ULTRA_LITE": 0,
                "LITE": 1,
                "STANDARD": 2,
                "FULL": 3
            }
            
            level_value = level_map.get(level, 2)
            filtered = filter_node_description(node_info_json, level_value)
            
            return {
                "status": "success",
                "level": level,
                "filtered_info": filtered
            }
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

    def clean_markdown_text(self, text):
        """清理指定文本的 Markdown 格式"""
        try:
            cleaned = clean_markdown(text)
            
            return {
                "status": "success",
                "original_length": len(text),
                "cleaned_length": len(cleaned),
                "cleaned_text": cleaned
            }
        except Exception as e:
            return {"error": str(e)}

    def get_tools_list(self):
        """获取所有可用的 MCP 工具列表"""
        try:
            tools = [
                {
                    "name": "get_scene_info",
                    "description": "获取当前 Blender 场景信息，包括场景名称、对象数量、材质数量等",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "get_object_info",
                    "description": "获取指定对象的详细信息，包括位置、旋转、缩放、材质等",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "对象名称"
                            }
                        },
                        "required": ["name"]
                    }
                },
                {
                    "name": "get_viewport_screenshot",
                    "description": "获取 3D 视口的截图",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "execute_code",
                    "description": "执行 Blender Python 代码",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "要执行的 Python 代码"
                            }
                        },
                        "required": ["code"]
                    }
                },
                {
                    "name": "get_selected_nodes_info",
                    "description": "获取当前选中节点的详细信息，包括节点名称、类型、位置、输入输出端口、连接关系等",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "get_all_nodes_info",
                    "description": "获取当前激活节点树中的所有节点信息，包括节点之间的连接关系",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "create_analysis_frame",
                    "description": "创建分析框架，将选中的节点加入框架中，用于确定分析范围",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "remove_analysis_frame",
                    "description": "移除分析框架",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "get_analysis_frame_nodes",
                    "description": "获取分析框架中的节点信息",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "get_config_variable",
                    "description": "读取配置文件中的指定变量",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "variable_name": {
                                "type": "string",
                                "description": "变量名称 (identity_presets, default_questions, output_detail_presets, system_prompt, output_detail_level)",
                                "enum": ["identity_presets", "default_questions", "output_detail_presets", "system_prompt", "output_detail_level"]
                            }
                        },
                        "required": ["variable_name"]
                    }
                },
                {
                    "name": "get_all_config_variables",
                    "description": "获取所有配置变量",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "create_text_note",
                    "description": "创建文本注记节点",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "文本内容"
                            }
                        },
                        "required": ["text"]
                    }
                },
                {
                    "name": "update_text_note",
                    "description": "更新当前激活的文本注记节点",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "新的文本内容"
                            }
                        },
                        "required": ["text"]
                    }
                },
                {
                    "name": "get_text_note",
                    "description": "获取当前激活的文本注记节点内容",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "delete_text_note",
                    "description": "删除当前激活的文本注记节点",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "filter_nodes_info",
                    "description": "根据精细度过滤节点信息",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "node_info": {
                                "type": "string",
                                "description": "节点信息 JSON 字符串"
                            },
                            "level": {
                                "type": "string",
                                "description": "精细度级别",
                                "enum": ["ULTRA_LITE", "LITE", "STANDARD", "FULL"]
                            }
                        },
                        "required": ["node_info", "level"]
                    }
                },
                {
                    "name": "get_nodes_info_with_filter",
                    "description": "获取节点信息并应用过滤",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "string",
                                "description": "精细度级别",
                                "enum": ["ULTRA_LITE", "LITE", "STANDARD", "FULL"]
                            }
                        },
                        "required": []
                    }
                },
                {
                    "name": "clean_markdown_text",
                    "description": "清理指定文本的 Markdown 格式",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "要清理的文本"
                            }
                        },
                        "required": ["text"]
                    }
                }
            ]
            
            return {"tools": tools}
        except Exception as e:
            return {"error": str(e)}

# 复制文本部分运算符
class NODE_OT_copy_text_part(bpy.types.Operator):
    bl_idname = "node.copy_text_part"
    bl_label = "切换文本部分选择"
    bl_description = "左键切换选中状态，Shift+单击直接复制"
    bl_options = {'UNDO'}

    part: bpy.props.StringProperty(name="Part", default="")

    def invoke(self, context, event):
        ain_settings = context.scene.ainode_analyzer_settings
        
        # 如果是Shift+单击，直接复制
        if event.shift:
            self.copy_text(context)
            return {'FINISHED'}
        
        # 左键点击，切换选中状态
        # 检查是否已经选中
        found_index = -1
        for i, item in enumerate(ain_settings.selected_text_parts):
            if item.part_name == self.part:
                found_index = i
                break
        
        if found_index >= 0:
            # 如果已经选中，移除它
            ain_settings.selected_text_parts.remove(found_index)
        else:
            # 如果没有找到，添加它
            item = ain_settings.selected_text_parts.add()
            item.part_name = self.part
        
        return {'FINISHED'}

    def copy_text(self, context):
        text_block_name = {
            'output_detail': '01-输出详细程度提示词',
            'system_prompt': '02-系统提示词',
            'user_question': '03-用户问题',
            'node_data': '04-节点数据'
        }.get(self.part)
        
        if text_block_name and text_block_name in bpy.data.texts:
            text_block = bpy.data.texts[text_block_name]
            content = text_block.as_string()
            if content:
                context.window_manager.clipboard = content
                self.report({'INFO'}, f"已复制{self.part}")

# 复制选中文本运算符
class NODE_OT_copy_active_text(bpy.types.Operator):
    bl_idname = "node.copy_active_text"
    bl_label = "复制选中文本"
    bl_description = "复制所有选中的文本部分到剪贴板"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        
        if len(ain_settings.selected_text_parts) == 0:
            self.report({'WARNING'}, "请先选择至少一个文本部分")
            return {'CANCELLED'}
        
        all_content = []
        for item in ain_settings.selected_text_parts:
            part = item.part_name
            text_block_name = {
                'output_detail': '01-输出详细程度提示词',
                'system_prompt': '02-系统提示词',
                'user_question': '03-用户问题',
                'node_data': '04-节点数据'
            }.get(part)
            
            if text_block_name and text_block_name in bpy.data.texts:
                text_block = bpy.data.texts[text_block_name]
                content = text_block.as_string()
                if content:
                    all_content.append(f"=== {part} ===\n{content}\n")
        
        if all_content:
            combined_content = "\n".join(all_content)
            context.window_manager.clipboard = combined_content
            self.report({'INFO'}, f"已复制 {len(all_content)} 个部分")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "选中的部分内容为空")
            return {'CANCELLED'}

# 复制文本编辑器内容运算符
class NODE_OT_copy_text_to_clipboard(bpy.types.Operator):
    bl_idname = "node.copy_text_to_clipboard"
    bl_label = "复制文本"
    bl_description = "复制当前文本编辑器的内容到剪贴板"

    def execute(self, context):
        # 获取当前活动的文本编辑器
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                for space in area.spaces:
                    if space.type == 'TEXT_EDITOR' and space.text:
                        content = space.text.as_string()
                        if content:
                            context.window_manager.clipboard = content
                            self.report({'INFO'}, "已复制文本内容")
                            return {'FINISHED'}
                        else:
                            self.report({'WARNING'}, "文本内容为空")
                            return {'CANCELLED'}
        
        self.report({'WARNING'}, "未找到活动的文本编辑器")
        return {'CANCELLED'}

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
            "name_localized": pgettext_iface(node.name),
            "label": node.label,
            "label_localized": pgettext_iface(node.label or node.name),
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
                "name_localized": pgettext_iface(input_socket.name),
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
                        "node_localized": pgettext_iface(link.from_node.name),
                        "socket": link.from_socket.name,
                        "socket_localized": pgettext_iface(link.from_socket.name)
                    }
                    connected = True
                    break
            input_info["is_connected"] = connected

            node_info["inputs"].append(input_info)

        # 解析输出端口
        for output_idx, output_socket in enumerate(node.outputs):
            output_info = {
                "name": output_socket.name,
                "name_localized": pgettext_iface(output_socket.name),
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
                        "node_localized": pgettext_iface(link.to_node.name),
                        "socket": link.to_socket.name,
                        "socket_localized": pgettext_iface(link.to_socket.name)
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
            "from_node_localized": pgettext_iface(link.from_node.name),
            "from_socket": link.from_socket.name,
            "from_socket_localized": pgettext_iface(link.from_socket.name),
            "to_node": link.to_node.name,
            "to_node_localized": pgettext_iface(link.to_node.name),
            "to_socket": link.to_socket.name,
            "to_socket_localized": pgettext_iface(link.to_socket.name),
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
    
    # 尝试多种方式获取选中节点
    selected_nodes = []
    
    # 方法 1: 从 context.selected_nodes 获取
    if hasattr(context, 'selected_nodes'):
        selected_nodes = list(context.selected_nodes)
    
    # 方法 2: 如果方法 1 失败，从节点树直接获取
    if not selected_nodes:
        selected_nodes = [node for node in node_tree.nodes if node.select]
    
    # 方法 3: 如果还是没有，尝试使用活动节点
    if not selected_nodes and hasattr(context, 'active_node') and context.active_node:
        selected_nodes = [context.active_node]
    
    # 如果还是没有选中节点，返回错误
    if not selected_nodes:
        return "No selected or active nodes to analyze."

    result = {
        "node_tree_type": space.tree_type,
        "selected_nodes_count": len(selected_nodes),
        "selected_nodes": []
    }

    for node in selected_nodes:
        node_info = {
            "name": node.name,
            "name_localized": pgettext_iface(node.name),
            "label": node.label,
            "label_localized": pgettext_iface(node.label or node.name),
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
                "name_localized": pgettext_iface(input_socket.name),
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
                        "node_localized": pgettext_iface(link.from_node.name),
                        "socket": link.from_socket.name,
                        "socket_localized": pgettext_iface(link.from_socket.name)
                    }
                    connected = True
                    break
            input_info["is_connected"] = connected

            node_info["inputs"].append(input_info)

        # 解析输出端口
        for output_idx, output_socket in enumerate(node.outputs):
            output_info = {
                "name": output_socket.name,
                "name_localized": pgettext_iface(output_socket.name),
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
                        "node_localized": pgettext_iface(link.to_node.name),
                        "socket": link.to_socket.name,
                        "socket_localized": pgettext_iface(link.to_socket.name)
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
                    "from_node_localized": pgettext_iface(link.from_node.name),
                    "from_socket": link.from_socket.name,
                    "from_socket_localized": pgettext_iface(link.from_socket.name),
                    "to_node": link.to_node.name,
                    "to_node_localized": pgettext_iface(link.to_node.name),
                    "to_socket": link.to_socket.name,
                    "to_socket_localized": pgettext_iface(link.to_socket.name),
                }
                connections.append(connection_info)
        result["connections"] = connections

    return json.dumps(result, indent=2)

# 选中的文本部分项
class SelectedTextPartItem(bpy.types.PropertyGroup):
    part_name: bpy.props.StringProperty(name="Part Name", default="")

# AI节点分析器设置
class AINodeAnalyzerSettings(PropertyGroup):
    """插件设置属性组"""

    # 后端服务器设置
    enable_backend: BoolProperty(
        name="启用后端",
        description="启用后端服务器以支持浏览器通信",
        default=False
    )

    backend_port: IntProperty(
        name="后端端口",
        description="后端服务器监听端口",
        default=5000,
        min=1024,
        max=65535
    )

    # AI服务商选择
    ai_provider: EnumProperty(
        name="AI服务提供商",
        description="选择AI服务提供商",
        items=[
            ('DEEPSEEK', "DeepSeek", "DeepSeek"),
            ('OLLAMA', "Ollama", "Ollama"),
            ('BIGMODEL', "BigModel", "BigModel (智谱AI)")
        ],
        default='DEEPSEEK',
        update=_on_provider_update
    )

    # DeepSeek设置
    deepseek_api_key: StringProperty(
        name="DeepSeek API密钥",
        description="DeepSeek API密钥用于模型访问",
        subtype='PASSWORD',
        default=""
    )

    deepseek_url: StringProperty(
        name="DeepSeek服务地址",
        description="DeepSeek服务的URL地址",
        default="https://api.deepseek.com",
        maxlen=2048
    )

    deepseek_model: StringProperty(
        name="DeepSeek模型",
        description="DeepSeek模型名称 (例如: deepseek-reasoner, deepseek-chat)",
        default="deepseek-chat",
        maxlen=256,
        update=_on_model_update
    )

    # 通用服务配置
    generic_base_url: StringProperty(
        name="服务地址",
        description="当前服务商的Base URL",
        default="",
        maxlen=2048
    )
    generic_api_key: StringProperty(
        name="API密钥",
        description="当前服务商的API密钥",
        subtype='PASSWORD',
        default=""
    )
    generic_model: StringProperty(
        name="模型",
        description="当前服务商的模型名称",
        default="",
        maxlen=256,
        update=_on_model_update
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
        maxlen=256,
        update=_on_model_update
    )

    # BigModel设置
    bigmodel_api_key: StringProperty(
        name="BigModel API密钥",
        description="BigModel (智谱AI) API密钥用于模型访问",
        subtype='PASSWORD',
        default=""
    )

    bigmodel_url: StringProperty(
        name="BigModel服务地址",
        description="BigModel服务的URL地址",
        default="https://open.bigmodel.cn/api/paas/v4",
        maxlen=2048
    )

    bigmodel_model: StringProperty(
        name="BigModel模型",
        description="BigModel模型名称 (例如: glm-4, glm-4-flash)",
        default="glm-4",
        maxlen=256,
        update=_on_model_update
    )

    # 系统提示
    system_prompt: StringProperty(
        name="系统提示",
        description="AI助手的系统提示信息",
        default="您是Blender节点的专家。分析以下节点结构并提供见解、优化或解释。",
        maxlen=2048
    )


    status_connectivity: StringProperty(name="连通性", default="未知")
    status_networking: StringProperty(name="联网", default="未知")
    status_thinking: StringProperty(name="思考", default="未知")
    status_model_fetch: StringProperty(name="模型获取", default="未知")

    # AI参数设置
    temperature: FloatProperty(
        name="温度",
        description="AI响应的随机性 (0.0 - 2.0)",
        default=0.7,
        min=0.0,
        max=2.0,
        update=_on_temperature_update
    )

    top_p: FloatProperty(
        name="Top P",
        description="核采样阈值 (0.0 - 1.0)",
        default=1.0,
        min=0.0,
        max=1.0,
        update=_on_top_p_update
    )

    # 记忆功能相关设置
    enable_memory: BoolProperty(
        name="启用记忆",
        description="启用对话记忆功能",
        default=True
    )

    memory_target_k: IntProperty(
        name="记忆目标",
        description="记忆目标值",
        default=4,
        min=1,
        max=128
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

    # 回答详细程度设置
    output_detail_level: EnumProperty(
        name="回答详细程度",
        description="控制AI回答的详细程度提示",
        items=[
            ('simple', "简约", "简要说明，不需要markdown格式"),
            ('medium', "适中", "按常规方式回答，使用适当的markdown格式"),
            ('detailed', "详细", "详细说明，使用图表、列表、代码块等markdown格式")
        ],
        default='medium'
    )
    prompt_simple: StringProperty(
        name="简约提示",
        description="用于简约输出的提示指令",
        default="请简要说明，不需要使用markdown格式，简单描述即可。"
    )
    prompt_medium: StringProperty(
        name="适中提示",
        description="用于适中输出的提示指令",
        default="请按常规方式回答，使用适当的markdown格式来组织内容。"
    )
    prompt_detailed: StringProperty(
        name="详细提示",
        description="用于详细输出的提示指令",
        default="请详细说明，使用图表、列表、代码块等markdown格式来清晰地表达内容。"
    )

    # 节点精细度设置（数字挡位）
    node_detail_level: IntProperty(
        name="节点精细度",
        description="控制发送给AI的节点信息详尽程度",
        default=2,
        min=0,
        max=3,
        update=lambda self, context: setattr(self, 'filter_level',
            ['ULTRA_LITE', 'LITE', 'STANDARD', 'FULL'][self.node_detail_level])
    )

    # 回答精细度设置（数字挡位）
    response_detail_level: IntProperty(
        name="回答精细度",
        description="控制AI回答的详细程度",
        default=1,
        min=0,
        max=2,
        update=lambda self, context: setattr(self, 'output_detail_level',
            ['simple', 'medium', 'detailed'][self.response_detail_level])
    )

    md_clean_target_text: EnumProperty(
        name="目标文本",
        description="选择要清理/恢复的文本数据块",
        items=get_text_items
    )
    identity_key: EnumProperty(
        name="身份",
        description="选择AI身份预设",
        items=get_identity_items,
        update=_on_identity_update
    )
    identity_text: StringProperty(
        name="身份文本",
        description="当前身份对应的系统提示文本",
        default="",
        maxlen=4096
    )
    default_question_preset: EnumProperty(
        name="预设问题",
        description="选择默认问题预设以填充输入框",
        items=get_default_question_items,
        update=_on_default_question_preset_update
    )
    filter_level: EnumProperty(
        name="节点过滤级别",
        description="控制发送给AI的节点信息详尽程度",
        items=[
            ('ULTRA_LITE', "极简", "仅最小标识"),
            ('LITE', "简化", "保留必要的IO"),
            ('STANDARD', "常规", "清除可视属性"),
            ('FULL', "完整", "完整上下文")
        ],
        default='STANDARD'
    )
    enable_thinking: BoolProperty(
        name="深度思考",
        description="启用深度思考模式",
        default=False
    )
    enable_web: BoolProperty(
        name="联网",
        description="允许联网检索",
        default=False
    )
    current_model: StringProperty(
        name="当前模型",
        description="当前使用的模型名称",
        default="",
        maxlen=256
    )

    # 当前可用模型列表
    available_models: EnumProperty(
        name="模型",
        description="当前可用的AI模型",
        items=get_model_items,
        update=lambda self, context: _on_model_change_update(self)
    )

    # 展开/折叠设置面板
    show_settings_expanded: BoolProperty(
        name="显示设置展开",
        description="控制设置面板是否展开",
        default=False
    )

    # 简化模式
    simplified_ui: BoolProperty(
        name="简化UI",
        description="简化UI显示，只保留问题输入框和发送按钮",
        default=False
    )

    # 提示信息相关
    show_help_text: BoolProperty(
        name="显示帮助提示",
        description="显示功能帮助提示信息",
        default=True
    )

    # 快速复制相关 - 支持多选
    selected_text_parts: CollectionProperty(
        type=SelectedTextPartItem,
        name="选中的文本部分",
        description="当前选中的文本部分集合"
    )

    # 分析框架相关 - 记录节点名称
    analysis_frame_node_names: StringProperty(
        name="分析框架节点名称",
        description="记录分析框架中包含的节点名称，用逗号分隔",
        default=""
    )

    # 当前选中的tab面板
    current_tab: EnumProperty(
        name="当前Tab",
        description="当前选中的设置tab",
        items=[
            ('IDENTITY', "身份", "身份预设设置"),
            ('PROMPTS', "提示词", "默认提示词设置"),
            ('DETAIL', "精细度控制", "回答精细度控制设置")
        ],
        default='IDENTITY'
    )

    # AI问答状态管理
    ai_question_status: EnumProperty(
        name="AI问答状态",
        description="AI问答的当前状态",
        items=[
            ('IDLE', "空闲", "等待用户提问"),
            ('PROCESSING', "处理中", "AI正在处理问题"),
            ('STOPPED', "已停止", "回答已被用户停止"),
            ('ERROR', "错误", "发生错误")
        ],
        default='IDLE'
    )

    # 是否允许终止当前请求
    can_terminate_request: BoolProperty(
        name="可终止请求",
        description="是否可以终止当前请求",
        default=False
    )

class NODE_OT_load_config_from_file(bpy.types.Operator):
    bl_idname = "node.load_config_from_file"
    bl_label = "从文件加载配置"
    bl_description = "从config.json加载配置"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        
        if not os.path.exists(config_path):
            self.report({'WARNING'}, "配置文件不存在")
            return {'CANCELLED'}
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Update Blender settings
            if 'port' in config:
                ain_settings.backend_port = config['port']

            if 'ai' in config:
                ai = config['ai']

                # 处理新的provider结构
                if 'provider' in ai:
                    provider_info = ai['provider']
                    if isinstance(provider_info, dict):
                        if 'name' in provider_info:
                            ain_settings.ai_provider = provider_info['name']
                        if 'model' in provider_info:
                            # 根据提供商类型设置相应的模型
                            # 使用setattr绕过枚举验证
                            if provider_info['name'] == 'DEEPSEEK':
                                setattr(ain_settings, 'deepseek_model', provider_info['model'])
                            elif provider_info['name'] == 'OLLAMA':
                                setattr(ain_settings, 'ollama_model', provider_info['model'])
                            else:
                                setattr(ain_settings, 'generic_model', provider_info['model'])
                    else:
                        # 兼容旧格式
                        ain_settings.ai_provider = ai['provider']

                # 加载模型列表到缓存
                if 'deepseek' in ai and 'models' in ai['deepseek']:
                    global deepseek_models_cache
                    deepseek_models_cache[:] = ai['deepseek']['models']
                if 'ollama' in ai and 'models' in ai['ollama']:
                    global ollama_models_cache
                    ollama_models_cache[:] = ai['ollama']['models']
                if 'generic' in ai and 'models' in ai['generic']:
                    global generic_models_cache
                    generic_models_cache[:] = ai['generic']['models']

                # 确保URL和API密钥正确加载
                if 'deepseek' in ai:
                    ds = ai['deepseek']
                    if 'url' in ds:
                        ain_settings.deepseek_url = ds['url']
                    if 'api_key' in ds:
                        ain_settings.deepseek_api_key = ds['api_key']
                if 'ollama' in ai:
                    ol = ai['ollama']
                    if 'url' in ol:
                        ain_settings.ollama_url = ol['url']

                # provider configs cache (为了兼容性保留)
                pconfs = ai.get('provider_configs', {})
                if isinstance(pconfs, dict):
                    provider_configs_cache.clear()
                    provider_configs_cache.update(pconfs)
                    
                    # 从provider_configs加载BigModel配置（如果ai.bigmodel中没有）
                    if 'BIGMODEL' in pconfs and isinstance(pconfs['BIGMODEL'], dict):
                        bm_pcfg = pconfs['BIGMODEL']
                        if 'bigmodel' not in ai or not isinstance(ai['bigmodel'], dict):
                            ai['bigmodel'] = {}
                        bm = ai['bigmodel']
                        if 'base_url' in bm_pcfg and not bm.get('url'):
                            bm['url'] = bm_pcfg['base_url']
                        if 'api_key' in bm_pcfg and not bm.get('api_key'):
                            bm['api_key'] = bm_pcfg['api_key']
                        if 'models' in bm_pcfg and not bm.get('models'):
                            bm['models'] = bm_pcfg['models']

                if 'deepseek' in ai:
                    ds = ai['deepseek']
                    if 'api_key' in ds: ain_settings.deepseek_api_key = ds['api_key']
                    if 'url' in ds: ain_settings.deepseek_url = ds['url']  # 确保URL也被设置
                    # 如果在provider中没有设置模型，则从deepseek部分获取
                    if 'model' in ds and not (hasattr(ain_settings, 'deepseek_model') and ain_settings.deepseek_model):
                        setattr(ain_settings, 'deepseek_model', ds['model'])

                if 'ollama' in ai:
                    ol = ai['ollama']
                    if 'url' in ol: ain_settings.ollama_url = ol['url']
                    # 如果在provider中没有设置模型，则从ollama部分获取
                    if 'model' in ol and not (hasattr(ain_settings, 'ollama_model') and ain_settings.ollama_model):
                        setattr(ain_settings, 'ollama_model', ol['model'])

                # 加载BigModel配置
                if 'bigmodel' in ai:
                    bm = ai['bigmodel']
                    if 'url' in bm:
                        ain_settings.bigmodel_url = bm['url']
                    if 'api_key' in bm:
                        ain_settings.bigmodel_api_key = bm['api_key']
                    if 'model' in bm:
                        setattr(ain_settings, 'bigmodel_model', bm['model'])
                    if 'models' in bm:
                        global bigmodel_models_cache
                        bigmodel_models_cache[:] = bm['models']

                if 'system_prompt' in ai: ain_settings.system_prompt = ai['system_prompt']
                if 'temperature' in ai: ain_settings.temperature = ai['temperature']
                if 'top_p' in ai: ain_settings.top_p = ai['top_p']

                # populate generic fields for current provider
                sel = ain_settings.ai_provider
                pcfg = pconfs.get(sel, {}) if isinstance(pconfs, dict) else {}
                ain_settings.generic_base_url = pcfg.get('base_url', "")
                ain_settings.generic_api_key = pcfg.get('api_key', "")
                if sel not in ('DEEPSEEK', 'OLLAMA'):
                    ain_settings.generic_model = (pcfg.get('default_model') or "")
            
            if 'system_message_presets' in config and isinstance(config['system_message_presets'], list):
                system_message_presets_cache.clear()
                system_message_presets_cache.extend(config['system_message_presets'])
                chosen = None
                for idx, it in enumerate(system_message_presets_cache):
                    if it.get('value') == ain_settings.system_prompt:
                        chosen = f"preset_{idx}"
                        break
                # 如果找到了匹配的预设，使用它；否则，如果存在预设则使用第一个，否则使用空字符串
                if chosen:
                    ain_settings.identity_key = chosen
                elif system_message_presets_cache:
                    ain_settings.identity_key = "preset_0"
                else:
                    ain_settings.identity_key = ""

                # 更新身份文本
                if (ain_settings.identity_key and
                    ain_settings.identity_key.startswith("preset_") and
                    system_message_presets_cache):
                    try:
                        idx = int(ain_settings.identity_key.split("_")[1])
                        if 0 <= idx < len(system_message_presets_cache):
                            ain_settings.identity_text = system_message_presets_cache[idx].get('value', '')
                    except (ValueError, IndexError):
                        # 如果解析索引失败，尝试匹配当前系统提示
                        for idx, it in enumerate(system_message_presets_cache):
                            if it.get('value') == ain_settings.system_prompt:
                                ain_settings.identity_key = f"preset_{idx}"
                                ain_settings.identity_text = it.get('value', '')
                                break

            if 'default_questions' in config and config['default_questions']:
                ain_settings.default_question = config['default_questions'][0]
            if 'default_question_presets' in config and isinstance(config['default_question_presets'], list):
                default_question_presets_cache.clear()
                default_question_presets_cache.extend(config['default_question_presets'])
                if default_question_presets_cache:
                    ain_settings.default_question_preset = "q_0"
            # 回答详细程度提示读取（使用统一的 output_detail_presets）
            odp = config.get('output_detail_presets', {})
            if isinstance(odp, dict):
                ain_settings.prompt_simple = odp.get('simple', ain_settings.prompt_simple)
                ain_settings.prompt_medium = odp.get('medium', ain_settings.prompt_medium)
                ain_settings.prompt_detailed = odp.get('detailed', ain_settings.prompt_detailed)
            lvl = config.get('output_detail_level')
            if isinstance(lvl, str) and lvl in ('simple','medium','detailed'):
                ain_settings.output_detail_level = lvl
                # 将output_detail_level映射到response_detail_level
                level_mapping = {
                    'simple': 0,
                    'medium': 1,
                    'detailed': 2
                }
                ain_settings.response_detail_level = level_mapping.get(lvl, 1)  # 默认为 medium (1)

            # 记忆功能设置
            if 'ai' in config:
                ai = config['ai']
                if 'memory' in ai:
                    memory = ai['memory']
                    if 'enabled' in memory:
                        ain_settings.enable_memory = memory['enabled']
                    if 'target_k' in memory:
                        ain_settings.memory_target_k = memory['target_k']
            
            # 配置加载完成后，设置available_models为当前提供商的模型
            # 使用setattr绕过枚举验证
            if ain_settings.ai_provider == 'DEEPSEEK':
                setattr(ain_settings, 'available_models', ain_settings.deepseek_model)
            elif ain_settings.ai_provider == 'OLLAMA':
                setattr(ain_settings, 'available_models', ain_settings.ollama_model)
            elif ain_settings.ai_provider == 'BIGMODEL':
                setattr(ain_settings, 'available_models', ain_settings.bigmodel_model)
            else:
                setattr(ain_settings, 'available_models', ain_settings.generic_model)

            self.report({'INFO'}, "配置已从文件加载")
        except Exception as e:
            self.report({'ERROR'}, f"加载配置失败: {e}")

        # 触发UI更新
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for region in area.regions:
                        if region.type == 'UI':
                            region.tag_redraw()
                            break
                    break

        return {'FINISHED'}

class NODE_OT_save_config_to_file(bpy.types.Operator):
    bl_idname = "node.save_config_to_file"
    bl_label = "保存配置到文件"
    bl_description = "保存当前配置到config.json"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        
        try:
            # Read existing to preserve other fields
            existing_config = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
            
            # Update Port
            existing_config['port'] = ain_settings.backend_port

            # Update AI section
            if 'ai' not in existing_config: existing_config['ai'] = {}
            ai = existing_config['ai']

            # 使用新的provider结构
            ai['provider'] = {
                'name': ain_settings.ai_provider,
                'model': ''
            }

            # 根据当前提供商设置模型
            if ain_settings.ai_provider == 'DEEPSEEK':
                ai['provider']['model'] = ain_settings.deepseek_model
            elif ain_settings.ai_provider == 'OLLAMA':
                ai['provider']['model'] = ain_settings.ollama_model
            elif ain_settings.ai_provider == 'BIGMODEL':
                ai['provider']['model'] = ain_settings.bigmodel_model
            else:
                ai['provider']['model'] = ain_settings.generic_model

            if 'deepseek' not in ai: ai['deepseek'] = {}
            ai['deepseek']['api_key'] = ain_settings.deepseek_api_key
            ai['deepseek']['model'] = ain_settings.deepseek_model
            ai['deepseek']['url'] = ain_settings.deepseek_url

            if 'ollama' not in ai: ai['ollama'] = {}
            ai['ollama']['url'] = ain_settings.ollama_url
            ai['ollama']['model'] = ain_settings.ollama_model

            if 'bigmodel' not in ai: ai['bigmodel'] = {}
            ai['bigmodel']['api_key'] = ain_settings.bigmodel_api_key
            ai['bigmodel']['model'] = ain_settings.bigmodel_model
            ai['bigmodel']['url'] = ain_settings.bigmodel_url
            if bigmodel_models_cache:
                ai['bigmodel']['models'] = bigmodel_models_cache[:]
            
            ai['system_prompt'] = ain_settings.system_prompt
            ai['temperature'] = ain_settings.temperature
            ai['top_p'] = ain_settings.top_p
            # provider_configs writeback
            if 'provider_configs' not in ai: ai['provider_configs'] = {}
            sel = ain_settings.ai_provider
            pcfg = ai['provider_configs'].get(sel, {})
            
            # 根据提供商类型设置相应的配置
            if sel == 'DEEPSEEK':
                pcfg['base_url'] = ain_settings.deepseek_url
                pcfg['api_key'] = ain_settings.deepseek_api_key
                if deepseek_models_cache:
                    pcfg['models'] = deepseek_models_cache[:]
            elif sel == 'OLLAMA':
                pcfg['base_url'] = ain_settings.ollama_url
                pcfg['api_key'] = ain_settings.generic_api_key  # Ollama通常不需要API密钥
                if ollama_models_cache:
                    pcfg['models'] = ollama_models_cache[:]
            elif sel == 'BIGMODEL':
                pcfg['base_url'] = ain_settings.bigmodel_url
                pcfg['api_key'] = ain_settings.bigmodel_api_key
                if bigmodel_models_cache:
                    pcfg['models'] = bigmodel_models_cache[:]
            else:
                # 对于其他提供商，使用generic字段
                pcfg['base_url'] = ain_settings.generic_base_url
                pcfg['api_key'] = ain_settings.generic_api_key
                if 'models' not in pcfg: pcfg['models'] = []
                dm = (ain_settings.generic_model or "").strip()
                if dm and dm not in pcfg['models']:
                    pcfg['models'].insert(0, dm)
                pcfg['default_model'] = dm
            ai['provider_configs'][sel] = pcfg

            # 记忆功能设置
            if 'memory' not in ai: ai['memory'] = {}
            ai['memory']['enabled'] = ain_settings.enable_memory
            ai['memory']['target_k'] = ain_settings.memory_target_k
            
            # Update default questions (keep existing list but maybe update first one?)
            # Or just append? Let's just update the list if empty, or keep as is.
            # User might want to edit the list in the file manually.
            # But let's ensure the current default_question is in the list
            if 'default_questions' not in existing_config: existing_config['default_questions'] = []
            if ain_settings.default_question and ain_settings.default_question not in existing_config['default_questions']:
                existing_config['default_questions'].insert(0, ain_settings.default_question)

            # 保存系统消息预设
            if 'system_message_presets' not in existing_config or not existing_config['system_message_presets']:
                # 如果配置中没有预设或为空，则使用缓存中的值
                existing_config['system_message_presets'] = system_message_presets_cache[:]

            # 保存默认问题预设
            if 'default_question_presets' not in existing_config or not existing_config['default_question_presets']:
                # 如果配置中没有预设或为空，则使用缓存中的值
                existing_config['default_question_presets'] = default_question_presets_cache[:]

            # 回答详细程度提示写回（使用统一的 output_detail_presets）
            existing_config['output_detail_presets'] = {
                'simple': ain_settings.prompt_simple,
                'medium': ain_settings.prompt_medium,
                'detailed': ain_settings.prompt_detailed
            }
            existing_config['output_detail_level'] = ain_settings.output_detail_level

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, indent=4, ensure_ascii=False)

            self.report({'INFO'}, "配置已保存到文件")
        except Exception as e:
            self.report({'ERROR'}, f"保存配置失败: {e}")

        # 触发UI更新
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for region in area.regions:
                        if region.type == 'UI':
                            region.tag_redraw()
                            break
                    break

        return {'FINISHED'}

# 设置弹窗面板
class AINodeAnalyzerSettingsPopup(bpy.types.Operator):
    bl_idname = "node.settings_popup"
    bl_label = "AI节点分析器设置"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        # 在屏幕中央打开对话框而不是在鼠标位置
        return wm.invoke_props_dialog(self, width=600)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ain_settings = scene.ainode_analyzer_settings

        # 显示当前Blender版本和节点类型 - 横向布局
        info_row = layout.row(align=True)
        info_row.label(text=f"版本: {bpy.app.version_string}", icon='BLENDER')

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

        info_row.label(text=f"类型: {node_type}")

        # 显示当前模型
        current_model = ""
        try:
            if ain_settings.ai_provider == 'DEEPSEEK':
                current_model = ain_settings.deepseek_model
            elif ain_settings.ai_provider == 'OLLAMA':
                current_model = ain_settings.ollama_model
            elif ain_settings.ai_provider == 'BIGMODEL':
                current_model = ain_settings.bigmodel_model
            else:
                current_model = ain_settings.generic_model
        except:
            current_model = "未知"

        info_row.label(text=f"模型: {current_model}")

        # AI服务提供商设置
        provider_box = layout.box()
        provider_box.label(text="AI服务提供商设置", icon='WORLD_DATA')
        provider_box.prop(ain_settings, "ai_provider")

        # 地址和密钥行
        addr_row = provider_box.row()
        # 根据当前提供商显示相应的URL字段
        if ain_settings.ai_provider == 'DEEPSEEK':
            addr_row.prop(ain_settings, "deepseek_url", text="地址")
        elif ain_settings.ai_provider == 'OLLAMA':
            addr_row.prop(ain_settings, "ollama_url", text="地址")
        elif ain_settings.ai_provider == 'BIGMODEL':
            addr_row.prop(ain_settings, "bigmodel_url", text="地址")
        else:
            addr_row.prop(ain_settings, "generic_base_url", text="地址")
        addr_row.operator("node.reset_provider_url", text="", icon='LOOP_BACK')

        key_row = provider_box.row()
        # 根据当前提供商显示相应的API密钥字段
        if ain_settings.ai_provider == 'DEEPSEEK':
            key_row.prop(ain_settings, "deepseek_api_key", text="密钥")
        elif ain_settings.ai_provider == 'OLLAMA':
            # Ollama通常不需要API密钥，显示空白或通用密钥字段
            key_row.prop(ain_settings, "generic_api_key", text="密钥")  # Ollama一般不需要API密钥
        elif ain_settings.ai_provider == 'BIGMODEL':
            key_row.prop(ain_settings, "bigmodel_api_key", text="密钥")
        else:
            key_row.prop(ain_settings, "generic_api_key", text="密钥")
        # 添加清空密钥按钮
        clear_key_op = key_row.operator("node.clear_api_key", text="", icon='X')

        # 模型行 - 左右布局
        model_row = provider_box.row()
        # 创建模型选择下拉菜单
        if ain_settings.ai_provider == 'DEEPSEEK':
            model_row.prop(ain_settings, "deepseek_model", text="模型")
        elif ain_settings.ai_provider == 'OLLAMA':
            model_row.prop(ain_settings, "ollama_model", text="模型")
        elif ain_settings.ai_provider == 'BIGMODEL':
            model_row.prop(ain_settings, "bigmodel_model", text="模型")
        else:
            model_row.prop(ain_settings, "generic_model", text="模型")
        # 刷新模型按钮 - 仅在后端服务器运行时启用
        if server_manager and server_manager.is_running:
            model_row.operator("node.refresh_models", text="", icon='FILE_REFRESH')
            # 对于BigModel，添加测试模型按钮
            if ain_settings.ai_provider == 'BIGMODEL':
                model_row.operator("node.test_bigmodel_model", text="", icon='CHECKMARK')
        else:
            # 当服务器未运行时，显示一个提示按钮
            model_row.operator("node.refresh_models_disabled", text="", icon='FILE_REFRESH')

        # 显示可用模型列表
        try:
            models_cache = []
            if ain_settings.ai_provider == 'DEEPSEEK':
                models_cache = deepseek_models_cache
            elif ain_settings.ai_provider == 'OLLAMA':
                models_cache = ollama_models_cache
            elif ain_settings.ai_provider == 'BIGMODEL':
                models_cache = bigmodel_models_cache
            else:
                models_cache = generic_models_cache

            if models_cache:
                model_list_box = provider_box.box()
                model_list_box.label(text="可用模型:", icon='LINENUMBERS_ON')
                for model in models_cache[:10]:  # 限制显示前10个模型
                    row = model_list_box.row()
                    row.label(text=f"• {model}")
                    op = row.operator("node.select_model", text="选择", icon='CHECKMARK')
                    op.model_name = model
                    op.provider = ain_settings.ai_provider
                if len(models_cache) > 10:
                    model_list_box.label(text=f"... 还有 {len(models_cache) - 10} 个模型")
        except:
            # 如果出现错误，跳过模型列表显示
            pass

        # 状态信息和检测按钮
        status_row = provider_box.row()
        # 检查后端服务器是否运行
        if server_manager and server_manager.is_running:
            # 根据连通性状态设置颜色
            if ain_settings.status_connectivity == "可用":
                status_row.label(text=f"连通性: {ain_settings.status_connectivity}", icon='CHECKMARK')
            else:
                status_row.label(text=f"连通性: {ain_settings.status_connectivity}", icon='CANCEL')
            status_row.operator("node.test_provider_status", text="检测连通性", icon='INFO')
        else:
            status_row.label(text="后端未启动", icon='CANCEL')
            status_row = provider_box.row()
            status_row.label(text="请先启动后端服务器", icon='ERROR')
            status_row = provider_box.row()
            status_row.operator("node.test_provider_status_disabled", text="检测连通性", icon='INFO')

        # Tab选择栏
        tab_row = layout.row()
        tab_row.prop_enum(ain_settings, "current_tab", 'IDENTITY')
        tab_row.prop_enum(ain_settings, "current_tab", 'PROMPTS')
        tab_row.prop_enum(ain_settings, "current_tab", 'DETAIL')

        # 根据当前选中的tab显示相应内容
        if ain_settings.current_tab == 'IDENTITY':
            # 身份设置面板
            identity_box = layout.box()
            identity_box.label(text="身份设置", icon='TEXT')

            # 身份预设板块
            identity_subbox = identity_box.box()
            identity_subbox.prop(ain_settings, "identity_key", text="身份预设")
            identity_subbox.prop(ain_settings, "system_prompt", text="系统提示词")

        elif ain_settings.current_tab == 'PROMPTS':
            # 提示词设置面板
            prompt_box = layout.box()
            prompt_box.label(text="提示词设置", icon='TEXT')

            # 默认提示词板块
            question_subbox = prompt_box.box()
            question_subbox.prop(ain_settings, "default_question_preset", text="默认提示词")
            question_subbox.prop(ain_settings, "default_question", text="自定义问题")

        elif ain_settings.current_tab == 'DETAIL':
            # 精细度控制面板
            detail_box = layout.box()
            detail_box.label(text="精细度控制", icon='TEXT')

            # 回答精细度控制板块
            detail_subbox = detail_box.box()
            detail_subbox.prop(ain_settings, "output_detail_level", text="回答精细度")

            # 根据选择的详细程度显示对应的提示词
            if ain_settings.output_detail_level == 'simple':
                detail_subbox.prop(ain_settings, "prompt_simple", text="简约提示")
            elif ain_settings.output_detail_level == 'medium':
                detail_subbox.prop(ain_settings, "prompt_medium", text="适中提示")
            elif ain_settings.output_detail_level == 'detailed':
                detail_subbox.prop(ain_settings, "prompt_detailed", text="详细提示")

        # 记忆与思考功能始终显示在下方
        memory_box = layout.box()
        memory_box.label(text="记忆与思考", icon='MEMORY')
        row = memory_box.row()
        row.prop(ain_settings, "enable_memory")
        row.prop(ain_settings, "memory_target_k")
        row = memory_box.row()
        row.prop(ain_settings, "enable_thinking")
        row.prop(ain_settings, "enable_web")

        # 后端服务器设置
        server_box = layout.box()
        server_box.label(text="后端服务器设置", icon='WORLD_DATA')
        server_row = server_box.row()
        # 使用与主面板相同的服务器控制按钮
        try:
            server_row.operator("node.toggle_backend_server", text="启动" if not (server_manager and server_manager.is_running) else "停止", icon='PLAY' if not (server_manager and server_manager.is_running) else 'SNAP_FACE')
        except:
            server_row.operator("node.toggle_backend_server", text="启动", icon='PLAY')
        server_row.prop(ain_settings, "backend_port", text="端口")

        # 配置文件控制
        config_box = layout.box()
        config_box.label(text="配置管理", icon='FILE_TEXT')
        config_row = config_box.row()
        config_row.operator("node.load_config_from_file", text="重载配置", icon='FILE_REFRESH')
        config_row.operator("node.save_config_to_file", text="保存配置", icon='FILE_TICK')
        config_row.operator("node.reset_settings", text="重置默认", icon='LOOP_BACK')


# 切换后端服务器运算符
class NODE_OT_toggle_backend_server(bpy.types.Operator):
    bl_idname = "node.toggle_backend_server"
    bl_label = "切换后端服务器"
    bl_description = "启动或停止后端服务器"

    def execute(self, context):
        global server_manager
        ain_settings = context.scene.ainode_analyzer_settings

        if server_manager:
            if server_manager.is_running:
                # 停止服务器
                server_manager.stop_server()
                ain_settings.current_status = "后端已停止"
                ain_settings.enable_backend = False  # 更新设置以反映状态
                self.report({'INFO'}, "后端服务器已停止")
            else:
                # 启动服务器
                port = ain_settings.backend_port
                success = server_manager.start_server(port)
                if success:
                    ain_settings.current_status = f"后端已启动 (端口: {port})"
                    ain_settings.enable_backend = True  # 更新设置以反映状态
                    self.report({'INFO'}, f"后端服务器已启动，端口: {port}")
                else:
                    ain_settings.current_status = "后端启动失败"
                    self.report({'ERROR'}, "后端服务器启动失败")
        else:
            self.report({'ERROR'}, "后端服务器未初始化")

        return {'FINISHED'}

# 选择模型运算符
class NODE_OT_select_model(bpy.types.Operator):
    bl_idname = "node.select_model"
    bl_label = "选择模型"
    bl_description = "选择此模型作为当前模型"

    model_name: StringProperty()
    provider: StringProperty()

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        if self.provider == 'DEEPSEEK':
            ain_settings.deepseek_model = self.model_name
        elif self.provider == 'OLLAMA':
            ain_settings.ollama_model = self.model_name
        elif self.provider == 'BIGMODEL':
            ain_settings.bigmodel_model = self.model_name
        else:
            ain_settings.generic_model = self.model_name
        self.report({'INFO'}, f"已选择模型: {self.model_name}")
        return {'FINISHED'}

# 复制节点信息到剪贴板运算符（根据按键修饰符决定行为）
class NODE_OT_copy_nodes_to_clipboard(bpy.types.Operator):
    bl_idname = "node.copy_nodes_to_clipboard"
    bl_label = "复制节点信息到剪贴板"
    bl_description = "复制节点信息到剪贴板 - 点击复制选中节点，Alt+点击复制全部节点"

    def invoke(self, context, event):
        # 检测Alt键是否按下
        alt_pressed = event.alt

        # 根据按键执行不同的操作
        if alt_pressed:
            # Alt+点击 - 复制全部节点
            return self.copy_all_nodes(context)
        else:
            # 普通点击 - 复制选中节点
            return self.copy_selected_nodes(context)

    def copy_selected_nodes(self, context):
        # 首先检查当前上下文是否有有效的节点编辑器
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
            self.report({'ERROR'}, "没有选择要复制的节点")
            return {'CANCELLED'}

        # 获取当前设置
        ain_settings = context.scene.ainode_analyzer_settings
        filter_level = ain_settings.filter_level

        # 创建节点描述
        fake_context = type('FakeContext', (), {
            'space_data': context.space_data,
            'selected_nodes': selected_nodes,
            'active_node': selected_nodes[0] if selected_nodes else None
        })()

        node_description = get_selected_nodes_description(fake_context)
        filtered_desc = filter_node_description(node_description, filter_level)

        # 复制到剪贴板
        if copy_to_clipboard(filtered_desc):
            self.report({'INFO'}, f"已将 {len(selected_nodes)} 个选中节点的信息复制到剪贴板")
        else:
            self.report({'ERROR'}, "复制到剪贴板失败")

        return {'FINISHED'}

    def copy_all_nodes(self, context):
        # 首先检查当前上下文是否有有效的节点编辑器
        if not context.space_data or not hasattr(context.space_data, 'node_tree') or not context.space_data.node_tree:
            self.report({'ERROR'}, "未找到活动的节点树")
            return {'CANCELLED'}

        node_tree = context.space_data.node_tree
        all_nodes = list(node_tree.nodes)

        if not all_nodes:
            self.report({'ERROR'}, "节点树中没有节点")
            return {'CANCELLED'}

        # 获取当前设置
        ain_settings = context.scene.ainode_analyzer_settings
        filter_level = ain_settings.filter_level

        # 使用递归解析函数获取完整的节点树信息
        full_node_info = parse_node_tree_recursive(node_tree)
        full_node_json = json.dumps(full_node_info, indent=2, ensure_ascii=False)
        filtered_desc = filter_node_description(full_node_json, filter_level)

        # 复制到剪贴板
        if copy_to_clipboard(filtered_desc):
            self.report({'INFO'}, f"已将节点树中全部 {len(all_nodes)} 个节点的信息复制到剪贴板")
        else:
            self.report({'ERROR'}, "复制到剪贴板失败")

        return {'FINISHED'}

# 复制全部节点信息到剪贴板运算符
class NODE_OT_copy_all_nodes_to_clipboard(bpy.types.Operator):
    bl_idname = "node.copy_all_nodes_to_clipboard"
    bl_label = "复制全部节点信息到剪贴板"
    bl_description = "复制当前节点树中的全部节点信息到剪贴板，使用当前精细度设置过滤"

    def execute(self, context):
        # 首先检查当前上下文是否有有效的节点编辑器
        if not context.space_data or not hasattr(context.space_data, 'node_tree') or not context.space_data.node_tree:
            self.report({'ERROR'}, "未找到活动的节点树")
            return {'CANCELLED'}

        node_tree = context.space_data.node_tree
        all_nodes = list(node_tree.nodes)

        if not all_nodes:
            self.report({'ERROR'}, "节点树中没有节点")
            return {'CANCELLED'}

        # 获取当前设置
        ain_settings = context.scene.ainode_analyzer_settings
        filter_level = ain_settings.filter_level

        # 使用递归解析函数获取完整的节点树信息
        full_node_info = parse_node_tree_recursive(node_tree)
        full_node_json = json.dumps(full_node_info, indent=2, ensure_ascii=False)
        filtered_desc = filter_node_description(full_node_json, filter_level)

        # 复制到剪贴板
        if copy_to_clipboard(filtered_desc):
            self.report({'INFO'}, f"已将节点树中全部 {len(all_nodes)} 个节点的信息复制到剪贴板")
        else:
            self.report({'ERROR'}, "复制到剪贴板失败")

        return {'FINISHED'}

# 清空API密钥运算符
class NODE_OT_clear_api_key(bpy.types.Operator):
    bl_idname = "node.clear_api_key"
    bl_label = "清空API密钥"
    bl_description = "清空当前API密钥"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        ain_settings.generic_api_key = ""
        ain_settings.deepseek_api_key = ""
        ain_settings.bigmodel_api_key = ""
        self.report({'INFO'}, "API密钥已清空")
        return {'FINISHED'}

# 测试BigModel模型操作符
class NODE_OT_test_bigmodel_model(bpy.types.Operator):
    bl_idname = "node.test_bigmodel_model"
    bl_label = "测试BigModel模型"
    bl_description = "测试当前BigModel模型是否可用"
    bl_options = {'REGISTER'}

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        
        if ain_settings.ai_provider != 'BIGMODEL':
            self.report({'WARNING'}, "请先选择BigModel作为AI服务提供商")
            return {'CANCELLED'}
        
        if not ain_settings.bigmodel_api_key:
            self.report({'WARNING'}, "请先配置BigModel API密钥")
            return {'CANCELLED'}
        
        if not server_manager or not server_manager.is_running:
            self.report({'WARNING'}, "请先启动后端服务器")
            return {'CANCELLED'}
        
        try:
            # 调用后端测试API
            resp = send_to_backend('/api/test-bigmodel-api', data={
                'api_key': ain_settings.bigmodel_api_key,
                'model': ain_settings.bigmodel_model,
                'base_url': ain_settings.bigmodel_url
            }, method='POST')
            
            if resp and isinstance(resp, dict):
                if resp.get('status') == 'Success':
                    self.report({'INFO'}, f"BigModel模型测试成功: {ain_settings.bigmodel_model}")
                else:
                    error_msg = resp.get('message', '未知错误')
                    self.report({'ERROR'}, f"BigModel模型测试失败: {error_msg}")
            else:
                self.report({'ERROR'}, "BigModel模型测试失败: 无效的响应")
        except Exception as e:
            self.report({'ERROR'}, f"BigModel模型测试失败: {str(e)}")
        
        return {'FINISHED'}

# 打开后端网页运算符
class NODE_OT_open_backend_webpage(bpy.types.Operator):
    bl_idname = "node.open_backend_webpage"
    bl_label = "打开后端网页"
    bl_description = "在浏览器中打开后端网页界面"

    def execute(self, context):
        import webbrowser
        global server_manager
        ain_settings = context.scene.ainode_analyzer_settings

        if server_manager and server_manager.is_running:
            port = server_manager.port
            url = f"http://127.0.0.1:{port}"
            webbrowser.open(url)
            self.report({'INFO'}, f"在浏览器中打开: {url}")
        else:
            # 如果服务器未运行，提示用户先启动
            self.report({'WARNING'}, "请先启动后端服务器")

        return {'FINISHED'}

# 重置设置运算符
class NODE_OT_reset_settings(bpy.types.Operator):
    bl_idname = "node.reset_settings"
    bl_label = "重置设置"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings

        # 重置所有设置为默认值
        ain_settings.ai_provider = 'DEEPSEEK'
        ain_settings.deepseek_api_key = ""
        ain_settings.deepseek_url = "https://api.deepseek.com"
        ain_settings.deepseek_model = 'deepseek-chat'
        ain_settings.ollama_url = "http://localhost:11434"
        ain_settings.ollama_model = "llama2"
        ain_settings.system_prompt = "您是Blender节点的专家。分析以下节点结构并提供见解、优化或解释。"
        ain_settings.user_input = ""
        ain_settings.default_question = "请分析这些节点的功能和优化建议"
        ain_settings.identity_key = ""
        ain_settings.default_question_preset = ""
        ain_settings.generic_base_url = ""
        ain_settings.generic_api_key = ""
        ain_settings.generic_model = ""
        ain_settings.enable_backend = False  # 默认不启用后端
        ain_settings.backend_port = 5000
        ain_settings.enable_memory = True  # 默认启用记忆
        ain_settings.memory_target_k = 4  # 默认目标值

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

class NODE_OT_clean_markdown_text(bpy.types.Operator):
    bl_idname = "node.clean_markdown_text"
    bl_label = "清理Markdown"
    bl_description = "清理当前文本文档的Markdown格式"

    def execute(self, context):
        import bpy
        # 获取当前活动的文本块
        text_block = context.space_data.text
        
        if not text_block:
            self.report({'WARNING'}, "没有打开的文本文档")
            return {'CANCELLED'}
        
        content = text_block.as_string()
        
        # 调用后端清理接口以复用Web过滤逻辑
        resp = send_to_backend('/api/clean-markdown', data={'content': content}, method='POST')
        cleaned = None
        if resp and isinstance(resp, dict):
            data = resp.get('data') or resp
            cleaned = data.get('cleaned')
        if isinstance(cleaned, str):
            text_block.clear()
            text_block.write(cleaned)
            self.report({'INFO'}, "已清理Markdown格式")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "清理失败：后端未返回结果")
            return {'CANCELLED'}

def text_header_draw(self, context):
    """在文本编辑器头部添加清理和复制按钮"""
    layout = self.layout
    layout.separator_spacer()
    layout.operator("node.clean_markdown_text", text="", icon='BRUSH_DATA')
    layout.operator("node.copy_text_to_clipboard", text="", icon='COPY_ID')

# 终止AI请求运算符
class NODE_OT_test_provider_status(bpy.types.Operator):
    bl_idname = "node.test_provider_status"
    bl_label = "测试提供商连通性"
    bl_description = "测试当前AI服务商的连通性"

    def execute(self, context):
        ain = context.scene.ainode_analyzer_settings
        prov = ain.ai_provider
        # 1. connectivity via provider-connectivity
        conn = "不可用"
        try:
            resp_c = send_to_backend('/api/provider-connectivity', data={"provider": prov}, method='POST')
            if resp_c and isinstance(resp_c, dict):
                data_c = resp_c.get('data') or resp_c
                if bool(data_c.get('ok', False)):
                    conn = "可用"
        except Exception:
            pass
        ain.status_connectivity = conn
        self.report({'INFO'}, f"连通性测试结果: {conn}")
        return {'FINISHED'}

# 创建一个当服务器未运行时的测试连接操作
class NODE_OT_test_provider_status_disabled(bpy.types.Operator):
    bl_idname = "node.test_provider_status_disabled"
    bl_label = "测试提供商连通性（服务器未启动）"
    bl_description = "后端服务器未启动，请先启动后端服务器"

    def execute(self, context):
        self.report({'WARNING'}, "后端服务器未启动，请先启动后端服务器")
        return {'CANCELLED'}

class NODE_OT_stop_ai_request(bpy.types.Operator):
    bl_idname = "node.stop_ai_request"
    bl_label = "终止AI请求"
    bl_description = "终止当前正在进行的AI请求"

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings

        # 更新状态
        ain_settings.ai_question_status = 'STOPPED'
        ain_settings.can_terminate_request = False
        ain_settings.current_status = "请求已终止"

        self.report({'INFO'}, "AI请求已终止")
        return {'FINISHED'}

class NODE_OT_reset_provider_url(bpy.types.Operator):
    bl_idname = "node.reset_provider_url"
    bl_label = "重置服务地址"

    def execute(self, context):
        ain = context.scene.ainode_analyzer_settings
        sel = ain.ai_provider

        # 根据提供商类型重置URL
        if sel == 'DEEPSEEK':
            ain.deepseek_url = "https://api.deepseek.com"
        elif sel == 'OLLAMA':
            ain.ollama_url = "http://localhost:11434"
        elif sel == 'BIGMODEL':
            ain.bigmodel_url = "https://open.bigmodel.cn/api/paas/v4"
        else:
            ain.generic_base_url = ""

        self.report({'INFO'}, "已重置服务地址")
        return {'FINISHED'}

class NODE_OT_refresh_models(bpy.types.Operator):
    bl_idname = "node.refresh_models"
    bl_label = "刷新模型列表"

    def execute(self, context):
        ain = context.scene.ainode_analyzer_settings
        prov = ain.ai_provider
        try:
            resp = send_to_backend('/api/provider-list-models', data={"provider": prov}, method='POST')
            models = []
            if resp and isinstance(resp, dict):
                data = resp.get('data') or resp
                models = data.get('models') or []

            # 更新相应的模型缓存
            if prov == 'DEEPSEEK':
                global deepseek_models_cache
                deepseek_models_cache[:] = models
                if models and ain.deepseek_model not in models:
                    ain.deepseek_model = models[0]  # 设置第一个模型为当前模型
            elif prov == 'OLLAMA':
                global ollama_models_cache
                ollama_models_cache[:] = models
                if models and ain.ollama_model not in models:
                    ain.ollama_model = models[0]  # 设置第一个模型为当前模型
            elif prov == 'BIGMODEL':
                global bigmodel_models_cache
                bigmodel_models_cache[:] = models
                if models and ain.bigmodel_model not in models:
                    ain.bigmodel_model = models[0]  # 设置第一个模型为当前模型
            else:
                global generic_models_cache
                generic_models_cache[:] = models
                if models and ain.generic_model not in models:
                    ain.generic_model = models[0]  # 设置第一个模型为当前模型

            # 更新配置文件中的模型列表
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)

                    if 'ai' not in config:
                        config['ai'] = {}

                    # 更新相应的模型列表到对应的服务商配置中
                    if prov == 'DEEPSEEK':
                        if 'deepseek' not in config['ai']:
                            config['ai']['deepseek'] = {}
                        config['ai']['deepseek']['models'] = models
                        # 同时更新provider中的模型（如果当前使用的是此提供商）
                        if (config['ai']['provider']['name'] == 'DEEPSEEK' and
                            models and
                            config['ai']['provider']['model'] not in models):
                            config['ai']['provider']['model'] = models[0] if models else config['ai']['provider']['model']  # 设置第一个模型为当前模型
                    elif prov == 'OLLAMA':
                        if 'ollama' not in config['ai']:
                            config['ai']['ollama'] = {}
                        config['ai']['ollama']['models'] = models
                        # 同时更新provider中的模型（如果当前使用的是此提供商）
                        if (config['ai']['provider']['name'] == 'OLLAMA' and
                            models and
                            config['ai']['provider']['model'] not in models):
                            config['ai']['provider']['model'] = models[0] if models else config['ai']['provider']['model']  # 设置第一个模型为当前模型
                    elif prov == 'BIGMODEL':
                        if 'bigmodel' not in config['ai']:
                            config['ai']['bigmodel'] = {}
                        config['ai']['bigmodel']['models'] = models
                        # 同时更新provider中的模型（如果当前使用的是此提供商）
                        if (config['ai']['provider']['name'] == 'BIGMODEL' and
                            models and
                            config['ai']['provider']['model'] not in models):
                            config['ai']['provider']['model'] = models[0] if models else config['ai']['provider']['model']  # 设置第一个模型为当前模型
                    else:
                        # 对于其他提供商，可以添加到generic配置中
                        if 'generic' not in config['ai']:
                            config['ai']['generic'] = {}
                        config['ai']['generic']['models'] = models

                    # 保存更新后的配置
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)

                except Exception as e:
                    print(f"更新配置文件中的模型列表时出错: {e}")

            ain.status_model_fetch = "可用" if models else "不可用"
            self.report({'INFO'}, f"模型刷新完成，共 {len(models)} 个: {', '.join(models[:5])}{'...' if len(models) > 5 else ''}")
        except Exception as e:
            ain.status_model_fetch = "不可用"
            self.report({'ERROR'}, f"模型刷新失败: {e}")
        return {'FINISHED'}

# 创建一个当服务器未运行时的刷新模型操作
class NODE_OT_refresh_models_disabled(bpy.types.Operator):
    bl_idname = "node.refresh_models_disabled"
    bl_label = "刷新模型列表（服务器未启动）"
    bl_description = "后端服务器未启动，请先启动后端服务器"

    def execute(self, context):
        self.report({'WARNING'}, "后端服务器未启动，请先启动后端服务器")
        return {'CANCELLED'}

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
        
        # Create or update text block
        text_block_name = "AINodeRefreshContent"
        if text_block_name in bpy.data.texts:
            text_block = bpy.data.texts[text_block_name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(name=text_block_name)

        # Check for active node tree
        if not context.space_data or not hasattr(context.space_data, 'node_tree') or not context.space_data.node_tree:
            # Write status to text block so frontend knows
            text_block.write("")  # Clear content
            
            # Push to server
            push_blender_content_to_server(context)
            return {'FINISHED'}

        # Check for selected nodes
        selected_nodes = []

        # Method 1: Check context.selected_nodes
        if hasattr(context, 'selected_nodes'):
            selected_nodes = list(context.selected_nodes)

        # If no selected nodes, use active node
        if not selected_nodes and hasattr(context, 'active_node') and context.active_node:
            selected_nodes = [context.active_node]

        # If still no nodes, try to get from current node tree
        if not selected_nodes:
            node_tree = context.space_data.node_tree
            for node in node_tree.nodes:
                if getattr(node, 'select', False):
                    selected_nodes.append(node)

        # If no nodes selected and no user input
        if not selected_nodes and not ain_settings.user_input:
            # Write status to text block
            text_block.write("No nodes selected.")
            
            # Push to server
            push_blender_content_to_server()
            return {'FINISHED'}

        # Get current node type
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
        # 在刷新与发送时更新节点类型，避免在UI绘制中写入

        # 写入内容 - 仅写入节点描述，不包含元数据头
        # 元数据将通过push_blender_content_to_server单独发送

        # 获取当前选中节点的描述（直接从当前上下文获取，而不是使用预览内容）
        if selected_nodes:
            fake_context = type('FakeContext', (), {
                'space_data': context.space_data,
                'selected_nodes': selected_nodes,
                'active_node': selected_nodes[0] if selected_nodes else None
            })()

            node_description = get_selected_nodes_description(fake_context)
            # 保存原始节点数据（不过滤）
            raw_json = json.dumps(json.loads(node_description), indent=2, ensure_ascii=False)
            # 过滤后的节点数据
            filtered = filter_node_description(node_description, ain_settings.filter_level)
            instr = get_output_detail_instruction(ain_settings)
            hdr = f"详细程度:\n{instr}\n\n" if instr else ""
            combined = f"{hdr}系统提示:\n{ain_settings.system_prompt}\n\n问题:\n{ain_settings.user_input}\n\n节点结构:\n{filtered}"
            text_block.write(combined)
            ain_settings.preview_content = combined
            
            print(f"[DEBUG] 有选中节点 {len(selected_nodes)} 个，开始拆分到5个文本块...")
            
            # 拆分为5个独立文本块（带编号前缀，确保顺序）
            # 0. 原始节点数据（不过滤，用于Web端过滤）
            original_data_block_name = "00-原始节点数据"
            if original_data_block_name in bpy.data.texts:
                original_data_block = bpy.data.texts[original_data_block_name]
                original_data_block.clear()
            else:
                original_data_block = bpy.data.texts.new(name=original_data_block_name)
            original_data_block.write(raw_json)
            print(f"[DEBUG] 已写入 {original_data_block_name}")
            
            # 1. 输出详细程度提示词
            output_detail_block_name = "01-输出详细程度提示词"
            if output_detail_block_name in bpy.data.texts:
                output_detail_block = bpy.data.texts[output_detail_block_name]
                output_detail_block.clear()
            else:
                output_detail_block = bpy.data.texts.new(name=output_detail_block_name)
            output_detail_block.write(instr if instr else "")
            print(f"[DEBUG] 已写入 {output_detail_block_name}")
            
            # 2. 系统提示词（身份提示词）
            system_prompt_block_name = "02-系统提示词"
            if system_prompt_block_name in bpy.data.texts:
                system_prompt_block = bpy.data.texts[system_prompt_block_name]
                system_prompt_block.clear()
            else:
                system_prompt_block = bpy.data.texts.new(name=system_prompt_block_name)
            system_prompt_block.write(ain_settings.system_prompt)
            print(f"[DEBUG] 已写入 {system_prompt_block_name}")
            
            # 3. 用户问题
            user_question_block_name = "03-用户问题"
            if user_question_block_name in bpy.data.texts:
                user_question_block = bpy.data.texts[user_question_block_name]
                user_question_block.clear()
            else:
                user_question_block = bpy.data.texts.new(name=user_question_block_name)
            user_question_block.write(ain_settings.user_input)
            print(f"[DEBUG] 已写入 {user_question_block_name}")
            
            # 4. 节点数据（过滤后的，用于发送给AI）
            raw_data_block_name = "04-节点数据"
            if raw_data_block_name in bpy.data.texts:
                raw_data_block = bpy.data.texts[raw_data_block_name]
                raw_data_block.clear()
            else:
                raw_data_block = bpy.data.texts.new(name=raw_data_block_name)
            raw_data_block.write(filtered)
            print(f"[DEBUG] 已写入 {raw_data_block_name}")
        else:
            print(f"[DEBUG] 没有选中节点，保留其他部分，只清空节点数据...")
            instr = get_output_detail_instruction(ain_settings)
            hdr = f"详细程度:\n{instr}\n\n" if instr else ""
            combined = f"{hdr}系统提示:\n{ain_settings.system_prompt}\n\n问题:\n{ain_settings.user_input}\n\n节点结构:\nNo nodes selected."
            text_block.write(combined)
            ain_settings.preview_content = combined
            
            # 只清空节点数据，保留其他部分
            # 0. 原始节点数据（清空）
            original_data_block_name = "00-原始节点数据"
            if original_data_block_name in bpy.data.texts:
                original_data_block = bpy.data.texts[original_data_block_name]
                original_data_block.clear()
            else:
                original_data_block = bpy.data.texts.new(name=original_data_block_name)
            
            # 1. 输出详细程度提示词
            output_detail_block_name = "01-输出详细程度提示词"
            if output_detail_block_name in bpy.data.texts:
                output_detail_block = bpy.data.texts[output_detail_block_name]
                output_detail_block.clear()
                output_detail_block.write(instr if instr else "")
            else:
                output_detail_block = bpy.data.texts.new(name=output_detail_block_name)
                output_detail_block.write(instr if instr else "")
            
            # 2. 系统提示词（身份提示词）
            system_prompt_block_name = "02-系统提示词"
            if system_prompt_block_name in bpy.data.texts:
                system_prompt_block = bpy.data.texts[system_prompt_block_name]
                system_prompt_block.clear()
                system_prompt_block.write(ain_settings.system_prompt)
            else:
                system_prompt_block = bpy.data.texts.new(name=system_prompt_block_name)
                system_prompt_block.write(ain_settings.system_prompt)
            
            # 3. 用户问题
            user_question_block_name = "03-用户问题"
            if user_question_block_name in bpy.data.texts:
                user_question_block = bpy.data.texts[user_question_block_name]
                user_question_block.clear()
                user_question_block.write(ain_settings.user_input)
            else:
                user_question_block = bpy.data.texts.new(name=user_question_block_name)
                user_question_block.write(ain_settings.user_input)
            
            # 4. 节点数据（清空，因为没有选中的节点）
            raw_data_block_name = "04-节点数据"
            if raw_data_block_name in bpy.data.texts:
                raw_data_block = bpy.data.texts[raw_data_block_name]
                raw_data_block.clear()
            else:
                raw_data_block = bpy.data.texts.new(name=raw_data_block_name)

        self.report({'INFO'}, f"内容已刷新到文本块 '{text_block_name}'")

        # 尝试将内容推送到后端服务器
        try:
            success = push_blender_content_to_server(context)
            if success:
                print("已将刷新内容推送到后端服务器")
            else:
                print("推送内容到后端服务器失败，服务器可能未启动")
        except Exception as e:
            print(f"推送内容时出错: {e}")

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
        filtered_desc = filter_node_description(node_description, ain_settings.filter_level)
        instr = get_output_detail_instruction(ain_settings)
        hdr = f"详细程度:\n{instr}\n\n" if instr else ""
        preview_content = f"{hdr}系统提示:\n{ain_settings.system_prompt}\n\n节点结构:\n{filtered_desc}"
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
            ain_settings = bpy.context.scene.ainode_analyzer_settings
            # 首先检查当前上下文是否有有效的节点编辑器
            if not self.current_space_data or not hasattr(self.current_space_data, 'node_tree') or not self.current_space_data.node_tree:
                self.report({'ERROR'}, "未找到活动的节点树")
                ain_settings.current_status = "错误：未找到活动的节点树"
                return {'CANCELLED'}

            # 使用保存的节点信息
            selected_nodes = self.selected_nodes

            # 允许不选择节点也能发送问题
            if not selected_nodes:
                # 没有选择节点，只发送问题，不包含节点信息
                pass
            else:
                # 有选择节点，获取节点描述
                # 由于在后台线程中，我们不能直接使用context，需要使用当前空间数据
                # 创建一个简化上下文用于节点描述函数
                fake_context = type('FakeContext', (), {
                    'space_data': self.current_space_data,
                    'selected_nodes': selected_nodes,
                    'active_node': self.active_node
                })()

                node_description = get_selected_nodes_description(fake_context)
                filtered_desc = filter_node_description(node_description, ain_settings.filter_level)

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

            # 如果没有选择节点，只发送问题
            if not selected_nodes:
                text_block.write("节点结构: 未选择节点\n")
                filtered_desc = "未选择节点"
            else:
                text_block.write("节点结构:\n")
                text_block.write(filtered_desc)

            # 根据AI提供商显示相关信息
            text_block.write(f"\n\nAI服务提供商: {ain_settings.ai_provider}\n")
            if ain_settings.ai_provider == 'DEEPSEEK':
                text_block.write(f"模型: {ain_settings.deepseek_model}\n")
            elif ain_settings.ai_provider == 'OLLAMA':
                text_block.write(f"模型: {ain_settings.ollama_model}\n")
                text_block.write(f"地址: {ain_settings.ollama_url}\n")

            # 生成分析结果
            analysis_result = self.perform_analysis(filtered_desc, ain_settings)
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
        ain_settings.ai_question_status = 'PROCESSING'
        ain_settings.can_terminate_request = True

        # 直接在主线程中执行，获取当前节点信息
        # 首先检查当前上下文是否有有效的节点编辑器
        if not context.space_data or not hasattr(context.space_data, 'node_tree') or not context.space_data.node_tree:
            self.report({'ERROR'}, "未找到活动的节点树")
            ain_settings.current_status = "错误：未找到活动的节点树"
            ain_settings.ai_question_status = 'ERROR'
            ain_settings.can_terminate_request = False
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

        # 允许不选择节点也能发送问题
        # 如果没有选择节点，selected_nodes 将为空列表

        # 创建预览内容（实时创建最新的节点信息）
        fake_context = type('FakeContext', (), {
            'space_data': context.space_data,
            'selected_nodes': selected_nodes,
            'active_node': selected_nodes[0] if selected_nodes else None
        })()

        node_description = get_selected_nodes_description(fake_context)
        filtered_desc = filter_node_description(node_description, ain_settings.filter_level)
        instr = get_output_detail_instruction(ain_settings)
        hdr = f"详细程度:\n{instr}\n\n" if instr else ""
        preview_content = f"{hdr}系统提示:\n{ain_settings.system_prompt}\n\n问题:\n{user_question}\n\n节点结构:\n{filtered_desc}"
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

    # 旧版 run_ask_analysis 已移除，使用下方统一实现

    def run_ask_analysis(self):
        """在后台线程中运行AI问答"""
        import bpy
        import requests
        try:
            ain_settings = bpy.context.scene.ainode_analyzer_settings
            # 首先检查当前上下文是否有有效的节点编辑器
            if not self.current_space_data or not hasattr(self.current_space_data, 'node_tree') or not self.current_space_data.node_tree:
                self.report({'ERROR'}, "未找到活动的节点树")
                ain_settings.current_status = "错误：未找到活动的节点树"
                ain_settings.ai_question_status = 'ERROR'
                ain_settings.can_terminate_request = False
                return {'CANCELLED'}

            # 使用保存的节点信息
            selected_nodes = self.selected_nodes

            # 允许不选择节点也能发送问题
            if not selected_nodes:
                # 没有选择节点，只发送问题，不包含节点信息
                filtered_desc = "未选择节点"
            else:
                # 有选择节点，获取节点描述
                fake_context = type('FakeContext', (), {
                    'space_data': self.current_space_data,
                    'selected_nodes': selected_nodes,
                    'active_node': self.active_node
                })()

                node_description = get_selected_nodes_description(fake_context)
                filtered_desc = filter_node_description(node_description, ain_settings.filter_level)

            # 创建文本块以显示结果
            text_block_name = "AINodeAnalysisResult"
            if text_block_name in bpy.data.texts:
                text_block = bpy.data.texts[text_block_name]
                text_block.clear()
            else:
                text_block = bpy.data.texts.new(name=text_block_name)

            base_url = f"http://127.0.0.1:{server_manager.port}" if (server_manager and server_manager.is_running) else ""
            if not base_url:
                self.report({'ERROR'}, "后端未启动，请先启动后端服务器")
                ain_settings.ai_question_status = 'ERROR'
                ain_settings.can_terminate_request = False
                return {'CANCELLED'}
            payload = {
                "question": (get_output_detail_instruction(ain_settings) + "\n\n" + self.user_question).strip(),
                "content": filtered_desc,
                "ai_provider": ain_settings.ai_provider,
                "ai_model": ain_settings.deepseek_model if ain_settings.ai_provider == 'DEEPSEEK' else (ain_settings.ollama_model if ain_settings.ai_provider == 'OLLAMA' else (ain_settings.bigmodel_model if ain_settings.ai_provider == 'BIGMODEL' else ain_settings.generic_model)),
                "ai": {
                    "thinking": {"enabled": bool(getattr(ain_settings, 'enable_thinking', False))},
                    "networking": {"enabled": True},
                    "memory": {"enabled": bool(getattr(ain_settings, 'enable_memory', True)), "target_k": getattr(ain_settings, 'memory_target_k', 4)}
                },
                "nodeContextActive": True
            }
            
            # 对于BigModel，如果启用深度思考，在问题中添加深度思考指令
            if ain_settings.ai_provider == 'BIGMODEL' and getattr(ain_settings, 'enable_thinking', False):
                thinking_instruction = "\n\n【深度思考模式】请逐步分析问题，展示你的思考过程，包括：1. 理解问题 2. 分析关键点 3. 推理过程 4. 得出结论。"
                payload["question"] = thinking_instruction + "\n\n" + payload["question"]
            
            url = base_url + "/api/stream-analyze"
            try:
                with requests.post(url, json=payload, timeout=300, stream=True) as r:
                    if r.status_code != 200:
                        self.report({'ERROR'}, f"后端错误: {r.status_code}")
                        ain_settings.ai_question_status = 'ERROR'
                        ain_settings.can_terminate_request = False
                        return {'CANCELLED'}
                    wrote_thinking_header = False
                    for line in r.iter_lines():
                        # 检查是否需要终止请求
                        if ain_settings.ai_question_status == 'STOPPED':
                            self.report({'INFO'}, "请求已被用户终止")
                            ain_settings.can_terminate_request = False
                            return {'CANCELLED'}

                        if not line:
                            continue
                        s = line.decode('utf-8')
                        if s.startswith("data: "):
                            if s.strip() == "data: [DONE]":
                                break
                            try:
                                j = json.loads(s[6:])
                                t = j.get('type')
                                c = j.get('content', '')

                                # 再次检查终止状态
                                if ain_settings.ai_question_status == 'STOPPED':
                                    self.report({'INFO'}, "请求已被用户终止")
                                    ain_settings.can_terminate_request = False
                                    return {'CANCELLED'}

                                if t == 'thinking':
                                    if not wrote_thinking_header:
                                        text_block.write(f"\n\n[思考]\n")
                                        wrote_thinking_header = True
                                    # 直接写入增量，不额外换行
                                    text_block.write(c)
                                elif t == 'chunk':
                                    text_block.write(c)
                                elif t == 'error':
                                    self.report({'ERROR'}, c)
                            except Exception:
                                text_block.write(s + "\n")

                    # 检查是否是因用户终止而结束
                    if ain_settings.ai_question_status != 'STOPPED':
                        ain_settings.current_status = "完成"
                        ain_settings.ai_question_status = 'IDLE'

                        # 将结果保存为注释节点
                        self.create_annotation_node(context, text_block.as_string())

                        self.report({'INFO'}, f"问题已回答。结果已保存为注释节点。")

                    ain_settings.can_terminate_request = False
            except Exception as e:
                self.report({'ERROR'}, f"请求后端时出错: {str(e)}")
                ain_settings.ai_question_status = 'ERROR'
                ain_settings.can_terminate_request = False
                return {'CANCELLED'}

        except Exception as e:
            self.report({'ERROR'}, f"AI分析过程中出现错误: {str(e)}")
            ain_settings = bpy.context.scene.ainode_analyzer_settings
            ain_settings.current_status = f"错误: {str(e)}"
            ain_settings.ai_question_status = 'ERROR'
            ain_settings.can_terminate_request = False

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

            # Check if input already has structure/question format to avoid duplication
            if "节点结构:" in node_description and "问题:" in node_description:
                 user_message = node_description
            else:
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

    def create_annotation_node(self, context, content):
        """创建注释节点并添加内容"""
        try:
            # 获取当前节点编辑器的节点树
            if not context.space_data or not hasattr(context.space_data, 'node_tree'):
                print("无法获取节点树")
                return

            node_tree = context.space_data.node_tree
            if not node_tree:
                print("节点树为空")
                return

            # 创建注释节点
            annotation_node = node_tree.nodes.new(type='NodeFrame')
            annotation_node.label = "AI分析结果"
            annotation_node.use_custom_color = True
            annotation_node.color = (0.2, 0.6, 1.0)  # 蓝色系

            # 设置节点位置（在视图中心或稍微偏移）
            if context.area and context.region:
                # 获取当前鼠标位置或视图中心作为参考点
                annotation_node.location = (0, 0)  # 默认位置，可根据需要调整

            # 将AI分析结果作为注释内容
            # 由于Frame节点不能直接显示长文本，我们可以创建一个文本块来存储详细内容
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            annotation_content = f"AI分析结果 - {timestamp}\n\n{content}"

            # 创建或更新文本块
            text_block_name = "AI_Annotation_Content"
            if text_block_name in bpy.data.texts:
                text_block = bpy.data.texts[text_block_name]
                text_block.clear()
            else:
                text_block = bpy.data.texts.new(name=text_block_name)

            text_block.write(annotation_content)

            # 在注释节点上显示部分内容作为标签
            # 限制显示的字符数以适应节点大小
            preview_content = content[:100] + "..." if len(content) > 100 else content
            annotation_node.label = f"AI分析: {preview_content}"

        except Exception as e:
            print(f"创建注释节点时出错: {e}")

class AINodeAnalyzer_MT_question_options_all(bpy.types.Menu):
    """AI Node Analyzer 问题选项子菜单 - 全部节点"""
    bl_label = "问题"
    bl_idname = "AINODE_MT_question_options_all"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ain_settings = scene.ainode_analyzer_settings

        # 显示预设问题选项
        if default_question_presets_cache:
            for idx, preset in enumerate(default_question_presets_cache):
                label = preset.get('label', f'问题 {idx+1}')
                op_preset = layout.operator("node.ask_ai_context", text=label, icon='DOT')
                # 传递节点范围和问题类型
                op_preset.node_scope = 'ALL'
                op_preset.question_type = 'PRESET'
                op_preset.question_index = idx

        # 添加手动输入问题选项
        manual_op = layout.operator("node.ask_ai_context", text="手动输入问题", icon='TEXT')
        manual_op.node_scope = 'ALL'
        manual_op.question_type = 'MANUAL'

class AINodeAnalyzer_MT_question_options_none(bpy.types.Menu):
    """AI Node Analyzer 问题选项子菜单 - 无节点"""
    bl_label = "问题"
    bl_idname = "AINODE_MT_question_options_none"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ain_settings = scene.ainode_analyzer_settings

        # 显示预设问题选项
        if default_question_presets_cache:
            for idx, preset in enumerate(default_question_presets_cache):
                label = preset.get('label', f'问题 {idx+1}')
                op_preset = layout.operator("node.ask_ai_context", text=label, icon='DOT')
                # 传递节点范围和问题类型
                op_preset.node_scope = 'NONE'
                op_preset.question_type = 'PRESET'
                op_preset.question_index = idx

        # 添加手动输入问题选项
        manual_op = layout.operator("node.ask_ai_context", text="手动输入问题", icon='TEXT')
        manual_op.node_scope = 'NONE'
        manual_op.question_type = 'MANUAL'

class AINodeAnalyzer_MT_question_options_selected(bpy.types.Menu):
    """AI Node Analyzer 问题选项子菜单 - 选中节点"""
    bl_label = "问题"
    bl_idname = "AINODE_MT_question_options_selected"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ain_settings = scene.ainode_analyzer_settings

        # 显示预设问题选项
        if default_question_presets_cache:
            for idx, preset in enumerate(default_question_presets_cache):
                label = preset.get('label', f'问题 {idx+1}')
                op_preset = layout.operator("node.ask_ai_context", text=label, icon='DOT')
                # 传递节点范围和问题类型
                op_preset.node_scope = 'SELECTED'
                op_preset.question_type = 'PRESET'
                op_preset.question_index = idx

        # 添加手动输入问题选项
        manual_op = layout.operator("node.ask_ai_context", text="手动输入问题", icon='TEXT')
        manual_op.node_scope = 'SELECTED'
        manual_op.question_type = 'MANUAL'

# 右键菜单功能
class AINodeAnalyzer_MT_context_menu(bpy.types.Menu):
    """AI Node Analyzer 右键菜单"""
    bl_label = "AI节点分析器"
    bl_idname = "AINODE_MT_context_menu"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ain_settings = scene.ainode_analyzer_settings

        # 复制节点信息选项
        copy_row = layout.row(align=True)
        copy_op = copy_row.operator("node.copy_nodes_to_clipboard", text="复制节点", icon='COPY_ID')

        layout.separator()

        # 按照全选节点提问
        all_row = layout.row(align=True)
        all_op = all_row.operator("node.ask_ai_context", text="分析全部节点", icon='SELECT_EXTEND')
        all_op.node_scope = 'ALL'
        all_op.question_type = 'PRESET_SELECTOR'  # 特殊类型，表示需要显示子菜单
        # 添加问题选项子菜单
        all_row.menu("AINODE_MT_question_options_all", text="", icon='TRIA_RIGHT')

        # 选择不使用节点进行提问
        layout.separator()
        none_row = layout.row(align=True)
        none_op = none_row.operator("node.ask_ai_context", text="不使用节点", icon='CANCEL')
        none_op.node_scope = 'NONE'
        none_op.question_type = 'PRESET_SELECTOR'  # 特殊类型，表示需要显示子菜单
        # 添加问题选项子菜单
        none_row.menu("AINODE_MT_question_options_none", text="", icon='TRIA_RIGHT')

        # 按照所选的节点进行提问
        layout.separator()
        selected_row = layout.row(align=True)
        selected_op = selected_row.operator("node.ask_ai_context", text="分析选中节点", icon='NODE')
        selected_op.node_scope = 'SELECTED'
        selected_op.question_type = 'PRESET_SELECTOR'  # 特殊类型，表示需要显示子菜单
        # 添加问题选项子菜单
        selected_row.menu("AINODE_MT_question_options_selected", text="", icon='TRIA_RIGHT')


# 右键菜单操作符
class NODE_OT_ask_ai_context(bpy.types.Operator):
    """右键菜单AI提问操作符"""
    bl_idname = "node.ask_ai_context"
    bl_label = "AI提问"
    bl_description = "使用AI分析节点"
    bl_options = {'REGISTER', 'UNDO'}

    # 节点范围选项
    node_scope: EnumProperty(
        name="节点范围",
        description="选择要分析的节点范围",
        items=[
            ('ALL', "全部节点", "分析当前节点树中的所有节点"),
            ('NONE', "无节点", "不传递任何节点信息，仅基于问题进行回答"),
            ('SELECTED', "选中节点", "仅分析当前选中的节点"),
        ],
        default='SELECTED'
    )

    # 问题类型选项
    question_type: StringProperty(
        name="问题类型",
        description="问题类型（手动输入或预设）",
        default='MANUAL'
    )

    # 预设问题索引
    question_index: IntProperty(
        name="预设问题索引",
        description="预设问题的索引",
        default=0
    )

    def execute(self, context):
        from bpy.app.translations import pgettext_iface
        ain_settings = context.scene.ainode_analyzer_settings

        # 检查AI是否正在处理中
        if ain_settings.ai_question_status == 'PROCESSING':
            self.report({'WARNING'}, "AI正在处理中，请稍后再试")
            return {'CANCELLED'}

        # 检查是否是特殊类型，需要显示子菜单
        if self.question_type == 'PRESET_SELECTOR':
            # 这种情况不应该直接执行，而是应该显示子菜单
            # 但在Blender中，菜单项的执行会触发这个函数
            # 所以我们需要检查是否是这种情况
            # 实际上，当用户点击带箭头的菜单项时，会直接显示子菜单
            # 而不会执行这个函数
            # 所以我们只需要处理实际的选择项
            return {'FINISHED'}

        # 获取节点信息
        node_tree = None
        selected_nodes = []
        all_nodes = []

        # 检查当前上下文是否有有效的节点编辑器
        if context.space_data and hasattr(context.space_data, 'node_tree') and context.space_data.node_tree:
            node_tree = context.space_data.node_tree
            all_nodes = list(node_tree.nodes)

            # 获取选中的节点
            if hasattr(context, 'selected_nodes'):
                selected_nodes = list(context.selected_nodes)
            else:
                # 备选方案：遍历所有节点查找选中的
                for node in all_nodes:
                    if getattr(node, 'select', False):
                        selected_nodes.append(node)

            # 如果没有选中的节点，使用活动节点
            if not selected_nodes and hasattr(context, 'active_node') and context.active_node:
                selected_nodes = [context.active_node]

        # 根据node_scope确定要分析的节点
        nodes_to_analyze = []
        if self.node_scope == 'ALL' and node_tree:
            nodes_to_analyze = all_nodes
        elif self.node_scope == 'SELECTED':
            nodes_to_analyze = selected_nodes
        elif self.node_scope == 'NONE':
            # 不使用节点，nodes_to_analyze保持为空
            pass

        # 获取问题内容
        question = ""
        if self.question_type == 'MANUAL':
            # 弹出对话框让用户输入问题
            ain_settings.ai_question_status = 'PROCESSING'
            ain_settings.can_terminate_request = True
            ain_settings.current_status = "等待用户输入问题..."

            # 保存当前上下文和节点信息，以便在确认后使用
            self.temp_context = {
                'node_tree': node_tree,
                'nodes_to_analyze': nodes_to_analyze,
                'context': context
            }

            # 弹出输入对话框
            bpy.ops.wm.call_panel(name="AINODE_PT_question_input_popup")
            return {'FINISHED'}
        elif self.question_type == 'PRESET':
            # 从预设中获取问题
            if 0 <= self.question_index < len(default_question_presets_cache):
                preset = default_question_presets_cache[self.question_index]
                question = preset.get('value', '')
            else:
                self.report({'ERROR'}, "预设问题索引超出范围")
                return {'CANCELLED'}

        # 如果是预设问题，直接执行分析
        if question:
            self.execute_analysis(context, nodes_to_analyze, question)

        return {'FINISHED'}

    def execute_analysis(self, context, nodes_to_analyze, question):
        """执行AI分析"""
        from bpy.app.translations import pgettext_iface
        ain_settings = context.scene.ainode_analyzer_settings

        # 更新状态
        ain_settings.ai_question_status = 'PROCESSING'
        ain_settings.can_terminate_request = True
        ain_settings.current_status = "正在向AI提问..."

        # 如果没有要分析的节点，但选择了节点范围，则报告错误
        if self.node_scope != 'NONE' and not nodes_to_analyze:
            self.report({'ERROR'}, "没有找到要分析的节点")
            ain_settings.ai_question_status = 'ERROR'
            ain_settings.can_terminate_request = False
            return

        # 创建节点描述
        node_description = ""
        if self.node_scope == 'NONE':
            # 不使用节点信息
            node_description = "无节点信息"
        else:
            # 创建一个模拟上下文来获取节点描述
            fake_context = type('FakeContext', (), {
                'space_data': context.space_data,
                'selected_nodes': nodes_to_analyze,
                'active_node': nodes_to_analyze[0] if nodes_to_analyze else None
            })()

            node_description = get_selected_nodes_description(fake_context)
            node_description = filter_node_description(node_description, ain_settings.filter_level)

        # 在后台线程中运行，以避免阻塞UI
        import threading
        # 保存当前的上下文信息
        self.current_space_data = context.space_data
        self.nodes_to_analyze = nodes_to_analyze
        self.active_node = nodes_to_analyze[0] if nodes_to_analyze else None
        self.user_question = question
        self.node_description = node_description
        thread = threading.Thread(target=self.run_ask_analysis)
        thread.start()

    def run_ask_analysis(self):
        """在后台线程中运行AI问答"""
        import bpy
        import requests
        try:
            ain_settings = bpy.context.scene.ainode_analyzer_settings
            # 首先检查当前上下文是否有有效的节点编辑器
            if not self.current_space_data or not hasattr(self.current_space_data, 'node_tree') or not self.current_space_data.node_tree:
                self.report({'ERROR'}, "未找到活动的节点树")
                ain_settings.current_status = "错误：未找到活动的节点树"
                ain_settings.ai_question_status = 'ERROR'
                ain_settings.can_terminate_request = False
                return {'CANCELLED'}

            # 使用保存的节点信息
            nodes_to_analyze = self.nodes_to_analyze

            if self.node_scope != 'NONE' and not nodes_to_analyze:
                self.report({'ERROR'}, "没有选择要分析的节点")
                ain_settings = bpy.context.scene.ainode_analyzer_settings
                ain_settings.current_status = "错误：没有选择要分析的节点"
                ain_settings.ai_question_status = 'ERROR'
                ain_settings.can_terminate_request = False
                return {'CANCELLED'}

            # 获取节点描述
            filtered_desc = self.node_description

            text_block_name = "AINodeAnalysisResult"
            if text_block_name in bpy.data.texts:
                text_block = bpy.data.texts[text_block_name]
            else:
                text_block = bpy.data.texts.new(name=text_block_name)
            base_url = f"http://127.0.0.1:{server_manager.port}" if (server_manager and server_manager.is_running) else ""
            if not base_url:
                self.report({'ERROR'}, "后端未启动，请先启动后端服务器")
                ain_settings.ai_question_status = 'ERROR'
                ain_settings.can_terminate_request = False
                return {'CANCELLED'}
            payload = {
                "question": (get_output_detail_instruction(ain_settings) + "\n\n" + self.user_question).strip(),
                "content": filtered_desc,
                "ai_provider": ain_settings.ai_provider,
                "ai_model": ain_settings.deepseek_model if ain_settings.ai_provider == 'DEEPSEEK' else (ain_settings.ollama_model if ain_settings.ai_provider == 'OLLAMA' else (ain_settings.bigmodel_model if ain_settings.ai_provider == 'BIGMODEL' else ain_settings.generic_model)),
                "ai": {
                    "thinking": {"enabled": bool(getattr(ain_settings, 'enable_thinking', False))},
                    "networking": {"enabled": True},
                    "memory": {"enabled": bool(getattr(ain_settings, 'enable_memory', True)), "target_k": getattr(ain_settings, 'memory_target_k', 4)}
                },
                "nodeContextActive": True
            }
            
            # 对于BigModel，如果启用深度思考，在问题中添加深度思考指令
            if ain_settings.ai_provider == 'BIGMODEL' and getattr(ain_settings, 'enable_thinking', False):
                thinking_instruction = "\n\n【深度思考模式】请逐步分析问题，展示你的思考过程，包括：1. 理解问题 2. 分析关键点 3. 推理过程 4. 得出结论。"
                payload["question"] = thinking_instruction + "\n\n" + payload["question"]
            
            url = base_url + "/api/stream-analyze"
            try:
                with requests.post(url, json=payload, timeout=300, stream=True) as r:
                    if r.status_code != 200:
                        self.report({'ERROR'}, f"后端错误: {r.status_code}")
                        ain_settings.ai_question_status = 'ERROR'
                        ain_settings.can_terminate_request = False
                        return {'CANCELLED'}
                    wrote_thinking_header = False
                    for line in r.iter_lines():
                        # 检查是否需要终止请求
                        if ain_settings.ai_question_status == 'STOPPED':
                            self.report({'INFO'}, "请求已被用户终止")
                            ain_settings.can_terminate_request = False
                            return {'CANCELLED'}

                        if not line:
                            continue
                        s = line.decode('utf-8')
                        if s.startswith("data: "):
                            if s.strip() == "data: [DONE]":
                                break
                            try:
                                j = json.loads(s[6:])
                                t = j.get('type')
                                c = j.get('content', '')

                                # 再次检查终止状态
                                if ain_settings.ai_question_status == 'STOPPED':
                                    self.report({'INFO'}, "请求已被用户终止")
                                    ain_settings.can_terminate_request = False
                                    return {'CANCELLED'}

                                if t == 'thinking':
                                    if not wrote_thinking_header:
                                        text_block.write(f"\n\n[思考]\n")
                                        wrote_thinking_header = True
                                    # 直接写入增量，不额外换行
                                    text_block.write(c)
                                elif t == 'chunk':
                                    text_block.write(c)
                                elif t == 'error':
                                    self.report({'ERROR'}, c)
                            except Exception:
                                text_block.write(s + "\n")

                    # 检查是否是因用户终止而结束
                    if ain_settings.ai_question_status != 'STOPPED':
                        ain_settings.current_status = "完成"
                        ain_settings.ai_question_status = 'IDLE'

                        # 将结果保存为注释节点
                        self.create_annotation_node(context, text_block.as_string())

                        self.report({'INFO'}, f"问题已回答。结果已保存为注释节点。")

                    ain_settings.can_terminate_request = False
            except Exception as e:
                self.report({'ERROR'}, f"请求后端时出错: {str(e)}")
                ain_settings.ai_question_status = 'ERROR'
                ain_settings.can_terminate_request = False
                return {'CANCELLED'}

        except Exception as e:
            self.report({'ERROR'}, f"AI分析过程中出现错误: {str(e)}")
            ain_settings = bpy.context.scene.ainode_analyzer_settings
            ain_settings.current_status = f"错误: {str(e)}"
            ain_settings.ai_question_status = 'ERROR'
            ain_settings.can_terminate_request = False


# 问题输入弹窗面板
class AINODE_PT_question_input_popup(bpy.types.Panel):
    """问题输入弹窗面板"""
    bl_label = "输入问题"
    bl_idname = "AINODE_PT_question_input_popup"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        ain_settings = scene.ainode_analyzer_settings

        # 问题输入框
        layout.prop(ain_settings, "user_input", text="问题")

        # 确认和取消按钮
        row = layout.row()
        row.operator("node.confirm_question_input", text="确认", icon='CHECKMARK')
        row.operator("node.cancel_question_input", text="取消", icon='X')


# 确认问题输入操作符
class NODE_OT_confirm_question_input(bpy.types.Operator):
    """确认问题输入"""
    bl_idname = "node.confirm_question_input"
    bl_label = "确认问题输入"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        question = ain_settings.user_input.strip()

        if not question:
            self.report({'WARNING'}, "请输入问题")
            return {'CANCELLED'}

        # 这里需要获取之前保存的上下文信息来执行分析
        # 由于在UI线程中，我们无法直接访问OPERATOR内部的临时变量
        # 所以需要通过场景属性或其他方式传递信息
        self.report({'INFO'}, f"问题已确认: {question}")
        return {'FINISHED'}


# 取消问题输入操作符
class NODE_OT_cancel_question_input(bpy.types.Operator):
    """取消问题输入"""
    bl_idname = "node.cancel_question_input"
    bl_label = "取消问题输入"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ain_settings = context.scene.ainode_analyzer_settings
        ain_settings.ai_question_status = 'IDLE'
        ain_settings.can_terminate_request = False
        ain_settings.current_status = "就绪"

        self.report({'INFO'}, "已取消问题输入")
        return {'FINISHED'}


# 注册函数
        """调用Ollama API"""
        try:
            import requests

            # 构建Ollama API URL
            url = f"{settings.ollama_url}/api/generate"

            system_message = settings.system_prompt
            
            # Check if input already has structure/question format to avoid duplication
            if "节点结构:" in node_description and "问题:" in node_description:
                 prompt = f"System: {system_message}\n\nUser: {node_description}\n\nAssistant:"
            else:
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
    print("开始注册AI Node Analyzer插件...")
    
    # 注册快速复制相关类（必须在AINodeAnalyzerSettings之前）
    bpy.utils.register_class(SelectedTextPartItem)
    
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
    bpy.utils.register_class(NODE_OT_load_config_from_file)
    bpy.utils.register_class(NODE_OT_save_config_to_file)
    # 注册节点信息复制到剪贴板运算符
    bpy.utils.register_class(NODE_OT_copy_nodes_to_clipboard)
    # 注册后端服务器相关运算符
    bpy.utils.register_class(NODE_OT_toggle_backend_server)
    bpy.utils.register_class(NODE_OT_open_backend_webpage)
    bpy.utils.register_class(NODE_OT_test_provider_status)
    bpy.utils.register_class(NODE_OT_test_provider_status_disabled)
    bpy.utils.register_class(NODE_OT_stop_ai_request)
    bpy.utils.register_class(NODE_OT_reset_provider_url)
    bpy.utils.register_class(NODE_OT_refresh_models)
    bpy.utils.register_class(NODE_OT_refresh_models_disabled)
    bpy.utils.register_class(NODE_OT_clean_markdown_text)
    bpy.utils.register_class(NODE_OT_clear_api_key)
    bpy.utils.register_class(NODE_OT_select_model)
    
    # 注册快速复制相关类（面板和运算符）
    bpy.utils.register_class(NODE_PT_quick_copy)
    bpy.utils.register_class(NODE_OT_copy_text_part)
    bpy.utils.register_class(NODE_OT_copy_active_text)
    bpy.utils.register_class(NODE_OT_copy_text_to_clipboard)

    # 注册 MCP 面板相关类
    print("=" * 50)
    print("开始注册 MCP 面板...")
    print("=" * 50)
    try:
        # 注册 MCP 相关的属性
        bpy.types.Scene.blendermcp_port = bpy.props.IntProperty(
            name="端口",
            description="BlenderMCP 服务器的端口",
            default=9876,
            min=1024,
            max=65535
        )

        bpy.types.Scene.blendermcp_server_running = bpy.props.BoolProperty(
            name="服务器运行中",
            default=False
        )

        # 注册 MCP 运算符和面板
        print("正在注册 MCP 类...")
        bpy.utils.register_class(BLENDERMCP_PT_Panel)
        bpy.utils.register_class(BLENDERMCP_OT_StartServer)
        bpy.utils.register_class(BLENDERMCP_OT_StopServer)

        print("MCP 面板已注册")
        
        # 自动启动 MCP 服务器
        print("正在启动 MCP 服务器...")
        try:
            print("创建 BlenderMCPServer 实例...")
            if not hasattr(bpy.types, "blendermcp_server") or not bpy.types.blendermcp_server:
                bpy.types.blendermcp_server = BlenderMCPServer(port=9876)
                print("BlenderMCPServer 实例已创建")
            
            print("调用 start() 方法...")
            bpy.types.blendermcp_server.start()
            
            # 使用延迟执行来设置 scene 属性
            def set_server_running():
                try:
                    if hasattr(bpy.context, 'scene'):
                        bpy.context.scene.blendermcp_server_running = True
                except:
                    pass
                return None
            
            bpy.app.timers.register(set_server_running, first_interval=0.1)
            print("MCP 服务器已启动，监听端口 9876")
        except Exception as e:
            print(f"MCP 服务器启动失败: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
    except Exception as e:
        print(f"MCP 面板注册失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    print("=" * 50)

    # 注册右键菜单相关类
    bpy.utils.register_class(AINodeAnalyzer_MT_context_menu)
    bpy.utils.register_class(AINodeAnalyzer_MT_question_options_all)
    bpy.utils.register_class(AINodeAnalyzer_MT_question_options_none)
    bpy.utils.register_class(AINodeAnalyzer_MT_question_options_selected)
    bpy.utils.register_class(NODE_OT_ask_ai_context)
    bpy.utils.register_class(AINODE_PT_question_input_popup)
    bpy.utils.register_class(NODE_OT_confirm_question_input)
    bpy.utils.register_class(NODE_OT_cancel_question_input)

    # 添加清理和复制按钮到文本编辑器头部
    bpy.types.TEXT_HT_header.append(text_header_draw)

    print("插件UI组件注册完成，开始初始化后端服务器...")
    # 初始化后端服务器（但不自动启动）
    if initialize_backend():
        print("后端服务器初始化成功")
    else:
        print("后端服务器初始化失败")

    # 启动刷新检查器
    start_refresh_checker()
    print("刷新检查器已启动")

    # 添加右键菜单到节点编辑器
    bpy.types.NODE_MT_context_menu.append(draw_ainode_menu)


# 全局变量来跟踪定时器
refresh_checker_timer = None


def draw_ainode_menu(self, context):
    """在节点编辑器右键菜单中添加AI Node Analyzer选项"""
    if context.area.type == 'NODE_EDITOR':
        self.layout.menu(AINodeAnalyzer_MT_context_menu.bl_idname, icon='PLUGIN')


# 注销函数

def refresh_checker():
    """定时检查是否有来自前端的请求（包括刷新请求和内容推送）"""
    global server_manager
    if server_manager and server_manager.is_running:
        try:
            # 检查是否有来自前端的刷新请求
            response_json = send_to_backend('/api/check-refresh-request', method='GET')
            
            data = {}
            if response_json:
                if 'data' in response_json:
                    data = response_json['data']
                else:
                    data = response_json

            if data and data.get('requested', False):
                # 如果有刷新请求，执行Blender中的刷新操作
                print("检测到前端刷新请求，正在执行Blender刷新操作...")

                # 找到合适的工作区域来执行操作
                # 遍历所有窗口和区域找到节点编辑器
                found_node_editor = False
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'NODE_EDITOR':
                            # 找到节点编辑器，执行刷新操作
                            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                            if not region and area.regions: region = area.regions[-1]
                            
                            try:
                                # Use temp_override for Blender 3.2+
                                if hasattr(bpy.context, 'temp_override'):
                                    with bpy.context.temp_override(window=window, area=area, region=region, screen=window.screen, scene=bpy.context.scene):
                                        bpy.ops.node.refresh_to_text()
                                else:
                                    # Legacy override
                                    override = {
                                        'window': window,
                                        'screen': window.screen,
                                        'area': area,
                                        'region': region,
                                        'scene': bpy.context.scene,
                                        'workspace': window.workspace
                                    }
                                    bpy.ops.node.refresh_to_text(override)
                                    
                                print("Blender刷新操作执行完成")
                                found_node_editor = True
                            except Exception as e:
                                print(f"执行刷新操作失败: {e}")
                            
                            break
                    if found_node_editor:
                        break
                
                if not found_node_editor:
                    print("未找到节点编辑器，尝试使用通用上下文刷新或提示用户")
                    # 即使没有节点编辑器，我们也应该尝试更新文本块，告诉前端没有选中节点
                    try:
                        text_block_name = "AINodeRefreshContent"
                        if text_block_name in bpy.data.texts:
                            text_block = bpy.data.texts[text_block_name]
                            text_block.clear()
                        else:
                            text_block = bpy.data.texts.new(name=text_block_name)
                        
                        text_block.write("No active node editor found.")
                        
                        # 推送更新到后端
                        push_blender_content_to_server()
                        print("已推送无节点状态到后端")
                    except Exception as e:
                        print(f"处理无节点编辑器状态时出错: {e}")
            
            # 处理设置更新
            if data and data.get('updates'):
                updates = data['updates']
                print(f"收到设置更新: {updates}")
                
                # Check for reload_config flag
                if updates.get('reload_config'):
                    print("Received reload config request")
                    try:
                        # 尝试找到节点编辑器
                        found_editor = False
                        for window in bpy.context.window_manager.windows:
                            for area in window.screen.areas:
                                if area.type == 'NODE_EDITOR':
                                    override = {'window': window, 'area': area, 'region': area.regions[-1], 'scene': bpy.context.scene}
                                    bpy.ops.node.load_config_from_file(override)
                                    found_editor = True
                                    break
                            if found_editor: break
                        
                        # 如果没找到，使用任意区域（配置加载不应依赖于节点编辑器）
                        if not found_editor and bpy.context.window_manager.windows:
                            window = bpy.context.window_manager.windows[0]
                            if window.screen.areas:
                                area = window.screen.areas[0]
                                override = {'window': window, 'area': area, 'region': area.regions[-1], 'scene': bpy.context.scene}
                                # 注意：如果load_config_from_file内部检查了space_data，这可能会失败。
                                # 但通常配置加载只涉及scene属性。
                                try:
                                    if hasattr(bpy.context, 'temp_override'):
                                        with bpy.context.temp_override(**override):
                                            bpy.ops.node.load_config_from_file()
                                    else:
                                        bpy.ops.node.load_config_from_file(override)
                                    print("已通过通用上下文重新加载配置")
                                except Exception as e:
                                    print(f"通用上下文加载配置失败: {e}")
                    except Exception as e:
                        print(f"Failed to auto-reload config: {e}")
                
                for scene in bpy.data.scenes:
                    settings = scene.ainode_analyzer_settings
                    if 'system_prompt' in updates:
                        settings.system_prompt = updates['system_prompt']
                    if 'default_question' in updates:
                        settings.default_question = updates['default_question']
                print("设置更新已应用")

            # 检查是否有从Web推送的内容需要处理
            content_response = send_to_backend('/api/get-web-content', method='GET')
            if content_response and content_response.get('has_content', False):
                content = content_response.get('content', '')
                question = content_response.get('question', '')

                print("检测到从Web推送的内容，正在处理...")

                # 更新当前场景的AINodeAnalyzer设置
                for scene in bpy.data.scenes:
                    ain_settings = scene.ainode_analyzer_settings
                    if question:
                        ain_settings.user_input = question  # 更新问题输入框
                        print(f"已更新问题输入框为: {question[:50]}...")

                # 如果有内容，更新AINodeRefreshContent文本块
                # 如果同时有节点内容和问题，将它们组合起来
                combined_content = ""
                if content:
                    combined_content = content
                if question:
                    if combined_content:
                        combined_content += f"\n\n用户问题:\n{question}"
                    else:
                        combined_content = f"用户问题:\n{question}"

                if combined_content:
                    text_block_name = "AINodeRefreshContent"
                    if text_block_name in bpy.data.texts:
                        text_block = bpy.data.texts[text_block_name]
                        text_block.clear()
                        text_block.write(combined_content)
                    else:
                        text_block = bpy.data.texts.new(name=text_block_name)
                        text_block.write(combined_content)
                    print(f"已更新AINodeRefreshContent文本块")

                    # 同时推送到后端服务器，确保前端获取到的是最新内容
                    # 尝试构建上下文
                    ctx = None
                    try:
                        if bpy.context.window_manager.windows:
                            win = bpy.context.window_manager.windows[0]
                            ctx = type('Context', (), {'window_manager': bpy.context.window_manager, 'window': win, 'screen': win.screen, 'scene': bpy.context.scene, 'view_layer': win.view_layer})()
                    except:
                        pass
                    push_blender_content_to_server(ctx)

        except Exception as e:
            print(f"检查前端请求时出错: {e}")

        try:
            analysis_response = send_to_backend('/api/get-analysis-result', method='GET')
            if analysis_response and analysis_response.get('has_content', False):
                result_text = analysis_response.get('result', '')
                question_text = analysis_response.get('question', '')
                text_block_name = "AINodeAnalysisResult"
                if text_block_name in bpy.data.texts:
                    text_block = bpy.data.texts[text_block_name]
                else:
                    text_block = bpy.data.texts.new(name=text_block_name)
                existing = text_block.as_string()
                if question_text and (question_text in existing):
                    pass
                else:
                    text_block.write(f"\n\n{'='*50}\n")
                    if question_text:
                        text_block.write(f"提问: {question_text}\n")
                    text_block.write(f"回答: {result_text}\n")
                send_to_backend('/api/clear-analysis-result', method='POST')
        except Exception:
            pass

    # 检查当前活动的节点编辑器并自动切换身份预设
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'NODE_EDITOR':
                    space_data = area.spaces.active
                    if space_data and hasattr(space_data, 'tree_type'):
                        tree_type = space_data.tree_type

                        # 为当前场景设置自动身份预设
                        current_scene = window.scene
                        ain_settings = current_scene.ainode_analyzer_settings

                        if tree_type and system_message_presets_cache:
                            auto_identity_idx = get_auto_identity_for_node_type(tree_type)
                            if auto_identity_idx is not None:
                                auto_identity_key = f"preset_{auto_identity_idx}"
                                # 只有当当前选择不是自动匹配的预设时才更新
                                if ain_settings.identity_key != auto_identity_key:
                                    ain_settings.identity_key = auto_identity_key
                                    # 触发更新
                                    ain_settings.identity_text = system_message_presets_cache[auto_identity_idx].get('value', '')
                                    ain_settings.system_prompt = system_message_presets_cache[auto_identity_idx].get('value', '')
                    break
    except Exception as e:
        print(f"自动切换身份预设时出错: {e}")

    # 继续下一次检查 - 每1秒检查一次，以提高响应速度
    return 1.0

def start_refresh_checker():
    """启动刷新检查器"""
    global refresh_checker_timer
    if refresh_checker_timer is None:
        # 使用bpy.app.timers来创建一个定期执行的函数
        refresh_checker_timer = bpy.app.timers.register(refresh_checker, persistent=True)
        print("刷新检查器已启动")

def stop_refresh_checker():
    """停止刷新检查器"""
    global refresh_checker_timer
    if refresh_checker_timer and bpy.app.timers.is_registered(refresh_checker_timer):
        bpy.app.timers.unregister(refresh_checker_timer)
        refresh_checker_timer = None
        print("刷新检查器已停止")

# 注销函数
def unregister():
    print("开始注销AI Node Analyzer插件...")
    # 停止刷新检查器
    stop_refresh_checker()
    # 停止后端服务器
    global server_manager
    if server_manager and server_manager.is_running:
        server_manager.stop_server()
        print("后端服务器已停止")

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
    bpy.utils.unregister_class(NODE_OT_load_config_from_file)
    bpy.utils.unregister_class(NODE_OT_save_config_to_file)
    # 注销节点信息复制到剪贴板运算符
    bpy.utils.unregister_class(NODE_OT_copy_nodes_to_clipboard)
    # 注销后端服务器相关运算符
    bpy.utils.unregister_class(NODE_OT_toggle_backend_server)
    bpy.utils.unregister_class(NODE_OT_open_backend_webpage)
    bpy.utils.unregister_class(NODE_OT_test_provider_status)
    bpy.utils.unregister_class(NODE_OT_test_provider_status_disabled)
    bpy.utils.unregister_class(NODE_OT_stop_ai_request)
    bpy.utils.unregister_class(NODE_OT_reset_provider_url)
    bpy.utils.unregister_class(NODE_OT_refresh_models)
    bpy.utils.unregister_class(NODE_OT_refresh_models_disabled)
    bpy.utils.unregister_class(NODE_OT_clean_markdown_text)
    bpy.utils.unregister_class(NODE_OT_clear_api_key)
    bpy.utils.unregister_class(NODE_OT_select_model)
    
    # 注销快速复制相关类（面板和运算符）
    bpy.utils.unregister_class(NODE_PT_quick_copy)
    bpy.utils.unregister_class(NODE_OT_copy_text_part)
    bpy.utils.unregister_class(NODE_OT_copy_active_text)
    bpy.utils.unregister_class(NODE_OT_copy_text_to_clipboard)

    # 注销 MCP 面板
    print("开始注销 MCP 面板...")
    try:
        # 停止 MCP 服务器
        print("正在停止 MCP 服务器...")
        try:
            if hasattr(bpy.types, "blendermcp_server") and bpy.types.blendermcp_server:
                bpy.types.blendermcp_server.stop()
                del bpy.types.blendermcp_server
                print("MCP 服务器已停止")
        except Exception as e:
            print(f"停止 MCP 服务器时出错: {e}", file=sys.stderr)
        
        bpy.utils.unregister_class(BLENDERMCP_PT_Panel)
        bpy.utils.unregister_class(BLENDERMCP_OT_StartServer)
        bpy.utils.unregister_class(BLENDERMCP_OT_StopServer)

        # 删除 MCP 属性
        del bpy.types.Scene.blendermcp_port
        del bpy.types.Scene.blendermcp_server_running

        print("MCP 面板已注销")
    except Exception as e:
        print(f"MCP 面板注销失败: {e}", file=sys.stderr)

    # 注销右键菜单相关类
    bpy.utils.unregister_class(AINodeAnalyzer_MT_context_menu)
    bpy.utils.unregister_class(AINodeAnalyzer_MT_question_options_all)
    bpy.utils.unregister_class(AINodeAnalyzer_MT_question_options_none)
    bpy.utils.unregister_class(AINodeAnalyzer_MT_question_options_selected)
    bpy.utils.unregister_class(NODE_OT_ask_ai_context)
    bpy.utils.unregister_class(AINODE_PT_question_input_popup)
    bpy.utils.unregister_class(NODE_OT_confirm_question_input)
    bpy.utils.unregister_class(NODE_OT_cancel_question_input)

    # 从文本编辑器头部移除清理和复制按钮
    bpy.types.TEXT_HT_header.remove(text_header_draw)

    # 注销面板
    bpy.utils.unregister_class(NODE_PT_ai_analyzer)

    # 注销偏好设置
    bpy.utils.unregister_class(AINodeAnalyzerPreferences)

    # 从节点编辑器移除右键菜单
    bpy.types.NODE_MT_context_menu.remove(draw_ainode_menu)

    # 删除设置属性
    del bpy.types.Scene.ainode_analyzer_settings
    bpy.utils.unregister_class(AINodeAnalyzerSettings)
    
    # 注销快速复制相关类（PropertyGroup必须在最后注销）
    bpy.utils.unregister_class(SelectedTextPartItem)
    
    print("插件已注销完成")


if __name__ == "__main__":
    register()
