# 阶段二：MCP 适配器实现

**文档版本**: 1.0.0
**创建日期**: 2026-01-13
**预计时间**: 3-4 天

---

## 1. 目标

实现基于 MCP 协议的服务器，支持 SSE (Server-Sent Events) 和 JSON-RPC 2.0 传输，确保 MCP 线程对 Blender API 的调用在主线程安全执行。

## 2. 架构设计

### 2.1 MCP 服务器架构

```
┌─────────────────────────────────────────┐
│           MCP Client (外部)              │
└──────────────────┬──────────────────────┘
                   │
                   │ SSE / JSON-RPC 2.0
                   │
┌──────────────────▼──────────────────────┐
│         Flask Server (端口 5000)        │
│  ┌──────────────────────────────────┐  │
│  │   /mcp/sse (SSE 端点)            │  │
│  │   /mcp/rpc (JSON-RPC 端点)       │  │
│  └──────────────┬───────────────────┘  │
└─────────────────┼──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│         MCP Server                      │
│  ┌──────────────────────────────────┐  │
│  │   Tool Registry                  │  │
│  │   Request Handler                │  │
│  │   Response Generator             │  │
│  └──────────────┬───────────────────┘  │
└─────────────────┼──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│       Blender Task Queue               │
│  ┌──────────────────────────────────┐  │
│  │   Task Queue (线程安全)          │  │
│  │   Result Storage                 │  │
│  │   Timer (bpy.app.timers)         │  │
│  └──────────────┬───────────────────┘  │
└─────────────────┼──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│       Core Modules (阶段一)            │
│  ┌──────────────────────────────────┐  │
│  │   hierarchy.py                   │  │
│  │   module_fetcher.py              │  │
│  │   node_filter.py                 │  │
│  │   node_parser.py                 │  │
│  │   config_reader.py               │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 2.2 模块划分

```
backend/mcp/
├── __init__.py           # 模块初始化
├── server.py             # MCP 服务器
├── tools.py              # MCP 工具定义
├── task_queue.py         # 任务队列管理
├── config_generator.py   # 配置生成器
└── protocol.py           # MCP 协议实现
```

## 3. 详细实现

### 3.1 任务队列管理 (`task_queue.py`)

#### 功能描述

实现一个基于 `bpy.app.timers` 的任务队列，确保 MCP 线程对 Blender API 的调用在主线程安全执行。

#### 类定义

```python
import bpy
import threading
import queue
import time
from typing import Callable, Any, Dict

