# MCP 功能实现总结

本文档总结了 Blender 插件中可以添加到 MCP 的功能及其实现方式。

## 1. 获取所选节点 JSON 信息

### 功能描述
获取当前选中的节点的详细信息，包括节点名称、类型、位置、输入输出端口、连接关系等。

### 实现方式
- **函数**: `get_selected_nodes_description(context)`
- **代码位置**: `__init__.py` 第 1546-1746 行
- **返回值**: JSON 字符串，包含节点树类型、选中节点数量、每个节点的详细信息

### 返回数据结构
```json
{
  "node_tree_type": "GeometryNodeTree",
  "selected_nodes_count": 2,
  "selected_nodes": [
    {
      "name": "节点名称",
      "name_localized": "本地化名称",
      "label": "节点标签",
      "label_localized": "本地化标签",
      "type": "GeometryNodeMeshPrimitiveCube",
      "location": [0.0, 0.0],
      "width": 140.0,
      "height": 100.0,
      "color": [0.0, 0.0, 0.0],
      "use_custom_color": false,
      "inputs": [
        {
          "name": "输入名称",
          "name_localized": "本地化输入名称",
          "type": "GEOMETRY",
          "identifier": "Identifier",
          "enabled": true,
          "hide": false,
          "hide_value": false,
          "default_value": null,
          "is_connected": false
        }
      ],
      "outputs": [
        {
          "name": "输出名称",
          "name_localized": "本地化输出名称",
          "type": "GEOMETRY",
          "identifier": "Identifier",
          "enabled": true,
          "hide": false,
          "default_value": null,
          "is_connected": false,
          "connected_to": []
        }
      ]
    }
  ],
  "connections": []
}
```

### MCP 工具定义
```python
def get_selected_nodes_info(self):
    """获取当前选中节点的详细信息"""
    try:
        return get_selected_nodes_description(bpy.context)
    except Exception as e:
        return {"error": str(e)}
```

---

## 2. 获取当前激活节点的全部节点 JSON 信息

### 功能描述
获取当前激活节点树中的所有节点信息，包括节点之间的连接关系。

### 实现方式
- **函数**: `parse_node_tree_recursive(node_tree, depth=0, max_depth=10)`
- **代码位置**: `__init__.py` 第 899-1108 行
- **返回值**: 包含完整节点树信息的字典

### 实现逻辑
1. 遍历节点树中的所有节点
2. 递归解析节点组（GROUP 类型节点）
3. 记录所有连接关系
4. 返回完整的节点树结构

### MCP 工具定义
```python
def get_all_nodes_info(self, params=None):
    """获取当前节点树中的所有节点信息"""
    try:
        space = bpy.context.space_data
        if not hasattr(space, 'node_tree') or not space.node_tree:
            return {"error": "No active node tree found."}
        
        node_tree = space.node_tree
        result = parse_node_tree_recursive(node_tree)
        return json.dumps(result, indent=2)
    except Exception as e:
        return {"error": str(e)}
```

---

## 3. 确定要分析的节点框架

### 功能描述
创建一个框架节点，将选中的节点加入框架中，用于确定分析范围。

### 实现方式
- **运算符**: `NODE_OT_create_analysis_frame`
- **代码位置**: `__init__.py` 第 3190-3310 行
- **行为**:
  - 如果已存在框架，则移除框架并记录节点名称
  - 如果不存在框架，则创建框架并加入选中的节点
  - 节点名称保存在 `analysis_frame_node_names` 属性中

