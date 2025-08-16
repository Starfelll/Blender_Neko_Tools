import bpy
from bpy.props import BoolProperty, FloatProperty
from decimal import Decimal
from pathlib import Path
import bmesh

bl_info = {
    "name": "NekoTools🐾",
    "blender": (4, 0, 0),
    "version": (2, 2),
    'location': 'View 3D > Tool Shelf',
    'category': '3D View',
    "author": "Starfelll",
    "url": "https://steamcommunity.com/profiles/76561198859761739"
}


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
        mat_tex_map = {}

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
                        mat_tex_map[mat.name] = Path(node.image.name).stem
                        break
        
        result = {}
        for mat in mat_tex_map:
            tex = mat_tex_map[mat]
            if tex not in result:
                result[tex] = []
            result[tex].append(mat)

        tmpStr = ""
        for tex in result:
            for mat in result[tex]:
                tmpStr += f'$PreRenameMaterial "{mat}" "{tex}"\n'
            tmpStr += "\n"
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


# class OP_ValueBoneToBldnerFriendly:
#     bl_idname = "sourcecat.value_bone_to_blender_friendly"
#     bl_label = "Value骨转到V骨"
#     bl_options = {'REGISTER', 'UNDO'}


class OP_VToMMD(bpy.types.Operator):
    bl_idname = "sourcecat.v_to_mmd"
    bl_label = "V骨映射MMD骨"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "选中两个骨架，活动项为MMD骨架。两个骨架的姿态方向需要大致相同"

    def execute(self, context: bpy.types.Context):
        init_mode = context.object.mode
        
        mmd: bpy.types.Armature = context.active_object.data
        v: bpy.types.Armature = None
        for obj in context.selected_objects:
            if mmd != obj and obj.type == "ARMATURE":
                v = obj.data
                break

        switch_mode("POSE")

        v_mappings: bpy.props.CollectionProperty = bpy.data.armatures[v.name].kumopult_bac.mappings
        def vmap(f: str, t: str):
            item = v_mappings.add()
            item.has_loccopy = True
            item.selected_owner = f
            item.target = t

        vmap("V_Neck1", "Neck")
        vmap("V_Head1", "Head")
            
        vmap("V_Finger0_L", "Thumb0_L")
        vmap("V_Finger0_R", "Thumb0_R")
        vmap("V_Finger01_L", "Thumb1_L")
        vmap("V_Finger01_R", "Thumb1_R")
        vmap("V_Finger02_L", "Thumb2_L")
        vmap("V_Finger02_R", "Thumb2_R")

        vmap("V_Hand_R", "Wrist_R")
        vmap("V_Hand_L", "Wrist_L")

        vmap("V_Foot_R", "Ankle_R")
        vmap("V_Foot_L", "Ankle_L")

        vmap("V_Thigh_R", "Leg_R")
        vmap("V_Thigh_L", "Leg_L")
        vmap("V_Calf_R", "Knee_R")
        vmap("V_Calf_L", "Knee_L")

        vmap("V_UpperArm_R", "Arm_R")
        vmap("V_UpperArm_L", "Arm_L")
        vmap("V_Forearm_R", "Elbow_R")
        vmap("V_Forearm_L", "Elbow_L")

        vmap("V_Finger1_L", "IndexFinger1_L")
        vmap("V_Finger1_R", "IndexFinger1_R")
        vmap("V_Finger11_L", "IndexFinger2_L")
        vmap("V_Finger11_R", "IndexFinger2_R")
        vmap("V_Finger12_L", "IndexFinger3_L")
        vmap("V_Finger12_R", "IndexFinger3_R")

        vmap("V_Finger2_L", "MiddleFinger1_L")
        vmap("V_Finger2_R", "MiddleFinger1_R")
        vmap("V_Finger21_L", "MiddleFinger2_L")
        vmap("V_Finger21_R", "MiddleFinger2_R")
        vmap("V_Finger22_L", "MiddleFinger3_L")
        vmap("V_Finger22_R", "MiddleFinger3_R")

        vmap("V_Finger3_L", "RingFinger1_L")
        vmap("V_Finger3_R", "RingFinger1_R")
        vmap("V_Finger31_L", "RingFinger2_L")
        vmap("V_Finger31_R", "RingFinger2_R")
        vmap("V_Finger32_L", "RingFinger3_L")
        vmap("V_Finger32_R", "RingFinger3_R")

        vmap("V_Finger4_L", "LittleFinger1_L")
        vmap("V_Finger4_R", "LittleFinger1_R")
        vmap("V_Finger41_L", "LittleFinger2_L")
        vmap("V_Finger41_R", "LittleFinger2_R")
        vmap("V_Finger42_L", "LittleFinger3_L")
        vmap("V_Finger42_R", "LittleFinger3_R")

       
        def snap(f: str, t: str):
            bpy.ops.pose.select_all(action="DESELECT")
            v.bones.active = v.bones[v.bones.find(f)]
            mmd.bones.active = mmd.bones[mmd.bones.find(t)]
            bpy.ops.view3d.snap_selected_to_active()
        
        snap("V_Toe0_R", "ToeTip_R")
        snap("V_Toe0_L", "ToeTip_L")
        snap("V_Spine", "UpperBody")
        snap("V_Spine1", "UpperBody")
        snap("V_Spine2", "UpperBody2")
        snap("V_Spine4", "UpperBody2")
        snap("V_Clavicle_R", "Shoulder_R")
        snap("V_Clavicle_L", "Shoulder_L")

        switch_mode(init_mode)
        return {'FINISHED'}


