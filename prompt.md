你是一个资深的Blender Python插件开发专家，熟悉Blender 4.2+版本的bpy API。
请帮我开发一个Blender addon插件，名为"AI Node Analyzer"，功能是：在节点编辑器（支持Geometry Nodes、Shader Nodes、Compositor Nodes等多种节点树类型）中，当用户选中一个或多个节点（包括节点组Node Group）时，点击插件面板中的按钮，能将选中的节点/节点组结构解析成详细的文本描述，然后发送给AI模型（默认使用OpenAI的GPT-4o或gpt-4o-mini）进行分析或操作。同时，支持联网检索（让AI能上网搜索最新信息）和自定义知识库（上传文档、链接等作为专有知识），以提升AI响应的准确性和实用性。
具体要求：

插件结构：
使用标准的Blender addon模板，包括bl_info、register/unregister函数。
在节点编辑器的侧边栏（N面板）添加一个自定义Panel，标题为"AI Node Analyzer"。
面板中提供：
一个StringProperty输入框，用于用户填写OpenAI API Key（默认隐藏或保存到addon preferences）。
一个EnumProperty选择AI模型（选项：gpt-4o, gpt-4o-mini, gpt-3.5-turbo）。
一个文本输入框，用于用户自定义系统提示（system prompt），默认提示为："You are an expert in Blender nodes. Analyze the following node structure and provide insights, optimizations, or explanations. You can use web search or provided knowledge base to answer accurately."
一个BoolProperty开关：启用联网检索（默认关闭）。
EnumProperty选择搜索API：选项包括"Tavily"（首选）、"Exa"、"Brave Search"、"None"。
StringProperty输入对应搜索API Key（多个，根据选择显示）。
多行TextProperty或按钮上传自定义知识库：支持输入文本、上传TXT/PDF文件，或添加URL列表。
一个按钮（Operator），标签为"Analyze Selected Nodes with AI"。


核心功能：
Operator执行时：
获取当前上下文的节点树（bpy.context.space_data.node_tree）。
获取所有选中的节点：selected_nodes = context.selected_nodes（如果没有，使用active_node）。
递归解析选中的节点和节点组：
对于每个节点：输出类型、名称、标签、输入/输出sockets（包括名称、类型、默认值、链接情况）。
如果是节点组（NodeGroup），递归进入其内部node_tree，解析子节点结构。
生成一个结构化的文本描述（如JSON或Markdown格式，便于AI阅读），例如：
"Node Tree Type: ShaderNodeTree
Selected Nodes:
Principled BSDF (name: Principled BSDF, location: (x,y))
Inputs: Base Color (linked to ...), Subsurface: 0.0, ...
Outputs: BSDF (linked to Material Output)
Node Group: MyGroup
Internal nodes: ..."


处理链接（links）：描述节点间的连接。
如果启用联网检索：根据解析的节点描述生成一个搜索查询（如"Blender Geometry Nodes: how to optimize this setup with [key nodes]"），调用选定的搜索API获取结果（用requests.post）。
示例Tavily调用：requests.post("https://api.tavily.com/search", json={"api_key": key, "query": query, "search_depth": "advanced"})，提取results中的content和urls。
将搜索结果摘要（带来源引用）添加到user message中。

知识库处理：如果用户提供了文本/文件/URL，先解析（PDF用简单文本提取，或预装库如PyPDF2），然后拼接进prompt："Additional knowledge: [content]"。
使用requests库（或openai库，如果可能）发送到OpenAI Chat Completions API：
messages: [{"role": "system", "content": user_system_prompt}, {"role": "user", "content": parsed_description + "Search results/Knowledge: [retrieved]"}]
处理响应，显示AI返回的分析结果（例如在Blender的弹出对话框、Info区域报告，或新Text Block中），标注来源（web链接或"from knowledge base"）。



额外考虑：
支持多种节点树类型（通过检查context.space_data.tree_type）。
线程处理网络调用，避免Blender卡顿（用threading.Thread）。
错误处理：如无选中节点、无API Key、网络错误、API限额等，弹出友好提示。
支持多API fallback。
在addon preferences中添加API Key的安全存储（bpy.types.AddonPreferences）。
插件支持安装/卸载正常。
代码要注释清晰，易于扩展（未来可添加AI生成新节点、优化节点树等功能，或本地向量数据库如Chroma）。
如果需要外部库（如openai或requests），说明如何在Blender中处理（Blender自带requests，但openai需用户pip安装或手动添加；PDF解析可简单文本或添加PyPDF2）。


请一步步生成完整的__init__.py代码，先给出整体框架，然后详细实现解析函数、API调用、检索和RAG部分。
谢谢！