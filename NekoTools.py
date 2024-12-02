import bpy
from decimal import Decimal


def switch_mode(mode):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)


def merge_weights(mesh, vg_from: str, vg_to: str):
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
    bl_description = "在选中的骨骼里，将不属于任何骨骼集合的骨骼，按照距离合并权重到存在于骨骼集合中的骨骼"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_bones = context.selected_bones
        if selected_bones is None:
            self.report({'INFO'}, 'No selected bone')
            return {'CANCELLED'}

        armature = context.object
        scene = context.scene
        merging_list = []
        print(len(selected_bones))
        for i in range(len(selected_bones)):
            boneA = selected_bones[i]
            for i2 in range(i+1, len(selected_bones)):
                boneB = selected_bones[i2]
                d = boneA.head - boneB.head

                if Decimal(d.length) <= Decimal(scene.merge_bones_threshold):
                    aInGroup = False
                    bInGroup = False
                    print(boneB.collections)
                    print(boneA.collections)
                    if len(boneA.collections.keys()):
                        aInGroup = True
                    if len(boneB.collections.keys()):
                        bInGroup = True
                    
                    if aInGroup and bInGroup:
                        print(boneA.collections, boneB.collections)
                        continue
                    elif aInGroup:
                        merging_list.append([boneB.name, boneA.name])
                    elif bInGroup:
                        merging_list.append([boneA.name, boneB.name])
                    switch_mode('EDIT')
                    merge_bone(armature, merging_list[-1][0], merging_list[-1][1], scene.keep_merged_bones)
                    #switch_mode("OBJECT")
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
        switch_mode('EDIT')
        return {'FINISHED'}

class OP_MergeToActive(bpy.types.Operator):
    bl_idname = "sourcecat.merge_bones_to_active"
    bl_label = "MergeToActive"
    bl_description = "在选中的骨骼里，将其它骨骼合并到激活的骨骼（包括权重）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_bones = context.selected_bones
        if selected_bones is None:
            self.report({'INFO'}, 'No selected bone')
            return {'CANCELLED'}
        
        active_bone = context.active_bone

        armature = context.object
        scene = context.scene
        merging_list = []
        for i in range(len(selected_bones)):
            s_bone = selected_bones[i]
            if s_bone == active_bone:
                continue
            print(s_bone)
            merging_list.append(s_bone.name)
            switch_mode('EDIT')
            merge_bone(armature, s_bone.name, active_bone.name, scene.keep_merged_bones)
            switch_mode("OBJECT")

        
        for obj in bpy.context.scene.objects.get(armature.name).children:
            if obj.type != 'MESH':
                continue
            for s_bone in merging_list:
                vg_tomerge = obj.vertex_groups.get(s_bone)
                if vg_tomerge:
                    if obj.vertex_groups.get(active_bone.name) is None:
                        obj.vertex_groups.new(name=active_bone.name)
                    set_active_obj(obj)
                    merge_weights(mesh=obj, vg_from=s_bone, vg_to=active_bone.name)
        set_active_obj(armature)
        switch_mode('EDIT')
        return {'FINISHED'}


class OP_MergeBones_GetThreshold(bpy.types.Operator):
    bl_idname = "sourcecat.merge_bones_get_threshold"
    bl_label = "Get Threshold"
    bl_description = "根据两骨骼距离获取阈值"
    bl_options = {'REGISTER'}

    def execute(self, context):
        boneA = context.active_bone.head
        boneB = context.selected_editable_bones[-1].head
        result = (boneA - boneB).length
        context.scene.merge_bones_threshold = result
        return {'FINISHED'}

class OP_CollapseMaterialName(bpy.types.Operator):
    bl_idname = "sourcecat.collapse_material_name"
    bl_label = "Collapse material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context):
        for mat in bpy.data.materials:
            node_tree = mat.node_tree
            if not node_tree:
                continue
            for node in node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    suff = node.image.name.split(".")[0]
                    if mat.name.split(".")[0] != suff:
                        mat.name = f'{suff}.{mat.name}'
        return {'FINISHED'}

class PT_MainPanel(bpy.types.Panel):
    bl_idname = "PT_MainPanel"
    bl_label = "Neko Tools 🐾"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Neko"

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
        row_row.operator(OP_MergeBones_GetThreshold.bl_idname, icon="FIXED_SIZE", text="")

        row = col.row()
        row.alignment = "EXPAND"
        row.prop(scene, "keep_merged_bones", text="不删除骨骼")
        row.operator(OP_MergeToActive.bl_idname, text="合并到激活")

        row = col.row()
        row.scale_y = 1.6
        row.operator(OP_MergeBones.bl_idname, text="合并🐾")


        # col = box.column()
        # col.operator(OP_CollapseMaterialName.bl_idname, text="塌陷所有材质")


class OP_SelectBones1(bpy.types.Operator):
    bl_idname = "nekotools.select_bones1"
    bl_label = "选择平级链平级骨"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context):
        chain_parent = context.active_bone
        if chain_parent.parent is None:
            return {'FINISHED'}
        
        in_chain_depth = 0
        while True:
            chain_parent = chain_parent.parent
            if len(chain_parent.children) > 2 or chain_parent.parent is None:
                break
            in_chain_depth += 1

        def select_bone_in_detph(bone, depth):
            if depth <= 0:
                bone.select = True
                return
            for bone_child in bone.children:
                select_bone_in_detph(bone_child, depth-1)
                break
        
        print(in_chain_depth)
        for bone in chain_parent.children:
            select_bone_in_detph(bone, in_chain_depth)
        return {'FINISHED'}


class SelectBones1Menu(bpy.types.Menu):
    bl_idname = "nekotools.select_bones1_menu"
    bl_label = "选择平级链平级骨"

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        this.layout.operator(OP_SelectBones1.bl_idname)

    @staticmethod
    def register():
        bpy.types.VIEW3D_MT_select_pose.append(SelectBones1Menu.draw_menu)
        bpy.types.VIEW3D_MT_select_edit_armature.append(SelectBones1Menu.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.VIEW3D_MT_select_pose.remove(SelectBones1Menu.draw_menu)
        bpy.types.VIEW3D_MT_select_edit_armature.remove(SelectBones1Menu.draw_menu)


class_list = [
    OP_MergeBones_GetThreshold,
    OP_CollapseMaterialName,
    OP_MergeBones,
    OP_MergeToActive,
    PT_MainPanel,
    OP_SelectBones1,
    SelectBones1Menu,
]