class OP_MMDBoneToVParent(bpy.types.Operator):
    bl_idname = "sourcecat.mmd_bone_to_v_parent"
    bl_label = "设置mmd骨父级到v骨"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context):
        if context.active_object.type != "ARMATURE":
            self.report({'ERROR'}, 'no active armature')
            return {'CANCELLED'}

        init_mode = context.object.mode
        armature: bpy.types.Armature = context.active_object.data
        switch_mode("EDIT")

        def rp(p: str, b: str):
            armature.edit_bones[armature.edit_bones.find(b)].parent = armature.edit_bones[armature.edit_bones.find(p)]



        #rp("V_Spine", "UpperBody")
        rp("V_Spine1", "UpperBody")
        #rp("V_Spine2", "UpperBody2")
        rp("V_Spine4", "UpperBody2")
        rp("V_Pelvis", "ParentNode")
        rp("V_Pelvis", "LowerBody")

        rp("V_Clavicle_R", "Shoulder_R")
        rp("V_Clavicle_L", "Shoulder_L")
        rp("V_Neck1", "Neck")
        rp("V_Head1", "Head")
        rp("V_Finger0_L", "Thumb0_L")
        rp("V_Finger0_R", "Thumb0_R")
        rp("V_Finger01_L", "Thumb1_L")
        rp("V_Finger01_R", "Thumb1_R")
        rp("V_Finger02_L", "Thumb2_L")
        rp("V_Finger02_R", "Thumb2_R")
        rp("V_Hand_R", "Wrist_R")
        rp("V_Hand_L", "Wrist_L")

        rp("V_Toe0_R", "ToeTip_R")
        rp("V_Toe0_L", "ToeTip_L")
        rp("V_Toe0_R", "LegTipEX_R")
        rp("V_Toe0_L", "LegTipEX_L")

        rp("V_Foot_R", "Ankle_R")
        rp("V_Foot_L", "Ankle_L")
        rp("V_Foot_R", "AnkleD_R")
        rp("V_Foot_L", "AnkleD_L")

        rp("V_Calf_R", "Knee_R")
        rp("V_Calf_L", "Knee_L")
        rp("V_Calf_R", "KneeD_R")
        rp("V_Calf_L", "KneeD_L")

        rp("V_Thigh_R", "Leg_R")
        rp("V_Thigh_L", "Leg_L")
        rp("V_Thigh_R", "LegD_R")
        rp("V_Thigh_L", "LegD_L")


        rp("V_UpperArm_R", "Arm_R")
        rp("V_UpperArm_L", "Arm_L")
        rp("V_Forearm_R", "Elbow_R")
        rp("V_Forearm_L", "Elbow_L")
        rp("V_Finger1_L", "IndexFinger1_L")
        rp("V_Finger1_R", "IndexFinger1_R")
        rp("V_Finger11_L", "IndexFinger2_L")
        rp("V_Finger11_R", "IndexFinger2_R")
        rp("V_Finger12_L", "IndexFinger3_L")
        rp("V_Finger12_R", "IndexFinger3_R")
        rp("V_Finger2_L", "MiddleFinger1_L")
        rp("V_Finger2_R", "MiddleFinger1_R")
        rp("V_Finger21_L", "MiddleFinger2_L")
        rp("V_Finger21_R", "MiddleFinger2_R")
        rp("V_Finger22_L", "MiddleFinger3_L")
        rp("V_Finger22_R", "MiddleFinger3_R")
        rp("V_Finger3_L", "RingFinger1_L")
        rp("V_Finger3_R", "RingFinger1_R")
        rp("V_Finger31_L", "RingFinger2_L")
        rp("V_Finger31_R", "RingFinger2_R")
        rp("V_Finger32_L", "RingFinger3_L")
        rp("V_Finger32_R", "RingFinger3_R")
        rp("V_Finger4_L", "LittleFinger1_L")
        rp("V_Finger4_R", "LittleFinger1_R")
        rp("V_Finger41_L", "LittleFinger2_L")
        rp("V_Finger41_R", "LittleFinger2_R")
        rp("V_Finger42_L", "LittleFinger3_L")
        rp("V_Finger42_R", "LittleFinger3_R")

        switch_mode(init_mode)

        self.report({'INFO'}, 'DONE')
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
        col.operator(OP_VToMMD.bl_idname)
        col.operator(OP_MMDBoneToVParent.bl_idname)


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
    pattern: bpy.props.StringProperty(name="模版", default="$BoneMerge \"$$\"") # type: ignore
    
    def execute(self, context: bpy.types.Context):
        copied_num = 0
        result = ''
        selected_bones = get_selected_bones(context)
        for bone in selected_bones:
            if len(result) > 0:
                result += "\n"
            if len(self.pattern) == 0:
                result += bone.name
            else:
                result += self.pattern.replace("$$", bone.name)
            copied_num += 1

        if len(result) > 0:
            context.window_manager.clipboard = result
            self.report({"INFO"}, f"已复制{copied_num}个骨骼的名字")
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


