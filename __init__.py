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
        lvl = getattr(settings, 'output_detail_level', 'STANDARD')
        if lvl == 'ULTRA_LITE':
            return getattr(settings, 'prompt_ultra_lite', '') or ''
        if lvl == 'LITE':
            return getattr(settings, 'prompt_lite', '') or ''
        if lvl == 'STANDARD':
            return getattr(settings, 'prompt_standard', '') or ''
        if lvl == 'FULL':
            return getattr(settings, 'prompt_full', '') or ''
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

def get_default_question_items(self, context):
    items = []
    for idx, it in enumerate(default_question_presets_cache):
        label = it.get('label', f'问题 {idx+1}')
        key = f"q_{idx}"
        items.append((key, label, label))
    if not items:
        items = [('none', "无预设", "无预设")]
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

# 模型列表缓存
deepseek_models_cache = []
ollama_models_cache = []
generic_models_cache = []


def _on_model_update(self, context):
    try:
        if self.ai_provider == 'DEEPSEEK':
            self.current_model = self.deepseek_model
        elif self.ai_provider == 'OLLAMA':
            self.current_model = self.ollama_model
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
    """将Blender中AINodeRefreshContent的内容推送到后端服务器"""
    global server_manager
    if not server_manager or not server_manager.is_running:
        print("后端服务器未运行")
        return False

    try:
        # 使用传入的上下文或全局上下文
        ctx = context if context else bpy.context

        # 获取AINodeRefreshContent文本块的内容
        import bpy
        if 'AINodeRefreshContent' in bpy.data.texts:
            text_block = bpy.data.texts['AINodeRefreshContent']
            content = text_block.as_string()

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
                print("成功推送AINodeRefreshContent内容到后端服务器")
                return True
            else:
                print("推送内容到后端服务器失败")
                return False
        else:
            print("AINodeRefreshContent文本块不存在")
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

        # 状态行和设置按钮
        top_row = layout.row()
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
        # 获取身份预设的显示名称
        identity_display = "未选择"
        try:
            if ain_settings.identity_key and ain_settings.identity_key.startswith("preset_"):
                idx = int(ain_settings.identity_key.split("_")[1])
                if 0 <= idx < len(system_message_presets_cache):
                    identity_display = system_message_presets_cache[idx].get('label', ain_settings.identity_key)
                else:
                    identity_display = ain_settings.identity_key
            else:
                identity_display = ain_settings.identity_key or "未选择"
        except:
            identity_display = ain_settings.identity_key or "未选择"

        top_row.label(text=f"节点: {node_type} | 身份: {identity_display}")
        top_row.separator()
        top_row.operator("node.load_config_from_file", text="", icon='FILE_REFRESH')
        top_row.operator("node.settings_popup", text="", icon='PREFERENCES')

        row_ident = layout.row()
        row_ident.prop(ain_settings, "identity_key", text="身份")

        # 后端服务器控制
        backend_box = layout.box()
        backend_box.label(text="后端服务器", icon='WORLD_DATA')

        # 服务器控制按钮 - 一行显示三个按钮：[启动/停止] [端口] [网页]
        row = backend_box.row()
        row.operator("node.toggle_backend_server", text="启动" if not (server_manager and server_manager.is_running) else "停止", icon='PLAY' if not (server_manager and server_manager.is_running) else 'SNAP_FACE')
        row.prop(ain_settings, "backend_port", text="端口")
        row.operator("node.open_backend_webpage", text="网页", icon='WORLD')

        # 对话功能
        box = layout.box()
        # 标题行包含标签和分析框架按钮
        title_row = box.row()
        title_row.label(text="交互式问答", icon='QUESTION')
        title_row.operator("node.create_analysis_frame", text="", icon='SEQ_STRIP_META')  # 使用图标按钮

        row = box.row(align=True)
        row.prop(ain_settings, "user_input", text="")

        # 第二行：默认问题下拉、清除、刷新按钮
        row = box.row(align=True)
        row.prop(ain_settings, "default_question_preset", text="默认问题")
        row.operator("node.clear_question", text="清除", icon='X')
        row.operator("node.refresh_to_text", text="刷新", icon='FILE_TEXT')

        # 过滤挡位 + 三项开关与模型
        row2 = box.row(align=True)
        row2.prop(ain_settings, "filter_level", text="挡位")
        row2.prop(ain_settings, "enable_thinking", text="深度思考")
        row2.prop(ain_settings, "enable_web", text="联网")
        if ain_settings.ai_provider == 'DEEPSEEK':
            row2.prop(ain_settings, "deepseek_model", text="模型")
        elif ain_settings.ai_provider == 'OLLAMA':
            row2.prop(ain_settings, "ollama_model", text="模型")

        # Markdown 清理行（左侧按钮控制）
        rowm = box.row(align=True)
        rowm.operator("node.clean_markdown_text", text="清理Markdown", icon='BRUSH_DATA')
        rowm.prop(ain_settings, "md_clean_target_text", text="目标文本")

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

