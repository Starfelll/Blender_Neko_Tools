import bpy
from decimal import Decimal
from pathlib import Path


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


class OP_MergeBonesByDistance(bpy.types.Operator):
    bl_idname = "sourcecat.merge_bones"
    bl_label = "Merge Bones"
    bl_description = "在选中的骨骼里，将不属于任何骨骼集合的骨骼，按照距离合并权重到存在于骨骼集合中的骨骼"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        init_mode = context.object.mode
        switch_mode('EDIT')

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
                    merge_bone(armature, merging_list[-1][0], merging_list[-1][1], scene.keep_merged_bones)
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
        switch_mode(init_mode)
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
        result = {}

        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue
            mesh: bpy.types.Mesh = obj.data
            for mat in mesh.materials:
                node_tree = mat.node_tree
                if not node_tree:
                    continue
                for node in node_tree.nodes:
                    if node.type == "TEX_IMAGE" and node.image:
                        result[mat.name] = Path(node.image.name).stem
                        break
        
        tmpStr = ""
        for r in result:
            tmpStr += f'$PreRenameMaterial "{r}" "{result[r]}"\n'
        if len(tmpStr) > 0:
            context.window_manager.clipboard = tmpStr

        return {'FINISHED'}

class OP_CopyBodyGroup(bpy.types.Operator):
    bl_idname = "sourcecat.copy_bodygroup"
    bl_label = "CopyBodyGroupQC"
    bl_options = {'REGISTER', 'UNDO'}

    def _make_bg_qc(self, name: str) -> str:
        tmpStr = f'$BodyGroup "{name}" '
        tmpStr += "{\n"
        tmpStr += f'\tstudio $custom_model$ InNode "{name}"\n\tblank\n'
        tmpStr += "}\n"
        return tmpStr

    def execute(self, context: bpy.types.Context):
        tmpStr = ""
        for id in context.selected_ids:
            if id.rna_type.name != 'Collection':
                continue
            tmpStr += self._make_bg_qc(id.name)
        
        for obj in context.selected_objects:
            tmpStr += self._make_bg_qc(obj.name)

        if len(tmpStr) > 0:
            context.window_manager.clipboard = tmpStr

        return {'FINISHED'}


class OP_SeparateByMaterial(bpy.types.Operator):
    bl_idname = "sourcecat.separate_by_material"
    bl_label = "根据材质拆分网格（保持法线）"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "请确保物体属性-数据-几何数据里有“清除自定义拆边法向数据”这个按钮"

    def execute(self, context: bpy.types.Context):
        init_mode = context.object.mode
        switch_mode("EDIT")
        meshObj = context.active_object
        for mat_slot in meshObj.material_slots.items():
            meshObj.active_material_index = mat_slot[1].slot_index
            bpy.ops.mesh.select_all(action="DESELECT")
            bpy.ops.object.material_slot_select()
            bpy.ops.mesh.split()
        bpy.ops.mesh.separate(type="MATERIAL")
        switch_mode(init_mode)
        return {'FINISHED'}


class OP_MergeArmature(bpy.types.Operator):
    bl_idname = "sourcecat.merge_armature"
    bl_label = "合并骨架"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "自动嫁接同名骨骼"

    def execute(self, context: bpy.types.Context):
        init_mode = context.object.mode

        merge_to = context.active_object
        to_merge = None

        try:
            if merge_to.type != "ARMATURE":
                self.report({"ERROR"}, "活动项不是骨架")
                raise

            for obj in context.selected_objects:
                if obj.name != merge_to.name and obj.type == merge_to.type:
                    to_merge = obj
                    break
            if to_merge is None or len(context.selected_objects) != 2:
                self.report({"ERROR"}, "需要选中两个骨架")
                raise

            switch_mode("EDIT")

            for bone in to_merge.data.edit_bones:
                if merge_to.data.edit_bones.find(bone.name) != -1:
                    bone.parent = None
            
            parent_backup = {}
            for bone in to_merge.data.edit_bones:
                if merge_to.data.edit_bones.find(bone.name) != -1:
                    for child in bone.children:
                        parent_backup[child.name] = bone.name
                    to_merge.data.edit_bones.remove(bone)

            switch_mode("OBJECT")
            bpy.ops.object.select_all(action="DESELECT")

            for child in to_merge.children:
                for modifier in child.modifiers:
                    modifier: bpy.types.ArmatureModifier = modifier
                    if modifier.type != "ARMATURE":
                        continue
                    if modifier.object == to_merge:
                        modifier.object = merge_to
                child.select_set(True)

            bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
            merge_to.select_set(True)
            bpy.ops.object.parent_set()

            bpy.ops.object.select_all(action="DESELECT")

            to_merge.select_set(True)
            merge_to.select_set(True)
            bpy.ops.object.join()

            switch_mode("EDIT")

            for bone_name in parent_backup:
                parent_bone_idx = merge_to.data.edit_bones.find(parent_backup[bone_name])
                bone_idx = merge_to.data.edit_bones.find(bone_name)
                merge_to.data.edit_bones[bone_idx].parent = merge_to.data.edit_bones[parent_bone_idx]

        except Exception:
            return {'CANCELLED'}
        finally:
            switch_mode(init_mode)
        
        
        return {'FINISHED'}


