import random
from typing import Any

import bpy
import numpy as np

bl_info = {
    "name": "Jigsaw",
    "author": "tsutomu",
    "version": (0, 1),
    "blender": (3, 1, 0),
    "support": "TESTING",
    "category": "Object",
    "description": "",
    "location": "View3D > Sidebar > Edit Tab",
    "warning": "",
    "doc_url": "https://github.com/SaitoTsutomu/Jigsaw",  # ドキュメントURL
}


class CJG_OT_make_puzzle(bpy.types.Operator):
    bl_idname = "object.make_puzzle"
    bl_label = "Select"
    bl_description = ""

    filepath: bpy.props.StringProperty()  # type: ignore # noqa
    num_x: bpy.props.IntProperty()  # type: ignore
    num_y: bpy.props.IntProperty()  # type: ignore

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        for i, col_name in enumerate(("jigsaw_frame", "jigsaw")):
            if col_name in bpy.data.collections:
                bpy.data.collections.remove(bpy.data.collections[col_name])
            col = bpy.data.collections.new(name=col_name)
            bpy.context.scene.collection.children.link(col)
            lc = bpy.context.view_layer.layer_collection.children[col_name]
            bpy.context.view_layer.active_layer_collection = lc
            if i == 0:
                if "frame" in bpy.data.materials:
                    bpy.data.materials.remove(bpy.data.materials["frame"])
                mat = bpy.data.materials.new(name="frame")
                mat.use_nodes = True
                bsdf = mat.node_tree.nodes["Principled BSDF"]
                bpy.ops.curve.simple(Simple_Type="Rectangle", use_cyclic_u=True)
                bpy.ops.transform.resize(value=(0.05 * self.num_x, 0.05 * self.num_y, 1))
                obj = context.object
                obj.active_material = mat
                obj.data.fill_mode = "NONE"
                obj.data.bevel_depth = 0.01
                obj.lock_location = True, True, True
        if "image" in bpy.data.materials:
            bpy.data.materials.remove(bpy.data.materials["image"])
        mat = bpy.data.materials.new(name="image")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        image = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
        image.image = bpy.data.images.load(filepath=self.filepath)
        mat.node_tree.links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
        self.num_x = max(1, self.num_x)
        self.num_y = max(1, self.num_y)
        bpy.ops.mesh.primitive_grid_add(
            x_subdivisions=self.num_x, y_subdivisions=self.num_y, size=0.1, enter_editmode=True
        )
        bpy.ops.transform.resize(value=(self.num_x, self.num_y, 1))
        obj = context.object
        obj.active_material = mat
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.modifier_add(type="EDGE_SPLIT")
        obj.modifiers[-1].split_angle = 0
        bpy.ops.object.modifier_apply(modifier=obj.modifiers[-1].name)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, 0.1)})
        bpy.ops.mesh.separate(type="LOOSE")
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        for obj in col.objects:
            obj.select_set(state=True)
            bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY")
            obj.select_set(state=False)
            obj.lock_location[2] = True
        return {"FINISHED"}


class CJG_OT_play_puzzle(bpy.types.Operator):
    bl_idname = "object.play_puzzle"
    bl_label = "Play Puzzle"
    bl_description = ""

    # インスタンスが異なることがあるので、代入はクラスにすること
    _timer = None
    answer: dict[str, Any] = {}

    def stop(self, context):
        if self._timer:
            mat = bpy.data.materials.get("frame")
            if mat:
                bsdf = mat.node_tree.nodes["Principled BSDF"]
                bsdf.inputs["Base Color"].default_value = 1, 0.8, 0, 1
            # タイマの登録を解除
            context.window_manager.event_timer_remove(self._timer)
            self.__class__._timer = None

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()
        if event.type == "TIMER":
            col = bpy.data.collections.get("jigsaw")
            for obj in col.objects:
                x, y, z = obj.location
                x = (x + 0.025) // 0.05 * 0.05
                y = (y + 0.025) // 0.05 * 0.05
                obj.location = x, y, z
            for obj in col.objects:
                df = np.linalg.norm(self.answer[obj.name] - obj.location)
                if df > 0.04:
                    print(obj.name, df)
                    break
            else:
                self.report({"INFO"}, "Clear!")
                self.stop(context)
        return {"PASS_THROUGH"} if self._timer else {"FINISHED"}

    def invoke(self, context, event):
        if context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        if not self._timer:
            col = bpy.data.collections.get("jigsaw")
            if not col:
                self.report({"WARNING"}, "No data.")
                return {"CANCELLED"}
            self.answer.clear()
            minx = miny = 99
            maxx = maxy = -99
            for obj in col.objects:
                minx = min(minx, obj.location[0])
                maxx = max(maxx, obj.location[0])
                miny = min(miny, obj.location[1])
                maxy = max(maxy, obj.location[1])
            for obj in col.objects:
                self.answer[obj.name] = np.array(obj.location)
                while True:
                    x = random.uniform(minx - 0.3, maxx + 0.3)
                    y = random.uniform(miny - 0.3, maxy + 0.3)
                    if not ((minx < x < maxx) and (miny < y < maxy)):
                        break
                obj.location = x, y, obj.location[2]
            mat = bpy.data.materials.get("frame")
            if mat:
                bsdf = mat.node_tree.nodes["Principled BSDF"]
                bsdf.inputs["Base Color"].default_value = 1, 1, 1, 1
            # タイマを登録
            timer = context.window_manager.event_timer_add(1, window=context.window)
            self.__class__._timer = timer
            context.window_manager.modal_handler_add(self)
            # モーダルモードへの移行
            return {"RUNNING_MODAL"}
        self.stop(context)
        # モーダルモードを終了
        return {"FINISHED"}


class CJG_PT_puzzle(bpy.types.Panel):
    bl_label = "Puzzle"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Edit"
    bl_context = "objectmode"

    def draw(self, context):
        self.layout.prop(context.scene, "num_x", text="num x")
        self.layout.prop(context.scene, "num_y", text="num y")
        prop = self.layout.operator(CJG_OT_make_puzzle.bl_idname, text="Make Puzzle")
        prop.num_x = context.scene.num_x
        prop.num_y = context.scene.num_y
        text, icon = "Start", "PLAY"
        if CJG_OT_play_puzzle._timer:
            text, icon = "Finish", "PAUSE"
        self.layout.operator(CJG_OT_play_puzzle.bl_idname, text=text, icon=icon)


classes = [
    CJG_OT_make_puzzle,
    CJG_OT_play_puzzle,
    CJG_PT_puzzle,
]


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.num_x = bpy.props.IntProperty(default=3)
    bpy.types.Scene.num_y = bpy.props.IntProperty(default=2)


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.num_x
    del bpy.types.Scene.num_y


if __name__ == "__main__":
    register()
