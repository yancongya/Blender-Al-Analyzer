## 总览
- 在主页面新增身份与预设联动、默认问题下拉、挡位过滤、刷新内容按钮，以及深度思考/联网/模型切换三项控制。
- 在设置界面呈现并对接 config.json 的 system_message_presets 与 default_question_presets，提供重新加载与自动保存联动。
- 保持现有后端交互与配置文件读写逻辑，新增必要属性与 Operator，所有改动与 UI 绘制集中于入口文件与后端 UI 配置接口。

## 变更范围与文件
- 主入口与 UI 面板：在 [__init__.py](file:///d:/blender/Plugin/addons/ainode/__init__.py) 的 Panel、Properties 与 Operators 内实现。
- 设置弹窗与配置操作：扩展 [AINodeAnalyzerSettingsPopup](file:///d:/blender/Plugin/addons/ainode/__init__.py#L900-L985) 内容。
- UI 配置获取：复用/扩展后端 [get_ui_config](file:///d:/blender/Plugin/addons/ainode/backend/server.py#L250-L284)。
- 配置文件：读取 d:\blender\Plugin\addons\ainode\config.json。

## 主页面改动
- 身份状态行与自动识别
  - 在主面板状态行显示：当前节点类型 + 当前身份键/名称。
  - 从 UI 配置的 system_message_presets 读取身份列表，初始自动选用配置中的默认身份；如识别不准，可手动选择。
  - 新增属性：identity_key、identity_text、current_node_type，用于显示与实际发送。
  - 在 [NODE_PT_ai_analyzer.draw](file:///d:/blender/Plugin/addons/ainode/__init__.py#L316-L347) 中加入顶部状态行与下一行身份列表（下拉或列表控件）。

- 默认问题下拉菜单
  - 将输入框下的“默认”按钮改为下拉菜单，项来源于 default_question_presets。
  - 选择后自动填充到当前输入框的文本。
  - 新增属性：default_question_preset，用于记录选择项。

- 挡位过滤与刷新
  - 增加“挡位”选择控件（例如 Low/Medium/High），控制将要发送的节点信息过滤程度：
    - Low：仅最小必要字段（节点类型、核心参数）。
    - Medium：包含常用元信息（身份、模型、基础参数）。
    - High：包含完整上下文（历史、额外描述）。
  - 新增属性：filter_level 与序列化函数，用于根据挡位构建待发送 payload。
  - 输入框下的“刷新”按钮调用刷新 Operator，重建 payload（节点信息 + 问题 + 身份）。

- 深度思考/联网/模型切换三按钮
  - 在输入框下一行加入三项开关/选择：
    - 深度思考：布尔开关，控制是否向后端传入思考模式标志。
    - 联网：布尔开关，控制是否允许服务端执行联网检索或带有网络上下文。
    - 模型切换：下拉选择，数据源为当前 provider 的模型列表。
  - 绑定现有属性或新增：enable_thinking、enable_web、current_model。

- 发送逻辑联动
  - 回答生成遵循：所选身份（system_message_presets 中的内容）+ 输入框问题 + 挡位后的节点信息 + 三按钮的开关状态。
  - 在现有发送 Operator 中组装最终 payload 并调用后端。

## 设置界面升级
- 呈现与管理预设
  - 在设置弹窗展示 system_message_presets 与 default_question_presets，支持“重新从 config.json 载入”。
  - 保持保存逻辑：保存时不覆盖原列表结构，仅更新当前选择和必要字段。
- 模型与开关联动
  - 与主页面保持一致的 Provider/模型/思考/联网设置显示；勾选或修改自动同步到属性。

## 属性与 Operator 设计
- 属性组 AINodeAnalyzerSettings 扩展：
  - identity_key、identity_text
  - default_question_preset
  - filter_level（EnumProperty 或 IntProperty）
  - enable_thinking（BoolProperty）
  - enable_web（BoolProperty）
  - current_model（StringProperty 或 EnumProperty 动态生成）
  - current_node_type（StringProperty）
- 新增/扩展 Operators：
  - 刷新待发送内容（重建 payload 并预览）
  - 重新载入 UI 配置（system_message_presets 与 default_question_presets）
  - 模型列表刷新（按当前 provider 更新枚举）

## 配置与后端联动
- 读取 UI 配置：
  - 优先通过后端 /api 获取 UI 配置（get_ui_config）；若失败则直接读本地 config.json。
  - 将 system_message_presets 与 default_question_presets 写入内存（属性或缓存结构）。
- 保存时仅写必要字段，避免覆盖预设集合结构。

## 发送前数据构建
- 新增序列化函数：根据 filter_level 整理节点信息，附加 identity_text、当前模型、思考/联网开关、输入问题，形成最终 payload。
- 在发送 Operator 中调用序列化函数，并按既有流程发送给 AI 后端。

## 验证与测试
- 启动后端，加载插件，验证：
  - 主面板显示身份与默认问题下拉，切换后输入框自动填充。
  - 切换挡位并刷新，查看重建的 payload 一致性。
  - 深度思考/联网开关与模型切换生效，并在发送时反映。
  - 设置弹窗可重新加载预设，主页面联动更新。

## 风险与兼容
- 动态枚举项（模型列表）需在属性定义时考虑更新策略，避免注册阶段错误。
- 预设来源可能为空时需回退到安全默认值。
- 保留现有 Operator 与 UI 行为，逐步插入新的控件避免破坏现有布局。

请确认以上方案，我将按照此计划开始实现并提交修改。