### MCP 工具定义
```python
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
        # 检查是否有框架
        node_tree = bpy.context.space_data.node_tree
        frame_node = None
        for node in node_tree.nodes:
            if node.type == 'FRAME' and node.label == "将要分析":
                frame_node = node
                break
        
        if frame_node:
            # 移除框架
            ain_settings = bpy.context.scene.ainode_analyzer_settings
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
        ain_settings = bpy.context.scene.ainode_analyzer_settings
        node_names = ain_settings.analysis_frame_node_names.split(',')
        nodes_info = []
        
        node_tree = bpy.context.space_data.node_tree
        for node_name in node_names:
            if node_name in node_tree.nodes:
                node = node_tree.nodes[node_name]
                nodes_info.append({
                    "name": node.name,
                    "type": node.bl_idname,
                    "label": node.label
                })
        
        return {
            "frame_node_names": ain_settings.analysis_frame_node_names,
            "nodes": nodes_info
        }
    except Exception as e:
        return {"error": str(e)}
```

---

## 4. 读取配置文件中的指定变量

### 功能描述
从配置文件 `config.json` 中读取指定的变量，包括身份提示词、默认提示词、控制输出详略关键词等。

### 实现方式
- **配置文件**: `config.json`
- **加载函数**: `NODE_OT_load_config_from_file.execute()`
- **代码位置**: `__init__.py` 第 1389-1614 行

### 可读取的变量
1. **身份提示词** (`system_message_presets`)
   - 几何节点专家
   - 材质节点专家
   - 合成节点专家
   - 默认助手

2. **默认提示词** (`default_question_presets`)
   - 功能分析
   - 性能优化
   - 原理解释
   - 排查错误

3. **控制输出详略关键词** (`output_detail_presets`)
   - `simple`: 简约提示
   - `medium`: 适中提示
   - `detailed`: 详细提示

4. **当前系统提示词** (`ai.system_prompt`)

5. **当前回答精细度** (`output_detail_level`)

### MCP 工具定义
```python
def get_config_variable(self, params):
    """读取配置文件中的指定变量"""
    try:
        import json
        import os
        
        var_name = params.get("variable_name")
        
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if not os.path.exists(config_path):
            return {"error": "Config file not found"}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 根据变量名返回对应的值
        if var_name == "identity_presets":
            return config.get("system_message_presets", [])
        elif var_name == "default_questions":
            return config.get("default_question_presets", [])
        elif var_name == "output_detail_presets":
            return config.get("output_detail_presets", {})
        elif var_name == "system_prompt":
            return config.get("ai", {}).get("system_prompt", "")
        elif var_name == "output_detail_level":
            return config.get("output_detail_level", "medium")
        else:
            return {"error": f"Unknown variable: {var_name}"}
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
```

---

## 5. 文本注记相关的四个功能

### 功能描述
文本注记节点用于在节点编辑器中添加注释和说明。

### 实现方式
- **模块**: `backend/ai_note.py`
- **节点类**: `AINodeTextNote`

### 四个主要功能

#### 5.1 创建文本注记节点
- **函数**: `create_note(text)`
- **代码位置**: `backend/ai_note.py` 第 183-233 行
- **参数**: `text` - 文本内容

#### 5.2 更新当前激活的文本注记节点
- **函数**: `update_active(text)`
- **代码位置**: `backend/ai_note.py` 第 235-251 行
- **参数**: `text` - 新的文本内容

#### 5.3 获取文本注记节点内容
- **函数**: `get_active_note()`
- **代码位置**: `backend/ai_note.py` 第 253-266 行
- **返回值**: 文本内容

#### 5.4 删除文本注记节点
- **函数**: `delete_active_note()`
- **代码位置**: `backend/ai_note.py` 第 268-278 行

### MCP 工具定义
```python
def create_text_note(self, params):
    """创建文本注记节点"""
    try:
        from backend.ai_note import create_note
        
        text = params.get("text", "")
        success = create_note(text)
        
        if success:
            return {"status": "success", "message": "Text note created"}
        else:
            return {"error": "Failed to create text note"}
    except Exception as e:
        return {"error": str(e)}

def update_text_note(self, params):
    """更新当前激活的文本注记节点"""
    try:
        from backend.ai_note import update_active
        
        text = params.get("text", "")
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
```

---

## 6. 控制节点信息详略的阈值控制

### 功能描述
根据不同的精细度级别过滤节点信息，控制输出的详细程度。