class BlenderTaskQueue:
    """Blender 主线程任务队列"""
    
    def __init__(self):
        self.task_queue = queue.Queue()
        self.results = {}
        self.lock = threading.Lock()
        self.timer_registered = False
    
    def add_task(
        self,
        task_id: str,
        task_func: Callable,
        *args,
        **kwargs
    ) -> None:
        """
        添加任务到队列
        
        Args:
            task_id: 任务 ID
            task_func: 任务函数
            *args: 位置参数
            **kwargs: 关键字参数
        """
        with self.lock:
            self.task_queue.put({
                'id': task_id,
                'func': task_func,
                'args': args,
                'kwargs': kwargs
            })
            
            # 如果还没有注册定时器，注册一个
            if not self.timer_registered:
                bpy.app.timers.register(self._process_queue)
                self.timer_registered = True
    
    def _process_queue(self) -> float:
        """
        在 Blender 主线程处理队列中的任务
        
        Returns:
            float: 下次执行的时间间隔（秒）
        """
        try:
            while not self.task_queue.empty():
                task = self.task_queue.get()
                
                try:
                    # 执行任务
                    result = task['func'](*task['args'], **task['kwargs'])
                    
                    # 存储结果
                    with self.lock:
                        self.results[task['id']] = {
                            'status': 'success',
                            'data': result
                        }
                except Exception as e:
                    # 存储错误
                    with self.lock:
                        self.results[task['id']] = {
                            'status': 'error',
                            'error': str(e)
                        }
        except Exception as e:
            print(f"处理任务队列时出错: {e}")
        
        # 返回 0.1 秒后再次检查
        return 0.1
    
    def get_result(
        self,
        task_id: str,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        获取任务结果（阻塞等待）
        
        Args:
            task_id: 任务 ID
            timeout: 超时时间（秒）
        
        Returns:
            dict: 任务结果
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.lock:
                if task_id in self.results:
                    return self.results.pop(task_id)
            
            time.sleep(0.1)
        
        return {
            'status': 'timeout',
            'error': f'Task {task_id} timeout after {timeout} seconds'
        }
    
    def has_result(self, task_id: str) -> bool:
        """
        检查任务是否已有结果
        
        Args:
            task_id: 任务 ID
        
        Returns:
            bool: 是否已有结果
        """
        with self.lock:
            return task_id in self.results
    
    def get_all_results(self) -> Dict[str, Any]:
        """
        获取所有待处理的结果
        
        Returns:
            dict: 所有结果
        """
        with self.lock:
            results = self.results.copy()
            self.results.clear()
            return results
    
    def clear_results(self) -> None:
        """清空所有结果"""
        with self.lock:
            self.results.clear()
```

#### 使用示例

```python
from backend.mcp.task_queue import blender_task_queue

# 添加任务
task_id = "task_123"
blender_task_queue.add_task(
    task_id,
    some_blender_function,
    arg1, arg2,
    kwarg1=value1
)

# 获取结果
result = blender_task_queue.get_result(task_id, timeout=30)
if result['status'] == 'success':
    print(result['data'])
else:
    print(f"Error: {result['error']}")
```

---

### 3.2 MCP 协议实现 (`protocol.py`)

#### 功能描述

实现 JSON-RPC 2.0 消息格式和 MCP 协议规范。

#### 函数定义

```python
import json
import uuid
from typing import Dict, Any, Optional

class JSONRPCError:
    """JSON-RPC 2.0 错误码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

def create_jsonrpc_request(
    method: str,
    params: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建 JSON-RPC 2.0 请求
    
    Args:
        method: 方法名
        params: 参数
        request_id: 请求 ID
    
    Returns:
        dict: JSON-RPC 请求
    """
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "id": request_id or str(uuid.uuid4())
    }
    
    if params is not None:
        request["params"] = params
    
    return request

