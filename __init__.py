import bpy
from bpy.props import BoolProperty, FloatProperty
from bpy.app.handlers import persistent

from . import NekoTools


bl_info = {
    "name": "NekoTools🐾",
    "blender": (4, 0, 0),
    "version": (2, 1),
    'location': 'View 3D > Tool Shelf',
    'category': '3D View',
    "author": "Starfelll",
    "url": "https://steamcommunity.com/profiles/76561198859761739"
}


def msgbus_callback(scene):
    print("骨骼状态改变")

@persistent
def subscribe_msgbus(*args):
    print("subscribe_msgbus")

    bpy.msgbus.subscribe_rna(
        key=(bpy.types.NodeTree, "nodes"),
        args=(),
        notify=msgbus_callback,
        options={"PERSISTENT",}
    )

def register():
    for c in NekoTools.class_list:
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

    subscribe_msgbus()
    #bpy.app.handlers.load_post.append(subscribe_msgbus)
    #bpy.app.handlers.depsgraph_update_post.append(msgbus_callback)
    

def unregister():
    #bpy.app.handlers.load_post.remove(subscribe_msgbus)
    #bpy.app.handlers.depsgraph_update_post.remove(msgbus_callback)
    for c in reversed(NekoTools.class_list):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()
