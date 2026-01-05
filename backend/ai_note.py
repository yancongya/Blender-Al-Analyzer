import bpy
import bpy.utils as _bu
import bpy.props as _bp
from bpy.types import Operator, Panel, AddonPreferences

class AINodeTextNote(bpy.types.Node):
    bl_idname = 'AINodeTextNote'
    bl_label = "Note"
    bl_icon = 'TEXT'
    text_name: _bp.StringProperty()
    def get_ui_color(self):
        return self.color
    def set_ui_color(self, value):
        self.color = value
        self.use_custom_color = True
    ui_color: _bp.FloatVectorProperty(name="Color", subtype='COLOR', default=(0.0, 0.0, 0.0), min=0.0, max=1.0, get=get_ui_color, set=set_ui_color)
    def init(self, context):
        self.width = 200
        self.use_custom_color = True
        prefs = get_preferences()
        if prefs:
            try:
                self.color = prefs.default_color
            except Exception:
                pass
    def get_char_width(self, ch):
        w = 7.5
        code = ord(ch)
        if code < 128:
            if ch in "il1.,'|:;!I()[] ":
                w = 4.0
            elif ch in "mwMW@%_":
                w = 10.0
            elif ch.isupper() or ch.isdigit():
                w = 8.2
            else:
                w = 5.5
        else:
            w = 11.0
        return w * 1.03
    def smart_wrap_text(self, text, max_width_px):
        lines = []
        padding = 20
        limit = max(20, max_width_px - padding)
        paragraphs = text.splitlines()
        for paragraph in paragraphs:
            if not paragraph:
                lines.append("")
                continue
            current_line = ""
            current_width = 0
            for char in paragraph:
                w = self.get_char_width(char)
                if current_width + w > limit:
                    if current_line:
                        lines.append(current_line)
                    current_line = char
                    current_width = w
                else:
                    current_line += char
                    current_width += w
            if current_line:
                lines.append(current_line)
        return lines
    def draw_buttons(self, context, layout):
        txt = bpy.data.texts.get(self.text_name)
        row = layout.row(align=True)
        row.operator("ainode.open_editor", text="Open")
        row.operator("ainode.fit_width", text="Fit")
        row.operator("ainode.paste_clipboard", text="Paste")
        if not txt:
            layout.label(text="[Empty]")
            return
        if not txt.use_fake_user:
            txt.use_fake_user = True
        raw_text = txt.as_string()
        if not raw_text.strip():
            layout.label(text="[Empty]")
        else:
            lines = self.smart_wrap_text(raw_text, self.width)
            col = layout.column(align=True)
            col.scale_y = 0.9
            for i, line in enumerate(lines):
                if i > 100:
                    sub = col.column(align=True)
                    sub.scale_y = 1.0
                    sub.label(text="... (Text too long)")
                    break
                display_text = line if line != "" else " "
                col.label(text=display_text, translate=False)
    def copy(self, node):
        self.text_name = ""
    def free(self):
        if self.text_name:
            txt = bpy.data.texts.get(self.text_name)
            if txt:
                txt.use_fake_user = False

class AINODE_Preferences(AddonPreferences):
    bl_idname = 'ainode'
    editor_width: _bp.IntProperty(default=600, min=200, max=1600)
    editor_height: _bp.IntProperty(default=500, min=200, max=1200)
    default_color: _bp.FloatVectorProperty(subtype='COLOR', default=(0.0, 0.0, 0.0), min=0.0, max=1.0)
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "editor_width", text="Editor Width")
        layout.prop(self, "editor_height", text="Editor Height")
        layout.prop(self, "default_color", text="Default Color")

def get_preferences():
    try:
        return bpy.context.preferences.addons.get('ainode').preferences
    except Exception:
        return None

