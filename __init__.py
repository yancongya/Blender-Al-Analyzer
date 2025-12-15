"""
AI Node Analyzer - Blender Add-on

This add-on allows users to analyze selected nodes in various node trees
(Geometry Nodes, Shader Nodes, Compositor Nodes) with AI assistance.
"""

import bpy
from bpy.props import (
    StringProperty,
    EnumProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty
)
from bpy.types import (
    Operator,
    Panel,
    AddonPreferences,
    PropertyGroup
)
import requests
import json
import threading
import subprocess
import sys
import os


def call_litellm_completion(model, messages, api_key=None, base_url=None, **kwargs):
    """使用litellm调用AI完成"""
    try:
        import litellm
    except ImportError:
        return "Error: litellm module is not installed. To use this feature, install it: pip install litellm in Blender's Python environment."

    # 设置API密钥和基础URL
    if api_key:
        # 根据模型类型设置相应的API密钥
        if "deepseek" in model.lower():
            litellm.api_key = api_key
            if base_url:
                # 为DeepSeek设置基础URL
                import os
                os.environ["DEEPSEEK_API_BASE"] = base_url
        elif "ollama" in model.lower() or model in ["llama3", "mistral", "phi3", "gemma2", "mixtral"]:
            if base_url:
                import os
                os.environ["OLLAMA_API_BASE"] = base_url

    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            api_key=api_key,
            **kwargs
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LiteLLM API error: {e}")
        return f"Error: {str(e)}"


def is_litellm_available():
    """检查litellm是否可用"""
    try:
        import litellm
        return True
    except ImportError:
        return False

def ensure_dependencies():
    """确保依赖已安装，如果未安装则尝试安装"""
    if is_litellm_available():
        return True

    # 尝试安装依赖
    success = check_and_install_dependencies()

    # 重新检查是否可用
    if success and is_litellm_available():
        return True
    else:
        return False

def get_blender_python_path():
    """获取Blender的Python路径"""
    import sys
    import os
    return sys.executable

