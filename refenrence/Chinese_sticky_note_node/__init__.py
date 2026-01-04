# sticky_note_node_enhanced/__init__.py
# 绕过 Text Editor 的增强版中文注释节点插件 (最终整合修复版 V6)
# 功能：直接弹窗输入中文/换行、按钮插入\n、可调预览行数、兼容 Blender 4.x & 5.x
# 优化：将提示语中的“\n”改为更易懂的“换行”
# 修复：解决 Blender 5.0 因顶层 import bgl 导致的加载失败

bl_info = {
    "name": "中文注释节点",
    "author": "Liuzhao by Qwen",
    "version": (1, 1, 7), # 版本号更新
    "blender": (4, 0, 0), # 最低兼容版本
    "location": "Add > Note > 中文注释",
    "description": "弹窗输入中文/换行，按钮插入\\n，可调预览行数，兼容 4.x & 5.x",
    "category": "Node",
}

import bpy
# >>>>>>>>>> 移除了顶层的 import bgl <<<<<<<<<<
from bpy.types import Node, Operator, Menu
from bpy.props import StringProperty, IntProperty
import textwrap

# -----------------------------
# 工具函数
# -----------------------------

def wrap_text_for_preview(text, max_chars_per_line=40):
    """为预览区域换行显示"""
    if not text.strip():
        return [""]
    lines = []
    for para in text.split('\n'):
        if not para:
            lines.append("")
            continue
        wrapped = textwrap.fill(para, width=max_chars_per_line, break_long_words=False, break_on_hyphens=False)
        lines.extend(wrapped.split('\n'))
    return lines

# -----------------------------
# 节点类 (已修复属性定义，并添加动态行数预览)
# -----------------------------

class StickyNoteNode(Node):
    bl_idname = 'StickyNoteNode'
    bl_label = "📝 中文注释"

    note_text: StringProperty(
        name="Content",
        default="在此输入注释...\n支持中文和换行"
    )
    
    max_preview_lines: IntProperty(
        name="最大预览行数",
        description="在节点面板上最多显示多少行预览",
        default=5,
        min=1,
        max=50
    )

    def draw_buttons(self, context, layout):
        wrapped = wrap_text_for_preview(self.note_text, max_chars_per_line=30)
        display_lines = wrapped[:self.max_preview_lines] 
        
        for line in display_lines:
            layout.label(text=line if line.strip() else "␣")
        
        fill_lines_needed = max(0, self.max_preview_lines - len(display_lines))
        for _ in range(fill_lines_needed):
             layout.label(text="␣")

        layout.separator()
        layout.prop(self, "max_preview_lines", text="预览行数")
        layout.operator("node.edit_sticky_note_simple", text="✎ 编辑注释").node_name = self.name

    def draw_label(self):
        return "📝 注释"

# -----------------------------
# Operator：简化版编辑器（核心） - 已修复插入 \n 功能
# -----------------------------

class NODE_OT_edit_sticky_note_simple(Operator):
    bl_idname = "node.edit_sticky_note_simple"
    bl_label = "编辑注释"
    bl_options = {'REGISTER', 'UNDO'}

    _instance = None 

    node_name: StringProperty()
    text_input: StringProperty(
        name="",
        description="输入文本，用 \\n 表示换行",
        default="",
    )

    @classmethod
    def poll(cls, context):
        return context.active_node is not None and context.active_node.bl_idname == 'StickyNoteNode'

    def invoke(self, context, event):
        node = context.active_node
        if not node or node.name != self.node_name:
            self.report({'ERROR'}, "节点无效")
            return {'CANCELLED'}
        
        self.text_input = node.note_text.replace('\n', '\\n')
        NODE_OT_edit_sticky_note_simple._instance = self
        
        return context.window_manager.invoke_props_dialog(self, width=600)

    def execute(self, context):
        node = context.active_node
        if node and node.name == self.node_name:
            node.note_text = self.text_input.replace('\\n', '\n')
        NODE_OT_edit_sticky_note_simple._instance = None
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="📝 输入注释内容：")
        col.label(text="💡 输入提示：")
        col.label(text="   - 使用 \\n 表示换行（如：第一行\\n第二行）")
        # >>>>>>>>>> 修改提示语 <<<<<<<<<<
        col.label(text="   - 可点击下方 '插入换行' 按钮快速添加")
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        
        col.scale_y = 1.5
        col.prop(self, "text_input", text="", emboss=True)
        col.scale_y = 1.0
        
        row = col.row()
        # >>>>>>>>>> 修改按钮文字 <<<<<<<<<<
        op = row.operator("node.insert_newline_escape_simple", text="插入换行")
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        op.target_property = "text_input" 

        layout.separator()

        if self.text_input.strip():
            layout.label(text="👁️ 实时预览：")
            box = layout.box()
            real_preview = self.text_input.replace('\\n', '\n')
            preview_lines = real_preview.split('\n')
            
            for line in preview_lines[:10]:
                box.label(text=line if line.strip() else "␣ (空行)")
            if len(preview_lines) > 10:
                box.label(text="... (更多)")

# -----------------------------
# Operator：插入 \n 按钮 - 已修复，现在能正确工作
# -----------------------------

