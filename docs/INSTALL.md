# AI Node Analyzer - 安装指南

## 必需的依赖项

此插件需要额外的Python包才能正常工作。请使用以下方法安装：

## 方法1: 使用命令行 (推荐)

1. 找到Blender安装目录
2. 打开命令提示符 / 终端
3. 运行以下命令在Blender的Python环境中安装依赖项：

Windows系统:
```cmd
"path/to/blender/python.exe" -m pip install -r requirements.txt
```

macOS系统:
```bash
"/Applications/Blender/blender.app/Contents/Resources/version/python/bin/python3.11" -m pip install -r requirements.txt
```

Linux系统:
```bash
blender --python-expr "import sys; print(sys.executable)" # 这将打印Blender的Python路径
# 然后使用该路径:
/path/to/blender/python -m pip install -r requirements.txt
```

## 方法2: 使用Blender的Python控制台

1. 打开Blender
2. 转到脚本工作区
3. 在Python控制台中运行:

```python
import subprocess
import sys

# 安装所需的包
subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "path/to/requirements.txt"])
```

## 依赖包列表

需要安装以下包:
- litellm: 用于统一管理AI服务提供商
- openai: 用于OpenAI和OpenAI兼容的API (如DeepSeek)
- requests: 用于HTTP请求

## Ollama设置 (可选)

如果计划使用Ollama:
1. 从 https://ollama.ai/ 下载并安装Ollama
2. 获取所需模型: `ollama pull llama3` (或您计划使用的其他模型)
3. 启动Ollama服务: `ollama serve`
4. 在插件设置中使用默认URL `http://localhost:11434/api`

## DeepSeek设置 (可选)

1. 在 https://www.deepseek.com/ 注册
2. 获取您的API密钥
3. 使用模型: `deepseek-chat` 或 `deepseek-coder`

## 故障排除

如果遇到问题:
- 确保您在Blender的Python环境中安装包，而不是系统Python
- 在某些系统上，您可能需要以管理员身份运行命令
- 检查Python版本是否兼容 (Blender 4.2 使用 Python 3.11+)