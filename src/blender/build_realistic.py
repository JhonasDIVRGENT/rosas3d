"""Ramo realista para la web: rosa escaneada (assets/models/pink-rose) x9 + tallos + hojas + lazo.
Materiales PBR (color, normal, oclusion, sheen) que el exportador glTF entiende, y GLB con Draco.

  blender -b --python src/blender/build_realistic.py -- --export             # web/models/rosas.glb
  blender -b --python src/blender/build_realistic.py -- --preview out.png    # render de control (EEVEE)
Siempre guarda assets/blender/rosas_realista.blend. Las rosas comparten una sola malla
(duplicados enlazados), asi el GLB guarda la geometria una vez.
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
ROSE_DIR = ASSETS / "models" / "pink-rose"
ROSE_OBJ = ROSE_DIR / "source" / "obj" / "Pink_rose_retopo_SF.obj"
TEX_WEB = ROSE_DIR / "web_tex"                  # texturas reducidas para la web (cache)
GLB = ROOT / "web" / "models" / "rosas.glb"
DECIMATE = 0.45                                 # ~110k -> ~50k triangulos por rosa
rng = np.random.default_rng(7)

# ------------------------------------------------------------ utilidades
def ctx_override():
    wm = bpy.context.window_manager
    if wm.windows:
        win = wm.windows[0]
        area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
        return bpy.context.temp_override(window=win, area=area) if area else bpy.context.temp_override(window=win)
    return bpy.context.temp_override()

def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.cameras,
                bpy.data.lights, bpy.data.images, bpy.data.node_groups):
        for b in list(blk):
            blk.remove(b)

def web_texture(src_name, size, non_color=False, saturation=1.0, gain=1.0):
    """Carga la textura reducida (la crea la primera vez a partir del original).
    saturation/gain se hornean en el JPEG: el glTF no lleva nodos de correccion de color."""
    TEX_WEB.mkdir(exist_ok=True)
    tag = f"_s{saturation:g}" if saturation != 1.0 or gain != 1.0 else ""
    dst = TEX_WEB / (Path(src_name).stem.replace(" ", "_") + f"_{size}{tag}.jpg")
    if not dst.exists():
        img = bpy.data.images.load(str(ROSE_DIR / "source" / "obj" / src_name))
        img.scale(size, size)
        if tag:
            px = np.empty(size * size * 4, np.float32)
            img.pixels.foreach_get(px)
            px = px.reshape(-1, 4)
            lum = px[:, :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
            px[:, :3] = np.clip((lum[:, None] + (px[:, :3] - lum[:, None]) * saturation) * gain, 0, 1)
            img.pixels.foreach_set(px.ravel())
        img.filepath_raw = str(dst)
        img.file_format = "JPEG"
        img.save()
        bpy.data.images.remove(img)
    img = bpy.data.images.load(str(dst))
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img

def node_of(nt, kind):
    """Nodo por tipo (los nombres cambian con el idioma de la interfaz)."""
    return next(n for n in nt.nodes if n.type == kind)

def principled(name, color, rough, sheen=0.0, sheen_tint=(1, 1, 1, 1), sss=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = node_of(m.node_tree, "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Sheen Tint"].default_value = sheen_tint
    b.inputs["Subsurface Weight"].default_value = sss
    return m

def gltf_output_group():
    """Grupo 'glTF Material Output': el exportador lee de aqui la textura de oclusion."""
    g = bpy.data.node_groups.get("glTF Material Output")
    if g is None:
        g = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return g

# ------------------------------------------------------------ materiales
def rose_material():
    m = bpy.data.materials.new("RosePetal")
    m.use_nodes = True
    nt = m.node_tree
    b = node_of(nt, "BSDF_PRINCIPLED")
    col = nt.nodes.new("ShaderNodeTexImage"); col.image = web_texture("Pink_rose_retopo.jpg", 2048, saturation=1.6, gain=0.92)
    nrm = nt.nodes.new("ShaderNodeTexImage"); nrm.image = web_texture("Pink_rose_retopo_normal.jpg", 2048, True)
    ao = nt.nodes.new("ShaderNodeTexImage"); ao.image = web_texture("Pink_rose_retopo_occlusion.jpg", 1024, True)
    nmap = nt.nodes.new("ShaderNodeNormalMap"); nmap.inputs["Strength"].default_value = 1.0
    nt.links.new(col.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(nrm.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], b.inputs["Normal"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    grp = nt.nodes.new("ShaderNodeGroup"); grp.node_tree = gltf_output_group()
    nt.links.new(ao.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
    # petalo: mate aterciopelado con brillo suave en los bordes y algo de translucidez (SSS solo en Blender)
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Specular IOR Level"].default_value = 0.35
    b.inputs["Sheen Weight"].default_value = 0.6
    b.inputs["Sheen Roughness"].default_value = 0.45
    b.inputs["Sheen Tint"].default_value = (1.0, 0.78, 0.84, 1)
    b.inputs["Subsurface Weight"].default_value = 0.25
    b.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.3)
    b.inputs["Subsurface Scale"].default_value = 0.02
    return m

# ------------------------------------------------------------ geometria
def import_rose():
    with ctx_override():
        bpy.ops.wm.obj_import(filepath=str(ROSE_OBJ))
    src = [o for o in bpy.data.objects if o.type == "MESH"][0]
    dec = src.modifiers.new("Decimate", "DECIMATE"); dec.ratio = DECIMATE
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(src.evaluated_get(dg))
    me.name = "RoseMesh"
    bpy.data.objects.remove(src, do_unlink=True)
    # OBJ importado viene rotado 90 deg en X; lo horneamos para que la malla ya este en Z arriba
    me.transform(Matrix.Rotation(math.pi / 2, 4, "X"))
    zmin = min(v.co.z for v in me.vertices)
    cx = sum(v.co.x for v in me.vertices) / len(me.vertices)
    cy = sum(v.co.y for v in me.vertices) / len(me.vertices)
    me.transform(Matrix.Translation((-cx, -cy, -zmin)))    # origen = base del tallito
    me.materials.clear()
    me.materials.append(rose_material())
    for p in me.polygons:
        p.use_smooth = True
    return me

def leaf_mesh():
    bm = bmesh.new()
    nu, nv, L, w = 12, 6, 0.32, 0.11
    grid = []
    for i in range(nu + 1):
        u = i / nu
        width = w * math.sin(math.pi * min(u * 1.15, 1.0)) ** 0.8 * (1 - 0.25 * u)
        row = []
        for j in range(nv + 1):
            v = 2 * j / nv - 1
            x = u * L
            y = v * width
            z = 0.35 * abs(v) * width - 0.12 * u * u       # pliegue en el nervio + caida de la punta
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
    me = bpy.data.meshes.new("LeafMesh")
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me

def curve_to_mesh(cu_obj, name):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cu_obj.evaluated_get(dg))
    me.name = name
    bpy.data.objects.remove(cu_obj, do_unlink=True)
    return me

# ------------------------------------------------------------ escena
def build():
    clear()
    coll = bpy.context.scene.collection
    pivot = bpy.data.objects.new("Bouquet", None)
    coll.objects.link(pivot)

    rose_me = import_rose()
    stem_mat = principled("Stem", (0.045, 0.16, 0.035), 0.5, sheen=0.15)
    leaf_mat = principled("Leaf", (0.035, 0.14, 0.03), 0.42, sheen=0.3, sheen_tint=(0.7, 1, 0.7, 1))
    leaf_mat.use_backface_culling = False
    ribbon_mat = principled("Ribbon", (0.55, 0.02, 0.12), 0.28, sheen=0.8, sheen_tint=(1, 0.6, 0.7, 1))
    ribbon_mat.use_backface_culling = False

    # 9 rosas: una central + dos anillos (misma disposicion que la escena neon)
    # escalas grandes para que las cabezas se toquen y se lea como un ramo apretado
    spec = [((0, 0, 1.55), (0, 0, 1), 0.78)]
    for a in np.linspace(0, 2 * np.pi, 5, endpoint=False) + 0.3:
        spec.append(((0.42 * math.cos(a), 0.42 * math.sin(a), 1.32 + rng.uniform(-0.05, 0.05)),
                     (0.55 * math.cos(a), 0.55 * math.sin(a), 1.0), 0.68))
    for a in np.linspace(0, 2 * np.pi, 3, endpoint=False) + 0.9:
        spec.append(((0.78 * math.cos(a), 0.78 * math.sin(a), 1.08 + rng.uniform(-0.04, 0.05)),
                     (0.9 * math.cos(a), 0.9 * math.sin(a), 0.7), 0.6))

    tie = Vector((0, 0, 0.45))
    stems = bpy.data.curves.new("Stems", "CURVE"); stems.dimensions = "3D"
    stems.bevel_depth = 0.017; stems.bevel_resolution = 2; stems.resolution_u = 10
    for i, (pos, dirn, sc) in enumerate(spec):
        d = Vector(dirn).normalized()
        spin = Quaternion((0, 0, 1), rng.uniform(0, 2 * math.pi))
        r = bpy.data.objects.new(f"Rose{i}", rose_me)
        r.rotation_mode = "QUATERNION"
        r.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d) @ spin
        r.location = pos
        r.scale = (sc,) * 3
        r.parent = pivot
        coll.objects.link(r)
        # tallo: de la base de la rosa al lazo y luego casi paralelo hacia abajo
        off = Vector((pos[0], pos[1], 0)) * 0.08
        pts = [Vector(pos) + d * 0.01, Vector(pos).lerp(tie, 0.5) + off * 2, tie + off, tie + off * 1.6 + Vector((0, 0, -0.75))]
        sp = stems.splines.new("BEZIER"); sp.bezier_points.add(len(pts) - 1)
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = p; bp.handle_left_type = bp.handle_right_type = "AUTO"
    so = bpy.data.objects.new("StemsTmp", stems); coll.objects.link(so)
    stem_me = curve_to_mesh(so, "StemsMesh"); stem_me.materials.append(stem_mat)
    st = bpy.data.objects.new("Stems", stem_me); st.parent = pivot; coll.objects.link(st)

    # hojas alrededor de las cabezas, mirando hacia afuera y un poco hacia abajo
    leaf_me = leaf_mesh(); leaf_me.materials.append(leaf_mat)
    for k in range(24):
        a = 2 * math.pi * k / 24 + rng.uniform(-0.12, 0.12)
        rad = rng.uniform(0.3, 0.85)
        z = 1.12 - rad * 0.4 + rng.uniform(-0.08, 0.04)
        tilt = math.radians(rng.uniform(15, 45))
        out = Vector((math.cos(a), math.sin(a), -math.tan(tilt))).normalized()
        q = out.to_track_quat("X", "Z") @ Quaternion((1, 0, 0), rng.uniform(-0.4, 0.4))
        lf = bpy.data.objects.new(f"Leaf{k}", leaf_me)
        lf.rotation_mode = "QUATERNION"; lf.rotation_quaternion = q
        lf.location = (rad * 0.7 * math.cos(a), rad * 0.7 * math.sin(a), z)
        lf.scale = (rng.uniform(0.85, 1.2),) * 3
        lf.parent = pivot; coll.objects.link(lf)

    # lazo de satin en el punto de amarre
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=40, radius1=0.09, radius2=0.085, depth=0.13,
                          matrix=Matrix.Translation(tie))
    # dos cintas que caen del nudo (frente al espectador, -Y) con una ondulacion suave
    for side in (-1, 1):
        rows = []
        for i in range(13):
            t = i / 12
            c = tie + Vector((side * (0.02 + 0.13 * t), -0.095 - 0.03 * math.sin(t * 3), -0.02 - 0.42 * t))
            half = 0.032 * (1 - 0.3 * t)
            tw = side * 0.6 * math.sin(t * 2.5)                  # giro de la cinta
            dx = Vector((math.cos(tw), 0, math.sin(tw))) * half
            rows.append((bm.verts.new(c - dx), bm.verts.new(c + dx)))
        for (a0, b0), (a1, b1) in zip(rows, rows[1:]):
            bm.faces.new((a0, b0, b1, a1))
    rib_me = bpy.data.meshes.new("RibbonMesh"); bm.to_mesh(rib_me); bm.free()
    for p in rib_me.polygons:
        p.use_smooth = True
    rib_me.materials.append(ribbon_mat)
    rib = bpy.data.objects.new("Ribbon", rib_me); rib.parent = pivot; coll.objects.link(rib)

    setup_preview_scene()
    bpy.ops.wm.save_as_mainfile(filepath=str(ASSETS / "blender" / "rosas_realista.blend"))
    return pivot

def setup_preview_scene():
    """Camara y luces solo para ver el ramo en Blender (la web pone las suyas)."""
    sc = bpy.context.scene
    coll = sc.collection
    cfg = json.loads((ASSETS / "camera.json").read_text())
    cam_d = bpy.data.cameras.new("Cam"); cam_d.sensor_fit = "HORIZONTAL"; cam_d.angle = math.radians(cfg["hfov_deg"])
    cam = bpy.data.objects.new("Cam", cam_d)
    cam.location = cfg["position"]
    cam.rotation_euler = (Vector((0, 0, 1.15)) - Vector(cfg["position"])).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(cam); sc.camera = cam
    for name, loc, power, color, size in (("Key", (3, -4, 4.5), 900, (1.0, 0.93, 0.85), 2.5),
                                          ("Rim", (-2.5, 3.5, 3.2), 700, (1.0, 0.55, 0.7), 2.0),
                                          ("Fill", (-4, -3, 1.2), 200, (0.8, 0.85, 1.0), 3.0)):
        ld = bpy.data.lights.new(name, "AREA"); ld.energy = power; ld.color = color; ld.size = size
        lo = bpy.data.objects.new(name, ld); lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 1.2)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        coll.objects.link(lo)
    w = bpy.data.worlds.new("Night"); w.use_nodes = True
    node_of(w.node_tree, "BACKGROUND").inputs["Color"].default_value = (0.012, 0.006, 0.012, 1)
    sc.world = w
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.view_settings.view_transform = "AgX"

def export_glb(pivot):
    GLB.parent.mkdir(parents=True, exist_ok=True)
    for o in bpy.context.scene.objects:
        o.select_set(o == pivot or o.parent == pivot)
    with ctx_override():
        bpy.ops.export_scene.gltf(
            filepath=str(GLB), export_format="GLB", use_selection=True,
            export_apply=True, export_yup=True, export_cameras=False, export_lights=False,
            export_image_format="AUTO",
            export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
            export_draco_position_quantization=14, export_draco_normal_quantization=10,
            export_draco_texcoord_quantization=12)

def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    pivot = build()
    if "--export" in args:
        export_glb(pivot)
    if "--preview" in args:
        sc = bpy.context.scene
        sc.render.filepath = args[args.index("--preview") + 1]
        bpy.ops.render.render(write_still=True)

main()
