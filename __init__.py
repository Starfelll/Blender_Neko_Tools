import bpy
from bpy.props import BoolProperty, FloatProperty

from . import NekoTools


bl_info = {
    "name": "NekoTools🐾",
    "blender": (4, 0, 0),
    "version": (2, 2),
    'location': 'View 3D > Tool Shelf',
    'category': '3D View',
    "author": "Starfelll",
    "url": "https://steamcommunity.com/profiles/76561198859761739"
}

def register():
    for c in NekoTools.classes:
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

    

def unregister():
    for c in reversed(NekoTools.classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()
