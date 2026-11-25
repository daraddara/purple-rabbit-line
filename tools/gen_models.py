"""
キャラクター3体のモデルを Blockbench 形式と GLB で書き出す.

単一の定義 (characters.py / rabbit_model.py のパーツリスト) から,
同じ名前・同じグループ構成で両形式を生成する.

- assets/a_squirrel.bbmodel / .glb   (リス)
- assets/b_rabbit.bbmodel / .glb     (紫うさぎ)
- assets/c_kid.bbmodel / .glb        (オレンジの子)

.bbmodel: Generic 形式, キューブ要素 (名前・グループ保持),
  色はパレットテクスチャ方式, 座標は x16 (Blockbench の単位)
.glb: ゲーム (pyxel.cube) が読み込む形. ノード名 = パーツ名,
  うさぎは歩行アニメ用の関節グループ (leg_l 等) をノード階層に持つ.
  座標はゲームのモデル単位のまま (x1)

使い方: python tools/gen_models.py
"""
import base64
import io
import json
import math
import os
import sys
import struct
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ASSETS = os.path.join(ROOT, "assets")
sys.path.insert(0, ROOT)

from PIL import Image

import characters
import rabbit_model
from models import MATERIALS, PALETTE_RGB
BB_SCALE = 16.0
TEX = 128                      # パレットテクスチャの一辺
CELL = 32                      # 1色のセル (4x4 = 16色)
DEG = 180.0 / math.pi