def create_jsonrpc_response(
    result: Optional[Any] = None,
    error: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建 JSON-RPC 2.0 响应
    
    Args:
        result: 结果
        error: 错误
        request_id: 请求 ID
    
    Returns:
        dict: JSON-RPC 响应
    """
    response = {
        "jsonrpc": "2.0",
        "id": request_id
    }
    
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    
    return response

def create_jsonrpc_error(
    code: int,
    message: str,
    data: Optional[Any] = None
) -> Dict[str, Any]:
    """
    创建 JSON-RPC 2.0 错误
    
    Args:
        code: 错误码
        message: 错误消息
        data: 错误数据
    
    Returns:
        dict: JSON-RPC 错误
    """
    error = {
        "code": code,
        "message": message
    }
    
    if data is not None:
        error["data"] = data
    
    return error

def validate_jsonrpc_request(request: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    验证 JSON-RPC 2.0 请求
    
    Args:
        request: 请求对象
    
    Returns:
        tuple: (是否有效, 错误消息)
    """
    if not isinstance(request, dict):
        return False, "Request must be a JSON object"
    
    if "jsonrpc" not in request:
        return False, "Missing 'jsonrpc' field"
    
    if request["jsonrpc"] != "2.0":
        return False, "Invalid 'jsonrpc' version"
    
    if "method" not in request:
        return False, "Missing 'method' field"
    
    if not isinstance(request["method"], str):
        return False, "'method' must be a string"
    
    return True, None
```

---

### 3.3 MCP 服务器 (`server.py`)

#### 功能描述

实现 MCP 服务器，支持工具注册、请求处理和响应生成。

#### 类定义

```python
import json
import uuid
from typing import Dict, Any, Callable
from backend.mcp.protocol import (
    create_jsonrpc_response,
    create_jsonrpc_error,
    validate_jsonrpc_request,
    JSONRPCError
)
from backend.mcp.task_queue import blender_task_queue

class MCPServer:
    """MCP 服务器"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 5000):
        """
        初始化 MCP 服务器
        
        Args:
            host: 主机地址
            port: 端口号
        """
        self.host = host
        self.port = port
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.task_queue = blender_task_queue
    
    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable
    ) -> None:
        """
        注册 MCP 工具
        
        Args:
            name: 工具名称
            description: 工具描述
            handler: 处理函数
        """
        self.tools[name] = {
            "name": name,
            "description": description,
            "handler": handler
        }
        print(f"Registered MCP tool: {name}")
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理 MCP 请求
        
        Args:
            request: JSON-RPC 请求
        
        Returns:
            dict: JSON-RPC 响应
        """
        # 验证请求
        is_valid, error_msg = validate_jsonrpc_request(request)
        if not is_valid:
            return create_jsonrpc_response(
                error=create_jsonrpc_error(
                    JSONRPCError.INVALID_REQUEST,
                    error_msg
                ),
                request_id=request.get('id')
            )
        
        method = request["method"]
        params = request.get("params", {})
        request_id = request.get('id')
        
        # 处理 methods/call 请求
        if method == "methods/call":
            return self._handle_tool_call(params, request_id)
        
        # 处理 methods/list 请求
        elif method == "methods/list":
            return self._handle_list_methods(request_id)
        
        # 处理 tools/list 请求
        elif method == "tools/list":
            return self._handle_list_tools(request_id)
        
        # 处理 tools/call 请求
        elif method == "tools/call":
            return self._handle_tool_call(params, request_id)
        
        # 未知方法
        else:
            return create_jsonrpc_response(
                error=create_jsonrpc_error(
                    JSONRPCError.METHOD_NOT_FOUND,
                    f"Method not found: {method}"
                ),
                request_id=request_id
            )
    
    def _handle_list_methods(self, request_id: Optional[str]) -> Dict[str, Any]:
        """处理 methods/list 请求"""
        methods = [
            {
                "name": "methods/list",
                "description": "List all available methods"
            },
            {
                "name": "methods/call",
                "description": "Call a method"
            },
            {
                "name": "tools/list",
                "description": "List all available tools"
            },
            {
                "name": "tools/call",
                "description": "Call a tool"
            }
        ]
        
        return create_jsonrpc_response(
            result={"methods": methods},
            request_id=request_id
        )
    
    def _handle_list_tools(self, request_id: Optional[str]) -> Dict[str, Any]:
        """处理 tools/list 请求"""
        tools = []
        for tool_name, tool_info in self.tools.items():
            tools.append({
                "name": tool_info["name"],
                "description": tool_info["description"]
            })
        
        return create_jsonrpc_response(
            result={"tools": tools},
            request_id=request_id
        )
    
    def _handle_tool_call(
        self,
        params: Dict[str, Any],
        request_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        处理工具调用请求
        
        Args:
            params: 请求参数
            request_id: 请求 ID
        
        Returns:
            dict: JSON-RPC 响应
        """
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        if not tool_name:
            return create_jsonrpc_response(
                error=create_jsonrpc_error(
                    JSONRPCError.INVALID_PARAMS,
                    "Missing 'name' parameter"
                ),
                request_id=request_id
            )
        
        if tool_name not in self.tools:
            return create_jsonrpc_response(
                error=create_jsonrpc_error(
                    JSONRPCError.METHOD_NOT_FOUND,
                    f"Tool not found: {tool_name}"
                ),
                request_id=request_id
            )
        
        # 生成任务 ID
        task_id = f"{tool_name}_{uuid.uuid4().hex[:8]}"
        
        # 添加任务到队列
        self.task_queue.add_task(
            task_id,
            self.tools[tool_name]["handler"],
            **tool_args
        )
        
        # 等待结果
        result = self.task_queue.get_result(task_id, timeout=30)
        
        if result['status'] == 'success':
            return create_jsonrpc_response(
                result=result['data'],
                request_id=request_id
            )
        else:
            return create_jsonrpc_response(
                error=create_jsonrpc_error(
                    JSONRPCError.INTERNAL_ERROR,
                    result['error']
                ),
                request_id=request_id
            )
    
    def has_pending_results(self) -> bool:
        """
        检查是否有待处理的结果
        
        Returns:
            bool: 是否有待处理的结果
        """
        return len(self.task_queue.results) > 0
    
    def get_pending_results(self) -> Dict[str, Any]:
        """
        获取所有待处理的结果
        
        Returns:
            dict: 所有结果
        """
        return self.task_queue.get_all_results()
```

---

### 3.4 MCP 工具定义 (`tools.py`)

#### 功能描述

定义所有 MCP 工具，并注册到 MCP 服务器。

#### 工具列表

| 工具名称 | 描述 | 对应模块 |
|----------|------|----------|
| `get_full_tree` | 获取全局资产路径 | `hierarchy.py` |
| `inspect_module` | 定位模块并提取数据 | `module_fetcher.py` + `node_parser.py` + `node_filter.py` |
| `get_config` | 读取配置 | `config_reader.py` |
| `parse_node_tree` | 解析节点树 | `node_parser.py` |
| `filter_node_data` | 过滤节点数据 | `node_filter.py` |

#### 实现代码

```python
from backend.core.hierarchy import get_hierarchy
from backend.core.module_fetcher import fetch_module
from backend.core.node_filter import filter_node_data
from backend.core.node_parser import parse_node_tree
from backend.core.config_reader import get_config

def register_mcp_tools(server):
    """
    注册所有 MCP 工具
    
    Args:
        server: MCP 服务器实例
    """
    
    # get_full_tree 工具
    def handle_get_full_tree(**kwargs):
        """处理 get_full_tree 工具调用"""
        include_geometry = kwargs.get('include_geometry', True)
        include_materials = kwargs.get('include_materials', True)
        include_compositor = kwargs.get('include_compositor', True)
        include_world = kwargs.get('include_world', True)
        include_textures = kwargs.get('include_textures', True)
        
        return get_hierarchy(
            include_geometry=include_geometry,
            include_materials=include_materials,
            include_compositor=include_compositor,
            include_world=include_world,
            include_textures=include_textures
        )
    
    server.register_tool(
        name="get_full_tree",
        description="获取 Blender 中所有资产的层级结构，包括几何节点组、材质、合成节点树等",
        handler=handle_get_full_tree
    )
    
    # inspect_module 工具
    def handle_inspect_module(**kwargs):
        """处理 inspect_module 工具调用"""
        path = kwargs.get('path')
        filter_level = kwargs.get('filter_level', 'STANDARD')
        
        if not path:
            return {
                "status": "Error",
                "error": "Missing 'path' parameter"
            }
        
        # 定位模块
        module_result = fetch_module(path)
        if module_result['status'] != 'Success':
            return module_result
        
        # 解析节点树
        node_tree = module_result['data'].get('node_tree')
        if node_tree:
            parsed_result = parse_node_tree(node_tree)
            if parsed_result['status'] == 'Success':
                # 过滤数据
                filtered_result = filter_node_data(
                    parsed_result['data'],
                    filter_level
                )
                return filtered_result
        
        return module_result
    
    server.register_tool(
        name="inspect_module",
        description="根据路径定位 Blender 数据块，解析节点树并返回过滤后的数据",
        handler=handle_inspect_module
    )
    
    # get_config 工具
    def handle_get_config(**kwargs):
        """处理 get_config 工具调用"""
        config_key = kwargs.get('config_key')
        
        if not config_key:
            return {
                "status": "Error",
                "error": "Missing 'config_key' parameter"
            }
        
        return get_config(config_key)
    
    server.register_tool(
        name="get_config",
        description="读取配置文件中的预设和设置",
        handler=handle_get_config
    )
    
    # parse_node_tree 工具
    def handle_parse_node_tree(**kwargs):
        """处理 parse_node_tree 工具调用"""
        # 注意：这个工具需要传入实际的 Blender 节点树对象
        # 在 MCP 上下文中，可能需要先通过 fetch_module 获取
        # 这里仅作为示例
        return {
            "status": "Error",
            "error": "This tool requires a Blender node tree object. Use inspect_module instead."
        }
    
    server.register_tool(
        name="parse_node_tree",
        description="解析节点树（需要先通过 fetch_module 获取节点树对象）",
        handler=handle_parse_node_tree
    )
    
    # filter_node_data 工具
    def handle_filter_node_data(**kwargs):
        """处理 filter_node_data 工具调用"""
        raw_data = kwargs.get('raw_data')
        filter_level = kwargs.get('filter_level', 'STANDARD')
        
        if not raw_data:
            return {
                "status": "Error",
                "error": "Missing 'raw_data' parameter"
            }
        
        return filter_node_data(raw_data, filter_level)
    
    server.register_tool(
        name="filter_node_data",
        description="过滤节点数据",
        handler=handle_filter_node_data
    )
```

---

### 3.5 集成到 Flask 服务器

#### 修改 `backend/server.py`

```python
# 在文件顶部添加导入
from backend.mcp.server import MCPServer
from backend.mcp.tools import register_mcp_tools

# 初始化 MCP 服务器
mcp_server = MCPServer(host='127.0.0.1', port=5000)

# 注册 MCP 工具
register_mcp_tools(mcp_server)

# 添加 SSE 端点
@app.route('/mcp/sse', methods=['GET'])
def mcp_sse():
    """MCP SSE 端点"""
    def generate():
        try:
            yield "event: connected\ndata: {\"status\":\"connected\"}\n\n"
            
            while True:
                # 检查是否有新的任务结果
                if mcp_server.has_pending_results():
                    results = mcp_server.get_pending_results()
                    for task_id, result in results.items():
                        yield f"event: message\ndata: {json.dumps(result)}\n\n"
                
                # 心跳
                yield "event: heartbeat\ndata: {}\n\n"
                time.sleep(1)
        except GeneratorExit:
            print("SSE 客户端断开连接")
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

# 添加 JSON-RPC 端点
@app.route('/mcp/rpc', methods=['POST'])
def mcp_rpc():
    """MCP JSON-RPC 2.0 端点"""
    try:
        request_data = request.get_json()
        
        # 处理请求
        result = mcp_server.handle_request(request_data)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": str(e)
            },
            "id": request_data.get('id') if request_data else None
        }), 500
```

---

## 4. 实施步骤

### 步骤 1: 创建 MCP 模块目录结构

```bash
mkdir -p backend/mcp
touch backend/mcp/__init__.py
```

### 步骤 2: 实现任务队列

1. 创建 `backend/mcp/task_queue.py`
2. 实现 `BlenderTaskQueue` 类
3. 测试任务队列的线程安全性

### 步骤 3: 实现 MCP 协议

1. 创建 `backend/mcp/protocol.py`
2. 实现 JSON-RPC 2.0 消息格式
3. 实现消息解析和生成

### 步骤 4: 实现 MCP 服务器

1. 创建 `backend/mcp/server.py`
2. 实现 `MCPServer` 类
3. 实现请求处理逻辑

### 步骤 5: 实现 MCP 工具

1. 创建 `backend/mcp/tools.py`
2. 实现工具注册机制
3. 实现所有 MCP 工具处理器

### 步骤 6: 集成到 Flask 服务器

1. 修改 `backend/server.py`
2. 添加 `/mcp/sse` 路由
3. 添加 `/mcp/rpc` 路由
4. 初始化 MCP 服务器

### 步骤 7: MCP 服务器测试

1. 启动 MCP 服务器
2. 测试 SSE 连接
3. 测试 JSON-RPC 请求
4. 测试所有 MCP 工具

---

## 5. 测试用例

### 5.1 任务队列测试

```python
# 测试任务队列
def test_task_queue():
    from backend.mcp.task_queue import blender_task_queue
    
    # 添加任务
    task_id = "test_task"
    blender_task_queue.add_task(
        task_id,
        lambda: {"result": "success"}
    )
    
    # 获取结果
    result = blender_task_queue.get_result(task_id)
    assert result['status'] == 'success'
```

### 5.2 MCP 服务器测试

```python
# 测试 MCP 服务器
def test_mcp_server():
    from backend.mcp.server import MCPServer
    
    server = MCPServer()
    
    # 测试 methods/list
    request = {
        "jsonrpc": "2.0",
        "method": "methods/list",
        "id": "1"
    }
    response = server.handle_request(request)
    assert response["result"]["methods"]
```

### 5.3 工具调用测试

```python
# 测试工具调用
def test_tool_call():
    from backend.mcp.server import MCPServer
    from backend.mcp.tools import register_mcp_tools
    
    server = MCPServer()
    register_mcp_tools(server)
    
    # 调用 get_config 工具
    request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_config",
            "arguments": {
                "config_key": "system_message_presets"
            }
        },
        "id": "1"
    }
    response = server.handle_request(request)
    assert response["result"]["status"] == "Success"
```

---

## 6. 验收标准

### 6.1 功能验收

- ✅ MCP 服务器正常启动
- ✅ SSE 连接稳定
- ✅ JSON-RPC 请求正确处理
- ✅ 所有 MCP 工具正常工作
- ✅ 任务队列正确执行

### 6.2 性能验收

- ✅ MCP 服务器响应时间 < 100ms
- ✅ 任务队列执行时间 < 1s
- ✅ 内存占用 < 100MB

### 6.3 兼容性验收

- ✅ 现有 Web 功能不受影响
- ✅ 现有 API 接口保持兼容

---

**文档结束**