def install_package(package_name):
    """安装Python包到Blender的Python环境中"""
    python_exe = get_blender_python_path()
    try:
        subprocess.check_call([python_exe, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError:
        return False

def install_requirements_from_file(requirements_path):
    """从requirements.txt文件安装依赖包"""
    python_exe = get_blender_python_path()
    try:
        subprocess.check_call([python_exe, "-m", "pip", "install", "-r", requirements_path])
        return True
    except subprocess.CalledProcessError:
        return False

def check_and_install_dependencies():
    """检查并安装缺失的依赖"""
    missing_packages = []

    # 检查litellm
    try:
        import litellm
    except ImportError:
        missing_packages.append("litellm")

    # 检查openai (如果需要使用OpenAI兼容的API如DeepSeek)
    try:
        import openai
    except ImportError:
        missing_packages.append("openai")

    # 如果有缺失的包，尝试安装它们
    if missing_packages:
        print(f"检测到缺失的包: {missing_packages}")

        # 构建requirements.txt在插件目录中的路径
        addon_dir = os.path.dirname(__file__)
        req_file = os.path.join(addon_dir, "requirements.txt")

        # 如果requirements.txt存在，使用它安装所有依赖
        if os.path.exists(req_file):
            print("正在从requirements.txt安装依赖...")
            if install_requirements_from_file(req_file):
                print("依赖安装成功")
                return True
            else:
                print("从requirements.txt安装失败")
                # 尝试逐个安装缺失的包
                for pkg in missing_packages:
                    print(f"正在尝试安装 {pkg}...")
                    if install_package(pkg):
                        print(f"{pkg} 安装成功")
                    else:
                        print(f"{pkg} 安装失败")
                return False
        else:
            # 逐个安装缺失的包
            success_count = 0
            for pkg in missing_packages:
                print(f"正在尝试安装 {pkg}...")
                if install_package(pkg):
                    print(f"{pkg} 安装成功")
                    success_count += 1
                else:
                    print(f"{pkg} 安装失败")

            return success_count == len(missing_packages)

    return True  # 所有依赖都已存在

def call_ai_service(provider_type, messages, model, api_key, base_url=None, **kwargs):
    """使用litellm调用AI服务"""
    if not ensure_dependencies():
        # 提供安装litellm到Blender环境的指导
        blender_python_path = get_blender_python_path()
        return f"Error: 无法安装或导入litellm模块。请尝试手动安装: '{blender_python_path}' -m pip install -r requirements.txt"

    # 根据provider_type和model构建完整的模型名称
    if provider_type == 'DEEPSEEK':
        # 为DeepSeek使用适当的模型名称
        full_model_name = f"deepseek/{model}"
        if base_url:
            # 如果提供了自定义base_url，则使用它
            import os
            os.environ["DEEPSEEK_API_BASE"] = base_url
    elif provider_type == 'OLLAMA':
        # Ollama模型格式: ollama/{model}
        full_model_name = f"ollama/{model}"
        if base_url:
            # 为Ollama设置基础URL，确保使用正确的聊天端点
            import os
            # 移除末尾的/chat，因为我们使用完整的API路径
            base_url = base_url.rstrip('/chat').rstrip('/')
            os.environ["OLLAMA_API_BASE"] = f"{base_url}/api/chat"
    else:
        # 如果没有特定的provider_type，则直接使用model名称
        full_model_name = model

    return call_litellm_completion(
        model=full_model_name,
        messages=messages,
        api_key=api_key,
        base_url=base_url,
        **kwargs
    )


# 插件基本信息
bl_info = {
    "name": "AI Node Analyzer",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "Node Editor > Sidebar > AI Node Analyzer",
    "description": "Analyze selected nodes with AI assistance",
    "category": "Node",
    "doc_url": "./INSTALL.md",  # 指向安装说明文档
    "tracker_url": ""
}


class AINodeAnalyzerSettings(PropertyGroup):
    """插件设置属性组"""

    # AI服务提供商选择
    ai_provider: EnumProperty(
        name="AI Provider",
        description="选择AI服务提供商",
        items=[
            ('DEEPSEEK', 'DeepSeek (需要openai)', 'DeepSeek API - 需要openai模块'),
            ('OLLAMA', 'Ollama (无需额外模块)', '本地Ollama API - 无需额外模块'),
        ],
        default='OLLAMA'  # 默认为Ollama，因为它不需要额外模块
    )

    # DeepSeek相关
    deepseek_api_key: StringProperty(
        name="DeepSeek API密钥",
        description="输入您的DeepSeek API密钥",
        subtype='PASSWORD'
    )

    # Ollama相关
    ollama_base_url: StringProperty(
        name="Ollama基础URL",
        description="输入Ollama API基础URL",
        default="http://localhost:11434/api"
    )

    # AI模型选择 - 所有模型选项（通过UI提示和验证来"过滤"）
    ai_model: EnumProperty(
        name="AI模型",
        description="根据提供商选择AI模型（先选择提供商）",
        items=[
            # DeepSeek Models
            ('deepseek-chat', 'DeepSeek Chat', 'DeepSeek Chat模型'),
            ('deepseek-coder', 'DeepSeek Coder', 'DeepSeek Coder模型'),

            # Ollama Models
            ('llama3', 'Llama 3', '通过Ollama的Llama 3模型'),
            ('mistral', 'Mistral', '通过Ollama的Mistral模型'),
            ('phi3', 'Phi-3', '通过Ollama的Phi-3模型'),
            ('gemma2', 'Gemma 2', '通过Ollama的Gemma 2模型'),
            ('mixtral', 'Mixtral', '通过Ollama的Mixtral模型'),
        ],
        default='llama3'  # 默认为Ollama的llama3，因为它不需要额外模块
    )

    # 系统提示词
    system_prompt: StringProperty(
        name="系统提示词",
        description="AI的自定义系统提示",
        default="您是Blender节点的专家。分析以下节点结构并提供见解、优化或解释。您可以使用网络搜索或提供的知识库来准确回答。"
    )

    # 启用联网检索
    enable_web_search: BoolProperty(
        name="启用网络搜索",
        description="启用网络搜索以增强AI响应",
        default=False
    )

    # 搜索API选择
    search_api: EnumProperty(
        name="搜索API",
        description="选择要使用的搜索API",
        items=[
            ('TAVILY', 'Tavily', 'Tavily搜索API'),
            ('EXA', 'Exa', 'Exa搜索API'),
            ('BRAVE', 'Brave搜索', 'Brave搜索API'),
            ('NONE', '无', '无网络搜索')
        ],
        default='NONE'
    )

    # 搜索API密钥
    tavily_api_key: StringProperty(
        name="Tavily API密钥",
        description="输入您的Tavily API密钥",
        subtype='PASSWORD'
    )

    exa_api_key: StringProperty(
        name="Exa API密钥",
        description="输入您的Exa API密钥",
        subtype='PASSWORD'
    )

    brave_api_key: StringProperty(
        name="Brave API密钥",
        description="输入您的Brave API密钥",
        subtype='PASSWORD'
    )


class NODE_OT_analyze_with_ai(Operator):
    """分析选中的节点与AI交互的算子"""
    bl_idname = "node.analyze_with_ai"
    bl_label = "Analyze Selected Nodes with AI"
    bl_description = "Analyze selected nodes using AI"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 实现分析功能的核心逻辑
        self.report({'INFO'}, "开始AI分析...")

        # 获取当前节点树
        space = context.space_data
        if not hasattr(space, 'node_tree'):
            self.report({'ERROR'}, "当前编辑器中未找到节点树")
            return {'CANCELLED'}

        node_tree = space.node_tree
        if not node_tree:
            self.report({'ERROR'}, "没有活动的节点树")
            return {'CANCELLED'}

        # 获取选中的节点
        selected_nodes = context.selected_nodes
        if not selected_nodes:
            if context.active_node:
                selected_nodes = [context.active_node]
                self.report({'INFO'}, f"未选择节点，使用活动节点: {context.active_node.name}")
            else:
                self.report({'ERROR'}, "未选择节点且无活动节点")
                return {'CANCELLED'}

        # 获取插件设置
        addon_prefs = context.scene.ainode_analyzer_settings

        # 执行节点分析
        try:
            node_analysis = self.analyze_nodes(context, selected_nodes)
            if not node_analysis:
                self.report({'WARNING'}, "节点分析未返回结果")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"节点分析时发生错误: {str(e)}")
            return {'CANCELLED'}

        # 获取AI配置
        provider_type = addon_prefs.ai_provider

        # 确保依赖已安装
        if not ensure_dependencies():
            blender_python_path = get_blender_python_path()
            self.report({'ERROR'}, f"无法安装所需的依赖包。请尝试手动安装: '{blender_python_path}' -m pip install -r requirements.txt")
            return {'CANCELLED'}

        model = addon_prefs.ai_model

        # 验证模型与提供商的兼容性
        if provider_type == 'DEEPSEEK':
            deepseek_models = ['deepseek-chat', 'deepseek-coder']
            if model not in deepseek_models:
                self.report({'ERROR'}, f"模型 {model} 与 DeepSeek 提供商不兼容。请使用: {', '.join(deepseek_models)}")
                return {'CANCELLED'}
        elif provider_type == 'OLLAMA':
            ollama_models = ['llama3', 'mistral', 'phi3', 'gemma2', 'mixtral']
            if model not in ollama_models:
                self.report({'ERROR'}, f"模型 {model} 与 Ollama 提供商不兼容。请使用: {', '.join(ollama_models)}")
                return {'CANCELLED'}

        # 根据服务提供商获取相应的API密钥和基础URL
        api_key = None
        base_url = None

        if provider_type == 'DEEPSEEK':
            api_key = addon_prefs.deepseek_api_key
        elif provider_type == 'OLLAMA':
            base_url = addon_prefs.ollama_base_url

        # 检查是否提供了API密钥
        if not api_key and provider_type != 'OLLAMA':
            self.report({'ERROR'}, f"{provider_type} 提供商需要API密钥")
            return {'CANCELLED'}

        # 获取节点树类型和Blender版本信息
        node_tree_type = self.get_node_tree_type_description(context)
        blender_version = bpy.app.version_string

        # 构建增强的系统提示词
        enhanced_system_prompt = f"{addon_prefs.system_prompt}\n\n上下文信息: 当前Blender版本 {blender_version}，节点类型 {node_tree_type}。请根据具体的节点类型提供针对性的分析。"

        # 构建消息
        messages = [
            {"role": "system", "content": enhanced_system_prompt},
            {"role": "user", "content": f"节点分析:\n{node_analysis}"}
        ]

        # 如果启用了网络搜索，执行搜索并将结果添加到消息中
        if addon_prefs.enable_web_search and addon_prefs.search_api != 'NONE':
            search_results = self.perform_web_search(node_analysis, addon_prefs)
            if search_results:
                search_content = f"\n\n搜索结果:\n{search_results}"
                # 更新用户消息以包含搜索结果
                messages[-1]["content"] += search_content

        # 准备AI请求参数
        ai_kwargs = {
            "temperature": 0.7,
            "max_tokens": 2000
        }

        # 调用AI服务
        try:
            self.report({'INFO'}, f"正在调用AI服务: {provider_type} / {model}")
            result = call_ai_service(
                provider_type=provider_type,
                messages=messages,
                model=model,
                api_key=api_key,
                base_url=base_url,
                **ai_kwargs
            )

            if result and not result.startswith("Error:"):
                self.report({'INFO'}, f"AI分析完成")
                # 将结果保存到文本块并存储在场景属性中以供UI显示
                self.save_result_to_text_block(context, result)
                # 将结果存储到场景属性中，以便在UI中显示
                context.scene.ainode_analysis_result = result
            else:
                self.report({'ERROR'}, f"AI服务错误: {result}")
                return {'CANCELLED'}

        except Exception as e:
            self.report({'ERROR'}, f"调用AI服务时出错: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}

    def get_node_tree_type_description(self, context):
        """获取节点树类型描述"""
        space = context.space_data
        if hasattr(space, 'node_tree') and space.node_tree:
            tree_type = space.tree_type
            if tree_type == 'GeometryNodeTree':
                return '几何节点 (Geometry Nodes)'
            elif tree_type == 'ShaderNodeTree':
                return '着色器节点 (Shader Nodes)'
            elif tree_type == 'CompositorNodeTree':
                return '合成节点 (Compositor Nodes)'
            elif tree_type == 'TextureNodeTree':
                return '纹理节点 (Texture Nodes)'
            elif tree_type == 'LineStyleNodeTree':
                return '线条样式节点 (Line Style Nodes)'
            else:
                return f'未知节点类型 ({tree_type})'
        return '未知节点类型'

    def perform_web_search(self, node_analysis, addon_prefs):
        """执行网络搜索"""
        # 根据解析的节点描述生成一个搜索查询
        node_tree_type = self.get_node_tree_type_description(bpy.context)
        query = f"Blender {node_tree_type} setup optimization guide for: {node_analysis[:200]}..."

        api_key = None
        if addon_prefs.search_api == 'TAVILY':
            api_key = addon_prefs.tavily_api_key
            url = "https://api.tavily.com/search"
        elif addon_prefs.search_api == 'EXA':
            api_key = addon_prefs.exa_api_key
            url = "https://api.exa.ai/search"  # 示例URL，实际可能不同
        elif addon_prefs.search_api == 'BRAVE':
            api_key = addon_prefs.brave_api_key
            url = "https://api.search.brave.com/res/v1/web/search"  # 示例URL
        else:
            return None

        if not api_key:
            self.report({'WARNING'}, f"API Key required for {addon_prefs.search_api} search")
            return None

        # 根据不同的搜索API格式发送请求
        if addon_prefs.search_api == 'TAVILY':
            data = {
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": True,
                "include_domains": [],
                "exclude_domains": [],
                "max_results": 3
            }
        elif addon_prefs.search_api == 'EXA':
            # Exa AI的请求格式可能不同
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key
            }
            data = {
                "query": query,
                "type": "neural",
                "size": 3
            }
            # 直接发起请求
            try:
                response = requests.post(url, headers={"x-api-key": api_key}, json=data)
                response.raise_for_status()
                search_data = response.json()
                # 简化处理Exa的结果
                results = []
                if 'results' in search_data:
                    for item in search_data['results'][:3]:  # 取前3个结果
                        if 'title' in item and 'content' in item:
                            results.append(f"Title: {item['title']}\nContent: {item['content']}")
                return "\n\n".join(results) if results else None
            except Exception as e:
                self.report({'WARNING'}, f"Exa search error: {str(e)}")
                return None
        elif addon_prefs.search_api == 'BRAVE':
            # Brave搜索使用GET请求和查询参数
            headers = {"X-Subscription-Token": api_key}
            params = {"q": query, "count": 3}
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                search_data = response.json()
                # 简化处理Brave的结果
                results = []
                if 'web' in search_data and 'results' in search_data['web']:
                    for item in search_data['web']['results'][:3]:
                        if 'title' in item and 'description' in item:
                            results.append(f"Title: {item['title']}\nDescription: {item['description']}")
                return "\n\n".join(results) if results else None
            except Exception as e:
                self.report({'WARNING'}, f"Brave search error: {str(e)}")
                return None

        # 对于Tavily等使用POST请求的API
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            search_data = response.json()

            # 提取结果
            results = []
            if 'results' in search_data:
                for item in search_data['results'][:3]:  # 取前3个结果
                    if 'content' in item:
                        results.append(f"Content: {item['content']}\nURL: {item.get('url', 'N/A')}")
            elif 'data' in search_data:  # 兼容不同API的返回格式
                for item in search_data['data'][:3]:
                    if 'content' in item:
                        results.append(f"Content: {item['content']}\nURL: {item.get('url', 'N/A')}")

            return "\n\n".join(results) if results else None
        except Exception as e:
            self.report({'WARNING'}, f"Search API error: {str(e)}")
            return None

    def save_result_to_text_block(self, context, result):
        """将结果保存到文本块"""
        # 检查是否已存在名为"AI Analysis Result"的文本块
        text_block_name = "AI Analysis Result"
        if text_block_name in bpy.data.texts:
            text_block = bpy.data.texts[text_block_name]
            text_block.clear()  # 清空现有内容
        else:
            text_block = bpy.data.texts.new(text_block_name)

        text_block.write(result)

        self.report({'INFO'}, f"AI analysis result saved to text block: {text_block_name}")

    def analyze_nodes(self, context, selected_nodes):
        """分析选中的节点"""
        # 这里是分析节点的核心逻辑，将在下一阶段实现
        node_info = []
        links_info = []

        # 获取当前节点树
        space = context.space_data
        node_tree = space.node_tree

        # 收集所有相关链接（包括选中节点之间的和与选中节点相连的其他节点）
        all_links = []
        selected_node_names = {node.name for node in selected_nodes}

        for link in node_tree.links:
            # 如果链接的一端或两端都在选中的节点中，就记录该链接
            if link.from_node.name in selected_node_names or link.to_node.name in selected_node_names:
                all_links.append(link)

        # 解析选中节点的信息
        for node in selected_nodes:
            node_dict = {
                'name': node.name,
                'label': node.label,
                'type': node.type,
                'bl_idname': node.bl_idname,  # 添加节点的bl_idname
                'location': (round(node.location.x, 2), round(node.location.y, 2)),
                'color': node.color[:],  # 节点颜色
                'use_custom_color': node.use_custom_color,  # 是否使用自定义颜色
                'dimensions': (node.dimensions.x, node.dimensions.y),  # 节点尺寸
                'inputs': [],
                'outputs': []
            }

            # 收集输入插座信息
            for input_socket in node.inputs:
                input_info = {
                    'name': input_socket.name,
                    'type': input_socket.type,
                    'enabled': input_socket.enabled,
                    'hide': input_socket.hide,
                    'hide_value': input_socket.hide_value,
                    'is_linked': input_socket.is_linked,
                    'link_count': len(input_socket.links)
                }
                # 如果有默认值，也收集
                if hasattr(input_socket, 'default_value'):
                    try:
                        # 处理不同类型的default_value
                        if isinstance(input_socket.default_value, (int, float)):
                            input_info['default_value'] = input_socket.default_value
                        elif hasattr(input_socket.default_value, '__len__') and len(input_socket.default_value) <= 4:
                            # 对于向量等序列类型，转换为列表
                            input_info['default_value'] = list(input_socket.default_value)
                        else:
                            input_info['default_value'] = str(input_socket.default_value)
                    except:
                        input_info['default_value'] = str(input_socket.default_value)

                # 记录链接到这个输入的信息
                if input_socket.is_linked:
                    for link in input_socket.links:
                        input_info['linked_from'] = {
                            'from_node': link.from_node.name,
                            'from_socket': link.from_socket.name
                        }

                node_dict['inputs'].append(input_info)

            # 收集输出插座信息
            for output_socket in node.outputs:
                output_info = {
                    'name': output_socket.name,
                    'type': output_socket.type,
                    'enabled': output_socket.enabled,
                    'hide': output_socket.hide,
                    'hide_value': output_socket.hide_value,
                    'is_linked': output_socket.is_linked,
                    'link_count': len(output_socket.links)
                }

                # 记录从这个输出链接到的信息
                if output_socket.is_linked:
                    linked_to = []
                    for link in output_socket.links:
                        linked_to.append({
                            'to_node': link.to_node.name,
                            'to_socket': link.to_socket.name
                        })
                    output_info['linked_to'] = linked_to

                node_dict['outputs'].append(output_info)

            # 特殊处理节点组
            if node.type == 'GROUP':
                if hasattr(node, 'node_tree') and node.node_tree:
                    node_dict['group_info'] = self.analyze_group_node(node.node_tree, node)

            node_info.append(node_dict)

        # 解析链接信息
        for link in all_links:
            link_info = {
                'from_node': link.from_node.name,
                'from_socket': link.from_socket.name,
                'to_node': link.to_node.name,
                'to_socket': link.to_socket.name,
                'from_socket_type': link.from_socket.type,  # 从输出插座获取类型
                'to_socket_type': link.to_socket.type  # 到输入插座的类型
            }
            links_info.append(link_info)

        # 组合结果
        result = {
            'node_tree_type': node_tree.bl_idname if hasattr(node_tree, 'bl_idname') else 'Unknown',
            'selected_nodes_count': len(selected_nodes),
            'nodes': node_info,
            'links': links_info
        }

        import json
        return json.dumps(result, indent=2, default=str)

    def analyze_group_node(self, group_tree, original_node):
        """递归分析节点组内部的节点"""
        group_info = {
            'name': group_tree.name,
            'nodes': [],
            'links': []
        }

        # 分析节点组内的所有节点
        for node in group_tree.nodes:
            node_dict = {
                'name': node.name,
                'label': node.label,
                'type': node.type,
                'bl_idname': node.bl_idname,
                'location': (round(node.location.x, 2), round(node.location.y, 2)),
                'color': node.color[:],
                'use_custom_color': node.use_custom_color,
                'inputs': [],
                'outputs': []
            }

            # 收集输入插座信息
            for input_socket in node.inputs:
                input_info = {
                    'name': input_socket.name,
                    'type': input_socket.type,
                    'enabled': input_socket.enabled,
                    'hide': input_socket.hide,
                    'hide_value': input_socket.hide_value,
                    'is_linked': input_socket.is_linked,
                    'link_count': len(input_socket.links)
                }
                if hasattr(input_socket, 'default_value'):
                    try:
                        if isinstance(input_socket.default_value, (int, float)):
                            input_info['default_value'] = input_socket.default_value
                        elif hasattr(input_socket.default_value, '__len__') and len(input_socket.default_value) <= 4:
                            input_info['default_value'] = list(input_socket.default_value)
                        else:
                            input_info['default_value'] = str(input_socket.default_value)
                    except:
                        input_info['default_value'] = str(input_socket.default_value)

                node_dict['inputs'].append(input_info)

            # 收集输出插座信息
            for output_socket in node.outputs:
                output_info = {
                    'name': output_socket.name,
                    'type': output_socket.type,
                    'enabled': output_socket.enabled,
                    'hide': output_socket.hide,
                    'hide_value': output_socket.hide_value,
                    'is_linked': output_socket.is_linked,
                    'link_count': len(output_socket.links)
                }
                node_dict['outputs'].append(output_info)

            # 如果组内还有节点组，继续递归
            if node.type == 'GROUP':
                if hasattr(node, 'node_tree') and node.node_tree:
                    node_dict['group_info'] = self.analyze_group_node(node.node_tree, node)

            group_info['nodes'].append(node_dict)

        # 收集节点组内的链接信息
        for link in group_tree.links:
            link_info = {
                'from_node': link.from_node.name,
                'from_socket': link.from_socket.name,
                'to_node': link.to_node.name,
                'to_socket': link.to_socket.name,
                'from_socket_type': link.from_socket.type,  # 从输出插座获取类型
                'to_socket_type': link.to_socket.type  # 到输入插座的类型
            }
            group_info['links'].append(link_info)

        return group_info


class NODE_OT_install_dependencies(Operator):
    """安装插件依赖的操作符"""
    bl_idname = "node.install_dependencies"
    bl_label = "Install Required Dependencies"
    bl_description = "Install required Python packages for the addon"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 尝试安装依赖
        success = check_and_install_dependencies()

        if success:
            self.report({'INFO'}, "依赖包安装成功！")
        else:
            self.report({'ERROR'}, "依赖包安装失败，请手动安装。")

        return {'FINISHED'}

class TEXT_OT_open_analysis_result(Operator):
    """在文本编辑器中打开AI分析结果"""
    bl_idname = "text.open_analysis_result"
    bl_label = "打开AI分析结果"
    bl_description = "在文本编辑器中打开完整的AI分析结果"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # 获取存储的分析结果
        result = context.scene.ainode_analysis_result

        if not result:
            self.report({'WARNING'}, "没有AI分析结果可显示")
            return {'CANCELLED'}

        # 检查是否存在名为"AI Analysis Result"的文本块
        text_name = "AI分析结果"
        if text_name in bpy.data.texts:
            text_block = bpy.data.texts[text_name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(text_name)

        text_block.write(result)

        # 尝试切换到脚本编辑器工作区以显示文本
        for window in context.window_manager.windows:
            screen = window.screen
            for area in screen.areas:
                if area.type == 'TEXT_EDITOR':
                    area.spaces[0].text = text_block
                    break
            else:
                # 如果没有文本编辑器区域，提示用户切换到脚本工作区
                self.report({'INFO'}, f"结果已保存到'{text_name}'文本块中，请切换到脚本工作区查看")

        return {'FINISHED'}

class NODE_OT_edit_system_prompt(Operator):
    """编辑系统提示词的操作符"""
    bl_idname = "node.edit_system_prompt"
    bl_label = "编辑系统提示词"
    bl_description = "打开系统提示词编辑面板"
    bl_options = {'REGISTER', 'INTERNAL'}

    # 添加一个文本属性用于编辑提示词
    system_prompt: StringProperty(
        name="系统提示词",
        description="AI的系统提示词，将包含Blender版本和节点类型信息",
        default="您是Blender节点的专家。分析以下节点结构并提供见解、优化或解释。您可以使用网络搜索或提供的知识库来准确回答。",
        maxlen=2048
    )

    def invoke(self, context, event):
        # 初始化编辑器中的当前系统提示词
        addon_prefs = context.scene.ainode_analyzer_settings
        self.system_prompt = addon_prefs.system_prompt
        return context.window_manager.invoke_props_dialog(self, width=600)

    def execute(self, context):
        # 保存更改后的系统提示词
        addon_prefs = context.scene.ainode_analyzer_settings
        addon_prefs.system_prompt = self.system_prompt
        self.report({'INFO'}, "系统提示词已更新")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        # 显示当前Blender版本和节点类型
        node_tree_type = "未知"
        space = context.space_data
        if hasattr(space, 'node_tree') and space.node_tree:
            node_tree_type = space.tree_type

        col.label(text=f"Blender版本: {bpy.app.version_string}", icon='BLENDER')
        col.label(text=f"节点类型: {node_tree_type}", icon='NODETREE')

        col.separator()

        # 显示编辑器
        col.prop(self, "system_prompt", text="系统提示词", translate=False)

        # 添加一些预设提示词的按钮
        preset_col = col.column(align=True)
        preset_col.label(text="预设提示词:", icon='PRESET')

        row = preset_col.row(align=True)
        row.operator("node.load_geo_nodes_prompt", text="几何节点", icon='GEOMETRY_NODES')
        row.operator("node.load_shader_nodes_prompt", text="着色器节点", icon='SHADERNODE')
        row.operator("node.load_compositor_nodes_prompt", text="合成节点", icon='COMPOSITING_NODES')

class NODE_OT_load_geo_nodes_prompt(Operator):
    """加载几何节点预设提示词"""
    bl_idname = "node.load_geo_nodes_prompt"
    bl_label = "几何节点预设"
    bl_description = "加载适合几何节点的预设提示词"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        # 获取编辑器中的操作符引用，设置预设提示词
        # 由于不能直接访问调用它的对话框，我们使用场景属性进行通信
        context.scene.ainode_temp_prompt = "您是Blender几何节点的专家。仔细分析以下几何节点结构，评估其效率、功能和潜在优化方案。提供关于节点连接、域、几何体处理、实例化等方面的详细见解和改进建议。"
        context.window_manager.clipboard = context.scene.ainode_temp_prompt  # 临时复制到剪贴板
        self.report({'INFO'}, "几何节点预设提示词已复制到剪贴板")
        return {'FINISHED'}

class NODE_OT_load_shader_nodes_prompt(Operator):
    """加载着色器节点预设提示词"""
    bl_idname = "node.load_shader_nodes_prompt"
    bl_label = "着色器节点预设"
    bl_description = "加载适合着色器节点的预设提示词"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        context.scene.ainode_temp_prompt = "您是Blender着色器节点的专家。分析以下着色器节点设置，评估其材质结构、纹理映射、光照效果和性能。提供关于节点组织、连接效率、物理准确性以及视觉质量优化的具体建议。"
        context.window_manager.clipboard = context.scene.ainode_temp_prompt
        self.report({'INFO'}, "着色器节点预设提示词已复制到剪贴板")
        return {'FINISHED'}

class NODE_OT_load_compositor_nodes_prompt(Operator):
    """加载合成节点预设提示词"""
    bl_idname = "node.load_compositor_nodes_prompt"
    bl_label = "合成节点预设"
    bl_description = "加载适合合成节点的预设提示词"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        context.scene.ainode_temp_prompt = "您是Blender合成节点的专家。分析以下合成节点设置，评估其图像处理流程、遮码使用、颜色校正和输出质量。提供关于节点连接、处理顺序、性能优化以及视觉效果增强的具体建议。"
        context.window_manager.clipboard = context.scene.ainode_temp_prompt
        self.report({'INFO'}, "合成节点预设提示词已复制到剪贴板")
        return {'FINISHED'}

class NODE_PT_ai_node_analyzer(Panel):
    """AI Node Analyzer面板"""
    bl_label = "AI节点分析器"
    bl_idname = "NODE_PT_ai_node_analyzer"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AI Node Analyzer"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 获取插件设置
        addon_prefs = scene.ainode_analyzer_settings

        # 依赖安装部分
        if not is_litellm_available():
            box = layout.box()
            box.label(text="依赖安装", icon='IMPORT')
            row = box.row()
            row.operator(NODE_OT_install_dependencies.bl_idname, text="一键安装依赖", icon='CONSOLE')
            blender_python_path = get_blender_python_path()
            box.label(text="需要安装: litellm, openai", icon='INFO')
            box.label(text=f"或手动运行: '{blender_python_path}' -m pip install -r requirements.txt", icon='INFO')
            layout.separator()

        # API配置
        box = layout.box()
        box.label(text="API配置", icon='PREFERENCES')

        # AI服务提供商选择
        row = box.row()
        row.prop(addon_prefs, "ai_provider", expand=True)

        # 根据选择的服务商显示相应的API密钥和配置
        if addon_prefs.ai_provider == 'DEEPSEEK':
            box.prop(addon_prefs, "deepseek_api_key")
        elif addon_prefs.ai_provider == 'OLLAMA':
            box.prop(addon_prefs, "ollama_base_url")

        # AI模型选择
        box.separator()
        row = box.row()
        row.prop(addon_prefs, "ai_model", text="模型")

        # 显示当前服务商可用的模型提示
        if addon_prefs.ai_provider == 'DEEPSEEK':
            box.label(text="DeepSeek模型: deepseek-chat, deepseek-coder", icon='INFO')
        elif addon_prefs.ai_provider == 'OLLAMA':
            box.label(text="Ollama模型: llama3, mistral, phi3, gemma2, mixtral", icon='INFO')

        # 系统提示词
        box.separator()
        row = box.row()
        row.prop(addon_prefs, "system_prompt", text="系统提示词")
        row.operator(NODE_OT_edit_system_prompt.bl_idname, text="", icon='TEXT')

        # 网络搜索设置
        col = box.column()
        col.prop(addon_prefs, "enable_web_search")

        if addon_prefs.enable_web_search:
            col.prop(addon_prefs, "search_api")

            # 根据选择显示相应的API密钥输入
            if addon_prefs.search_api == 'TAVILY':
                col.prop(addon_prefs, "tavily_api_key")
            elif addon_prefs.search_api == 'EXA':
                col.prop(addon_prefs, "exa_api_key")
            elif addon_prefs.search_api == 'BRAVE':
                col.prop(addon_prefs, "brave_api_key")

        # 分析按钮
        layout.separator()
        col = layout.column()
        col.operator(NODE_OT_analyze_with_ai.bl_idname, text="使用AI分析选中节点", icon='PLAY')

        # 显示AI分析结果
        if scene.ainode_analysis_result:
            layout.separator()
            result_box = layout.box()
            result_box.label(text="AI分析结果", icon='TEXT')

            # 显示结果的前几行，如果太长则截断
            result_lines = scene.ainode_analysis_result.split('\n')
            for i, line in enumerate(result_lines[:10]):  # 显示前10行
                result_box.label(text=line[:80] + ("..." if len(line) > 80 else ""))  # 每行最多显示80个字符

            if len(result_lines) > 10:
                result_box.label(text=f"... 还有 {len(result_lines) - 10} 行", icon='FILE_TEXT')

            # 提供一个按钮来在文本编辑器中打开完整结果
            result_box.operator(TEXT_OT_open_analysis_result.bl_idname, text="在文本编辑器中查看完整结果", icon='WINDOW')


def register():
    """注册插件"""
    bpy.utils.register_class(AINodeAnalyzerSettings)
    bpy.utils.register_class(NODE_OT_analyze_with_ai)
    bpy.utils.register_class(NODE_OT_install_dependencies)  # 新增：依赖安装操作符
    bpy.utils.register_class(TEXT_OT_open_analysis_result)  # 新增：打开分析结果操作符
    bpy.utils.register_class(NODE_OT_edit_system_prompt)  # 新增：编辑系统提示词操作符
    bpy.utils.register_class(NODE_OT_load_geo_nodes_prompt)  # 新增：几何节点预设
    bpy.utils.register_class(NODE_OT_load_shader_nodes_prompt)  # 新增：着色器节点预设
    bpy.utils.register_class(NODE_OT_load_compositor_nodes_prompt)  # 新增：合成节点预设
    bpy.utils.register_class(NODE_PT_ai_node_analyzer)

    # 注册场景属性
    bpy.types.Scene.ainode_analyzer_settings = bpy.props.PointerProperty(type=AINodeAnalyzerSettings)
    # 添加用于存储AI分析结果的属性
    bpy.types.Scene.ainode_analysis_result = bpy.props.StringProperty(
        name="AI分析结果",
        description="存储AI分析结果",
        default=""
    )
    # 添加临时提示词存储属性
    bpy.types.Scene.ainode_temp_prompt = bpy.props.StringProperty(
        name="临时提示词",
        description="用于临时存储预设提示词",
        default=""
    )


def unregister():
    """注销插件"""
    bpy.utils.unregister_class(AINodeAnalyzerSettings)
    bpy.utils.unregister_class(NODE_OT_analyze_with_ai)
    bpy.utils.unregister_class(NODE_OT_install_dependencies)  # 新增：依赖安装操作符
    bpy.utils.unregister_class(TEXT_OT_open_analysis_result)  # 新增：打开分析结果操作符
    bpy.utils.unregister_class(NODE_OT_edit_system_prompt)  # 新增：编辑系统提示词操作符
    bpy.utils.unregister_class(NODE_OT_load_geo_nodes_prompt)  # 新增：几何节点预设
    bpy.utils.unregister_class(NODE_OT_load_shader_nodes_prompt)  # 新增：着色器节点预设
    bpy.utils.unregister_class(NODE_OT_load_compositor_nodes_prompt)  # 新增：合成节点预设
    bpy.utils.unregister_class(NODE_PT_ai_node_analyzer)

    # 删除场景属性
    del bpy.types.Scene.ainode_analyzer_settings
    del bpy.types.Scene.ainode_analysis_result
    del bpy.types.Scene.ainode_temp_prompt


# 如果直接运行此脚本，则注册插件
if __name__ == "__main__":
    register()