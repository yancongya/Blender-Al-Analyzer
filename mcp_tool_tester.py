#!/usr/bin/env python3
"""
MCP 工具测试工具
用于测试所有 MCP 工具的功能
"""

import sys
import json
import socket
import time


class MCPToolTester:
    """MCP 工具测试器"""
    
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
    
    def connect(self):
        """连接到 Blender"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"✓ 已连接到 Blender ({self.host}:{self.port})")
            return True
        except Exception as e:
            print(f"✗ 连接失败: {e}")
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
    
    def send_command(self, command_type, params=None):
        """发送命令到 Blender"""
        if params is None:
            params = {}
        
        command = {
            "type": command_type,
            "params": params
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
                    pass
            
            return {"status": "error", "message": "No response"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def test_tool(self, tool_name, params=None, description=""):
        """测试单个工具"""
        if params is None:
            params = {}
        
        print(f"\n{'='*60}")
        print(f"测试工具: {tool_name}")
        if description:
            print(f"描述: {description}")
        print(f"{'='*60}")
        
        # 显示参数
        if params:
            print(f"\n参数:")
            for key, value in params.items():
                print(f"  {key}: {value}")
        else:
            print(f"\n参数: 无")
        
        print(f"\n发送请求...")
        
        # 发送请求
        start_time = time.time()
        response = self.send_command(tool_name, params)
        elapsed_time = time.time() - start_time
        
        print(f"响应时间: {elapsed_time:.2f} 秒")
        
        # 显示结果
        print(f"\n响应:")
        print(json.dumps(response, indent=2, ensure_ascii=False))
        
        # 检查状态
        if response.get("status") == "success":
            print(f"\n✓ 测试成功")
            return True
        else:
            error_msg = response.get("message", "Unknown error")
            print(f"\n✗ 测试失败: {error_msg}")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("MCP 工具全面测试")
        print("="*60)
        
        if not self.connect():
            print("\n无法连接到 Blender，请确保：")
            print("1. Blender 正在运行")
            print("2. AI Node Analyzer 插件已启用")
            print("3. MCP 服务器正在运行（端口 9876）")
            return
        
        results = []
        
        # 测试 1: get_scene_info
        results.append(self.test_tool(
            "get_scene_info",
            description="获取当前 Blender 场景信息"
        ))
        
        # 测试 2: get_object_info
        results.append(self.test_tool(
            "get_object_info",
            {"name": "Cube"},
            "获取指定对象的详细信息"
        ))
        
        # 测试 3: get_viewport_screenshot
        results.append(self.test_tool(
            "get_viewport_screenshot",
            description="获取 3D 视口的截图"
        ))
        
        # 测试 4: execute_code
        results.append(self.test_tool(
            "execute_code",
            {"code": "import bpy; print('Hello from MCP!')"},
            "执行 Blender Python 代码"
        ))
        
        # 测试 5: get_selected_nodes_info
        results.append(self.test_tool(
            "get_selected_nodes_info",
            description="获取当前选中节点的详细信息"
        ))
        
        # 测试 6: get_all_nodes_info
        results.append(self.test_tool(
            "get_all_nodes_info",
            description="获取当前节点树中的所有节点信息"
        ))
        
        # 测试 7: create_analysis_frame
        results.append(self.test_tool(
            "create_analysis_frame",
            description="创建分析框架"
        ))
        
        # 测试 8: get_analysis_frame_nodes
        results.append(self.test_tool(
            "get_analysis_frame_nodes",
            description="获取分析框架中的节点信息"
        ))
        
        # 测试 9: get_config_variable
        results.append(self.test_tool(
            "get_config_variable",
            {"variable_name": "identity_presets"},
            "读取配置文件中的身份预设"
        ))
        
        # 测试 10: get_all_config_variables
        results.append(self.test_tool(
            "get_all_config_variables",
            description="获取所有配置变量"
        ))
        
        # 测试 11: create_text_note
        results.append(self.test_tool(
            "create_text_note",
            {"text": "这是一个测试文本注记"},
            "创建文本注记节点"
        ))
        
        # 测试 12: get_text_note
        results.append(self.test_tool(
            "get_text_note",
            description="获取当前激活的文本注记节点内容"
        ))
        
        # 测试 13: clean_markdown_text
        results.append(self.test_tool(
            "clean_markdown_text",
            {"text": "# 标题\n\n这是**粗体**文本\n\n```python\ncode\n```"},
            "清理 Markdown 格式"
        ))
        
        # 测试 14: get_tools_list
        results.append(self.test_tool(
            "get_tools_list",
            description="获取所有可用的 MCP 工具列表"
        ))
        
        # 清理：移除分析框架
        print(f"\n{'='*60}")
        print(f"清理: 移除分析框架")
        print(f"{'='*60}")
        self.test_tool("remove_analysis_frame")
        
        # 显示测试总结
        print(f"\n{'='*60}")
        print("测试总结")
        print(f"{'='*60}")
        
        total_tests = len(results)
        passed_tests = sum(results)
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests} ✓")
        print(f"失败: {failed_tests} ✗")
        print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print(f"\n失败的测试:")
            tool_names = [
                "get_scene_info",
                "get_object_info",
                "get_viewport_screenshot",
                "execute_code",
                "get_selected_nodes_info",
                "get_all_nodes_info",
                "create_analysis_frame",
                "get_analysis_frame_nodes",
                "get_config_variable",
                "get_all_config_variables",
                "create_text_note",
                "get_text_note",
                "clean_markdown_text",
                "get_tools_list"
            ]
            for i, result in enumerate(results):
                if not result:
                    print(f"  - {tool_names[i]}")
        
        self.disconnect()
    
    def interactive_test(self):
        """交互式测试"""
        print("\n" + "="*60)
        print("MCP 工具交互式测试")
        print("="*60)
        
        if not self.connect():
            return
        
        # 获取工具列表
        print("\n获取工具列表...")
        response = self.send_command("get_tools_list")
        
        if response.get("status") != "success":
            print("✗ 无法获取工具列表")
            self.disconnect()
            return
        
        tools = response.get("result", {}).get("tools", [])
        
        print(f"\n可用工具 ({len(tools)} 个):")
        for i, tool in enumerate(tools):
            print(f"  {i+1}. {tool['name']}")
            print(f"     {tool['description'][:60]}...")
        
        while True:
            print(f"\n{'='*60}")
            print("选择操作:")
            print("  1. 输入工具编号进行测试")
            print("  2. 输入工具名称进行测试")
            print("  3. 运行所有测试")
            print("  4. 退出")
            
            choice = input("\n请选择 (1-4): ").strip()
            
            if choice == "1":
                # 按编号测试
                try:
                    num = int(input("输入工具编号: "))
                    if 1 <= num <= len(tools):
                        tool = tools[num-1]
                        self.test_single_tool(tool)
                    else:
                        print("✗ 无效的编号")
                except ValueError:
                    print("✗ 请输入有效的数字")
            
            elif choice == "2":
                # 按名称测试
                name = input("输入工具名称: ").strip()
                tool = next((t for t in tools if t["name"] == name), None)
                if tool:
                    self.test_single_tool(tool)
                else:
                    print(f"✗ 未找到工具: {name}")
            
            elif choice == "3":
                # 运行所有测试
                self.run_all_tests()
                break
            
            elif choice == "4":
                # 退出
                print("退出测试")
                break
            
            else:
                print("✗ 无效的选择")
        
        self.disconnect()
    
    def test_single_tool(self, tool):
        """测试单个工具"""
        print(f"\n{'='*60}")
        print(f"工具: {tool['name']}")
        print(f"描述: {tool['description']}")
        print(f"{'='*60}")
        
        # 显示输入参数
        input_schema = tool.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        if properties:
            print(f"\n需要参数:")
            params = {}
            for prop_name, prop_info in properties.items():
                is_required = prop_name in required
                prop_type = prop_info.get("type", "unknown")
                prop_desc = prop_info.get("description", "")
                enum_values = prop_info.get("enum", [])
                
                print(f"\n  {prop_name}")
                print(f"    类型: {prop_type}")
                print(f"    描述: {prop_desc}")
                if enum_values:
                    print(f"    可选值: {', '.join(enum_values)}")
                print(f"    必需: {'是' if is_required else '否'}")
                
                if is_required:
                    if enum_values:
                        print(f"    请输入值 (可选: {', '.join(enum_values)}):", end=" ")
                    else:
                        print(f"    请输入值:", end=" ")
                    
                    value = input().strip()
                    
                    # 根据类型转换值
                    if prop_type == "number":
                        try:
                            value = float(value)
                        except ValueError:
                            print(f"    警告: 无法转换为数字，使用字符串")
                    elif prop_type == "integer":
                        try:
                            value = int(value)
                        except ValueError:
                            print(f"    警告: 无法转换为整数，使用字符串")
                    
                    params[prop_name] = value
        else:
            print(f"\n无需参数")
            params = {}
        
        # 确认测试
        confirm = input(f"\n是否继续测试? (y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return
        
        # 执行测试
        self.test_tool(tool["name"], params, tool["description"])


def main():
    """主函数"""
    print("\nMCP 工具测试工具")
    print("="*60)
    
    tester = MCPToolTester()
    
    print("\n选择测试模式:")
    print("  1. 自动运行所有测试")
    print("  2. 交互式测试")
    
    choice = input("\n请选择 (1-2): ").strip()
    
    if choice == "1":
        tester.run_all_tests()
    elif choice == "2":
        tester.interactive_test()
    else:
        print("✗ 无效的选择")


if __name__ == "__main__":
    main()