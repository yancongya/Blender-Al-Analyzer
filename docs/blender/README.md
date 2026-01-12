# Blender 插件文档索引

## 文档列表

### 00-总览.md
Blender 插件整体结构、技术栈、目录结构、核心功能

### 01-主面板文档.md
- 面板信息
- 面板结构
- 核心功能
  - 节点数据发送
  - AI 分析
  - 结果显示
  - 历史记录
- 布局结构
- 状态管理
- 事件处理
- 样式说明

### 02-快速复制面板文档.md
- 面板信息
- 面板结构
- 核心功能
  - 快速复制节点数据
  - 格式化输出
  - 复制到剪贴板
- 使用方法
- 快捷键

### 03-设置弹窗文档.md
- 弹窗信息
- 弹窗结构
- 核心功能
  - AI 服务商配置
  - 模型选择
  - 系统提示词配置
  - 输出详细程度配置
  - 温度、Top P 配置
  - 深度思考模式
  - 联网搜索
- 配置项说明
- 配置文件格式

### 04-运算符文档.md
- 运算符列表
  - `ai_note.send_to_backend` - 发送节点数据到后端
  - `ai_note.refresh_node_data` - 刷新节点数据
  - `ai_note.toggle_node_context` - 切换节点上下文
  - `ai_note.copy_node_data` - 复制节点数据
  - `ai_note.open_settings` - 打开设置
  - `ai_note.open_docs` - 打开文档
- 运算符参数
- 运算符返回值
- 运算符注册

### 05-右键菜单文档.md
- 菜单项
  - 发送节点数据
  - 刷新节点数据
  - 复制节点数据
  - 打开设置
  - 打开文档
- 菜单注册
- 菜单回调

### 06-后端服务器文档.md
- 服务器信息
- 文件结构
- 初始化
- 全局变量
- 路由端点
  - 静态文件服务
  - Blender 数据接收
  - 流式分析
  - 服务商连通性测试
  - 模型列表获取
  - 文档列表获取
  - 文档内容获取
  - 文档分类获取
  - 文档搜索
- 与 Blender 的通信
- 配置管理
- 错误处理
- 测试端点

### 07-文本注记节点文档.md
- 节点信息
- 节点结构
- 核心功能
  - 创建文本注记
  - 更新文本注记
  - 删除文本注记
  - 显示/隐藏注记
  - 注记样式配置
- 节点属性
- 节点方法
- 使用示例

---

## 技术栈

### 核心框架
- Blender 3.0+
- Python 3.10+

### Web 框架
- Flask
- Flask-CORS

### HTTP 客户端
- requests

### 配置管理
- JSON

---

## 目录结构

```
ainode/
├── __init__.py              # 插件主文件
├── backend/                 # 后端服务
│   ├── server.py            # Flask 服务器
│   ├── ai_note.py           # 文本注记节点
│   └── api/
│       └── blender_api.py   # Blender API
├── frontend/                # 前端资源
│   ├── index.html           # HTML 模板
│   ├── css/                 # 样式文件
│   └── js/                  # JavaScript 文件
├── nodes/                   # 节点定义
├── docs/                    # 文档
├── config.example.json      # 配置示例
├── prompt_templates.json    # 提示词模板
├── QWEN.md                  # Qwen 模型说明
├── GEMINI.md                # Gemini 模型说明
└── README.md                # 项目说明
```

---

## 核心功能

### 1. 节点数据分析
- 发送节点数据到 AI
- 流式接收分析结果
- 显示思考过程
- 支持多轮对话

### 2. AI 服务商支持
- DeepSeek
- Ollama
- BigModel (智谱)
- Qwen (通义千问)
- Gemini (Google)

### 3. 节点上下文
- 启用/禁用节点上下文
- 控制上下文长度
- 上下文过滤

### 4. 提示词管理
- 系统提示词配置
- 提示词模板
- 提示词导入/导出
- 默认提示词

### 5. 文本注记
- 创建文本注记节点
- 更新注记内容
- 删除注记
- 注记样式配置

### 6. 文档系统
- 文档列表浏览
- 文档内容阅读
- 关键词搜索
- 分类筛选
- Markdown 渲染
- 代码语法高亮

---

## 开发指南

### 安装插件

1. 将 `ainode` 文件夹复制到 Blender 的插件目录：
   - Windows: `%APPDATA%\Blender Foundation\Blender\X.X\scripts\addons\`
   - macOS: `~/Library/Application Support/Blender/X.X/scripts/addons/`
   - Linux: `~/.config/blender/X.X/scripts/addons/`

2. 在 Blender 中启用插件：
   - 打开 `Edit > Preferences > Add-ons`
   - 搜索 `AI Node Analyzer`
   - 勾选启用

### 配置插件

1. 打开设置面板：
   - 在 3D 视图中按 `N` 打开侧边栏
   - 切换到 `AI Note` 标签
   - 点击设置按钮

2. 配置 AI 服务商：
   - 选择服务商
   - 输入 API Key
   - 选择模型
   - 配置参数

### 使用插件

1. 选择节点
2. 点击 `Send to Backend` 按钮
3. 查看分析结果
4. 继续对话或选择其他节点

---

## 相关文档

- [Web 前端文档](../web/README.md)
- [项目 README](../../README.md)
- [文档系统文档](../web/07-文档系统文档.md)