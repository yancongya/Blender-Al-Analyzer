# AI Node Analyzer Blender Add-on

AI Node Analyzer是一个Blender插件，允许用户分析节点编辑器中的节点（支持几何节点、着色器节点、合成节点等），并可选择将其发送给AI进行进一步分析。插件还包含一个后端服务器，支持与外部应用（如浏览器）进行通信。

## 功能

- 解析选中的节点结构，包括节点组的递归解析
- 在节点编辑器侧边栏提供便捷的分析面板
- 支持多种节点类型：几何节点、着色器节点、合成节点等
- 支持DeepSeek和Ollama两种AI服务提供商
- 将解析结果保存到Blender文本块中供查看
- **新增**: 包含后端服务器，支持与浏览器等外部应用通信

## 安装

1. 下载此插件文件夹
2. 在Blender中，进入编辑 > 首选项 > 插件
3. 点击"安装..."并选择此插件的__init__.py文件
4. 激活插件

## 使用方法

### 基础AI分析功能:
1. 在节点编辑器中打开任意节点树（几何节点、材质节点或合成节点）
2. 选择一个或多个节点
3. 在右侧N面板中找到"AI Node Analyzer"面板
4. 选择AI服务提供商（DeepSeek或Ollama）
5. 根据选择的提供商配置相应参数
6. 点击"Analyze Selected Nodes with AI"按钮
7. 分析结果将在Blender的文本编辑器中显示

### 后端通信功能:
1. 启动插件后，默认不启动后端服务器
2. 在插件主面板中，使用"启动服务器"按钮启动后端（端口可在设置中调整）
3. 使用"打开网页"按钮在浏览器中打开测试页面
4. 通过页面按钮测试与Blender插件的通信
5. 可使用 `/api/send-message` 端点发送消息到Blender
6. 可使用 `/api/get-messages` 端点获取Blender收到的消息

## API端点

- `GET /api/test-connection` - 测试连接
- `GET /api/status` - 获取Blender插件状态
- `POST /api/send-message` - 发送消息到Blender
- `GET /api/get-messages` - 获取消息列表
- `POST /api/clear-messages` - 清空消息列表
- `POST /api/execute-operation` - 执行Blender操作

## 配置

当前版本支持以下配置：

- **AI Provider**: 选择AI服务提供商（DeepSeek或Ollama）
- **DeepSeek**: API密钥和模型选择
- **Ollama**: 服务URL和模型名称
- **System Prompt**: 自定义AI系统提示
- **Web Search**: 启用/禁用网络搜索功能

## 当前状态

当前版本实现了节点解析、DeepSeek和Ollama服务支持、基础UI功能，以及后端通信功能。

## 许可证

MIT License