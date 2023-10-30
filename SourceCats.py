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


def merge_bone(armature, tomerge, bone):
    tomerge = armature.data.edit_bones.get(tomerge)
    bone = armature.data.edit_bones.get(bone)
    if tomerge and bone:
        tomerge.parent = bone
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
                    if not scene.keep_merged_bones:
                        switch_mode('EDIT')
                        merge_bone(armature,
                                   merging_list[-1][0], merging_list[-1][1])
                        switch_mode("OBJECT")

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
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        boneA = context.active_pose_bone.head
        boneB = context.selected_pose_bones[-1].head
        result = (boneA - boneB).length
        context.scene.merge_bones_threshold = result
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

        # # Create a simple row.
        # layout.label(text=" Simple Row:")

        # row = layout.row()
        # row.prop(scene, "frame_start")
        # row.prop(scene, "frame_end")

        # # Create an row where the buttons are aligned to each other.
        # layout.label(text=" Aligned Row:")

        # row = layout.row(align=True)
        # row.prop(scene, "frame_start")
        # row.prop(scene, "frame_end")

        # # Create two columns, by using a split layout.
        # split = layout.split()

        # # First column
        # col = split.column()
        # col.label(text="Column One:")
        # col.prop(scene, "frame_end")
        # col.prop(scene, "frame_start")

        # # Second column, aligned
        # col = split.column(align=True)
        # col.label(text="Column Two:")
        # col.prop(scene, "frame_start")
        # col.prop(scene, "frame_end")

        # # Big render button
        # layout.label(text="Big Button:")
        # row = layout.row()
        # row.scale_y = 3.0
        # row.operator("render.render")

        # # Different sizes in a row
        # layout.label(text="Different button sizes:")
        # row = layout.row(align=True)
        # row.operator("render.render")

        # sub = row.row()
        # sub.scale_x = 2.0
        # sub.operator("render.render")

        # row.operator("render.render")


