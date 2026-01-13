#!/usr/bin/env python3
"""
测试节点选择修复
"""

import sys
import json
import socket


def test_node_selection():
    """测试节点选择"""
    print("="*60)
    print("测试节点选择修复")
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
    
    # 步骤 1: 检查所有区域
    print("\n" + "="*60)
    print("步骤 1: 检查所有区域")
    print("="*60)
    
    command = {
        "type": "execute_code",
        "params": {
            "code": """
import bpy

print("所有区域类型:")
for area in bpy.context.screen.areas:
    print(f"  - {area.type}")

print("\\n查找节点编辑器:")
node_editor_found = False
for area in bpy.context.screen.areas:
    if area.type == 'NODE_EDITOR':
        node_editor_found = True
        print(f"  ✓ 找到节点编辑器")
        
        # 检查空间
        for space in area.spaces:
            if space.type == 'NODE_EDITOR':
                print(f"    空间类型: {space.type}")
                if hasattr(space, 'node_tree'):
                    if space.node_tree:
                        print(f"    节点树: {space.node_tree.name}")
                        print(f"    节点数: {len(space.node_tree.nodes)}")
                    else:
                        print(f"    节点树: None")
                break
        break

if not node_editor_found:
    print("  ✗ 未找到节点编辑器")
    print("\\n请在 Blender 中:")
    print("  1. 按 Shift + F3 切换到节点编辑器")
    print("  2. 或在顶部菜单选择 Scripting > Geometry Nodes")
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
        print(f"\n{output}")
    
    # 步骤 2: 全选节点（使用上下文覆盖）
    print("\n" + "="*60)
    print("步骤 2: 全选节点")
    print("="*60)
    
    command = {
        "type": "execute_code",
        "params": {
            "code": """
import bpy

# 查找节点编辑器
node_space = None
node_area = None

for area in bpy.context.screen.areas:
    if area.type == 'NODE_EDITOR':
        for space in area.spaces:
            if space.type == 'NODE_EDITOR':
                node_space = space
                node_area = area
                break
        if node_space:
            break

if node_space and node_space.node_tree:
    # 使用上下文覆盖
    override = bpy.context.copy()
    override['area'] = node_area
    override['space_data'] = node_space
    override['node_tree'] = node_space.node_tree
    
    # 在覆盖上下文中全选
    with bpy.context.temp_override(**override):
        bpy.ops.node.select_all(action='SELECT')
    
    print(f"✓ 已全选所有节点")
    
    # 检查选中状态
    selected = [node for node in node_space.node_tree.nodes if node.select]
    print(f"  选中节点数: {len(selected)}")
    for node in selected:
        print(f"    - {node.name}")
else:
    print("✗ 未找到节点编辑器或节点树")
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
        print(f"\n{output}")
    
    # 步骤 3: 测试获取选中节点信息
    print("\n" + "="*60)
    print("步骤 3: 测试获取选中节点信息")
    print("="*60)
    
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
        if isinstance(result, dict):
            count = result.get("selected_nodes_count", 0)
            if count > 0:
                print(f"\n✓ 成功！获取到 {count} 个节点")
                
                # 显示节点列表
                print(f"\n节点列表:")
                for i, node in enumerate(result.get("selected_nodes", [])):
                    print(f"  {i+1}. {node['name']} ({node['type']})")
            else:
                print(f"\n✗ 仍然没有获取到节点")
                print(f"\n可能的解决方案:")
                print(f"  1. 运行 debug_context.py 查看详细诊断")
                print(f"  2. 确保在正确的节点编辑器中")
                print(f"  3. 确保节点树中有节点")
    else:
        print(f"\n✗ 失败: {response.get('message')}")
    
    sock.close()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    test_node_selection()