class OP_DecimateBoneChain(bpy.types.Operator):
    bl_idname = "nekotools.decimate_bone_chain"
    bl_label = "精简"
    bl_description = "精简骨骼链"
    bl_options = {'REGISTER', 'UNDO'}

    algorithm:  bpy.props.EnumProperty(
        name="Algorithm", 
        default="2",
        items=[
            ("1", "曲线", ""),
            ("2", "相隔", ""),
            ("3", "边", ""),
        ]
    )
    iterations: bpy.props.IntProperty(name="Iterations", default=1, min=0)
    ratio: bpy.props.FloatProperty(name="曲线比率", default=0.5, min=0.0, max=1.0)

    def _garb_bone_chain_vertices_(self, bone: bpy.types.EditBone, bm: bmesh.types.BMesh):
        bm.verts.new(bone.head)
        for child in bone.children:
            self._garb_bone_chain_vertices_(child, bm)
            break

    def _update_bone_chain(self, bone: bpy.types.EditBone, bm: bmesh.types.BMesh, context: bpy.types.Context = None, deep: int = 0):
        need_remove = False
        if deep >= len(bm.verts):
            need_remove = True
        else:
            bone.use_connect = False
            tail_delta = bone.tail - bone.head
            bone.head = bm.verts[deep].co
            bone.tail = bone.head + tail_delta


        for child in bone.children:
            self._update_bone_chain(child, bm, context, deep=deep+1)

            if need_remove:
                context.active_object.data.edit_bones.remove(bone)
            break

    def _update_bone_chain_tail(self, bone: bpy.types.EditBone):
        for child in bone.children:
            bone.tail = child.head
            self._update_bone_chain_tail(child)
            break
        
    def _get_bone_chain_root_list(self, context: bpy.types.Context) -> list[bpy.types.EditBone]:
        bone_chain_roots: list[bpy.types.EditBone] = []
        for bone in context.selected_editable_bones:
            if bone.parent is None or bone.parent.select is False:
                bone_chain_roots.append(bone)
        return bone_chain_roots

    def execute_1(self, context: bpy.types.Context):

        bone_chain_roots = self._get_bone_chain_root_list(context)

        bone_chain_root_name_list = []
        for bone in bone_chain_roots:
            bone_chain_root_name_list.append(bone.name)
        
        bone_chain_roots.clear()


        points = []
        def _garb_bone_chain_points(bone: bpy.types.EditBone):
            points.append(bone.head)
            for child in bone.children:
                _garb_bone_chain_points(child)
                break

        armature = context.active_object


        for bone_name in bone_chain_root_name_list:
            
            points = []
            _garb_bone_chain_points(armature.data.edit_bones.get(bone_name))

            curve_data = bpy.data.curves.new(f"curves_{bone_name}", type='CURVE')
            curve_data.dimensions = '3D'

            spline = curve_data.splines.new('BEZIER')
            spline.bezier_points.add(len(points)-1)
            

            for i, coord in enumerate(points):
                spline.bezier_points[i].co = coord
                spline.bezier_points[i].handle_left_type = 'AUTO'
                spline.bezier_points[i].handle_right_type = 'AUTO'


            curve_obj = bpy.data.objects.new(curve_data.name, curve_data)
            #curve_obj.update_from_editmode()
            context.collection.objects.link(curve_obj)

           
            bpy.ops.object.mode_set(mode='OBJECT')
            curve_obj.select_set(state=True)
            context.view_layer.objects.active = curve_obj
           

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.curve.select_all(action='SELECT')   
            bpy.ops.curve.decimate(ratio=self.ratio)

            bpy.ops.object.mode_set(mode='OBJECT')
            context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='EDIT')

            spline = curve_obj.data.splines[0]
            def _update_bone_chain_by_spine(bone: bpy.types.EditBone, point_index: int):
                need_remove = False
                
                if len(spline.bezier_points) > 0:
                   print(len(spline.bezier_points))
                   pass
                if point_index >= len(spline.bezier_points):
                    need_remove = True
                elif spline.bezier_points[point_index].co != bone.head:
                    need_remove = True
                else:
                    point_index += 1

                for child in bone.children:
                    if need_remove:
                        child.parent = bone.parent
                    _update_bone_chain_by_spine(child, point_index)
                    break
                if need_remove:
                    armature.data.edit_bones.remove(bone)
                    pass

            bone = armature.data.edit_bones.get(bone_name)
            _update_bone_chain_by_spine(bone, 0)
            self._update_bone_chain_tail(bone)

            context.collection.objects.unlink(curve_obj)
            bpy.data.objects.remove(curve_obj)
            bpy.data.curves.remove(curve_data)
            curve_data = None
            curve_obj = None

        
        return {'FINISHED'}

    def execute_2(self, context: bpy.types.Context):
        bone_chain_roots = self._get_bone_chain_root_list(context)


        need_removes = []
        def _test2(bone: bpy.types.EditBone, need_remove: bool = False):
            for child in bone.children:
                if need_remove:
                    child.parent = bone.parent
                _test2(child, need_remove=not need_remove)
                break

            if need_remove:
                if len(bone.children) == 0:
                    bone.parent.tail = bone.tail
                bone.parent = None
                need_removes.append(bone)


        for i in range(self.iterations):
            for bone in bone_chain_roots:
                _test2(bone, False)

        for bone in bone_chain_roots:
            self._update_bone_chain_tail(bone)

        for bone in need_removes:
            context.active_object.data.edit_bones.remove(bone)


        return {'FINISHED'}

    def execute_3(self, context: bpy.types.Context):

        bone_chain_roots = self._get_bone_chain_root_list(context)

        for bone in bone_chain_roots:
            print(bone.name)
            
            bm: bmesh.types.BMesh = bmesh.new()
            self._garb_bone_chain_vertices_(bone, bm)
            bm.verts.ensure_lookup_table()

            num_vertices = len(bm.verts)
            if num_vertices < 2:
                continue
            for i in range(num_vertices - 1):
                
                bm.edges.new((bm.verts[i], bm.verts[i+1]))

            if self.iterations > 0:
                bmesh.ops.unsubdivide(bm, verts=bm.verts, iterations=self.iterations)
                bm.verts.ensure_lookup_table()

            if False: #test
                mesh_data = bpy.data.meshes.new("test_data")
                bm.to_mesh(mesh_data)
                mesh_obj = bpy.data.objects.new("test", mesh_data)
                bpy.context.collection.objects.link(mesh_obj)
                    

            self._update_bone_chain(bone, bm, context)
            self._update_bone_chain_tail(bone)

            bm.free()
        
        return {'FINISHED'}


    def execute(self, context: bpy.types.Context):
        if self.algorithm == "2":
            return self.execute_2(context)
        elif self.algorithm == "3":
            return self.execute_3(context)
        return self.execute_1(context)


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