### 实现方式
- **函数**: `filter_node_description(text, level)`
- **代码位置**: `__init__.py` 第 267-317 行

### 精细度级别
1. **ULTRA_LITE (0)** - 极简：仅最小标识
2. **LITE (1)** - 简化：保留必要的 IO
3. **STANDARD (2)** - 常规：清除可视属性
4. **FULL (3)** - 完整：完整上下文

### MCP 工具定义
```python
def filter_nodes_info(self, params):
    """根据精细度过滤节点信息"""
    try:
        import json
        
        node_info = params.get("node_info", "")
        level = params.get("level", "STANDARD")
        
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

def get_nodes_info_with_filter(self, params):
    """获取节点信息并应用过滤"""
    try:
        level = params.get("level", "STANDARD")
        
        # 获取原始节点信息
        space = bpy.context.space_data
        if not hasattr(space, 'node_tree') or not space.node_tree:
            return {"error": "No active node tree found."}
        
        node_tree = space.node_tree
        selected_nodes = bpy.context.selected_nodes
        
        if not selected_nodes:
            return {"error": "No selected nodes"}
        
        # 获取节点描述
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
        return {"error": str(e)}
```

---

## 7. 清理指定文本的 MD 格式

### 功能描述
清理文本中的 Markdown 格式，规范化格式。

### 实现方式
- **函数**: `clean_markdown(text)`
- **代码位置**: `__init__.py` 第 61-91 行

### 清理规则
1. 统一换行符（`\r\n` → `\n`）
2. 移除行尾空白
3. 合并过多空行（3个或以上 → 2个）
4. 移除行首空白
5. 规范化代码块标记（多个反引号 → 3个）
6. 规范化多级标题（多个# → ##）

### MCP 工具定义
```python
def clean_markdown_text(self, params):
    """清理指定文本的 Markdown 格式"""
    try:
        text = params.get("text", "")
        cleaned = clean_markdown(text)
        
        return {
            "status": "success",
            "original_length": len(text),
            "cleaned_length": len(cleaned),
            "cleaned_text": cleaned
        }
    except Exception as e:
        return {"error": str(e)}
```

---

## 完整的 MCP 工具列表

基于以上分析，可以添加以下 MCP 工具：

1. **`get_selected_nodes_info`** - 获取所选节点 JSON 信息
2. **`get_all_nodes_info`** - 获取当前激活节点的全部节点 JSON 信息
3. **`create_analysis_frame`** - 创建分析框架
4. **`remove_analysis_frame`** - 移除分析框架
5. **`get_analysis_frame_nodes`** - 获取分析框架中的节点信息
6. **`get_config_variable`** - 读取配置文件中的指定变量
7. **`get_all_config_variables`** - 获取所有配置变量
8. **`create_text_note`** - 创建文本注记节点
9. **`update_text_note`** - 更新文本注记节点
10. **`get_text_note`** - 获取文本注记节点内容
11. **`delete_text_note`** - 删除文本注记节点
12. **`filter_nodes_info`** - 过滤节点信息
13. **`get_nodes_info_with_filter`** - 获取节点信息并应用过滤
14. **`clean_markdown_text`** - 清理 Markdown 格式

---

## 实现建议

1. **在 `BlenderMCPServer` 类中添加这些工具方法**
2. **确保所有工具都有适当的错误处理**
3. **在 MCP 面板中显示这些新工具**
4. **考虑添加工具分类**（节点操作、配置管理、文本操作等）
5. **为每个工具添加详细的文档字符串**

---

## 注意事项

1. **上下文限制**: 某些操作需要在 Blender 主线程中执行
2. **节点树检查**: 在操作节点前，确保存在活动的节点树
3. **错误处理**: 所有工具都应该有完善的错误处理机制
4. **返回格式**: 统一使用 JSON 格式返回结果
5. **性能考虑**: 对于大量节点，考虑添加分页或限制返回数量