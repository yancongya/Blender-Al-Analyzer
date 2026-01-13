#!/usr/bin/env python3
"""
调试上下文问题
检查为什么 MCP 无法获取选中的节点
"""

import sys
import json
import socket


def debug_context():
    """调试上下文"""
    print("="*60)
    print("调试上下文问题")
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
    
    # 诊断 1: 检查当前上下文的选中节点
    print("\n" + "="*60)
    print("诊断 1: 检查当前上下文的选中节点")
    print("="*60)
    
    command = {
        "type": "execute_code",
        "params": {
            "code": """
import bpy

# 检查当前上下文
print("=== 上下文信息 ===")
print(f"当前区域类型: {bpy.context.area.type if bpy.context.area else 'None'}")
print(f"当前空间类型: {bpy.context.space_data.type if bpy.context.space_data else 'None'}")

# 检查节点树
if hasattr(bpy.context.space_data, 'node_tree'):
    print(f"节点树: {bpy.context.space_data.node_tree.name if bpy.context.space_data.node_tree else 'None'}")
    print(f"节点树类型: {bpy.context.space_data.node_tree.bl_idname if bpy.context.space_data.node_tree else 'None'}")
else:
    print("节点树: 不存在")

# 检查选中节点
print(f"\\n=== 选中节点 ===")
if hasattr(bpy.context, 'selected_nodes'):
    selected = list(bpy.context.selected_nodes)
    print(f"选中节点数量: {len(selected)}")
    for i, node in enumerate(selected):
        print(f"  {i+1}. {node.name} (selected={node.select})")
else:
    print("selected_nodes 属性不存在")

# 检查活动节点
print(f"\\n=== 活动节点 ===")
if hasattr(bpy.context, 'active_node'):
    active = bpy.context.active_node
    if active:
        print(f"活动节点: {active.name}")
    else:
        print("活动节点: None")
else:
    print("active_node 属性不存在")

# 检查所有节点
print(f"\\n=== 所有节点 ===")
if hasattr(bpy.context.space_data, 'node_tree') and bpy.context.space_data.node_tree:
    node_tree = bpy.context.space_data.node_tree
    print(f"节点树中的节点数量: {len(node_tree.nodes)}")
    for i, node in enumerate(node_tree.nodes):
        print(f"  {i+1}. {node.name} (selected={node.select})")
"""
        }
    }
    
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
        result = response.get("result", {})
        output = result.get("result", "")
        print(f"\n输出:")
        print(output)
    else:
        print(f"✗ 执行失败: {response}")
    
    # 诊断 2: 尝试直接从节点树获取选中节点
    print("\n" + "="*60)
    print("诊断 2: 从节点树获取选中节点")
    print("="*60)
    
    command = {
        "type": "execute_code",
        "params": {
            "code": """
import bpy

if hasattr(bpy.context.space_data, 'node_tree') and bpy.context.space_data.node_tree:
    node_tree = bpy.context.space_data.node_tree
    
    # 从节点树获取选中的节点
    selected_from_tree = [node for node in node_tree.nodes if node.select]
    
    print(f"从节点树获取的选中节点数量: {len(selected_from_tree)}")
    for i, node in enumerate(selected_from_tree):
        print(f"  {i+1}. {node.name}")
else:
    print("没有节点树")
"""
        }
    }
    
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
        result = response.get("result", {})
        output = result.get("result", "")
        print(f"\n输出:")
        print(output)
    else:
        print(f"✗ 执行失败: {response}")
    
    # 诊断 3: 尝试使用 bpy.ops.node.select_all 来选择
    print("\n" + "="*60)
    print("诊断 3: 测试选择操作")
    print("="*60)
    
    command = {
        "type": "execute_code",
        "params": {
            "code": """
import bpy

# 尝试全选节点
try:
    bpy.ops.node.select_all(action='SELECT')
    print("已全选所有节点")
    
    # 检查选择结果
    if hasattr(bpy.context, 'selected_nodes'):
        selected = list(bpy.context.selected_nodes)
        print(f"选择后选中节点数量: {len(selected)}")
except Exception as e:
    print(f"选择操作失败: {e}")
"""
        }
    }
    
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
        result = response.get("result", {})
        output = result.get("result", "")
        print(f"\n输出:")
        print(output)
    else:
        print(f"✗ 执行失败: {response}")
    
    sock.close()
    
    print("\n" + "="*60)
    print("调试完成")
    print("="*60)
    print("\n如果诊断显示选中节点数量为 0，可能的原因：")
    print("1. MCP 请求时使用了错误的上下文")
    print("2. 节点选择在 MCP 请求前被取消")
    print("3. Blender 的上下文在 MCP 请求时发生了变化")


if __name__ == "__main__":
    debug_context()