def draw_VIEW3D_MT_armature_context_menu(this: bpy.types.Menu, context: bpy.types.Context):
    this.layout.separator()
    this.layout.operator(OP_DecimateBoneChain.bl_idname)
    this.layout.operator(OP_SelectedBonesToClipboard.bl_idname)
    pass

def draw_VIEW3D_MT_edit_armature(this: bpy.types.Menu, _):
    this.layout.separator()
    this.layout.operator(OP_DecimateBoneChain.bl_idname)
    this.layout.operator(OP_SelectedBonesToClipboard.bl_idname)

def draw_VIEW3D_MT_pose(this: bpy.types.Menu, _):
    this.layout.operator(OP_SelectedBonesToClipboard.bl_idname)
    pass

def draw_VIEW3D_MT_pose_context_menu(this: bpy.types.Menu, _):
    this.layout.operator(OP_SelectedBonesToClipboard.bl_idname)
    pass

classes = [
    OP_MergeBones_GetThreshold,
    OP_CollapseMaterialName,
    OP_CopyBodyGroup,
    OP_SeparateByMaterial,
    OP_MergeBonesByDistance,
    OP_MergeToActive,
    OP_MergeArmature,
    OP_VToMMD,
    OP_MMDBoneToVParent,
    OP_DecimateBoneChain,
    VIEW_3D_PT_nekotools,
    OP_SelectBones1,
    OP_SelectedBonesToClipboard,
    OP_SetAllShapeKeyMuteState,
    VIEW3D_MT_select_pose_nekotools,
    MESH_MT_shape_key_context_menu_nekotools,
    OUTLINER_MT_collection_nekotools
]