class NODE_OT_insert_newline_escape_simple(Operator):
    bl_idname = "node.insert_newline_escape_simple"
    bl_label = "插入 \\n"
    
    target_property: StringProperty()

    def execute(self, context):
        main_op_instance = NODE_OT_edit_sticky_note_simple._instance
        
        if main_op_instance and hasattr(main_op_instance, self.target_property):
            current_val = getattr(main_op_instance, self.target_property, "")
            new_val = current_val + "\\n"
            setattr(main_op_instance, self.target_property, new_val)
            
            for area in context.screen.areas:
                 area.tag_redraw()
            
        else:
            self.report({'WARNING'}, "无法插入换行符")
            
        return {'FINISHED'}

# -----------------------------
# 视口绘制回调 - 兼容 Blender 4.x 和 5.x
# -----------------------------

# --- Blender 5.x+ 的 gpu/blf 绘制 ---
def draw_callback_px_gpu(self, context):
    import gpu
    from gpu_extras.batch import batch_for_shader
    import blf
    
    if not context.space_data or not context.space_data.edit_tree:
        return

    tree = context.space_data.edit_tree
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    font_id = 0
    blf.size(font_id, 10) # Blender 5.x+ 简化了 size 函数

    vertices = []
    indices = []
    texts = []
    colors = []

    idx_counter = 0
    for node in tree.nodes:
        if node.bl_idname == 'StickyNoteNode':
            content = node.note_text
            if not content.strip():
                continue

            x = node.location.x + 10
            y = node.location.y + node.height - 20
            lines = content.split('\n')
            line_height = 12
            
            for i, line in enumerate(lines[:8]):
                pos_x = x
                pos_y = y - i * line_height
                
                vertices.append((pos_x, pos_y))
                indices.append((idx_counter,))
                texts.append(line if line.strip() else "␣")
                colors.append((1.0, 1.0, 1.0, 1.0)) # 白色
                idx_counter += 1

    with gpu.matrix.push_pop():
         pass

    gpu.state.blend_set('ALPHA')
    
    for i, (pos, text, color) in enumerate(zip(vertices, texts, colors)):
        shader.bind()
        shader.uniform_float("color", color)
        blf.color(font_id, *color)
        blf.position(font_id, pos[0], pos[1], 0)
        blf.draw(font_id, text)

    gpu.state.blend_set('NONE')

# --- Blender 4.x 的 bgl/blf 绘制 ---
# >>>>>>>>>> 将 import bgl 移动到这里 <<<<<<<<<<
def draw_callback_px_bgl(self, context):
    if not context.space_data or not context.space_data.edit_tree:
        return

    tree = context.space_data.edit_tree
    # >>>>>>>>>> 在需要时才导入 bgl <<<<<<<<<<
    from bgl import glColor4f, glEnable, glDisable, GL_BLEND 
    import blf

    font_id = 0
    blf.size(font_id, 10, 72) # Blender 4.x 需要 dpi 参数
    glEnable(GL_BLEND)

    for node in tree.nodes:
        if node.bl_idname == 'StickyNoteNode':
            content = node.note_text
            if not content.strip():
                continue

            x = node.location.x + 10
            y = node.location.y + node.height - 20

            lines = content.split('\n')
            line_height = 12
            for i, line in enumerate(lines[:8]):
                glColor4f(1.0, 1.0, 1.0, 1.0)
                blf.position(font_id, x, y - i * line_height, 0)
                blf.draw(font_id, line if line.strip() else "␣")

    glDisable(GL_BLEND)


# --- 根据 Blender 版本选择绘制函数 ---
def draw_callback_px_wrapper(self, context):
    # >>>>>>>>>> 通过比较元组来判断版本 <<<<<<<<<<
    if bpy.app.version >= (5, 0, 0): 
        draw_callback_px_gpu(self, context)
    else:
        draw_callback_px_bgl(self, context)

# -----------------------------
# 其他 Operators & 注册
# -----------------------------

class NODE_OT_add_sticky_note(Operator):
    bl_idname = "node.add_sticky_note"
    bl_label = "添加中文注释节点"

    def execute(self, context):
        tree = context.space_data.edit_tree
        if not tree:
            self.report({'WARNING'}, "不在节点编辑器中")
            return {'CANCELLED'}
        node = tree.nodes.new('StickyNoteNode')
        node.location = context.space_data.cursor_location
        tree.nodes.active = node
        return {'FINISHED'}

def menu_func(self, context):
    if context.space_data.tree_type in {'ShaderNodeTree', 'GeometryNodeTree', 'CompositorNodeTree'}:
        self.layout.operator("node.add_sticky_note", text="中文注释", icon='TEXT')

# -----------------------------
# 注册/注销
# -----------------------------

classes = (
    StickyNoteNode,
    NODE_OT_edit_sticky_note_simple,
    NODE_OT_insert_newline_escape_simple,
    NODE_OT_add_sticky_note,
)

_draw_handle = None

def register():
    global _draw_handle

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_add.append(menu_func)

    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceNodeEditor.draw_handler_add(draw_callback_px_wrapper, (None, bpy.context), 'WINDOW', 'POST_PIXEL')

def unregister():
    global _draw_handle

    if _draw_handle is not None:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_draw_handle, 'WINDOW')
        _draw_handle = None

    bpy.types.NODE_MT_add.remove(menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()