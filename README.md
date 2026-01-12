# AI Node Analyzer Blender Add-on

AI Node Analyzer是一个Blender插件，允许用户分析节点编辑器中的节点（支持几何节点、着色器节点、合成节点等），并可选择将其发送给AI进行进一步分析。插件还包含一个后端服务器，支持与外部应用（如浏览器）进行通信。

## 功能

- 解析选中的节点结构，包括节点组的递归解析
- 在节点编辑器侧边栏提供便捷的分析面板
- 支持多种节点类型：几何节点、着色器节点、合成节点等
- 支持多种AI服务提供商：DeepSeek、Ollama、BigModel、Qwen、Gemini
- 将解析结果保存到Blender文本块中供查看
- 包含后端服务器，支持与浏览器等外部应用通信
- **新增**: 文档阅读系统，支持浏览和搜索项目文档
- **新增**: VitePress 风格的文档界面
- **新增**: Markdown 渲染和代码语法高亮
- **新增**: 深色/浅色主题切换
- **新增**: 自动生成文档目录

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
4. 选择AI服务提供商（DeepSeek、Ollama、BigModel、Qwen、Gemini）
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

### 文档阅读系统:
1. 启动后端服务器
2. 在浏览器中访问：`http://127.0.0.1:5000`
3. 点击导航栏中的文档图标（📖）或直接访问 `http://127.0.0.1:5000/#/docs`
4. 使用左侧边栏浏览文档列表
5. 点击文档标题查看内容
6. 使用搜索框搜索文档
7. 使用右侧目录快速导航
8. 点击主题切换按钮切换深色/浅色模式

## API端点

### 基础端点
- `GET /api/test-connection` - 测试连接
- `GET /api/status` - 获取Blender插件状态
- `POST /api/send-message` - 发送消息到Blender
- `GET /api/get-messages` - 获取消息列表
- `POST /api/clear-messages` - 清空消息列表
- `POST /api/execute-operation` - 执行Blender操作

### AI 分析端点
- `POST /api/blender-data` - 接收Blender节点数据
- `POST /api/stream-analyze` - 流式AI分析
- `POST /api/provider-connectivity` - 测试服务商连通性
- `POST /api/provider-list-models` - 获取可用模型列表

### 文档系统端点
- `GET /api/docs/list` - 获取文档列表
- `POST /api/docs/content` - 获取文档内容
- `GET /api/docs/categories` - 获取文档分类
- `POST /api/docs/search` - 搜索文档

## 配置

当前版本支持以下配置：

- **AI Provider**: 选择AI服务提供商（DeepSeek、Ollama、BigModel、Qwen、Gemini）
- **DeepSeek**: API密钥和模型选择
- **Ollama**: 服务URL和模型名称
- **BigModel**: API密钥和模型选择
- **Qwen**: API密钥和模型选择
- **Gemini**: API密钥和模型选择
- **System Prompt**: 自定义AI系统提示
- **Web Search**: 启用/禁用网络搜索功能
- **Thinking Mode**: 启用/禁用深度思考模式
- **Output Detail Level**: 输出详细程度（简约/适中/详细）
- **Temperature**: 温度参数
- **Top P**: Top P 参数
- **Server Port**: 后端服务器端口（默认 5000）

### 文档系统

文档系统位于 `docs/` 文件夹，包含以下内容：

- **blender/** - Blender 插件相关文档
  - 00-总览.md
  - 01-主面板文档.md
  - 02-快速复制面板文档.md
  - 03-设置弹窗文档.md
  - 04-运算符文档.md
  - 05-右键菜单文档.md
  - 06-后端服务器文档.md
  - 07-文本注记节点文档.md
- **web/** - Web 前端相关文档
  - 00-总览.md
  - 01-主界面文档.md
  - 02-组件文档.md
  - 03-Store文档.md
  - 04-API文档.md
  - 05-Hooks文档.md
  - 06-路由文档.md
  - 07-文档系统文档.md

### 访问文档系统

1. 启动后端服务器
2. 在浏览器中访问：`http://127.0.0.1:5000`
3. 点击导航栏中的文档图标（📖）
4. 或直接访问：`http://127.0.0.1:5000/#/docs`

## 当前状态

当前版本实现了节点解析、多种AI服务商支持（DeepSeek、Ollama、BigModel、Qwen、Gemini）、基础UI功能、后端通信功能，以及文档阅读系统。

### 已实现功能
- ✅ 节点解析和递归解析
- ✅ 多种AI服务商支持
- ✅ 流式AI分析
- ✅ 深度思考模式
- ✅ 联网搜索
- ✅ 节点上下文管理
- ✅ 提示词模板管理
- ✅ 文本注记节点
- ✅ 后端服务器
- ✅ Web 前端界面
- ✅ 文档阅读系统
- ✅ VitePress 风格界面
- ✅ Markdown 渲染
- ✅ 代码语法高亮
- ✅ 深色/浅色主题切换
- ✅ 自动生成目录
- ✅ 文档搜索功能

## 许可证

MIT License