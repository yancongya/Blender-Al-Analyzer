"""
MCP 工具测试脚本
直接连接到 Blender MCP 服务器测试所有工具
"""
import socket
import json
import time
from typing import Dict, Any, List
import sys

class MCPTester:
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.timeout = 10.0
    
    def connect(self) -> bool:
        """连接到 MCP 服务器"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            print(f"✓ 成功连接到 MCP 服务器 ({self.host}:{self.port})")
            return True
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False
    
    def call_tool(self, tool_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """调用 MCP 工具"""
        if params is None:
            params = {}
        
        command = {
            "type": tool_type,
            "params": params
        }
        
        try:
            # 发送命令
            self.sock.sendall(json.dumps(command).encode('utf-8'))
            
            # 接收响应
            response_data = b''
            while True:
                chunk = self.sock.recv(8192)
                if not chunk:
                    break
                response_data += chunk
                try:
                    response = json.loads(response_data.decode('utf-8'))
                    return response
                except json.JSONDecodeError:
                    pass
            
            return {"error": "No response received"}
        except Exception as e:
            return {"error": str(e)}
    
    def disconnect(self):
        """断开连接"""
        try:
            self.sock.close()
            print("✓ 已断开连接")
        except:
            pass
    
    def print_table(self, data: List[Dict[str, Any]], columns: List[str]):
        """打印表格"""
        if not data:
            print("无数据")
            return
        
        # 计算每列的最大宽度
        col_widths = []
        for col in columns:
            max_width = len(col)
            for row in data:
                value = str(row.get(col, ""))
                max_width = max(max_width, len(value))
            col_widths.append(max_width + 2)  # 加 2 作为间距
        
        # 打印表头
        header = "|"
        for i, col in enumerate(columns):
            header += f" {col.ljust(col_widths[i] - 1)}|"
        print(header)
        
        # 打印分隔线
        separator = "+"
        for width in col_widths:
            separator += "-" * (width - 1) + "+"
        print(separator)
        
        # 打印数据行
        for row in data:
            line = "|"
            for i, col in enumerate(columns):
                value = str(row.get(col, ""))
                line += f" {value.ljust(col_widths[i] - 1)}|"
            print(line)
    
    def run_info_tools(self):
        """运行获取信息类的工具"""
        print(f"\n{'='*60}")
        print("获取信息类工具测试")
        print(f"{'='*60}")
        
        info_tools = [
            {
                "name": "get_tools_list",
                "description": "获取所有可用工具列表",
                "params": {}
            },
            {
                "name": "get_scene_info",
                "description": "获取当前 Blender 场景信息",
                "params": {}
            },
            {
                "name": "get_object_info",
                "description": "获取指定对象的详细信息",
                "params": {"name": "Cube"}
            },
            {
                "name": "get_selected_nodes_info",
                "description": "获取选中节点的详细信息",
                "params": {}
            },
            {
                "name": "get_all_nodes_info",
                "description": "获取当前节点树中的所有节点信息",
                "params": {}
            },
            {
                "name": "get_analysis_frame_nodes",
                "description": "获取分析框架中的节点信息",
                "params": {}
            },
            {
                "name": "get_config_variable",
                "description": "读取配置文件中的指定变量",
                "params": {"variable_name": "system_prompt"}
            },
            {
                "name": "get_all_config_variables",
                "description": "获取所有配置变量",
                "params": {}
            },
            {
                "name": "get_text_note",
                "description": "获取当前激活的文本注记节点内容",
                "params": {}
            },
        ]
        
        results = []
        for tool in info_tools:
            print(f"\n正在运行: {tool['name']} - {tool['description']}")
            result = self.call_tool(tool["name"], tool["params"])
            
            success = "error" not in result
            status = "✓" if success else "✗"
            
            # 提取关键信息
            key_info = "N/A"
            if success and "result" in result:
                res = result["result"]
                if tool["name"] == "get_scene_info":
                    key_info = f"对象数: {res.get('object_count', 0)}, 材质数: {res.get('materials_count', 0)}"
                elif tool["name"] == "get_object_info":
                    key_info = f"类型: {res.get('type', 'N/A')}"
                elif tool["name"] == "get_selected_nodes_info":
                    key_info = f"节点数: {res.get('selected_nodes_count', 0)}"
                elif tool["name"] == "get_all_nodes_info":
                    key_info = f"节点数: {len(res.get('nodes', []))}"
                elif tool["name"] == "get_analysis_frame_nodes":
                    key_info = f"节点数: {res.get('nodes_count', 0)}"
                elif tool["name"] == "get_config_variable":
                    # 处理返回字符串的情况
                    if isinstance(res, str):
                        key_info = f"值: {res[:50]}..."
                    elif isinstance(res, dict):
                        key_info = f"值长度: {len(str(res.get('value', '')))}"
                    else:
                        key_info = str(res)[:50]
                elif tool["name"] == "get_all_config_variables":
                    key_info = f"变量数: {len(res.get('variables', {}))}"
                elif tool["name"] == "get_text_note":
                    key_info = f"内容: {res.get('content', 'N/A')[:30]}..."
                else:
                    key_info = str(res)[:50]
            
            results.append({
                "工具名": tool["name"],
                "状态": status,
                "描述": tool["description"],
                "关键信息": key_info
            })
            
            time.sleep(0.3)
        
        # 打印结果表格
        print(f"\n{'='*60}")
        print("获取信息类工具测试结果")
        print(f"{'='*60}")
        self.print_table(results, ["工具名", "状态", "描述", "关键信息"])
        
        # 统计
        success_count = sum(1 for r in results if r["状态"] == "✓")
        print(f"\n总计: {len(results)} 个工具")
        print(f"成功: {success_count} 个")
        print(f"失败: {len(results) - success_count} 个")
        
        return results
    
    def run_operation_tools(self):
        """运行操作类的工具"""
        print(f"\n{'='*60}")
        print("操作类工具测试")
        print(f"{'='*60}")
        print("将逐个运行每个操作工具，请确认每个操作是否成功")
        print(f"{'='*60}")
        
        operation_tools = [
            {
                "name": "create_analysis_frame",
                "description": "创建分析框架",
                "params": {},
                "check": "检查 Blender 中是否创建了分析框架"
            },
            {
                "name": "create_text_note",
                "description": "创建文本注记节点",
                "params": {"text": "测试文本注记 - MCP 测试"},
                "check": "检查 Blender 中是否创建了文本注记节点"
            },
            {
                "name": "update_text_note",
                "description": "更新文本注记节点内容",
                "params": {"text": "更新后的文本 - MCP 测试更新"},
                "check": "检查文本注记节点内容是否已更新"
            },
            {
                "name": "remove_analysis_frame",
                "description": "移除分析框架",
                "params": {},
                "check": "检查 Blender 中分析框架是否已移除"
            },
            {
                "name": "delete_text_note",
                "description": "删除文本注记节点",
                "params": {},
                "check": "检查 Blender 中文本注记节点是否已删除"
            },
            {
                "name": "execute_code",
                "description": "执行 Blender Python 代码",
                "params": {"code": 'print("MCP 测试代码执行成功")'},
                "check": "查看 Blender 控制台是否输出测试信息"
            },
        ]
        
        results = []
        for i, tool in enumerate(operation_tools, 1):
            print(f"\n[{i}/{len(operation_tools)}] {tool['name']} - {tool['description']}")
            print(f"检查方法: {tool['check']}")
            
            input("\n按 Enter 键执行此操作...")
            
            result = self.call_tool(tool["name"], tool["params"])
            
            success = "error" not in result
            status = "✓" if success else "✗"
            
            print(f"\n结果: {status}")
            if success:
                print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            else:
                print(f"错误: {result.get('error', 'Unknown error')}")
            
            # 询问用户确认
            while True:
                confirm = input("\n操作是否成功？(y/n): ").strip().lower()
                if confirm in ['y', 'n']:
                    break
                print("请输入 y 或 n")
            
            operation_success = confirm == 'y'
            results.append({
                "工具名": tool["name"],
                "状态": status,
                "描述": tool["description"],
                "操作成功": "✓" if operation_success else "✗"
            })
            
            time.sleep(0.5)
        
        # 打印结果表格
        print(f"\n{'='*60}")
        print("操作类工具测试结果")
        print(f"{'='*60}")
        self.print_table(results, ["工具名", "状态", "描述", "操作成功"])
        
        # 统计
        success_count = sum(1 for r in results if r["状态"] == "✓")
        operation_success_count = sum(1 for r in results if r["操作成功"] == "✓")
        print(f"\n总计: {len(results)} 个工具")
        print(f"执行成功: {success_count} 个")
        print(f"操作成功: {operation_success_count} 个")
        print(f"执行失败: {len(results) - success_count} 个")
        
        return results

def main():
    print("="*60)
    print("MCP 工具测试器")
    print("="*60)
    print("\n使用说明:")
    print("1. 确保 Blender 正在运行")
    print("2. 确保 AI Node Analyzer 插件已启用")
    print("3. 确保 MCP 服务器已启动（端口 9876）")
    print("4. 运行此脚本进行测试")
    print("\n测试模式:")
    print("- 获取信息类工具: 批量运行，生成表格查看结果")
    print("- 操作类工具: 逐个运行，手动确认操作是否成功")
    print("\n" + "="*60)
    
    tester = MCPTester()
    
    if not tester.connect():
        print("\n无法连接到 MCP 服务器，请检查:")
        print("1. Blender 是否正在运行")
        print("2. AI Node Analyzer 插件是否已启用")
        print("3. MCP 服务器是否已启动")
        return
    
    try:
        # 运行获取信息类工具
        info_results = tester.run_info_tools()
        
        # 询问是否继续测试操作类工具
        continue_test = input("\n是否继续测试操作类工具？(y/n): ").strip().lower()
        if continue_test == 'y':
            operation_results = tester.run_operation_tools()
        
        print(f"\n{'='*60}")
        print("测试完成")
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    finally:
        tester.disconnect()

if __name__ == "__main__":
    main()