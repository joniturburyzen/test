"""
SEGARRO MIXAMO — Combinar animaciones FBX → un único GLB por personaje
=======================================================================
Compatible con Blender 4.x y 5.0 (usa import_scene.fbx, no collada_import)

Ejecutar desde Blender:
    blender --background --python combinar_animaciones.py

Resultado en RECURSOS/:
    protagonista.glb  — mesh + Correr + Saltar + Girar     (~5-10 MB)
    policia.glb       — mesh + PoliCorrer + PoliEnfadado    (~2-3 MB)
    cerdo.glb         — mesh + CerdoCorrer                  (~1 MB)
"""

import bpy
import os

CARPETA = r"C:\Users\jonit\Desktop\SEGARROMIXAMO\RECURSOS"

# ── Fix Blender 5.0: bug en importador FBX ────────────────────────────────────
# Blender 5.0 eliminó CyclesLightSettings.cast_shadow, pero el importer FBX
# aún intenta escribirlo. Lo registramos como propiedad custom para que no falle.
if hasattr(bpy.types, 'CyclesLightSettings') and \
   not hasattr(bpy.types.CyclesLightSettings, 'cast_shadow'):
    bpy.types.CyclesLightSettings.cast_shadow = bpy.props.BoolProperty(
        name="Cast Shadow", default=True
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def limpiar_escena():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for col in [bpy.data.meshes, bpy.data.armatures, bpy.data.actions,
                bpy.data.materials, bpy.data.images, bpy.data.textures]:
        for item in list(col):
            col.remove(item)


def importar_fbx(ruta):
    """Importa un FBX de Mixamo y devuelve los objetos nuevos creados."""
    antes = set(o.name for o in bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=ruta, use_custom_normals=True)
    return [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in antes]


def solo_diffuse():
    """
    En cada material Principled BSDF desconecta todo excepto Base Color.
    Esto elimina normal maps, specular, roughness, etc.
    Solo queda la textura difusa → GLB mucho más ligero.
    """
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        tree = mat.node_tree
        bsdf = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not bsdf:
            continue
        # Desconectar todo excepto Base Color
        links_borrar = [
            lk for lk in tree.links
            if lk.to_node == bsdf and lk.to_socket.name != 'Base Color'
        ]
        for lk in links_borrar:
            tree.links.remove(lk)
        # Eliminar nodos TEX_IMAGE que quedaron sin conectar
        usados = {
            lk.from_node for lk in tree.links
            if lk.to_node == bsdf and lk.to_socket.name == 'Base Color'
        }
        for node in list(tree.nodes):
            if node.type == 'TEX_IMAGE' and node not in usados:
                tree.nodes.remove(node)


def purgar_huerfanos():
    try:
        bpy.ops.outliner.orphans_purge(do_recursive=True)
    except Exception:
        # Fallback para versiones donde el operador cambió
        for blk in [bpy.data.images, bpy.data.textures, bpy.data.materials]:
            for item in list(blk):
                if item.users == 0:
                    blk.remove(item)


def escalar_texturas(max_px=512):
    """Escala todas las imágenes cargadas a max max_px × max_px."""
    for img in bpy.data.images:
        if img.type != 'IMAGE' or img.source == 'GENERATED' or img.size[0] == 0:
            continue
        w, h = img.size
        if w > max_px or h > max_px:
            factor = max_px / max(w, h)
            nw = max(1, int(w * factor))
            nh = max(1, int(h * factor))
            img.scale(nw, nh)
            print(f"     Textura: {w}×{h} → {nw}×{nh}")


def exportar_glb(ruta_glb):
    """Intenta exportar con JPEG, WEBP o sin compresión si los parámetros no existen."""
    base = dict(
        filepath=ruta_glb,
        export_format='GLB',
        export_animations=True,
        export_nla_strips=True,
    )
    for fmt, q in [('JPEG', 70), ('WEBP', 70), (None, None)]:
        try:
            if fmt:
                bpy.ops.export_scene.gltf(**base,
                    export_image_format=fmt,
                    export_jpeg_quality=q)
            else:
                bpy.ops.export_scene.gltf(**base)
            return True
        except TypeError:
            continue
    return False


# ── Motor principal ────────────────────────────────────────────────────────────

def combinar_glb(nombre_salida, fbxs_y_nombres):
    """
    fbxs_y_nombres : [(ruta_fbx, nombre_animacion), ...]
    El PRIMER FBX aporta el mesh base + su animación.
    Los SIGUIENTES solo aportan su animación (mesh duplicado se descarta).
    """
    print(f"\n>>> {nombre_salida}")
    limpiar_escena()
    armature_base = None

    for i, (ruta, nombre_anim) in enumerate(fbxs_y_nombres):
        if not os.path.exists(ruta):
            print(f"  [SKIP] No encontrado: {ruta}")
            continue

        mb = os.path.getsize(ruta) / 1024 / 1024
        print(f"  [{i + 1}] {os.path.basename(ruta)}  ({mb:.0f} MB)")

        nuevos = importar_fbx(ruta)

        # Buscar el armature recién importado
        arm = next((o for o in nuevos if o.type == 'ARMATURE'), None)
        if arm is None:
            print(f"  AVISO: sin armature en {ruta}")
            continue

        # Renombrar la acción activa con el nombre deseado
        accion = None
        if arm.animation_data and arm.animation_data.action:
            accion = arm.animation_data.action
            accion.name = nombre_anim
            print(f"     acción: '{nombre_anim}'  frames {int(accion.frame_range[0])}–{int(accion.frame_range[1])}")

        if i == 0:
            # Primer FBX: este es el base (mesh + armature + animación)
            armature_base = arm
            if accion:
                track = armature_base.animation_data.nla_tracks.new()
                track.name = nombre_anim
                track.strips.new(nombre_anim, int(accion.frame_range[0]), accion)
                armature_base.animation_data.action = None
        else:
            # FBXs adicionales: añadir la animación al armature base y descartar duplicados
            if accion and armature_base:
                if not armature_base.animation_data:
                    armature_base.animation_data_create()
                track = armature_base.animation_data.nla_tracks.new()
                track.name = nombre_anim
                track.strips.new(nombre_anim, int(accion.frame_range[0]), accion)

            for obj in nuevos:
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception:
                    pass

    if armature_base is None:
        print(f"  ERROR: no se pudo construir {nombre_salida}\n")
        return

    # Reducir texturas: solo Diffuse + escalar a 512px + purgar huérfanos
    solo_diffuse()
    escalar_texturas(max_px=512)
    purgar_huerfanos()

    ruta_glb = os.path.join(CARPETA, nombre_salida)
    ok = exportar_glb(ruta_glb)

    if ok and os.path.exists(ruta_glb):
        mb_out = os.path.getsize(ruta_glb) / 1024 / 1024
        print(f"  ✓  {nombre_salida}  →  {mb_out:.1f} MB\n")
    else:
        print(f"  FALLO al exportar {nombre_salida}\n")


# ── Ejecutar ───────────────────────────────────────────────────────────────────

print("\n=== SEGARRO — FBX → GLB (combinando animaciones) ===\n")

# Protagonista: 3 FBX → 1 GLB con 3 clips
combinar_glb("protagonista.glb", [
    (os.path.join(CARPETA, "CORRERPROTAGONISTA.fbx"), "Correr"),
    (os.path.join(CARPETA, "SALTOPROTAGONISTA.fbx"),  "Saltar"),
    (os.path.join(CARPETA, "CAMBIARRECTA.fbx"),       "Girar"),
])

# Policía: 2 FBX → 1 GLB con 2 clips
combinar_glb("policia.glb", [
    (os.path.join(CARPETA, "POLICIACORRER.fbx"),  "PoliCorrer"),
    (os.path.join(CARPETA, "POLICIAENFADO.fbx"),  "PoliEnfadado"),
])

# Cerdo: 1 FBX → 1 GLB
combinar_glb("cerdo.glb", [
    (os.path.join(CARPETA, "CERDOCORRE.fbx"), "CerdoCorrer"),
])

print("=== FIN ===")