# 添加对话历史记录属性
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
            ('OLLAMA', "Ollama", "Ollama")
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
    output_detail_level: EnumProperty(
        name="回答详细程度",
        description="控制AI回答的详细程度提示",
        items=[
            ('ULTRA_LITE', "极简", "仅最小输出"),
            ('LITE', "简化", "保留必要信息"),
            ('STANDARD', "常规", "正常详尽度"),
            ('FULL', "完整", "尽可能详细")
        ],
        default='STANDARD'
    )
    prompt_ultra_lite: StringProperty(
        name="极简提示",
        description="用于极简输出的提示指令",
        default="回答尽量简短，仅提供关键要点与结论。"
    )
    prompt_lite: StringProperty(
        name="简化提示",
        description="用于简化输出的提示指令",
        default="回答简洁，保留必要的解释与步骤。"
    )
    prompt_standard: StringProperty(
        name="常规提示",
        description="用于常规输出的提示指令",
        default="回答正常详尽度，结构清晰、逐步说明。"
    )
    prompt_full: StringProperty(
        name="完整提示",
        description="用于完整输出的提示指令",
        default="回答详细全面，包含充分例子、注意事项与扩展建议。"
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
        name="过滤挡位",
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

    # 分析框架相关 - 记录节点名称
    analysis_frame_node_names: StringProperty(
        name="分析框架节点名称",
        description="记录分析框架中包含的节点名称，用逗号分隔",
        default=""
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
                            if provider_info['name'] == 'DEEPSEEK':
                                ain_settings.deepseek_model = provider_info['model']
                            elif provider_info['name'] == 'OLLAMA':
                                ain_settings.ollama_model = provider_info['model']
                            else:
                                ain_settings.generic_model = provider_info['model']
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

                if 'deepseek' in ai:
                    ds = ai['deepseek']
                    if 'api_key' in ds: ain_settings.deepseek_api_key = ds['api_key']
                    if 'url' in ds: ain_settings.deepseek_url = ds['url']  # 确保URL也被设置
                    # 如果在provider中没有设置模型，则从deepseek部分获取
                    if 'model' in ds and not (hasattr(ain_settings, 'deepseek_model') and ain_settings.deepseek_model):
                        ain_settings.deepseek_model = ds['model']

                if 'ollama' in ai:
                    ol = ai['ollama']
                    if 'url' in ol: ain_settings.ollama_url = ol['url']
                    # 如果在provider中没有设置模型，则从ollama部分获取
                    if 'model' in ol and not (hasattr(ain_settings, 'ollama_model') and ain_settings.ollama_model):
                        ain_settings.ollama_model = ol['model']

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
                ain_settings.identity_key = chosen or ("preset_0" if system_message_presets_cache else "")
                if system_message_presets_cache:
                    ain_settings.identity_text = system_message_presets_cache[int(ain_settings.identity_key.split("_")[1])].get('value', "")

            if 'default_questions' in config and config['default_questions']:
                ain_settings.default_question = config['default_questions'][0]
            if 'default_question_presets' in config and isinstance(config['default_question_presets'], list):
                default_question_presets_cache.clear()
                default_question_presets_cache.extend(config['default_question_presets'])
                if default_question_presets_cache:
                    ain_settings.default_question_preset = "q_0"
            # 回答详细程度提示读取
            odp = config.get('output_detail_prompts', {})
            if isinstance(odp, dict):
                ain_settings.prompt_ultra_lite = odp.get('ULTRA_LITE', ain_settings.prompt_ultra_lite)
                ain_settings.prompt_lite = odp.get('LITE', ain_settings.prompt_lite)
                ain_settings.prompt_standard = odp.get('STANDARD', ain_settings.prompt_standard)
                ain_settings.prompt_full = odp.get('FULL', ain_settings.prompt_full)
            lvl = config.get('output_detail_level')
            if isinstance(lvl, str) and lvl in ('ULTRA_LITE','LITE','STANDARD','FULL'):
                ain_settings.output_detail_level = lvl

            # 记忆功能设置
            if 'ai' in config:
                ai = config['ai']
                if 'memory' in ai:
                    memory = ai['memory']
                    if 'enabled' in memory:
                        ain_settings.enable_memory = memory['enabled']
                    if 'target_k' in memory:
                        ain_settings.memory_target_k = memory['target_k']
            
            self.report({'INFO'}, "配置已从文件加载")
        except Exception as e:
            self.report({'ERROR'}, f"加载配置失败: {e}")
            
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
            else:
                ai['provider']['model'] = ain_settings.generic_model

            if 'deepseek' not in ai: ai['deepseek'] = {}
            ai['deepseek']['api_key'] = ain_settings.deepseek_api_key
            ai['deepseek']['model'] = ain_settings.deepseek_model
            ai['deepseek']['url'] = ain_settings.deepseek_url

            if 'ollama' not in ai: ai['ollama'] = {}
            ai['ollama']['url'] = ain_settings.ollama_url
            ai['ollama']['model'] = ain_settings.ollama_model
            
            ai['system_prompt'] = ain_settings.system_prompt
            ai['temperature'] = ain_settings.temperature
            ai['top_p'] = ain_settings.top_p
            # provider_configs writeback
            if 'provider_configs' not in ai: ai['provider_configs'] = {}
            sel = ain_settings.ai_provider
            pcfg = ai['provider_configs'].get(sel, {})
            pcfg['base_url'] = ain_settings.generic_base_url
            pcfg['api_key'] = ain_settings.generic_api_key
            if sel not in ('DEEPSEEK', 'OLLAMA'):
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

            # 回答详细程度提示写回
            existing_config['output_detail_prompts'] = {
                'ULTRA_LITE': ain_settings.prompt_ultra_lite,
                'LITE': ain_settings.prompt_lite,
                'STANDARD': ain_settings.prompt_standard,
                'FULL': ain_settings.prompt_full
            }
            existing_config['output_detail_level'] = ain_settings.output_detail_level

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(existing_config, f, indent=4, ensure_ascii=False)
                
            self.report({'INFO'}, "配置已保存到文件")
        except Exception as e:
            self.report({'ERROR'}, f"保存配置失败: {e}")
            
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
        else:
            model_row.prop(ain_settings, "generic_model", text="模型")
        # 刷新模型按钮
        model_row.operator("node.refresh_models", text="", icon='FILE_REFRESH')

        # 显示可用模型列表
        try:
            models_cache = []
            if ain_settings.ai_provider == 'DEEPSEEK':
                models_cache = deepseek_models_cache
            elif ain_settings.ai_provider == 'OLLAMA':
                models_cache = ollama_models_cache
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
        # 根据连通性状态设置颜色
        if ain_settings.status_connectivity == "可用":
            status_row.label(text=f"连通性: {ain_settings.status_connectivity}", icon='CHECKMARK')
        else:
            status_row.label(text=f"连通性: {ain_settings.status_connectivity}", icon='CANCEL')
        status_row.operator("node.test_provider_status", text="检测连通性", icon='INFO')

        # 提示词工程与精细度控制（整合面板）
        prompt_box = layout.box()
        prompt_box.label(text="提示词工程与精细度控制", icon='TEXT')

        # 身份预设板块
        identity_subbox = prompt_box.box()
        identity_subbox.prop(ain_settings, "identity_key", text="身份预设")
        identity_subbox.prop(ain_settings, "system_prompt", text="系统提示词")

        # 默认提示词板块
        question_subbox = prompt_box.box()
        question_subbox.prop(ain_settings, "default_question_preset", text="默认提示词")
        question_subbox.prop(ain_settings, "default_question", text="自定义问题")

        # 回答精细度控制板块
        detail_subbox = prompt_box.box()
        detail_subbox.prop(ain_settings, "output_detail_level", text="回答精细度")

        # 根据选择的详细程度显示对应的提示词
        if ain_settings.output_detail_level == 'ULTRA_LITE':
            detail_subbox.prop(ain_settings, "prompt_ultra_lite", text="极简提示")
        elif ain_settings.output_detail_level == 'LITE':
            detail_subbox.prop(ain_settings, "prompt_lite", text="简化提示")
        elif ain_settings.output_detail_level == 'STANDARD':
            detail_subbox.prop(ain_settings, "prompt_standard", text="标准提示")
        elif ain_settings.output_detail_level == 'FULL':
            detail_subbox.prop(ain_settings, "prompt_full", text="完整提示")

        # 记忆与思考功能
        memory_subbox = prompt_box.box()
        memory_subbox.label(text="记忆与思考", icon='MEMORY')
        row = memory_subbox.row()
        row.prop(ain_settings, "enable_memory")
        row.prop(ain_settings, "memory_target_k")
        row = memory_subbox.row()
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
        else:
            ain_settings.generic_model = self.model_name
        self.report({'INFO'}, f"已选择模型: {self.model_name}")
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
        self.report({'INFO'}, "API密钥已清空")
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
    bl_description = "使用与Web一致的过滤方法清理选中文本"

    def execute(self, context):
        import bpy
        ain = context.scene.ainode_analyzer_settings
        target = ain.md_clean_target_text or "AINodeAnalysisResult"
        if target not in bpy.data.texts:
            self.report({'WARNING'}, f"未找到文本: {target}")
            return {'CANCELLED'}
        txt = bpy.data.texts[target]
        content = txt.as_string()
        # 调用后端清理接口以复用Web过滤逻辑
        resp = send_to_backend('/api/clean-markdown', data={'content': content}, method='POST')
        cleaned = None
        if resp and isinstance(resp, dict):
            data = resp.get('data') or resp
            cleaned = data.get('cleaned')
        if isinstance(cleaned, str):
            txt.clear()
            txt.write(cleaned)
            self.report({'INFO'}, "已按Web方法清理Markdown")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "清理失败：后端未返回结果")
            return {'CANCELLED'}

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
            filtered = filter_node_description(node_description, ain_settings.filter_level)
            instr = get_output_detail_instruction(ain_settings)
            hdr = f"详细程度:\n{instr}\n\n" if instr else ""
            combined = f"{hdr}系统提示:\n{ain_settings.system_prompt}\n\n问题:\n{ain_settings.user_input}\n\n节点结构:\n{filtered}"
            text_block.write(combined)
            ain_settings.preview_content = combined
        else:
            instr = get_output_detail_instruction(ain_settings)
            hdr = f"详细程度:\n{instr}\n\n" if instr else ""
            combined = f"{hdr}系统提示:\n{ain_settings.system_prompt}\n\n问题:\n{ain_settings.user_input}\n\n节点结构:\nNo nodes selected."
            text_block.write(combined)
            ain_settings.preview_content = combined

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
            filtered_desc = filter_node_description(node_description, ain_settings.filter_level)

            text_block_name = "AINodeAnalysisResult"
            if text_block_name in bpy.data.texts:
                text_block = bpy.data.texts[text_block_name]
            else:
                text_block = bpy.data.texts.new(name=text_block_name)
            base_url = f"http://127.0.0.1:{server_manager.port}" if (server_manager and server_manager.is_running) else ""
            if not base_url:
                self.report({'ERROR'}, "后端未启动，请先启动后端服务器")
                return {'CANCELLED'}
            payload = {
                "question": (get_output_detail_instruction(ain_settings) + "\n\n" + self.user_question).strip(),
                "content": filtered_desc,
                "ai_provider": ain_settings.ai_provider,
                "ai_model": ain_settings.deepseek_model if ain_settings.ai_provider == 'DEEPSEEK' else (ain_settings.ollama_model if ain_settings.ai_provider == 'OLLAMA' else ain_settings.generic_model),
                "ai": {
                    "thinking": {"enabled": bool(getattr(ain_settings, 'enable_thinking', False))},
                    "networking": {"enabled": True},
                    "memory": {"enabled": bool(getattr(ain_settings, 'enable_memory', True)), "target_k": getattr(ain_settings, 'memory_target_k', 4)}
                },
                "nodeContextActive": True
            }
            url = base_url + "/api/stream-analyze"
            try:
                with requests.post(url, json=payload, timeout=300, stream=True) as r:
                    if r.status_code != 200:
                        self.report({'ERROR'}, f"后端错误: {r.status_code}")
                        return {'CANCELLED'}
                    wrote_thinking_header = False
                    for line in r.iter_lines():
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
                ain_settings.current_status = "完成"
                self.report({'INFO'}, f"问题已回答。请在'{text_block_name}'文本块中查看详细信息。")
            except Exception as e:
                self.report({'ERROR'}, f"请求后端时出错: {str(e)}")
                return {'CANCELLED'}

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
    # 注册后端服务器相关运算符
    bpy.utils.register_class(NODE_OT_toggle_backend_server)
    bpy.utils.register_class(NODE_OT_open_backend_webpage)
    bpy.utils.register_class(NODE_OT_test_provider_status)
    bpy.utils.register_class(NODE_OT_reset_provider_url)
    bpy.utils.register_class(NODE_OT_refresh_models)
    bpy.utils.register_class(NODE_OT_clean_markdown_text)
    bpy.utils.register_class(NODE_OT_clear_api_key)
    bpy.utils.register_class(NODE_OT_select_model)

    print("插件UI组件注册完成，开始初始化后端服务器...")
    # 初始化后端服务器（但不自动启动）
    if initialize_backend():
        print("后端服务器初始化成功")
    else:
        print("后端服务器初始化失败")

    # 启动刷新检查器
    start_refresh_checker()
    print("刷新检查器已启动")


# 全局变量来跟踪定时器
refresh_checker_timer = None

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
    # 注销后端服务器相关运算符
    bpy.utils.unregister_class(NODE_OT_toggle_backend_server)
    bpy.utils.unregister_class(NODE_OT_open_backend_webpage)
    bpy.utils.unregister_class(NODE_OT_refresh_models)
    bpy.utils.unregister_class(NODE_OT_reset_provider_url)
    bpy.utils.unregister_class(NODE_OT_test_provider_status)
    bpy.utils.unregister_class(NODE_OT_clean_markdown_text)
    bpy.utils.unregister_class(NODE_OT_clear_api_key)
    bpy.utils.unregister_class(NODE_OT_select_model)

    # 注销面板
    bpy.utils.unregister_class(NODE_PT_ai_analyzer)

    # 注销偏好设置
    bpy.utils.unregister_class(AINodeAnalyzerPreferences)

    # 删除设置属性
    del bpy.types.Scene.ainode_analyzer_settings
    bpy.utils.unregister_class(AINodeAnalyzerSettings)
    print("插件已注销完成")


if __name__ == "__main__":
    register()