class VIEW_3D_PT_nekotools(bpy.types.Panel):
    bl_idname = "VIEW_3D_PT_nekotools"
    bl_label = "Neko Tools 🐾"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "⭐"

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
        row.operator(OP_MergeBonesByDistance.bl_idname, text="合并🐾")

        col = box.column()
        col.operator(OP_CollapseMaterialName.bl_idname, text="生成精简后的材质列表")
        col.operator(OP_SeparateByMaterial.bl_idname)
        col.operator(OP_MergeArmature.bl_idname)


# resutn posebone or editbone
def get_selected_bones(context: bpy.types.Context):
    if context.mode == "EDIT_ARMATURE":
        return context.selected_bones
    else:
        return context.selected_pose_bones


class OP_SelectedBonesToClipboard(bpy.types.Operator):
    bl_idname = "nekotools.selected_bones_to_clipboard"
    bl_label = "复制选中骨骼名字"
    bl_options = {'REGISTER', 'UNDO'}
    prefix: bpy.props.StringProperty(name="前缀", default="$BoneMerge ") # type: ignore
    
    def execute(self, context: bpy.types.Context):
        is_first = True
        result = ''
        selected_bones = get_selected_bones(context)
        for bone in selected_bones:
            if is_first:
                is_first = False
            else:
                result += "\n"
            result += f'{self.prefix}"{bone.name}"'
        if len(result) > 0:
            context.window_manager.clipboard = result
        return {"FINISHED"}


class OP_SelectBones1(bpy.types.Operator):
    bl_idname = "nekotools.select_bones1"
    bl_label = "选择平级链平级骨"
    bl_options = {'REGISTER', 'UNDO'}
    same_prefix: bpy.props.BoolProperty(name="相同前缀", default=True)

    def execute(self, context: bpy.types.Context):
        chain_parent = context.active_bone
        if chain_parent.parent is None:
            return {'FINISHED'}
        
        in_chain_depth = 0
        init_mode = context.object.mode
        switch_mode("EDIT")

        selected_bones = {}
        for bone in get_selected_bones(context):
            selected_bones[bone.name] = True

        def set_edit_bone_select(bone: bpy.types.EditBone, state: bool):
            bone.select = state
            bone.select_head = state
            bone.select_tail = state

        while True:
            ref_chain_root = chain_parent.name
            chain_parent = chain_parent.parent
            if len(chain_parent.children) > 2 or chain_parent.parent is None:
                break
            in_chain_depth += 1
        
        if self.same_prefix:
            context_override = {}
            if (context.object.type != "ARMATURE"):
                return {"nonono"}
            context_override["active_bone"] = context.object.data.edit_bones[ref_chain_root]
            with context.temp_override(**context_override):
                bpy.ops.armature.select_similar(type="PREFIX")
                selected_prefix_bones = {}
                for bone in get_selected_bones(context):
                    selected_prefix_bones[bone.name] = True

        def select_bone_in_detph(bone, depth):
            if depth <= 0 and not (bone.hide_select or bone.hide):
                if self.same_prefix:
                    # if bone.name not in selected_prefix_bones:
                    #     return
                    selected_bones[bone.name] = True
                set_edit_bone_select(bone, True)
                return
            for bone_child in bone.children:
                select_bone_in_detph(bone_child, depth-1)
                break
        
        for bone in chain_parent.children:
            if self.same_prefix and bone.name not in selected_prefix_bones:
                continue
            select_bone_in_detph(bone, in_chain_depth)

        if self.same_prefix:
            for bone in get_selected_bones(context):
                if bone.name not in selected_bones:
                    set_edit_bone_select(bone, False)
        
        switch_mode(init_mode)
        return {'FINISHED'}


class OP_SetAllShapeKeyMuteState(bpy.types.Operator):
    bl_idname = "nekotools.set_all_shape_key_mute_state"
    bl_label = "设置所有形态键屏蔽状态"
    bl_options = {'REGISTER', 'UNDO'}
    options: bpy.props.StringProperty(name="options", default="INVERT")
    protect_locked: bpy.props.BoolProperty(name="protect_locked", default=True)

    def execute(self, context: bpy.types.Context):
        if self.options == "INVERT":
            for shape_key in context.object.data.shape_keys.key_blocks:
                if not self.protect_locked or not shape_key.lock_shape:
                    shape_key.mute = not shape_key.mute
        else:
            state = self.options == "MUTE"
            for shape_key in context.object.data.shape_keys.key_blocks:
                if not self.protect_locked or not shape_key.lock_shape:
                    shape_key.mute = state
        
        return {'FINISHED'}