def ensure_registered():
    try:
        if not hasattr(bpy.types, 'AINodeTextNote'):
            _bu.register_class(AINodeTextNote)
        if not hasattr(bpy.types, 'AINODE_Preferences'):
            _bu.register_class(AINODE_Preferences)
        # Operators and Panel
        if not hasattr(bpy.types, 'AINODE_OT_open_editor'):
            _bu.register_class(AINODE_OT_open_editor)
        if not hasattr(bpy.types, 'AINODE_OT_close_window'):
            _bu.register_class(AINODE_OT_close_window)
        if not hasattr(bpy.types, 'AINODE_OT_paste_clipboard'):
            _bu.register_class(AINODE_OT_paste_clipboard)
        if not hasattr(bpy.types, 'AINODE_OT_fit_width'):
            _bu.register_class(AINODE_OT_fit_width)
        if not hasattr(bpy.types, 'AINODE_PT_note_panel'):
            _bu.register_class(AINODE_PT_note_panel)
        ensure_keymap()
    except Exception:
        pass

def _compute_width(text):
    def w(ch):
        v = 7.5
        c = ord(ch)
        if c < 128:
            if ch in "il1.,'|:;!I()[] ":
                v = 4.0
            elif ch in "mwMW@%_":
                v = 10.0
            elif ch.isupper() or ch.isdigit():
                v = 8.2
            else:
                v = 5.5
        else:
            v = 11.0
        return v * 1.03
    m = 0
    for line in (text.splitlines() or [text]):
        cur = 0
        for ch in line:
            cur += w(ch)
        if cur > m:
            m = cur
    return max(100, int(m) + 15)

def _get_tree_and_space():
    ctx = bpy.context
    area = None
    for a in ctx.screen.areas:
        if a.type == 'NODE_EDITOR':
            area = a
            break
    space = None
    tree = None
    if area:
        for s in area.spaces:
            if s.type == 'NODE_EDITOR':
                space = s
                break
    if space:
        tree = space.edit_tree
    if not tree and hasattr(ctx, 'space_data') and getattr(ctx.space_data, 'type', '') == 'NODE_EDITOR':
        tree = ctx.space_data.edit_tree
        space = ctx.space_data
    return tree, space, area

def create_note(text):
    ensure_registered()
    tree, space, area = _get_tree_and_space()
    if not tree:
        return False
    try:
        node = tree.nodes.new('AINodeTextNote')
    except Exception:
        return False
    if space and hasattr(space, 'cursor_location') and space.cursor_location:
        loc = space.cursor_location
        node.location = (loc.x - 100, loc.y)
    node.label = '注记'
    try:
        txt_block = bpy.data.texts.new(name='注记')
    except Exception:
        txt_block = None
    if txt_block:
        txt_block.use_fake_user = True
        txt_block.from_string(text)
        node.text_name = txt_block.name
        width = _compute_width(text)
        node.width = width
    for n in tree.nodes:
        n.select = False
    node.select = True
    tree.nodes.active = node
    if area:
        area.tag_redraw()
    return True

def update_active(text):
    ensure_registered()
    tree, _, area = _get_tree_and_space()
    if not tree or not tree.nodes.active:
        return False
    node = tree.nodes.active
    if getattr(node, 'bl_idname', '') != 'AINodeTextNote':
        return False
    txt = None
    if getattr(node, 'text_name', ''):
        txt = bpy.data.texts.get(node.text_name)
    if not txt:
        try:
            txt = bpy.data.texts.new(name='注记')
            node.text_name = txt.name
        except Exception:
            return False
    txt.use_fake_user = True
    txt.clear()
    txt.write(text)
    node.width = _compute_width(text)
    if area:
        area.tag_redraw()
    return True

def fit_active():
    tree, _, area = _get_tree_and_space()
    if not tree or not tree.nodes.active:
        return False
    node = tree.nodes.active
    if getattr(node, 'bl_idname', '') != 'AINodeTextNote':
        return False
    txt = bpy.data.texts.get(getattr(node, 'text_name', ''))
    if not txt:
        return False
    text = txt.as_string()
    node.width = _compute_width(text)
    if area:
        area.tag_redraw()
    return True

