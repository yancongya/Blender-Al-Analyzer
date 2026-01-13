#!/usr/bin/env python3
"""
Blender 状态诊断工具
帮助诊断为什么无法获取节点信息
"""

import sys
import json
import socket


def diagnose_blender():
    """诊断 Blender 状态"""
    print("="*60)
    print("Blender 状态诊断")
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
        return
    
    # 诊断 1: 检查 Blender 上下文
    print("\n" + "="*60)
    print("诊断 1: 检查 Blender 上下文")
    print("="*60)
    
    command = {
        "type": "execute_code",
        "params": {
            "code": """
import bpy
import json

# 获取当前上下文信息
ctx_info = {
    "current_area_type": bpy.context.area.type if bpy.context.area else "None",
    "current_space_type": bpy.context.space_data.type if bpy.context.space_data else "None",
    "has_node_tree": hasattr(bpy.context.space_data, 'node_tree') and bpy.context.space_data.node_tree is not None,
    "node_tree_name": bpy.context.space_data.node_tree.name if hasattr(bpy.context.space_data, 'node_tree') and bpy.context.space_data.node_tree else "None",
    "node_tree_type": bpy.context.space_data.node_tree.bl_idname if hasattr(bpy.context.space_data, 'node_tree') and bpy.context.space_data.node_tree else "None",
    "selected_nodes_count": len(bpy.context.selected_nodes) if hasattr(bpy.context, 'selected_nodes') else 0,
    "active_node": bpy.context.active_node.name if hasattr(bpy.context, 'active_node') and bpy.context.active_node else "None",
}

print(json.dumps(ctx_info, indent=2))
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
        
        print("\nBlender 上下文信息:")
        try:
            ctx_info = json.loads(output)
            for key, value in ctx_info.items():
                print(f"  {key}: {value}")
            
            # 分析状态
            print("\n状态分析:")
            
            if ctx_info.get("current_area_type") != "NODE_EDITOR":
                print("  ✗ 不在节点编辑器中")
                print("    解决方法：在 Blender 中切换到节点编辑器视图")
            else:
                print("  ✓ 在节点编辑器中")
            
            if not ctx_info.get("has_node_tree"):
                print("  ✗ 没有活动的节点树")
                print("    解决方法：创建或打开一个节点树")
            else:
                print(f"  ✓ 有活动的节点树: {ctx_info.get('node_tree_name')}")
            
            if ctx_info.get("selected_nodes_count") == 0:
                print("  ⚠ 没有选中节点")
                print("    提示：选择一些节点以获取详细信息")
            else:
                print(f"  ✓ 已选中 {ctx_info.get('selected_nodes_count')} 个节点")
                
        except json.JSONDecodeError:
            print(f"  输出: {output}")
    else:
        print(f"✗ 获取上下文信息失败: {response}")
    
    # 诊断 2: 尝试获取场景信息
    print("\n" + "="*60)
    print("诊断 2: 测试基本功能")
    print("="*60)
    
    command = {"type": "get_scene_info", "params": {}}
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
        if isinstance(result, dict) and "error" not in result:
            print("✓ 基本功能正常")
            print(f"  场景名称: {result.get('name')}")
            print(f"  对象数量: {result.get('object_count')}")
        else:
            print("✗ 基本功能异常")
            print(f"  错误: {result}")
    else:
        print("✗ 基本功能测试失败")
    
    # 诊断 3: 列出所有节点
    print("\n" + "="*60)
    print("诊断 3: 列出节点树中的所有节点")
    print("="*60)
    
    command = {
        "type": "execute_code",
        "params": {
            "code": """
import bpy
import json

if hasattr(bpy.context.space_data, 'node_tree') and bpy.context.space_data.node_tree:
    node_tree = bpy.context.space_data.node_tree
    nodes_info = []
    for node in node_tree.nodes:
        nodes_info.append({
            "name": node.name,
            "type": node.bl_idname,
            "label": node.label,
            "selected": node.select
        })
    
    print(json.dumps({
        "total_nodes": len(nodes_info),
        "selected_nodes": len([n for n in nodes_info if n["selected"]]),
        "nodes": nodes_info[:5]  # 只显示前5个
    }, indent=2))
else:
    print(json.dumps({"error": "No node tree"}))
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
        
        try:
            nodes_data = json.loads(output)
            if "error" in nodes_data:
                print(f"✗ {nodes_data['error']}")
            else:
                print(f"✓ 节点树中有 {nodes_data['total_nodes']} 个节点")
                print(f"  已选中: {nodes_data['selected_nodes']} 个")
                
                if nodes_data['nodes']:
                    print("\n  前5个节点:")
                    for i, node in enumerate(nodes_data['nodes']):
                        status = "✓" if node['selected'] else " "
                        print(f"    {status} {i+1}. {node['name']} ({node['type']})")
        except json.JSONDecodeError:
            print(f"  输出: {output}")
    else:
        print(f"✗ 获取节点列表失败: {response}")
    
    sock.close()
    
    # 提供解决建议
    print("\n" + "="*60)
    print("建议")
    print("="*60)
    print("\n如果所有测试都失败，请检查：")
    print("1. Blender 是否正在运行")
    print("2. AI Node Analyzer 插件是否已启用")
    print("3. MCP 服务器是否正在运行（端口 9876）")
    print("\n如果基本功能正常但节点功能失败：")
    print("1. 在 Blender 中切换到节点编辑器（Geometry Nodes、Shader Nodes 等）")
    print("2. 创建或打开一个节点树")
    print("3. 选择一些节点（可选）")
    print("\n" + "="*60)


if __name__ == "__main__":
    diagnose_blender()