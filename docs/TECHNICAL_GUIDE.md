# AI Node Analyzer - 技术指导文档

## 项目概述

AI Node Analyzer 是一个Blender插件，允许用户将节点编辑器中的节点结构发送给AI模型进行分析、优化建议和错误检测。该插件支持多种节点类型（几何节点、着色器节点、合成节点）并提供Web界面进行交互。

## 技术架构

### 整体架构
```
[Blender 插件] <--(HTTP API/Socket)--> [Python Web服务器] <--(AI API)--> [AI服务提供商]
                                    |
                                    --> [Web前端界面 (HTML/CSS/JS)]
```

### 技术栈

#### 后端 (Python)
- **Flask**: Web服务器框架
- **litellm**: 统一AI服务提供商接口
- **requests**: HTTP请求处理
- **bpy**: Blender Python API
- **webbrowser**: Web界面启动

#### 前端 (HTML/CSS/JS)
- **原生HTML/CSS/JS**: 无需额外框架，保持轻量级
- **WebSockets (可选)**: 实时通信
- **Fetch API**: 与后端通信

#### AI服务
- **支持的提供商**:
  - OpenAI (GPT-4o, GPT-4o Mini)
  - Anthropic (Claude 3)
  - Google (Gemini)
  - Mistral AI
  - Ollama (本地模型)
  - DeepSeek

## 实现阶段

### 阶段 1: 基础插件框架
- [x] Blender插件基本结构
- [x] 插件注册/注销机制
- [x] N面板UI基本布局
- [x] 插件基本信息定义

### 阶段 2: 节点分析功能
- [x] 节点数据解析（类型、名称、输入输出、连接等）
- [x] 节点组递归解析
- [x] 链接信息提取
- [x] 节点树类型识别（几何、着色器、合成等）

### 阶段 3: AI服务集成
- [x] 多AI提供商支持（litellm库）
- [x] API密钥管理
- [x] 模型选择机制
- [x] 系统提示词自定义
- [x] 网络搜索集成（Tavily等）

### 阶段 4: Web界面开发
- [ ] Flask Web服务器
- [ ] 前端界面（HTML/CSS/JS）
- [ ] WebSocket/HTTP API通信
- [ ] 实时对话界面
- [ ] 数据传输机制
- [ ] 会话管理

### 阶段 5: 用户体验优化
- [x] 依赖自动安装
- [x] 中文界面
- [x] 端口配置
- [x] 错误处理
- [x] 安装说明文档

### 阶段 6: 高级功能 (待实现)
- [ ] 代码生成（根据AI建议生成节点组）
- [ ] 本地向量数据库（知识库RAG）
- [ ] 导出功能（多种格式）
- [ ] 主题定制
- [ ] 多语言支持

## 数据流

### 节点分析流程
```
Blender节点编辑器 
    ↓ (获取选中节点)
插件节点解析器 
    ↓ (生成JSON)
Web服务器 
    ↓ (AI分析)
AI服务 
    ↓ (返回结果)
Web界面显示
```

### API端点设计

#### 服务器API
- `GET /` - Web界面主页面
- `POST /api/session` - 创建新会话
- `POST /api/chat` - 发送消息给AI
- `GET /api/history/<session_id>` - 获取会话历史
- `POST /api/history/clear` - 清空会话历史
- `POST /api/send_data` - 接收Blender数据
- `GET /api/latest_data/<session_id>` - 检查新数据

## 安全考虑

### API密钥安全
- 使用Blender密码字段隐藏API密钥
- 不在前端暴露API密钥
- 建议使用环境变量或安全存储

### 本地服务器安全
- 仅绑定到127.0.0.1（本地回环）
- 不对外网开放
- 会话数据本地存储

## 依赖管理

### Python依赖
- `flask>=2.0.0` - Web服务器
- `litellm>=1.40.0` - AI服务统一接口
- `requests>=2.25.0` - HTTP请求
- `openai>=1.0.0` - OpenAI兼容API
- `pywebview>=4.0.0` - Webview窗口（可选）

### 自动安装
- 插件启动时自动检查并安装依赖
- 提供手动安装选项
- 详细的安装说明

## 部署与分发

### 插件结构
```
ai_node_analyzer/
├── __init__.py          # 插件主文件
├── server.py           # Web服务器
├── requirements.txt    # 依赖列表
├── INSTALL.md          # 安装说明
├── TECHNICAL_GUIDE.md  # 技术文档
├── frontend/           # 前端资源（可选）
└── docs/               # 文档
```

### 安装步骤
1. 将插件文件夹复制到Blender addons目录
2. 在Blender中启用插件
3. 自动或手动安装Python依赖
4. 配置AI服务提供商和API密钥

## 开发指南

### 代码规范
- 使用Python标准库和Blender API
- 遵循PEP 8代码风格
- 中文注释和文档
- 错误处理和日志记录

### 扩展性
- 模块化设计，易于扩展新的AI服务提供商
- 标准化API端点，易于前端交互
- 灵活的配置系统

## 故障排除

### 常见问题
1. **依赖安装失败**: 确保使用正确的Python环境
2. **Web服务器无法启动**: 检查端口是否被占用
3. **AI服务连接失败**: 验证API密钥和网络连接

### 调试信息
- 启用Blender控制台查看日志
- 检查Flask服务器输出
- 验证API端点响应