# Web 文档索引

## 文档列表

### 00-总览.md
Web 前端整体结构、技术栈、目录结构、核心功能

### 01-主界面文档.md
- 页面信息
- 页面结构
- 组件依赖
- 核心功能
  - 聊天功能
  - Blender 节点集成
  - AI 配置
  - 对话管理
  - 节点数据过滤
  - 导出功能
- 布局结构
- 状态管理
- Store 依赖
- Hooks 使用
- 事件处理
- 样式说明
- 响应式设计
- 可访问性
- 性能优化

### 02-组件文档.md
- HoverButton - 悬浮按钮
- NaiveProvider - Naive UI 提供者
- PromptStore - 提示词存储
- SelectionSend - 选择发送
- Setting - 设置面板
- SvgIcon - SVG 图标
- UserAvatar - 用户头像
- GithubSite - GitHub 站点链接
- Message - 消息组件
- Header - 头部组件
- BlenderNode - Blender 节点组件
- NodeDataView - 节点数据视图
- VariableRichInput - 变量富输入框
- 组件通信
- 组件样式
- 组件测试
- 组件最佳实践

### 03-Store文档.md
- App Store - 应用状态
- Auth Store - 认证状态
- Chat Store - 聊天状态
- Prompt Store - 提示词状态
- Settings Store - 设置状态
- User Store - 用户状态
- Store 持久化
- Store 模块化
- Store 最佳实践

### 04-API文档.md
- fetchChatAPI - 聊天 API
- fetchChatConfig - 获取配置
- fetchBlenderData - 获取 Blender 数据
- fetchChatAPIProcess - 流式分析
- fetchSession - 获取会话
- fetchVerify - 验证令牌
- fetchUiConfig - 获取 UI 配置
- triggerRefresh - 触发刷新
- updateSettings - 保存设置
- fetchPromptTemplates - 获取提示词模板
- savePromptTemplates - 保存提示词模板
- importPromptTemplates - 导入提示词模板
- fetchDefaultPromptTemplates - 获取默认提示词模板
- sendSelectionToBlender - 创建注释
- updateBlenderAnnotation - 更新注释
- openBlenderAnnotationEditor - 打开注释编辑器
- fitBlenderAnnotation - 适应注释
- fetchProviderModels - 获取服务商模型列表
- 请求工具
- 错误处理

### 05-Hooks文档.md
- useBasicLayout - 基础布局
- useIconRender - 图标渲染
- useLanguage - 语言切换
- useTheme - 主题切换
- useChat - 聊天逻辑
- useScroll - 滚动管理
- useUsingContext - 上下文使用
- 自定义 Hook 开发
- Hooks 最佳实践

### 06-路由文档.md
- 路由配置
- 路由模式
- 路由守卫
- 路由参数
- 路由导航
- 路由组件
- 路由元信息
- 路由懒加载
- 路由过渡
- 路由错误处理
- 路由最佳实践

### 07-文档系统文档.md
- 页面信息
- 页面结构
- 核心功能
  - 文档浏览
  - 搜索功能
  - 主题切换
  - 响应式布局
- API 接口
  - 获取文档列表
  - 获取文档内容
  - 获取文档分类
  - 搜索文档
- 组件说明
  - 左侧边栏
  - 主内容区
  - 右侧目录
- 使用说明
- 布局结构
- 样式说明
- 响应式设计
- 性能优化
- 可访问性
- 浏览器兼容性
- 常见问题
- 更新日志

---

## 技术栈

### 核心框架
- Vue 3.3.4
- TypeScript 4.9.5
- Vite 4.2.0

### UI 框架
- Naive UI 2.34.3
- Tailwind CSS 3.2.7
- Less 4.1.3

### 状态管理
- Pinia 2.0.33

### 路由
- Vue Router 4.1.6

### 国际化
- Vue I18n 9.2.2

### 工具库
- @vueuse/core 9.13.0
- Axios 1.3.4
- Crypto-JS 4.1.1

### Markdown
- markdown-it 13.0.1
- highlight.js 11.7.0
- katex 0.16.4
- mermaid-it-markdown 1.0.8

### 图表
- cytoscape 3.33.1
- cytoscape-dagre 2.5.0
- dagre 0.8.5

### 编辑器
- codemirror 5.65.11
- codemirror-editor-vue3 2.8.0

### 图标
- @iconify/vue 4.1.0

### 导出
- html-to-image 1.11.11

### 开发工具
- ESLint 8.35.0
- Husky 8.0.3
- Commitlint 17.4.4
- lint-staged 13.1.2

---

## 目录结构

```
chatgpt-web/
├── public/              # 静态资源
│   ├── avatar.png
│   └── favicon.svg
├── src/
│   ├── api/            # API 接口
│   │   └── index.ts
│   ├── assets/         # 资源文件
│   ├── components/     # 组件
│   │   ├── common/     # 通用组件
│   │   └── custom/     # 自定义组件
│   ├── hooks/          # Hooks
│   ├── icons/          # 图标
│   ├── locales/        # 国际化
│   ├── plugins/        # 插件
│   ├── router/         # 路由
│   ├── store/          # 状态管理
│   │   └── modules/    # Store 模块
│   ├── styles/         # 样式
│   ├── typings/        # 类型定义
│   ├── utils/          # 工具函数
│   ├── views/          # 页面
│   │   ├── chat/       # 聊天页面
│   │   └── exception/  # 异常页面
│   ├── App.vue         # 根组件
│   └── main.ts         # 入口文件
├── .eslintrc.cjs       # ESLint 配置
├── .gitignore          # Git 忽略
├── package.json        # 依赖配置
├── tailwind.config.js  # Tailwind 配置
├── tsconfig.json       # TypeScript 配置
├── vite.config.ts      # Vite 配置
└── index.html          # HTML 模板
```

---

## 核心功能

### 1. 聊天功能
- 发送消息
- 接收流式响应
- 显示思考过程
- 支持多轮对话

### 2. Blender 节点集成
- 节点数据同步
- 变量插入
- 节点数据过滤
- 导出节点数据

### 3. AI 配置
- AI 服务商配置
- 模型选择
- 系统提示词配置
- 输出详细程度配置
- 温度、Top P 配置
- 深度思考模式
- 联网搜索

### 4. 对话管理
- 对话历史
- 多轮对话
- 对话 ID 管理
- 上下文使用

### 5. 提示词管理
- 提示词模板
- 提示词导入/导出
- 默认提示词

### 6. 注释功能
- 创建注释
- 更新注释
- 打开注释编辑器
- 适应注释大小

### 7. 导出功能
- 导出对话为图片
- 导出节点数据
- 复制到剪贴板

### 8. 文档系统
- 文档列表浏览
- 文档内容阅读
- 关键词搜索
- 分类筛选
- 深色/浅色主题切换
- 自动生成目录
- Markdown 渲染
- 代码语法高亮

---

## 开发指南

### 安装依赖

```bash
pnpm install
```

### 开发模式

```bash
pnpm dev
```

### 构建生产

```bash
pnpm build
```

### 类型检查

```bash
pnpm type-check
```

### 代码检查

```bash
pnpm lint
```

### 代码修复

```bash
pnpm lint:fix
```

---

## 相关文档

- [Blender 插件文档](../blender/00-总览.md)
- [后端服务器文档](../blender/06-后端服务器文档.md)
- [README.md](../../README.md)