#!/usr/bin/env python3
"""
快速测试节点信息获取工具
"""

import sys
import json
import socket
import time


def test_node_tools():
    """测试节点信息获取工具"""
    print("="*60)
    print("测试节点信息获取工具")
    print("="*60)
    
    # 连接到 Blender
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        sock.connect(('localhost', 9876))
        print("✓ 已连接到 Blender")
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        print("\n请确保：")
        print("1. Blender 正在运行")
        print("2. AI Node Analyzer 插件已启用")
        print("3. MCP 服务器正在运行（端口 9876）")
        print("4. **重要：您必须在节点编辑器中！**")
        return
    
    # 测试工具列表
    print("\n1. 获取工具列表...")
    command = {"type": "get_tools_list", "params": {}}
    sock.sendall(json.dumps(command).encode('utf-8'))
    
    response_data = b''
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        response_data += chunk
        try:
            response = json.loads(response_data.decode('utf-8'))
            break
        except json.JSONDecodeError:
            pass
    
    if response.get("status") == "success":
        tools = response.get("result", {}).get("tools", [])
        print(f"✓ 工具列表获取成功，共 {len(tools)} 个工具")
    else:
        print(f"✗ 工具列表获取失败: {response}")
        sock.close()
        return
    
    # 测试获取选中节点信息
    print("\n2. 测试获取选中节点信息...")
    print("   提示：请在 Blender 中选择一些节点")
    input("   按 Enter 继续...")
    
    command = {"type": "get_selected_nodes_info", "params": {}}
    sock.sendall(json.dumps(command).encode('utf-8'))
    
    response_data = b''
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        response_data += chunk
        try:
            response = json.loads(response_data.decode('utf-8'))
            break
        except json.JSONDecodeError:
            pass
    
    print(f"\n响应:")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    
    if response.get("status") == "success":
        result = response.get("result", {})
        
        # 检查结果是否是字典
        if isinstance(result, dict):
            count = result.get("selected_nodes_count", 0)
            if count > 0:
                print(f"\n✓ 成功获取 {count} 个选中节点的信息")
            elif "node_tree_type" in result:
                print(f"\n✓ 成功获取节点信息（但未选中节点）")
            else:
                print(f"\n✓ 成功获取节点信息")
        else:
            print(f"\n✓ 成功获取节点信息")
    else:
        error = response.get("message", "未知错误")
        print(f"\n✗ 获取失败: {error}")
        if "Not in Node Editor" in error:
            print("\n   解决方法：请在 Blender 中切换到节点编辑器视图")
        elif "No selected nodes" in error:
            print("\n   解决方法：请在 Blender 中选择一些节点")
        elif "No active node tree" in error:
            print("\n   解决方法：请在 Blender 中打开或创建一个节点树")
    
    # 测试获取所有节点信息
    print("\n3. 测试获取所有节点信息...")
    command = {"type": "get_all_nodes_info", "params": {}}
    sock.sendall(json.dumps(command).encode('utf-8'))
    
    response_data = b''
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        response_data += chunk
        try:
            response = json.loads(response_data.decode('utf-8'))
            break
        except json.JSONDecodeError:
            pass
    
    print(f"\n响应:")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    
    if response.get("status") == "success":
        result = response.get("result", {})
        
        # 检查结果是否是字典
        if isinstance(result, dict):
            if "node_tree_type" in result:
                print(f"\n✓ 成功获取所有节点信息")
            else:
                print(f"\n✓ 成功获取节点信息")
        else:
            print(f"\n✓ 成功获取节点信息")
    else:
        error = response.get("message", "未知错误")
        print(f"\n✗ 获取失败: {error}")
        if "Not in Node Editor" in error:
            print("\n   解决方法：请在 Blender 中切换到节点编辑器视图")
        elif "No active node tree" in error:
            print("\n   解决方法：请在 Blender 中打开或创建一个节点树")
    
    sock.close()
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    print("\n注意：此测试要求您在 Blender 的节点编辑器中！")
    print("请确保：")
    print("  1. Blender 正在运行")
    print("  2. AI Node Analyzer 插件已启用")
    print("  3. MCP 服务器正在运行（端口 9876）")
    print("  4. **您在节点编辑器中**（Geometry Nodes、Shader Nodes 等）")
    print("  5. 已打开一个节点树")
    print()
    
    test_node_tools()