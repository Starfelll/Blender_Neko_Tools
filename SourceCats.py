import bpy
from decimal import Decimal


def switch_mode(mode):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)


def merge_weights(mesh, vg_from, vg_to):
    mesh.active_shape_key_index = 0
    mod = mesh.modifiers.new("VertexWeightMix", 'VERTEX_WEIGHT_MIX')
    mod.vertex_group_a = vg_to
    mod.vertex_group_b = vg_from
    mod.mix_mode = "ADD"
    mod.mix_set = 'B'
    mod.mask_constant = 1.0
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mesh.vertex_groups.remove(mesh.vertex_groups.get(vg_from))


def merge_bone(armature, tomerge, bone, keep_merged_bones: bool):
    tomerge = armature.data.edit_bones.get(tomerge)
    bone = armature.data.edit_bones.get(bone)
    if tomerge and bone:
        tomerge.parent = bone
        if not keep_merged_bones:
            armature.data.edit_bones.remove(tomerge)


def set_active_obj(obj):
    bpy.context.view_layer.objects.active = obj


class OP_MergeBones(bpy.types.Operator):
    bl_idname = "sourcecat.merge_bones"
    bl_label = "Merge Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_bones = context.selected_pose_bones
        if selected_bones is None:
            self.report({'INFO'}, 'No selected bone')
            return {'CANCELLED'}

        armature = context.object
        scene = context.scene
        switch_mode("OBJECT")
        set_active_obj(armature)
        merging_list = []
        for i in range(len(selected_bones)):
            boneA = selected_bones[i]
            for i2 in range(i+1, len(selected_bones)):
                boneB = selected_bones[i2]
                d = boneA.head \
                    - boneB.head

                if Decimal(d.length) <= Decimal(scene.merge_bones_threshold):
                    aIsValveBone = boneA.name.startswith("ValveBiped.Bip")
                    bIsValveBone = boneB.name.startswith("ValveBiped.Bip")
                    if aIsValveBone and bIsValveBone:
                        continue
                    elif aIsValveBone:
                        merging_list.append([boneB.name, boneA.name])
                    elif bIsValveBone:
                        merging_list.append([boneA.name, boneB.name])
                        switch_mode('EDIT')
                        merge_bone(armature,
                                   merging_list[-1][0], merging_list[-1][1], scene.keep_merged_bones)
                        switch_mode("OBJECT")

        if not scene.keep_merged_bones:
            for obj in bpy.context.scene.objects.get(armature.name).children:
                if obj.type != 'MESH':
                    continue
                for tomerge, bone in merging_list:
                    vg_tomerge = obj.vertex_groups.get(tomerge)
                    vg_bone = obj.vertex_groups.get(bone)
                    if vg_tomerge:
                        if vg_bone is None:
                            obj.vertex_groups.new(name=bone)
                        set_active_obj(obj)
                        merge_weights(mesh=obj, vg_from=tomerge, vg_to=bone)
        set_active_obj(armature)
        switch_mode("POSE")
        return {'FINISHED'}


class OP_MergeBones_GetThreshold(bpy.types.Operator):
    bl_idname = "sourcecat.merge_bones_get_threshold"
    bl_label = "Get Threshold"
    bl_options = {'REGISTER'}

    def execute(self, context):
        boneA = context.active_pose_bone.head
        boneB = context.selected_pose_bones[-1].head
        result = (boneA - boneB).length
        context.scene.merge_bones_threshold = result
        return {'FINISHED'}

class OP_GenLRFlexs(bpy.types.Operator):
    bl_idname = "sourcecat.gen_lr_flexs"
    bl_label = "Gen LR Flexs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context):
        selected_object:bpy.types.Object = context.selected_objects[0]

        shape_keys = selected_object.data.shape_keys.key_blocks
        for shape_key in shape_keys:
            name:str = shape_key.name
            if name[-1] != "R" and name[-1] != "L" and shape_key.vertex_group == "":
                
                flexL:bpy.types.ShapeKey = shape_key

                if flexL.relative_key == flexL:
                    continue
                flexL.name = f'{name}L'
                flexL.vertex_group = "L"

                bpy.ops.object.shape_key_clear()
                flexL.value = flexL.slider_max
                # func from shape keys+ addon
                flexR = selected_object.shape_key_add(name=f'{name}R', from_mix=True)
                flexR.vertex_group = "R"
        return {'FINISHED'}

class OP_ClearLRFlexs(bpy.types.Operator):
    bl_idname = "sourcecat.clear_lr_flexs"
    bl_label = "Clear LR Flexs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context):
        selected_object:bpy.types.Object = context.selected_objects[0]

        shape_keys = selected_object.data.shape_keys.key_blocks
        pairs = {}
        for shape_key in shape_keys:
            name:str = shape_key.name
            name = name.removesuffix("R")
            name = name.removesuffix("L")
            #print(name)
            if pairs.get(name):
                pairs[name].append(shape_key)
            else:
                pairs[name] = [shape_key]

        for v in pairs:
            pair = pairs[v]
            if len(pair) == 2:
                flexL = None
                flexR = None
                for flex in pair:
                    vertex_group = flex.vertex_group
                    if vertex_group == "L":
                        flexL = flex
                    elif vertex_group == "R":
                        flexR = flex
                
                if flexL and flexR:
                    flexL.vertex_group = ""
                    flexL.name = flexL.name.removesuffix("L")
                    selected_object.shape_key_remove(flexR)

        return {'FINISHED'}


class SourceCats_PT_MainPanel(bpy.types.Panel):
    bl_idname = "SourceCats_PT_MainPanel"
    bl_label = "SourceCats"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SCats"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        col = box.column()

        row = col.row()
        row.alignment = "EXPAND"
        row.prop(scene, "merge_bones_threshold")
        row_row = row.row()
        row_row.alignment = "CENTER"
        row_row.operator(OP_MergeBones_GetThreshold.bl_idname, text="Get")

        col.prop(scene, "keep_merged_bones")
        row = col.row()
        row.scale_y = 1.6
        row.operator(OP_MergeBones.bl_idname)

        box = layout.box()
        row = box.row()
        row.operator(OP_GenLRFlexs.bl_idname)
        row.operator(OP_ClearLRFlexs.bl_idname)


