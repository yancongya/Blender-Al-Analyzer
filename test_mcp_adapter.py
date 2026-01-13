#!/usr/bin/env python3
"""
MCP 适配器测试脚本
用于测试 MCP 适配器是否能正常连接到 Blender 并获取工具列表
"""

import sys
import json
import subprocess
import time


def test_mcp_adapter():
    """测试 MCP 适配器"""
    print("=" * 60)
    print("MCP 适配器测试")
    print("=" * 60)
    
    # 启动 MCP 适配器进程
    print("\n1. 启动 MCP 适配器...")
    adapter_path = r"D:\blender\Plugin\addons\ainode\mcp_adapter.py"
    
    try:
        process = subprocess.Popen(
            [sys.executable, adapter_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("✓ MCP 适配器已启动")
    except Exception as e:
        print(f"✗ 启动失败: {e}")
        return False
    
    # 等待适配器启动
    time.sleep(1)
    
    # 测试初始化
    print("\n2. 测试初始化请求...")
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    try:
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        response_data = json.loads(response)
        
        if response_data.get("result"):
            print("✓ 初始化成功")
            print(f"  服务器信息: {response_data['result']['serverInfo']}")
        else:
            print(f"✗ 初始化失败: {response_data.get('error')}")
            process.terminate()
            return False
    except Exception as e:
        print(f"✗ 初始化请求失败: {e}")
        process.terminate()
        return False
    
    # 测试获取工具列表
    print("\n3. 测试获取工具列表...")
    tools_list_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    
    try:
        process.stdin.write(json.dumps(tools_list_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        response_data = json.loads(response)
        
        if response_data.get("result"):
            tools = response_data["result"]["tools"]
            print(f"✓ 获取工具列表成功，共 {len(tools)} 个工具")
            
            # 显示前 5 个工具
            print("\n  可用工具（前 5 个）:")
            for i, tool in enumerate(tools[:5]):
                print(f"    {i+1}. {tool['name']}: {tool['description'][:60]}...")
            
            if len(tools) > 5:
                print(f"    ... 还有 {len(tools) - 5} 个工具")
        else:
            print(f"✗ 获取工具列表失败: {response_data.get('error')}")
            process.terminate()
            return False
    except Exception as e:
        print(f"✗ 获取工具列表请求失败: {e}")
        process.terminate()
        return False
    
    # 测试工具调用（get_scene_info）
    print("\n4. 测试工具调用（get_scene_info）...")
    tool_call_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_scene_info",
            "arguments": {}
        }
    }
    
    try:
        process.stdin.write(json.dumps(tool_call_request) + "\n")
        process.stdin.flush()
        
        # 等待响应
        time.sleep(0.5)
        response = process.stdout.readline()
        response_data = json.loads(response)
        
        if response_data.get("result"):
            print("✓ 工具调用成功")
            content = response_data["result"]["content"][0]["text"]
            scene_info = json.loads(content)
            print(f"  场景名称: {scene_info.get('name')}")
            print(f"  对象数量: {scene_info.get('object_count')}")
        else:
            error = response_data.get("error", {})
            print(f"✗ 工具调用失败: {error.get('message', '未知错误')}")
            process.terminate()
            return False
    except Exception as e:
        print(f"✗ 工具调用请求失败: {e}")
        process.terminate()
        return False
    
    # 关闭适配器
    print("\n5. 关闭 MCP 适配器...")
    shutdown_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "shutdown",
        "params": {}
    }
    
    try:
        process.stdin.write(json.dumps(shutdown_request) + "\n")
        process.stdin.flush()
        time.sleep(0.5)
        process.terminate()
        print("✓ MCP 适配器已关闭")
    except Exception as e:
        print(f"✗ 关闭失败: {e}")
        process.terminate()
    
    print("\n" + "=" * 60)
    print("所有测试通过！✓")
    print("=" * 60)
    print("\n您现在可以在 IDE 中配置 MCP 适配器了。")
    print("请参考 docs/MCP配置说明.md 进行配置。")
    
    return True


if __name__ == "__main__":
    print("\n注意：请确保 Blender 正在运行并且 AI Node Analyzer 插件已启用")
    print("并且 MCP 服务器正在端口 9876 上运行\n")
    
    input("按 Enter 键开始测试...")
    
    success = test_mcp_adapter()
    
    if not success:
        print("\n测试失败！请检查：")
        print("1. Blender 是否正在运行")
        print("2. AI Node Analyzer 插件是否已启用")
        print("3. MCP 服务器是否正在运行（端口 9876）")
        print("4. Python 路径是否正确")
    
    input("\n按 Enter 键退出...")