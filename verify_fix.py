#!/usr/bin/env python3
"""
验证 MCP 工具修复
"""

import sys
import json
import socket


def verify_fix():
    """验证修复"""
    print("="*60)
    print("验证 MCP 工具修复")
    print("="*60)
    
    # 连接到 Blender
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        sock.connect(('localhost', 9876))
        print("✓ 已连接到 Blender")
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        return
    
    # 测试 1: 成功情况（有选中节点）
    print("\n" + "="*60)
    print("测试 1: 获取选中节点信息（成功情况）")
    print("="*60)
    print("\n请在 Blender 中选择一些节点，然后按 Enter 继续...")
    input()
    
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
    
    # 检查响应格式
    if response.get("status") == "success":
        result = response.get("result")
        if isinstance(result, dict):
            if "selected_nodes_count" in result:
                count = result["selected_nodes_count"]
                print(f"\n✓ 测试通过！成功获取 {count} 个节点")
            else:
                print(f"\n⚠ 响应格式正确，但没有节点信息")
        else:
            print(f"\n✗ 测试失败：结果不是字典")
    else:
        print(f"\n✗ 测试失败：{response.get('message')}")
    
    # 测试 2: 错误情况（不在节点编辑器）
    print("\n" + "="*60)
    print("测试 2: 获取选中节点信息（错误情况）")
    print("="*60)
    print("\n请在 Blender 中切换到非节点编辑器视图（如 3D Viewport），然后按 Enter 继续...")
    input()
    
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
    
    # 检查响应格式
    if response.get("status") == "error":
        print(f"\n✓ 测试通过！正确返回错误状态")
        print(f"  错误消息: {response.get('message')}")
    else:
        print(f"\n✗ 测试失败：应该返回错误状态")
    
    sock.close()
    
    print("\n" + "="*60)
    print("验证完成")
    print("="*60)


if __name__ == "__main__":
    verify_fix()