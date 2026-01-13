#!/usr/bin/env python3
"""
MCP Adapter for Blender AI Node Analyzer
连接到 Blender 插件的 Socket 服务器，实现 MCP 协议
"""

import sys
import json
import socket
import threading
import time
from typing import Dict, Any, Optional


class BlenderMCPAdapter:
    """MCP 适配器，连接到 Blender 插件的 Socket 服务器"""
    
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.lock = threading.Lock()
        
    def connect(self) -> bool:
        """连接到 Blender Socket 服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"Connected to Blender MCP server at {self.host}:{self.port}", file=sys.stderr)
            return True
        except Exception as e:
            print(f"Failed to connect to Blender: {e}", file=sys.stderr)
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        self.connected = False
    
    def send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """发送命令到 Blender 并获取响应"""
        with self.lock:
            if not self.connected:
                if not self.connect():
                    return {
                        "jsonrpc": "2.0",
                        "id": command.get("id", 0),
                        "error": {
                            "code": -32000,
                            "message": "Failed to connect to Blender"
                        }
                    }
            
            try:
                # 发送命令
                command_json = json.dumps(command)
                self.socket.sendall(command_json.encode('utf-8'))
                
                # 接收响应
                response_data = b''
                while True:
                    chunk = self.socket.recv(8192)
                    if not chunk:
                        break
                    response_data += chunk
                    # 尝试解析 JSON
                    try:
                        response = json.loads(response_data.decode('utf-8'))
                        return response
                    except json.JSONDecodeError:
                        # 数据不完整，继续接收
                        pass
                
                return {
                    "jsonrpc": "2.0",
                    "id": command.get("id", 0),
                    "error": {
                        "code": -32001,
                        "message": "No response from Blender"
                    }
                }
            except socket.timeout:
                return {
                    "jsonrpc": "2.0",
                    "id": command.get("id", 0),
                    "error": {
                        "code": -32002,
                        "message": "Timeout waiting for Blender response"
                    }
                }
            except Exception as e:
                print(f"Error communicating with Blender: {e}", file=sys.stderr)
                self.connected = False
                return {
                    "jsonrpc": "2.0",
                    "id": command.get("id", 0),
                    "error": {
                        "code": -32003,
                        "message": f"Communication error: {str(e)}"
                    }
                }


class MCPServer:
    """MCP 服务器实现"""
    
    def __init__(self):
        self.blender_adapter = BlenderMCPAdapter()
        self.request_id = 0
    
    def send_response(self, response: Dict[str, Any]):
        """发送响应到 stdout"""
        response_json = json.dumps(response)
        print(response_json, flush=True)
    
    def handle_request(self, request: Dict[str, Any]):
        """处理 MCP 请求"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "initialize":
            return self.handle_initialize(request_id, params)
        elif method == "tools/list":
            return self.handle_tools_list(request_id)
        elif method == "tools/call":
            return self.handle_tools_call(request_id, params)
        elif method == "shutdown":
            return self.handle_shutdown(request_id)
        else:
            return self.send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            })
    
    def handle_initialize(self, request_id: int, params: Dict[str, Any]):
        """处理初始化请求"""
        return self.send_response({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "blender-ai-node-analyzer",
                    "version": "1.0.0"
                },
                "capabilities": {
                    "tools": {}
                }
            }
        })
    
    def handle_tools_list(self, request_id: int):
        """处理工具列表请求"""
        # 从 Blender 获取工具列表
        command = {
            "type": "get_tools_list",
            "params": {}
        }
        
        response = self.blender_adapter.send_command(command)
        
        if response.get("status") == "success":
            tools = response.get("result", {}).get("tools", [])
            return self.send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": tools
                }
            })
        else:
            return self.send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32010,
                    "message": "Failed to get tools list from Blender"
                }
            })
    
    def handle_tools_call(self, request_id: int, params: Dict[str, Any]):
        """处理工具调用请求"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        # 构建发送到 Blender 的命令
        command = {
            "type": tool_name,
            "params": arguments
        }
        
        response = self.blender_adapter.send_command(command)
        
        if response.get("status") == "success":
            result = response.get("result")
            return self.send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            })
        else:
            error_msg = response.get("message", "Unknown error")
            return self.send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32011,
                    "message": f"Tool execution failed: {error_msg}"
                }
            })
    
    def handle_shutdown(self, request_id: int):
        """处理关闭请求"""
        self.blender_adapter.disconnect()
        return self.send_response({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {}
        })
    
    def run(self):
        """运行 MCP 服务器"""
        print("Blender MCP Adapter starting...", file=sys.stderr)
        
        # 尝试连接到 Blender
        if not self.blender_adapter.connect():
            print("Warning: Could not connect to Blender. Will retry on tool calls.", file=sys.stderr)
        
        # 从 stdin 读取请求
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    request = json.loads(line)
                    self.handle_request(request)
                except json.JSONDecodeError as e:
                    print(f"Failed to parse request: {e}", file=sys.stderr)
                    self.send_response({
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": "Parse error"
                        }
                    })
        except KeyboardInterrupt:
            print("Shutting down...", file=sys.stderr)
        finally:
            self.blender_adapter.disconnect()


def main():
    """主函数"""
    server = MCPServer()
    server.run()


if __name__ == "__main__":
    main()