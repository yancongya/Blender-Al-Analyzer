import json
import os

# 读取配置文件
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

print("配置文件中的output_detail_prompts:")
output_detail_prompts = config.get('output_detail_prompts', {})
for key, value in output_detail_prompts.items():
    print(f"  {key}: {value}")

print("\n配置文件中的output_detail_level:")
output_detail_level = config.get('output_detail_level')
print(f"  {output_detail_level}")

# 显示映射关系
level_mapping = {
    'ULTRA_LITE': 0,
    'LITE': 1,
    'STANDARD': 2,
    'FULL': 3
}

if output_detail_level in level_mapping:
    mapped_value = level_mapping[output_detail_level]
    print(f"\n映射到response_detail_level的值: {mapped_value}")
else:
    print(f"\n未找到映射，将使用默认值: 2")