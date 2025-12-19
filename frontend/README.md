# 前端现代化重构说明

## 结构
- `src/index.html`：页面结构与资源引入（使用 `type=module`）。
- `src/css/tokens.css`：设计令牌（颜色、间距、字体、圆角、阴影）。
- `src/css/theme.css`：暗/亮主题基础样式与焦点可见性。
- `src/css/components.css`：组件通用样式（面板、按钮、列表、滚动条、骨架）。
- `src/css/style.css`：页面局部布局与覆盖（已接入令牌）。
- `src/js/state.js`：共享状态与元素引用。
- `src/js/api.js`：后端 API 封装（保持原有路径与参数）。
- `src/js/ui.js`：状态栏更新、按钮状态控制、输入填充。
- `src/js/render.js`：安全渲染与基础 Markdown（代码块）。
- `src/js/main.js`：入口编排（初始化、事件绑定、数据流）。

## 主题
- 页面右上角 `主题` 按钮可在暗/亮模式切换，偏好保存在 `localStorage`。
- 同时支持系统暗色偏好（`prefers-color-scheme`）。

## 骨架与空态
- 历史与响应区域在加载时显示骨架占位，提升感知性能与反馈。

## 安全渲染
- 响应内容以文本插入，防止 HTML 注入。
- 对三引号代码块进行基础格式化并保留原样。

## 开发建议
- 如需扩展组件样式，优先在 `components.css` 增加通用类，再在 `style.css` 做局部覆盖。
- 如需调整主题色，统一在 `tokens.css` 中修改变量。