class VIEW3D_MT_select_pose_nekotools(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_select_pose_nekotools"
    bl_label = bl_idname

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        this.layout.operator(OP_SelectBones1.bl_idname)

    @staticmethod
    def register():
        bpy.types.VIEW3D_MT_select_pose.append(VIEW3D_MT_select_pose_nekotools.draw_menu)
        bpy.types.VIEW3D_MT_select_edit_armature.append(VIEW3D_MT_select_pose_nekotools.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.VIEW3D_MT_select_pose.remove(VIEW3D_MT_select_pose_nekotools.draw_menu)
        bpy.types.VIEW3D_MT_select_edit_armature.remove(VIEW3D_MT_select_pose_nekotools.draw_menu)


class VIEW3D_MT_pose_nekotools(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_pose_nekotools"
    bl_label = bl_idname

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        this.layout.operator(OP_SelectedBonesToClipboard.bl_idname)
    
    @staticmethod
    def register():
        bpy.types.VIEW3D_MT_pose.append(VIEW3D_MT_pose_nekotools.draw_menu)
        bpy.types.VIEW3D_MT_pose_context_menu.append(VIEW3D_MT_pose_nekotools.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.VIEW3D_MT_pose.remove(VIEW3D_MT_pose_nekotools.draw_menu)
        bpy.types.VIEW3D_MT_pose_context_menu.remove(VIEW3D_MT_pose_nekotools.draw_menu)


class VIEW3D_MT_edit_armature_nekotools(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_edit_armature_nekotools"
    bl_label = bl_idname

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        this.layout.operator(OP_SelectedBonesToClipboard.bl_idname)
    
    @staticmethod
    def register():
        bpy.types.VIEW3D_MT_edit_armature.append(VIEW3D_MT_edit_armature_nekotools.draw_menu)
        bpy.types.VIEW3D_MT_armature_context_menu.append(VIEW3D_MT_edit_armature_nekotools.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.VIEW3D_MT_edit_armature.remove(VIEW3D_MT_edit_armature_nekotools.draw_menu)
        bpy.types.VIEW3D_MT_armature_context_menu.remove(VIEW3D_MT_edit_armature_nekotools.draw_menu)


class MESH_MT_shape_key_context_menu_nekotools(bpy.types.Menu):
    bl_idname = "MESH_MT_shape_key_context_menu_nekotools"
    bl_label = bl_idname

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        op = this.layout.operator(OP_SetAllShapeKeyMuteState.bl_idname, text="屏蔽", icon="CHECKBOX_DEHLT")
        op.options = "MUTE"
        op = this.layout.operator(OP_SetAllShapeKeyMuteState.bl_idname, text="取消屏蔽", icon="CHECKBOX_HLT")
        op.options = "UNMUTE"
        op = this.layout.operator(OP_SetAllShapeKeyMuteState.bl_idname, text="反转屏蔽", icon="SELECT_DIFFERENCE")
        op.options = "INVERT"
    
    @staticmethod
    def register():
        bpy.types.MESH_MT_shape_key_context_menu.append(
            MESH_MT_shape_key_context_menu_nekotools.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.MESH_MT_shape_key_context_menu.remove(
            MESH_MT_shape_key_context_menu_nekotools.draw_menu)
        

class OUTLINER_MT_collection_nekotools(bpy.types.Menu):
    bl_idname = "OUTLINER_MT_collection_nekotools"
    bl_label = bl_idname

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        op = this.layout.operator(OP_CopyBodyGroup.bl_idname)
    
    @staticmethod
    def register():
        bpy.types.OUTLINER_MT_collection.append(
            OUTLINER_MT_collection_nekotools.draw_menu)
        bpy.types.OUTLINER_MT_object.append(OUTLINER_MT_collection_nekotools.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.OUTLINER_MT_collection.remove(
            OUTLINER_MT_collection_nekotools.draw_menu)
        bpy.types.OUTLINER_MT_object.remove(OUTLINER_MT_collection_nekotools.draw_menu)
        


classes = [
    OP_MergeBones_GetThreshold,
    OP_CollapseMaterialName,
    OP_CopyBodyGroup,
    OP_SeparateByMaterial,
    OP_MergeBonesByDistance,
    OP_MergeToActive,
    OP_MergeArmature,
    VIEW_3D_PT_nekotools,
    OP_SelectBones1,
    OP_SelectedBonesToClipboard,
    OP_SetAllShapeKeyMuteState,
    VIEW3D_MT_select_pose_nekotools,
    VIEW3D_MT_pose_nekotools,
    VIEW3D_MT_edit_armature_nekotools,
    MESH_MT_shape_key_context_menu_nekotools,
    OUTLINER_MT_collection_nekotools
]
