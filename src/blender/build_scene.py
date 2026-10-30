"""Construye la escena rosas3d en Blender (probado en 5.1, headless):
ramo de rosas neon + tallos + anillo con espinas + camara + turntable 240 frames.

  blender -b --python build_scene.py -- --save                    # solo crea assets/blender/rosas.blend
  blender -b --python build_scene.py -- --frame 1 [--out ruta]    # render de un frame
  blender -b --python build_scene.py -- --all                     # assets/render/frame_0001..0240.png
Camara y centro se leen de assets/camera.json (fuente unica compartida con las particulas).
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
N, FPS, W, H = 240, 30, 1920, 1080
NEON, LIGHT, PEACH, WHITE = "#FF3D8B", "#FFB3D1", "#FFD2A8", "#FFE6F0"
rng = np.random.default_rng(11)

def rgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [(x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, 1.0)

# ------------------------------------------------------------ materiales
def emission_material(name, base, rim, wire_strength, strength, peach_mix=True):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.35
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = rgb(base)
    ramp.color_ramp.elements[1].color = rgb(rim)
    nt.links.new(lw.outputs["Facing"], ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    if peach_mix:
        at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "inner"
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"
        mx.inputs["B"].default_value = rgb(PEACH)
        mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 0.7
        nt.links.new(at.outputs["Fac"], mul.inputs[0])
        nt.links.new(mul.outputs[0], mx.inputs["Factor"])
        nt.links.new(col, mx.inputs["A"])
        col = mx.outputs["Result"]
    e1 = nt.nodes.new("ShaderNodeEmission"); e1.inputs["Strength"].default_value = strength
    nt.links.new(col, e1.inputs["Color"])
    wf = nt.nodes.new("ShaderNodeWireframe"); wf.use_pixel_size = True; wf.inputs["Size"].default_value = 1.1
    e2 = nt.nodes.new("ShaderNodeEmission"); e2.inputs["Strength"].default_value = wire_strength
    e2.inputs["Color"].default_value = rgb(WHITE)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(wf.outputs["Fac"], mix.inputs["Fac"])
    nt.links.new(e1.outputs["Emission"], mix.inputs[1])
    nt.links.new(e2.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return m

def flat_emission(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = rgb(color); e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs["Emission"], out.inputs["Surface"])
    return m

# ------------------------------------------------------------ rosa
def build_rose(name, scale=1.0, layers=5):
    bm = bmesh.new()
    inner_l = bm.verts.layers.float.new("inner")
    nu, nv = 4, 5
    for i in range(layers):
        n_pet = 3 + 2 * i
        r0, w, l = 0.015 + 0.03 * i, 0.05 + 0.032 * i, 0.07 + 0.042 * i
        tilt, curl = 0.04 + 0.13 * i, 0.12 + 0.22 * i
        cup = 0.22 + 0.05 * i
        off = rng.uniform(0, 6.28)
        for k in range(n_pet):
            phi = off + 2 * math.pi * k / n_pet + rng.normal(0, 0.12)
            tl = tilt + rng.normal(0, 0.05)
            grid = []
            pr, pz = 0.0, 0.0
            for j in range(nv + 1):
                v = j / nv
                th = tl + curl * v ** 1.6
                if j:
                    pr += l / nv * math.sin(th); pz += l / nv * math.cos(th)
                wp = math.sin(math.pi * (0.18 + 0.82 * v)) ** 0.55
                row = []
                for q in range(-nu, nu + 1):
                    u = q / nu
                    x = r0 + pr + cup * u * u * w * 0.8
                    y = u * w * wp
                    z = pz - 0.35 * w * u * u * (1 - v)
                    vert = bm.verts.new((x * math.cos(phi) - y * math.sin(phi),
                                         x * math.sin(phi) + y * math.cos(phi), z * 1.0))
                    vert[inner_l] = 1 - i / max(layers - 1, 1)
                    row.append(vert)
                grid.append(row)
            for j in range(nv):
                for q in range(2 * nu):
                    bm.faces.new((grid[j][q], grid[j][q + 1], grid[j + 1][q + 1], grid[j + 1][q]))
    bm.verts.ensure_lookup_table()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.scale = (scale,) * 3
    return ob

# ------------------------------------------------------------ escena
def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.cameras, bpy.data.lights):
        for b in list(blk):
            blk.remove(b)

def build():
    clear()
    cfg = json.loads((ASSETS / "camera.json").read_text())
    center = Vector(cfg["bouquet_center"])
    coll = bpy.context.scene.collection
    pivot = bpy.data.objects.new("Bouquet", None)
    coll.objects.link(pivot)
    drv = pivot.driver_add("rotation_euler", 2).driver       # turntable: 360 deg en 240 frames
    drv.type = "SCRIPTED"; drv.expression = f"(frame - 1) / {N} * 2 * pi"

    rose_mat = emission_material("RoseNeon", NEON, LIGHT, 1.8, 1.0)
    stem_mat = flat_emission("Stem", LIGHT, 0.8)
    ring_mat = flat_emission("Ring", NEON, 2.6)
    thorn_mat = flat_emission("Thorn", LIGHT, 3.0)

    # 9 rosas: una central + dos anillos
    spec = [((0, 0, 1.85), (0, 0, 1), 1.3)]
    for a in np.linspace(0, 2 * np.pi, 5, endpoint=False) + 0.3:
        spec.append(((0.55 * math.cos(a), 0.55 * math.sin(a), 1.55 + rng.uniform(-0.1, 0.1)),
                     (0.55 * math.cos(a), 0.55 * math.sin(a), 1.0), 1.1))
    for a in np.linspace(0, 2 * np.pi, 3, endpoint=False) + 0.9:
        spec.append(((0.95 * math.cos(a), 0.95 * math.sin(a), 1.2 + rng.uniform(-0.05, 0.1)),
                     (0.9 * math.cos(a), 0.9 * math.sin(a), 0.7), 1.0))
    bottom = Vector((0, 0, -0.25))
    for i, (pos, dirn, sc) in enumerate(spec):
        rose = build_rose(f"Rose{i}", sc)
        rose.data.materials.append(rose_mat)
        d = Vector(dirn).normalized()
        rose.rotation_mode = "QUATERNION"
        rose.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
        rose.location = pos
        rose.parent = pivot
        coll.objects.link(rose)
        base = Vector(pos) - d * 0.05
        cu = bpy.data.curves.new(f"Stem{i}", "CURVE"); cu.dimensions = "3D"
        cu.bevel_depth = 0.014; cu.bevel_resolution = 3
        sp = cu.splines.new("BEZIER"); sp.bezier_points.add(2)
        pts = [base, base.lerp(bottom, 0.5) + Vector((0, 0, 0.1)), bottom]
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = p; bp.handle_left_type = bp.handle_right_type = "AUTO"
        so = bpy.data.objects.new(f"Stem{i}", cu)
        so.data.materials.append(stem_mat); so.parent = pivot
        coll.objects.link(so)

    # anillo elipse inclinado 20 deg con espinas
    a_, b_ = 1.35, 0.85
    cu = bpy.data.curves.new("Ring", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.014; cu.bevel_resolution = 3
    sp = cu.splines.new("POLY"); n_pts = 120; sp.points.add(n_pts - 1); sp.use_cyclic_u = True
    for k, p in enumerate(sp.points):
        t = 2 * math.pi * k / n_pts
        p.co = (a_ * math.cos(t), b_ * math.sin(t), 0, 1)
    ring = bpy.data.objects.new("Ring", cu)
    ring.data.materials.append(ring_mat)
    thorn_bm = bmesh.new()
    for k in range(56):
        t = 2 * math.pi * (k + rng.uniform(-0.2, 0.2)) / 56
        p = Vector((a_ * math.cos(t), b_ * math.sin(t), 0))
        nrm = Vector((b_ * math.cos(t), a_ * math.sin(t), 0)).normalized()
        nrm = (nrm + Vector((0, 0, 0.9 * (1 if k % 2 else -1)))).normalized()
        mat = Matrix.Translation(p) @ nrm.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Translation((0, 0, 0.04))
        bmesh.ops.create_cone(thorn_bm, cap_ends=True, segments=5, radius1=0.018, radius2=0.0, depth=0.08, matrix=mat)
    tm = bpy.data.meshes.new("Thorns"); thorn_bm.to_mesh(tm); thorn_bm.free()
    thorns = bpy.data.objects.new("Thorns", tm); thorns.data.materials.append(thorn_mat)
    for o in (ring, thorns):
        o.location = center - Vector((0, 0, 0.1)); o.rotation_euler = (math.radians(20), 0, 0)
        o.parent = pivot; coll.objects.link(o)

    # camara (hFOV de camera.json)
    cam_d = bpy.data.cameras.new("Cam"); cam_d.sensor_fit = "HORIZONTAL"; cam_d.angle = math.radians(cfg["hfov_deg"])
    cam = bpy.data.objects.new("Cam", cam_d)
    cam.location = cfg["position"]
    cam.rotation_euler = (Vector(cfg["target"]) - Vector(cfg["position"])).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(cam)

    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, N
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "8"
    sc.view_settings.view_transform = "Standard"
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng; break
        except TypeError:
            pass
    sc.world = bpy.data.worlds.new("W"); sc.world.color = (0, 0, 0)
    bpy.ops.wm.save_as_mainfile(filepath=str(ASSETS / "blender" / "rosas.blend"))

def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    build()
    sc = bpy.context.scene
    if "--frame" in args:
        f = int(args[args.index("--frame") + 1])
        sc.frame_set(f)
        sc.render.filepath = args[args.index("--out") + 1] if "--out" in args else str(ASSETS / "render" / f"frame_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    elif "--all" in args:
        sc.render.filepath = str(ASSETS / "render" / "frame_")
        bpy.ops.render.render(animation=True)

main()