# ボックスの面 (models.py と同じ定義)
CORNERS = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
           (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
FACES = [((4, 5, 6, 7), (0, 0, 1)), ((1, 0, 3, 2), (0, 0, -1)),
         ((5, 1, 2, 6), (1, 0, 0)), ((0, 4, 7, 3), (-1, 0, 0)),
         ((7, 6, 2, 3), (0, 1, 0)), ((0, 1, 5, 4), (0, -1, 0))]
BB_FACE_NAMES = ["south", "north", "east", "west", "up", "down"]


# ---------------------------------------------------------------- 共通
def tilt_axis_angle(tilt):
    """単一軸の tilt (rx, ry, rz) -> (軸名, 角度rad). 傾きなしは None."""
    axes = [(abs(a), name, a) for a, name in zip(tilt, "xyz") if a != 0.0]
    if not axes:
        return None
    assert len(axes) == 1, f"複数軸の tilt は未対応: {tilt}"
    _abs, name, ang = axes[0]
    return name, ang


def quat_axis_angle(axis, ang):
    s = math.sin(ang / 2)
    q = {"x": (s, 0.0, 0.0), "y": (0.0, s, 0.0), "z": (0.0, 0.0, s)}[axis]
    return [q[0], q[1], q[2], math.cos(ang / 2)]


def mat_rgb(material, mats):
    return PALETTE_RGB[mats[material][1]]


class Palette:
    """モデルで使うマテリアルを集めたパレットテクスチャ."""

    def __init__(self, material_names, mats):
        self.names = sorted(set(material_names))
        self.index = {m: i for i, m in enumerate(self.names)}
        img = Image.new("RGB", (TEX, TEX), (255, 0, 255))
        px = img.load()
        for m, i in self.index.items():
            cx, cy = (i % 4) * CELL, (i // 4) * CELL
            for yy in range(cy, cy + CELL):
                for xx in range(cx, cx + CELL):
                    px[xx, yy] = mat_rgb(m, mats)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self.png = buf.getvalue()

    def cell_center_px(self, material):
        i = self.index[material]
        return ((i % 4) * CELL + CELL / 2, (i // 4) * CELL + CELL / 2)

    def cell_rect_px(self, material, inset=5):
        i = self.index[material]
        cx, cy = (i % 4) * CELL, (i // 4) * CELL
        return [cx + inset, cy + inset, cx + CELL - inset, cy + CELL - inset]

    def cell_center_uv(self, material):
        cx, cy = self.cell_center_px(material)
        return (cx / TEX, cy / TEX)


# ---------------------------------------------------------------- 配置
class Placed:
    """1パーツの配置情報 (bbmodel 用と glb 用をまとめて持つ)."""

    def __init__(self, name, material, size):
        self.name = name
        self.material = material
        self.size = size
        # bbmodel: 未回転の from/to, 回転中心 origin, 回転 (軸, 角度rad)
        self.bb_from = None
        self.bb_to = None
        self.bb_origin = None
        self.bb_rot = None
        # glb: 親グループ内での平行移動と回転クォータニオン
        self.glb_translation = None
        self.glb_quat = None
        self.group = "body"            # A/C: 所属グループ名
        self.anim = None               # B: 関節グループ名


def _box_ft(center, size):
    lo = [(c - s / 2) * BB_SCALE for c, s in zip(center, size)]
    hi = [(c + s / 2) * BB_SCALE for c, s in zip(center, size)]
    return lo, hi


def place_simple(part, group):
    """A/C 用: center に置き, tilt は自中心回転."""
    p = Placed(part.name, part.material, part.size)
    p.bb_from, p.bb_to = _box_ft(part.center, part.size)
    p.bb_origin = [c * BB_SCALE for c in part.center]
    p.bb_rot = tilt_axis_angle(part.tilt)
    p.glb_translation = list(part.center)
    if p.bb_rot:
        p.glb_quat = quat_axis_angle(*p.bb_rot)
    p.group = group
    return p


def place_rabbit(part):
    """B 用: posed_faces の静止ポーズ (anim=0) と同じ配置にする."""
    p = Placed(part.name, part.material, part.size)
    rot = tilt_axis_angle(part.tilt)
    p.anim = part.anim
    if part.pivot is not None and not part.absolute:
        # 支点まわりに tilt で回る: 未回転の箱は pivot+center の位置
        base = [pv + c for pv, c in zip(part.pivot, part.center)]
        p.bb_from, p.bb_to = _box_ft(base, part.size)
        p.bb_origin = [v * BB_SCALE for v in part.pivot]
        p.bb_rot = rot
        # glb: 関節ノード (原点=pivot) の子. translation は center のまま
        p.glb_translation = list(part.center)
        if rot:
            p.glb_quat = quat_axis_angle(*rot)
    elif part.pivot is not None and part.absolute:
        # 最終位置 center に置き, tilt は自中心回転 (anim は関節側)
        p.bb_from, p.bb_to = _box_ft(part.center, part.size)
        p.bb_origin = [c * BB_SCALE for c in part.center]
        p.bb_rot = rot
        # glb: 関節ノードの子. translation は center - pivot
        p.glb_translation = [c - pv for c, pv in zip(part.center, part.pivot)]
        if rot:
            p.glb_quat = quat_axis_angle(*rot)
    else:
        p.bb_from, p.bb_to = _box_ft(part.center, part.size)
        p.bb_origin = [c * BB_SCALE for c in part.center]
        p.bb_rot = rot
        p.glb_translation = list(part.center)
        if rot:
            p.glb_quat = quat_axis_angle(*rot)
    return p


def group_of(kind, name):
    if kind == "A":
        if name.startswith("ear"):
            return "ears"
        if name.startswith("arm"):
            return "arms"
        if name.startswith("tail"):
            return "tail"
        if name.startswith(("leg", "foot")):
            return "legs"
        return "body"
    if kind == "C":
        if name.startswith("ear"):
            return "ears"
        if name.startswith("arm"):
            return "arms"
        if name.startswith(("strap", "pouch", "mole")):
            return "accessory"
        if name.startswith(("leg", "foot", "boot")):
            return "legs"
        return "body"
    if kind == "D":
        if name.startswith(("eye", "pupil", "beak")):
            return "face"
        if name.startswith("flipper"):
            return "flippers"
        if name.startswith("foot"):
            return "feet"
        if name.startswith("tail"):
            return "tail"
        return "body"
    return "body"


# ---------------------------------------------------------------- bbmodel
def build_bbmodel(model_name, placed, groups_order, palette, nested=None):
    elements = []
    el_uuid = {}
    for p in placed:
        faces = {}
        for fname in BB_FACE_NAMES:
            faces[fname] = {"uv": palette.cell_rect_px(p.material),
                            "texture": 0}
        el = {
            "name": p.name,
            "box_uv": False,
            "rescale": False,
            "locked": False,
            "render_order": "default",
            "allow_mirror_modeling": True,
            "from": [round(v, 3) for v in p.bb_from],
            "to": [round(v, 3) for v in p.bb_to],
            "autouv": 0,
            "color": 0,
            "origin": [round(v, 3) for v in p.bb_origin],
            "faces": faces,
            "uuid": str(uuid.uuid4()),
            "visibility": True,
        }
        if p.bb_rot:
            axis, ang = p.bb_rot
            el["rotation"] = {"angle": round(ang * DEG, 3), "axis": axis,
                              "origin": [round(v, 3) for v in p.bb_origin]}
        elements.append(el)
        el_uuid[p.name] = el["uuid"]

    def group_node(gname, children):
        return {"name": gname, "uuid": str(uuid.uuid4()),
                "origin": [0, 0, 0], "rotation": [0, 0, 0],
                "children": children}

    if nested is not None:
        # B: body グループの中に関節グループを入れ子にする
        body_children = []
        for gname, members in nested:
            if members is None:      # body 直下のパーツ名リスト
                body_children += [el_uuid[n] for n in gname]
            else:
                body_children.append(
                    group_node(gname, [el_uuid[n] for n in members]))
        outliner = [group_node("body", body_children)]
    else:
        outliner = []
        for gname in groups_order:
            members = [el_uuid[p.name] for p in placed if p.group == gname]
            if members:
                outliner.append(group_node(gname, members))

    tex_src = "data:image/png;base64," + base64.b64encode(
        palette.png).decode()
    doc = {
        "meta": {"format_version": "4.10", "model_format": "generic",
                 "box_uv": False},
        "name": model_name,
        "model_identifier": "",
        "parent": "",
        "ambientocclusion": True,
        "front_gui_light": False,
        "visible_box": [1, 1, 1],
        "variable_placeholders": "",
        "variable_placeholder_buttons": [],
        "timeline_setups": [],
        "unhandled_root_fields": {},
        "resolution": {"width": TEX, "height": TEX},
        "elements": elements,
        "outliner": outliner,
        "textures": [{
            "path": "", "name": "palette.png", "folder": "", "namespace": "",
            "id": "0", "group": "", "width": TEX, "height": TEX,
            "uv_width": TEX, "uv_height": TEX, "particle": False,
            "use_override": False, "layers_enabled": False,
            "sync_to_project": "", "render_mode": "default",
            "render_sides": "auto", "frame_time": 1,
            "frame_order_type": "loop", "frame_order": "",
            "frame_interpolate": False, "visible": True, "mode": "bitmap",
            "saved": True, "uuid": str(uuid.uuid4()), "relative_path": "",
            "source": tex_src,
        }],
    }
    return doc


# ---------------------------------------------------------------- glb
class GlbBuilder:
    def __init__(self, palette):
        self.palette = palette
        self.nodes = []
        self.meshes = []
        self.bin = bytearray()
        self.views = []
        self.accessors = []

    def _add_buffer(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        offset = len(self.bin)
        self.bin += data
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target:
            view["target"] = target
        self.views.append(view)
        return len(self.views) - 1

    def _add_accessor(self, view, comp_type, acc_type, count, minmax=None):
        acc = {"bufferView": view, "componentType": comp_type,
               "type": acc_type, "count": count}
        if minmax:
            acc["min"], acc["max"] = minmax
        self.accessors.append(acc)
        return len(self.accessors) - 1

    def add_part_mesh(self, p):
        """パーツの直方体ジオメトリ (原点中心) を mesh として追加."""
        sx, sy, sz = (s / 2 for s in p.size)
        pos, nor, uv, idx = [], [], [], []
        uvc = self.palette.cell_center_uv(p.material)
        for corners, normal in FACES:
            base = len(pos) // 3
            for ci in corners:
                cx, cy, cz = CORNERS[ci]
                pos += [cx * sx, cy * sy, cz * sz]
            nor += list(normal) * 4
            uv += list(uvc) * 4
            idx += [base, base + 1, base + 2, base, base + 2, base + 3]
        mins = [min(pos[i::3]) for i in range(3)]
        maxs = [max(pos[i::3]) for i in range(3)]
        a_pos = self._add_accessor(
            self._add_buffer(struct.pack(f"<{len(pos)}f", *pos), 34962),
            5126, "VEC3", len(pos) // 3, (mins, maxs))
        a_nor = self._add_accessor(
            self._add_buffer(struct.pack(f"<{len(nor)}f", *nor), 34962),
            5126, "VEC3", len(nor) // 3)
        a_uv = self._add_accessor(
            self._add_buffer(struct.pack(f"<{len(uv)}f", *uv), 34962),
            5126, "VEC2", len(uv) // 2)
        a_idx = self._add_accessor(
            self._add_buffer(struct.pack(f"<{len(idx)}I", *idx), 34963),
            5125, "SCALAR", len(idx))
        self.meshes.append({
            "name": p.name,
            "primitives": [{
                "attributes": {"POSITION": a_pos, "NORMAL": a_nor,
                               "TEXCOORD_0": a_uv},
                "indices": a_idx,
                "material": 0,
            }],
        })
        return len(self.meshes) - 1

    def add_node(self, name, translation=None, quat=None, mesh=None,
                 children=None):
        node = {"name": name}
        if translation is not None:
            node["translation"] = [round(v, 5) for v in translation]
        if quat is not None:
            node["rotation"] = [round(v, 6) for v in quat]
        if mesh is not None:
            node["mesh"] = mesh
        if children:
            node["children"] = children
        self.nodes.append(node)
        return len(self.nodes) - 1

    def build(self, root_idx, model_name):
        img_view = self._add_buffer(self.palette.png)
        gltf = {
            "asset": {"version": "2.0",
                      "generator": "pyxel-3d-snake gen_models.py"},
            "scene": 0,
            "scenes": [{"name": model_name, "nodes": [root_idx]}],
            "nodes": self.nodes,
            "meshes": self.meshes,
            "materials": [{
                "name": "palette",
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                },
            }],
            "textures": [{"sampler": 0, "source": 0}],
            "samplers": [{"magFilter": 9728, "minFilter": 9728,
                          "wrapS": 33071, "wrapT": 33071}],
            "images": [{"bufferView": img_view, "mimeType": "image/png",
                        "name": "palette.png"}],
            "buffers": [{"byteLength": len(self.bin)}],
            "bufferViews": self.views,
            "accessors": self.accessors,
        }
        js = json.dumps(gltf, separators=(",", ":")).encode()
        while len(js) % 4:
            js += b" "
        while len(self.bin) % 4:
            self.bin.append(0)
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        out = bytearray()
        out += struct.pack("<III", 0x46546C67, 2, total)
        out += struct.pack("<II", len(js), 0x4E4F534A) + js
        out += struct.pack("<II", len(self.bin), 0x004E4942) + self.bin
        return bytes(out)


def build_glb_simple(model_name, placed, groups_order, palette):
    """A/C: ルート -> グループ -> パーツ の2階層."""
    b = GlbBuilder(palette)
    group_nodes = {}
    for gname in groups_order:
        members = [p for p in placed if p.group == gname]
        if not members:
            continue
        child_idx = []
        for p in members:
            mesh = b.add_part_mesh(p)
            child_idx.append(b.add_node(p.name, p.glb_translation,
                                        p.glb_quat, mesh))
        group_nodes[gname] = b.add_node(gname, children=child_idx)
    root = b.add_node(model_name,
                      children=[group_nodes[g] for g in groups_order
                                if g in group_nodes])
    return b.build(root, model_name)


BODY_ORIGIN = (0.0, 0.5, 0.0)    # うさぎの体全体の傾きの支点


def build_glb_rabbit(model_name, placed, palette):
    """B: ルート -> body (傾き支点) -> [パーツ / 関節グループ -> パーツ]."""
    b = GlbBuilder(palette)
    anim_groups = {}
    body_children = []
    for p in placed:
        mesh = b.add_part_mesh(p)
        if p.anim:
            if p.anim not in anim_groups:
                pv = next(q for q in placed if q.name == p.name)
                anim_groups[p.anim] = (pv, [])
            anim_groups[p.anim][1].append((p, mesh))
        else:
            tr = [c - o for c, o in zip(p.glb_translation, BODY_ORIGIN)]
            body_children.append(b.add_node(p.name, tr, p.glb_quat, mesh))
    # 関節グループの原点 (pivot) はモデルの定義から取る
    pivots = {}
    for part in rabbit_model.build_parts():
        if part.anim and part.pivot is not None:
            pivots[part.anim] = part.pivot
    for anim, (_pv, members) in anim_groups.items():
        child_idx = [b.add_node(p.name, p.glb_translation, p.glb_quat, mesh)
                     for p, mesh in members]
        tr = [c - o for c, o in zip(pivots[anim], BODY_ORIGIN)]
        body_children.append(b.add_node(anim, tr, children=child_idx))
    body = b.add_node("body", list(BODY_ORIGIN), children=body_children)
    root = b.add_node(model_name, children=[body])
    return b.build(root, model_name)


# ---------------------------------------------------------------- main
def main():
    os.makedirs(ASSETS, exist_ok=True)

    jobs = []
    for kind, fname in (("A", "a_squirrel"), ("C", "c_kid")):
        parts = characters.food_parts(kind)
        placed = [place_simple(p, group_of(kind, p.name)) for p in parts]
        mats = {p.material for p in parts}
        palette = Palette(mats, MATERIALS)
        order = ["body", "head", "ears", "arms", "legs", "tail", "accessory"]
        jobs.append((fname, placed, order, palette, None))

    parts = characters.penguin_parts()
    placed = [place_simple(p, group_of("D", p.name)) for p in parts]
    palette = Palette({p.material for p in parts}, MATERIALS)
    order = ["body", "face", "flippers", "feet", "tail"]
    jobs.append(("d_penguin", placed, order, palette, None))

    parts = rabbit_model.build_parts()
    placed = [place_rabbit(p) for p in parts]
    palette = Palette({p.material for p in parts}, rabbit_model.MATERIALS)
    anim_order = ["leg_l", "leg_r", "arm_l", "arm_r", "ear_l", "ear_r"]
    nested = []
    direct = [p.name for p in placed if not p.anim]
    nested.append((direct, None))
    for anim in anim_order:
        members = [p.name for p in placed if p.anim == anim]
        if members:
            nested.append((anim, members))
    jobs.append(("b_rabbit", placed, None, palette, nested))

    for fname, placed, order, palette, nested in jobs:
        doc = build_bbmodel(fname, placed,
                            order or [], palette, nested)
        bb_path = os.path.join(ASSETS, fname + ".bbmodel")
        with open(bb_path, "w") as f:
            json.dump(doc, f)
        if fname == "b_rabbit":
            glb = build_glb_rabbit(fname, placed, palette)
        else:
            glb = build_glb_simple(fname, placed, order, palette)
        glb_path = os.path.join(ASSETS, fname + ".glb")
        with open(glb_path, "wb") as f:
            f.write(glb)
        print(f"{fname}: bbmodel {os.path.getsize(bb_path)} bytes / "
              f"glb {len(glb)} bytes / parts {len(placed)}")


if __name__ == "__main__":
    main()
