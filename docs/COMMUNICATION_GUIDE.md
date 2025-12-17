# Blender 插件后端服务器通信实现指南

## 1. 实现概述

本文档详细说明了如何在Blender插件中实现后端服务器功能，实现与浏览器的通信。此功能允许用户通过网页界面与Blender插件进行交互，扩展了插件的功能和使用场景。

## 2. 技术架构

### 2.1 核心技术栈
- **Flask**: 轻量级Python Web框架，用于构建后端API服务器
- **Flask-CORS**: 处理跨域请求，允许浏览器访问API
- **bpy**: Blender Python API，用于访问Blender内部数据和功能
- **Threading**: 在后台线程中运行服务器，避免阻塞Blender UI

### 2.2 系统组件
1. **后端服务器** (server.py) - Flask应用，提供REST API
2. **前端页面** (frontend.html) - 浏览器界面，与服务器通信
3. **Blender插件** (__init__.py) - 集成服务器管理功能
4. **通信协议** - JSON格式的API请求/响应

## 3. 实现细节

### 3.1 后端服务器 (backend/server.py)

```python
class ServerManager:
    def __init__(self):
        # 初始化服务器参数
        self.server_thread = None
        self.is_running = False
        self.host = '127.0.0.1'
        self.port = 5000
    
    def start_server(self, port=None):
        # 在后台线程中启动Flask服务器
        pass
```

**关键API端点:**
- `GET /` - 提供前端页面
- `GET /api/test-connection` - 测试连接
- `GET /api/status` - 获取Blender插件状态
- `POST /api/send-message` - 发送消息到Blender
- `GET /api/get-messages` - 获取消息列表
- `POST /api/clear-messages` - 清空消息列表
- `POST /api/execute-operation` - 执行Blender操作

### 3.2 插件集成 (__init__.py)

- **服务器管理**: 使用`ServerManager`管理后端服务器生命周期
- **UI集成**: 将服务器控制按钮集成到插件面板
- **状态同步**: 服务器状态与插件UI同步更新

### 3.3 前端界面 (frontend.html)

- 基于HTML/JavaScript的网页界面
- 通过fetch API与后端服务器通信
- 实时显示服务器状态和操作结果

## 4. 通信流程

### 4.1 服务器启动流程
1. 插件注册时初始化`ServerManager`
2. 用户点击"启动服务器"按钮
3. `toggle_backend_server`运算符启动后端
4. 服务器在后台线程中运行，监听指定端口
5. 更新插件状态和UI显示

### 4.2 浏览器-服务器通信流程
1. 浏览器发起HTTP请求到`http://127.0.0.1:{port}/api/...`
2. Flask服务器接收请求并处理
3. 服务器与Blender上下文交互，执行相应操作
4. 返回JSON格式的响应到浏览器

## 5. 常见问题及解决方案

### 5.1 服务器无法启动
**问题:** 服务器启动失败或无法连接
**解决方案:**
- 检查端口是否被其他应用占用
- 确认Flask和Flask-CORS已正确安装
- 验证Blender的Python环境是否支持所需依赖

### 5.2 依赖安装问题
**问题:** 在Blender环境中无法安装Flask
**解决方案:**
```python
try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "flask-cors"])
```

### 5.3 跨域请求问题
**问题:** 浏览器报跨域错误
**解决方案:** 
- 使用Flask-CORS扩展
- 配置适当的CORS策略

### 5.4 Blender UI卡顿
**问题:** 启动服务器后Blender界面卡顿
**解决方案:**
- 将服务器运行在后台线程中
- 使用`threaded=True`和`daemon=True`参数

### 5.5 服务器状态不同步
**问题:** UI显示的服务器状态与实际不符
**解决方案:**
- 在`toggle_backend_server`运算符中同步更新`enable_backend`属性
- 确保服务器状态变化时UI及时更新

## 6. 优化策略

### 6.1 性能优化
- 默认禁用后端服务器，避免插件启动延迟
- 按需启动服务器，只在用户需要时运行
- 移除不必要的自动启动机制

### 6.2 UI优化
- 单一按钮实现启动/停止切换功能
- 简洁的UI布局，减少界面复杂性
- 状态指示器准确反映服务器运行状况

### 6.3 错误处理
- 完善的异常捕获和错误报告
- 优雅的错误处理机制
- 提供清晰的错误提示信息

## 7. 部署注意事项

### 7.1 依赖管理
- 确保目标环境中安装了Flask和Flask-CORS
- 考虑离线安装或包含依赖包的分发方式

### 7.2 网络安全
- 服务器仅在本地(127.0.0.1)监听
- 默认端口设置为5000，可自定义
- 建议不要在生产环境中暴露到外网

### 7.3 兼容性
- 兼容Blender 4.2+版本
- 跨平台支持(Windows, macOS, Linux)
- 向后兼容现有插件功能

## 8. 维护建议

1. **定期更新**: 保持Flask等依赖库在安全版本
2. **监控日志**: 添加详细的日志记录以方便调试
3. **错误处理**: 持续改进错误处理和用户反馈机制
4. **性能监控**: 监控服务器对Blender性能的影响
5. **安全审计**: 定期检查API安全性

## 9. 扩展方向

- WebSocket支持，实现双向实时通信
- 用户认证和授权机制
- 数据持久化和历史记录功能
- 高级API功能和操作类型
- 多语言支持和国际化