def open_editor():
    tree, _, _ = _get_tree_and_space()
    if not tree or not tree.nodes.active:
        return False
    node = tree.nodes.active
    if getattr(node, 'bl_idname', '') != 'AINodeTextNote':
        return False
    txt = bpy.data.texts.get(getattr(node, 'text_name', ''))
    if not txt:
        try:
            txt = bpy.data.texts.new(name='注记')
            node.text_name = txt.name
        except Exception:
            return False
    if bpy.ops.screen.area_dupli.poll():
        bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
    new_window = bpy.context.window_manager.windows[-1]
    for area in new_window.screen.areas:
        area.type = "TEXT_EDITOR"
        for space in area.spaces:
            if space.type == "TEXT_EDITOR":
                space.text = txt
                space.show_region_header = False
                space.show_region_ui = False
                space.show_line_numbers = False
                space.show_syntax_highlight = True
                space.show_margin = False
                space.show_word_wrap = True
                if hasattr(space, "font_size"):
                    space.font_size = 14
    return True

class AINODE_OT_open_editor(Operator):
    bl_idname = "ainode.open_editor"
    bl_label = "Open Editor"
    @classmethod
    def poll(cls, context):
        tree = getattr(context.space_data, 'edit_tree', None)
        node = tree.nodes.active if tree else None
        return bool(node and getattr(node, 'bl_idname', '') == 'AINodeTextNote')
    def invoke(self, context, event):
        open_editor()
        return {'FINISHED'}

class AINODE_OT_close_window(Operator):
    bl_idname = "ainode.close_window"
    bl_label = "Close Editor Window"
    def execute(self, context):
        try:
            bpy.ops.wm.window_close()
        except Exception:
            pass
        return {'FINISHED'}

class AINODE_OT_paste_clipboard(Operator):
    bl_idname = "ainode.paste_clipboard"
    bl_label = "Paste Clipboard"
    def execute(self, context):
        content = context.window_manager.clipboard
        if content:
            update_active(content)
        return {'FINISHED'}

class AINODE_OT_fit_width(Operator):
    bl_idname = "ainode.fit_width"
    bl_label = "Fit Width"
    def execute(self, context):
        fit_active()
        return {'FINISHED'}

class AINODE_PT_note_panel(Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'AINode'
    bl_label = 'Note'
    def draw(self, context):
        layout = self.layout
        tree = getattr(context.space_data, 'edit_tree', None)
        node = tree.nodes.active if tree else None
        if not node or getattr(node, 'bl_idname', '') != 'AINodeTextNote':
            layout.label(text="No active note")
            return
        layout.prop(node, "ui_color", text="Color")
        row = layout.row(align=True)
        row.operator("ainode.open_editor", text="Open")
        row.operator("ainode.fit_width", text="Fit")
        row.operator("ainode.paste_clipboard", text="Paste")

def ensure_keymap():
    kc = bpy.context.window_manager.keyconfigs.addon
    if not kc:
        return
    km = kc.keymaps.get('Node Editor') or kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
    has_open = any(kmi.idname == 'ainode.open_editor' for kmi in km.keymap_items)
    if not has_open:
        try:
            km.keymap_items.new('ainode.open_editor', 'LEFTMOUSE', 'DOUBLE_CLICK')
        except Exception:
            pass
    km2 = kc.keymaps.get('Text') or kc.keymaps.new(name='Text', space_type='TEXT_EDITOR')
    has_close = any(kmi.idname == 'ainode.close_window' for kmi in km2.keymap_items)
    if not has_close:
        try:
            km2.keymap_items.new('ainode.close_window', 'ESC', 'PRESS')
        except Exception:
            pass
    has_paste = any(kmi.idname == 'ainode.paste_clipboard' for kmi in km.keymap_items)
    if not has_paste:
        try:
            km.keymap_items.new('ainode.paste_clipboard', 'V', 'PRESS', ctrl=True, shift=True)
        except Exception:
            pass
