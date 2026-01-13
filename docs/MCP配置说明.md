# MCP 配置说明

本文档说明如何配置 IDE 使用 Blender AI Node Analyzer 的本地 MCP 服务器。

## 架构说明

```
IDE (Claude Desktop / Cursor / 其他)
  ↓ (MCP 协议 - stdio)
MCP 适配器 (mcp_adapter.py)
  ↓ (Socket 连接 - 端口 9876)
Blender 插件 (Socket 服务器)
  ↓
Blender API
```

## 前置条件

1. **Blender 已安装** 并启用了 AI Node Analyzer 插件
2. **Python 3.8+** 已安装
3. **IDE 支持 MCP 协议**（如 Claude Desktop、Cursor 等）

## 配置步骤

### 步骤 1：启动 Blender 并启用插件

1. 打开 Blender
2. 进入 `Edit` → `Preferences` → `Add-ons`
3. 启用 `AI Node Analyzer` 插件
4. 在节点编辑器中，找到 `AI Node Analyzer` 面板
5. 确保 `AI Node MCP` 面板中的服务器状态为"运行在端口 9876"

### 步骤 2：配置 IDE

#### Claude Desktop

1. 打开 Claude Desktop
2. 进入 `Settings` → `Developer`
3. 点击 `Edit Config` 按钮
4. 在配置文件中添加以下内容：

```json
{
  "mcpServers": {
    "blender-ai-node-analyzer": {
      "command": "python",
      "args": [
        "D:\\blender\\Plugin\\addons\\ainode\\mcp_adapter.py"
      ]
    }
  }
}
```

**注意**：
- 请将 `D:\\blender\\Plugin\\addons\\ainode\\mcp_adapter.py` 替换为实际的文件路径
- Windows 路径使用双反斜杠 `\\`

5. 保存配置文件
6. 重启 Claude Desktop

#### Cursor

1. 打开 Cursor
2. 进入 `Settings` → `MCP Servers`
3. 添加新的 MCP 服务器：

```json
{
  "name": "blender-ai-node-analyzer",
  "command": "python",
  "args": [
    "D:\\blender\\Plugin\\addons\\ainode\\mcp_adapter.py"
  ]
}
```

4. 保存配置

#### 其他 IDE

如果您的 IDE 支持 MCP 协议，请参考其文档进行配置。关键配置项：

- **command**: `python`（或 `python3`）
- **args**: `[mcp_adapter.py 的完整路径]`

## 可用的 MCP 工具

配置成功后，IDE 将能够识别以下 18 个 MCP 工具：

### 基础 Blender 操作工具

1. **get_scene_info**
   - 描述：获取当前 Blender 场景信息
   - 参数：无

2. **get_object_info**
   - 描述：获取指定对象的详细信息
   - 参数：
     - `name` (string): 对象名称

3. **get_viewport_screenshot**
   - 描述：获取 3D 视口的截图
   - 参数：无

4. **execute_code**
   - 描述：执行 Blender Python 代码
   - 参数：
     - `code` (string): 要执行的 Python 代码

### 节点分析工具

5. **get_selected_nodes_info**
   - 描述：获取当前选中节点的详细信息
   - 参数：无

6. **get_all_nodes_info**
   - 描述：获取当前节点树中的所有节点信息
   - 参数：无

7. **create_analysis_frame**
   - 描述：创建分析框架，将选中的节点加入框架
   - 参数：无

8. **remove_analysis_frame**
   - 描述：移除分析框架
   - 参数：无

9. **get_analysis_frame_nodes**
   - 描述：获取分析框架中的节点信息
   - 参数：无

### 配置管理工具

10. **get_config_variable**
    - 描述：读取配置文件中的指定变量
    - 参数：
      - `variable_name` (string): 变量名称
        - 可选值：`identity_presets`, `default_questions`, `output_detail_presets`, `system_prompt`, `output_detail_level`

