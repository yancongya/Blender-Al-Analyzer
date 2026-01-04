# AI Node Analyzer Blender Add-on

## 项目概述

AI Node Analyzer 是一个Blender插件，允许用户分析节点编辑器中的节点（支持几何节点、着色器节点、合成节点等），并可选择将其发送给AI进行进一步分析。插件还包含一个后端服务器，支持与外部应用（如浏览器）进行通信。

该项目是一个混合项目，包含：
- Blender插件部分（Python）
- 后端服务器（Flask）
- 前端Web界面（基于chatgpt-web项目）

## 架构

- `__init__.py`: Blender插件的主入口文件，包含插件注册、UI面板、节点解析逻辑和AI分析功能
- `backend/server.py`: Flask后端服务器，提供API端点用于与Blender通信
- `chatgpt-web/`: 基于开源chatgpt-web的前端界面，用于与AI进行交互
- `config.example.json`: 配置文件示例，包含端口、AI提供商设置等
- `prompt_templates.json`: 预设的提示模板

## 功能

- 解析选中的节点结构，包括节点组的递归解析
- 在节点编辑器侧边栏提供便捷的分析面板
- 支持多种节点类型：几何节点、着色器节点、合成节点等
- 支持DeepSeek和Ollama两种AI服务提供商
- 将解析结果保存到Blender文本块中供查看
- 包含后端服务器，支持与浏览器等外部应用通信

## API端点

- `GET /api/test-connection` - 测试连接
- `GET /api/status` - 获取Blender插件状态
- `POST /api/send-message` - 发送消息到Blender
- `GET /api/get-messages` - 获取消息列表
- `POST /api/clear-messages` - 清空消息列表
- `POST /api/execute-operation` - 执行Blender操作
- `POST /api/stream-analyze` - 流式分析节点内容
- `GET/POST /api/blender-data` - 获取/设置Blender数据

## 配置

- **AI Provider**: 选择AI服务提供商（DeepSeek或Ollama）
- **DeepSeek**: API密钥和模型选择
- **Ollama**: 服务URL和模型名称
- **System Prompt**: 自定义AI系统提示
- **Web Search**: 启用/禁用网络搜索功能

## 构建和运行

### Blender插件
1. 将插件文件夹复制到Blender的addons目录
2. 在Blender中启用插件（编辑 > 首选项 > 插件）

### 后端服务器
- 服务器在Blender插件启动时自动初始化
- 默认端口为5000（可通过配置文件修改）

### 前端Web界面
- 基于chatgpt-web项目，使用Vue 3和TypeScript
- 需要安装pnpm依赖并构建
- 构建命令：`pnpm build`（在chatgpt-web目录下）

## 开发约定

- Python代码遵循PEP 8规范
- 使用bpy进行Blender API交互
- Flask用于后端API开发
- Vue 3 + TypeScript用于前端开发
- 配置文件使用JSON格式

## 文件结构

```
ainode/
├── __init__.py          # Blender插件主文件
├── config.example.json  # 配置文件示例
├── prompt_templates.json # 提示模板
├── README.md           # 项目说明
├── backend/
│   └── server.py       # Flask后端服务器
├── chatgpt-web/        # 前端Web界面
└── frontend/           # 可选前端源码
```