def register():
    for c in classes:
        bpy.utils.register_class(c)

    scene = bpy.types.Scene
    scene.keep_merged_bones = BoolProperty(
        name='Keep Merged Bones',
        description='',
        default=False
    )
    scene.merge_bones_threshold = FloatProperty(
        name='Threshold',
        description="",
        default=0.00001,
        min=0,
        max=10,
        step=0.0001,
        precision=8,
        subtype='FACTOR'
    )

    bpy.types.VIEW3D_MT_armature_context_menu.append(draw_VIEW3D_MT_armature_context_menu)
    bpy.types.VIEW3D_MT_edit_armature.append(draw_VIEW3D_MT_edit_armature)
    bpy.types.VIEW3D_MT_pose.append(draw_VIEW3D_MT_pose)
    bpy.types.VIEW3D_MT_pose_context_menu.append(draw_VIEW3D_MT_pose_context_menu)


def unregister():
    bpy.types.VIEW3D_MT_armature_context_menu.remove(draw_VIEW3D_MT_armature_context_menu)
    bpy.types.VIEW3D_MT_edit_armature.remove(draw_VIEW3D_MT_edit_armature)
    bpy.types.VIEW3D_MT_pose.remove(draw_VIEW3D_MT_pose)
    bpy.types.VIEW3D_MT_pose_context_menu.remove(draw_VIEW3D_MT_pose_context_menu)

    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()