11. **get_all_config_variables**
    - 描述：获取所有配置变量
    - 参数：无

### 文本注记工具

12. **create_text_note**
    - 描述：创建文本注记节点
    - 参数：
      - `text` (string): 文本内容

13. **update_text_note**
    - 描述：更新当前激活的文本注记节点
    - 参数：
      - `text` (string): 新的文本内容

14. **get_text_note**
    - 描述：获取当前激活的文本注记节点内容
    - 参数：无

15. **delete_text_note**
    - 描述：删除当前激活的文本注记节点
    - 参数：无

### 节点信息过滤工具

16. **filter_nodes_info**
    - 描述：根据精细度过滤节点信息
    - 参数：
      - `node_info` (string): 节点信息 JSON 字符串
      - `level` (string): 精细度级别
        - 可选值：`ULTRA_LITE`, `LITE`, `STANDARD`, `FULL`

17. **get_nodes_info_with_filter**
    - 描述：获取节点信息并应用过滤
    - 参数：
      - `level` (string): 精细度级别（可选，默认为 `STANDARD`）

### 文本处理工具

18. **clean_markdown_text**
    - 描述：清理指定文本的 Markdown 格式
    - 参数：
      - `text` (string): 要清理的文本

## 使用示例

### 示例 1：获取场景信息

在 Claude Desktop 中：

```
请帮我获取当前 Blender 场景的信息
```

Claude 会自动调用 `get_scene_info` 工具。

### 示例 2：分析选中节点

```
请分析当前选中的节点
```

Claude 会调用 `get_selected_nodes_info` 工具获取节点信息。

### 示例 3：创建分析框架

```
请为选中的节点创建一个分析框架
```

Claude 会调用 `create_analysis_frame` 工具。

### 示例 4：获取配置变量

```
请获取所有身份预设
```

Claude 会调用 `get_config_variable` 工具，参数为 `variable_name: "identity_presets"`。

## 故障排除

### 问题 1：无法连接到 Blender

**症状**：
- IDE 提示 "Failed to connect to Blender"

**解决方案**：
1. 确保 Blender 正在运行
2. 确保 AI Node Analyzer 插件已启用
3. 检查 MCP 面板是否显示"运行在端口 9876"
4. 重启 Blender 插件（禁用后重新启用）

### 问题 2：工具列表为空

**症状**：
- IDE 中看不到任何工具

**解决方案**：
1. 检查 `mcp_adapter.py` 文件路径是否正确
2. 确保 Python 环境正确
3. 查看适配器日志（stderr 输出）

### 问题 3：工具调用失败

**症状**：
- IDE 能够看到工具，但调用时出错

**解决方案**：
1. 确保在正确的上下文中（节点编辑器）
2. 检查参数是否正确
3. 查看 Blender 控制台的错误信息

### 问题 4：Python 路径问题

**症状**：
- IDE 提示找不到 python 命令

**解决方案**：
1. 使用完整的 Python 可执行文件路径
2. 例如：`"C:\\Python311\\python.exe"`

## 高级配置

### 自定义端口

如果需要使用不同的端口，可以修改 `mcp_adapter.py` 中的端口配置：

```python
self.blender_adapter = BlenderMCPAdapter(host='localhost', port=9877)
```

同时在 Blender 插件中修改端口设置。

### 调试模式

要查看详细的调试信息，可以在 IDE 配置中添加环境变量：

```json
{
  "command": "python",
  "args": ["D:\\blender\\Plugin\\addons\\ainode\\mcp_adapter.py"],
  "env": {
    "DEBUG": "1"
  }
}
```

## 相关文档

- [MCP 功能实现总结](./blender/MCP功能实现总结.md)
- [Blender 插件文档](./blender/README.md)

## 支持

如果遇到问题，请：
1. 检查 Blender 控制台的错误信息
2. 查看 IDE 的 MCP 日志
3. 确保所有前置条件都已满足