"""
3Dモデルの共通基盤 (直方体パーツ・面生成・パレット).

キャラクター本体は characters.py (リス / オレンジの子) と
rabbit_model.py (紫うさぎ, 別プロジェクトから流用) にある.
ここは両者が使う Part 定義とワールド変換, 色パレットを置く.

ローカル座標系 (characters.py のパーツ): x=右, y=上, z=後ろ (正面は -Z).
rabbit_model.py は正面が +Z の別規約なので, 変換は characters.py 側で行う.
"""
import math
from dataclasses import dataclass

# マテリアル名 -> (暗, 中, 明) Pyxelカラー番号
# リスとオレンジの子は色がほぼ同じオレンジ (#F08D4C / #F0871C)
# なので, 色は別スロットに正確に入れた上で, 形の特徴でも分ける
# (characters.py 参照).
MATERIALS = {
    "squirrel": (4, 9, 15),      # リス: 暗 #C96A2B / 中 #F08D4C / 明(クリーム寄り)
    "kid": (8, 14, 14),          # オレンジの子: 暗 #D96F0E / 中 #F0871C
    "pink": (3, 3, 3),           # Cの耳の内側・モグラの鼻 #F4BECE
    "mole": (5, 4, 4),           # モグラ (茶)
    "red": (13, 13, 13),         # Cの鼻 #E5383B
    "white": (6, 7, 7),          # Aの目の白
    "belly": (9, 15, 15),        # Aのお腹: 体のオレンジに近い暖クリーム
    "black": (0, 0, 0),          # Aのライン/目鼻口, Cのストラップ/ポシェット/ブーツ
    "wall": (5, 6, 7),           # 壁 (石色)
}

# main.py が pyxel.colors に設定するカスタム色と, preview.py の
# PILパレットは, この表で一致させる
PALETTE_RGB = {
    0: (0, 0, 0), 1: (0x87, 0xCE, 0xEB), 2: (0x73, 0x26, 0xC7),
    3: (0xF4, 0xBE, 0xCE), 4: (0xC9, 0x6A, 0x2B), 5: (0x5F, 0x57, 0x4F),
    6: (0xC2, 0xC3, 0xC7), 7: (0xFF, 0xF1, 0xE8), 8: (0x80, 0xC2, 0x41),
    9: (0xF0, 0x8D, 0x4C), 10: (0xD9, 0xBE, 0x7A), 11: (0x9F, 0x40, 0xF4),
    12: (0xBC, 0x7F, 0xFF), 13: (0xE5, 0x38, 0x3B), 14: (0xF0, 0x87, 0x1C),
    15: (0xF5, 0xC7, 0x7E),
}
CUSTOM_COLORS = {1: 0x87CEEB, 2: 0x7326C7, 3: 0xF4BECE, 4: 0xC96A2B,
                 8: 0x80C241, 9: 0xF08D4C, 11: 0x9F40F4, 12: 0xBC7FFF,
                 13: 0xE5383B, 14: 0xF0871C, 15: 0xF5C77E}
# ※ 10 (砂・暗) は Pyxel 既定に近い値のまま使う. 15 は地面の明色と
# リスのお腹を兼ねるため, 暖かいクリーム #F5C77E に寄せている
# ※ 8 は Cube 版ではオレンジの子の暗色 (MATERIALS の [0]) として
# しか使われていないため, 緑 #80C241 に転用している

# 地面チェッカーの色 (直接指定)
GROUND_COLORS = (8, 7)           # 緑 (#80C241) と白


@dataclass
class Part:
    name: str
    material: str
    size: tuple                  # (sx, sy, sz)
    center: tuple = (0.0, 0.0, 0.0)
    tilt: tuple = (0.0, 0.0, 0.0)  # 自中心まわりの傾き (rx, ry, rz)


# ---------- 直方体の面 ----------
_CORNERS = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
FACES = [
    ((4, 5, 6, 7), (0, 0, 1)),
    ((1, 0, 3, 2), (0, 0, -1)),
    ((5, 1, 2, 6), (1, 0, 0)),
    ((0, 4, 7, 3), (-1, 0, 0)),
    ((7, 6, 2, 3), (0, 1, 0)),
    ((0, 1, 5, 4), (0, -1, 0)),
]


def _rot(v, rx, ry, rz):
    x, y, z = v
    if rx:
        c, s = math.cos(rx), math.sin(rx)
        y, z = y * c - z * s, y * s + z * c
    if ry:
        c, s = math.cos(ry), math.sin(ry)
        x, z = x * c + z * s, -x * s + z * c
    if rz:
        c, s = math.cos(rz), math.sin(rz)
        x, y = x * c - y * s, x * s + y * c
    return (x, y, z)


def _yaw_transform(v, yaw):
    """ローカル (正面=-Z) -> ワールド (正面=forward(yaw)) への回転.
    ローカル +X はワールドの右手, ローカル +Z は後方 (-forward)."""
    fx, fz = math.sin(yaw), -math.cos(yaw)     # forward
    rx, rz = -fz, fx                            # 右手ベクトル
    x, y, z = v
    return (rx * x - fx * z, y, rz * x - fz * z)


def faces_for_parts(parts, pos, yaw=0.0):
    """
    パーツ群をワールド座標へ置いた全フェイスを返す.
    pos: (x, y, z) ワールド位置. 戻り値:
    [(world_vertices[4], normal, material, part_name), ...]
    """
    out = []
    px, py, pz = pos
    for p in parts:
        local = [(c[0] * p.size[0] / 2, c[1] * p.size[1] / 2, c[2] * p.size[2] / 2)
                 for c in _CORNERS]
        verts = []
        for v in local:
            r = _rot(v, *p.tilt)
            w = (r[0] + p.center[0], r[1] + p.center[1], r[2] + p.center[2])
            wy = _yaw_transform(w, yaw)
            verts.append((wy[0] + px, wy[1] + py, wy[2] + pz))
        normals = []
        for _, n in FACES:
            rn = _rot(n, *p.tilt)
            normals.append(_yaw_transform(rn, yaw))
        for (idx, _), n in zip(FACES, normals):
            out.append(([verts[i] for i in idx], n, p.material, p.name))
    return out


def cuboid_faces(center, size, material, name="cuboid"):
    """任意位置の直方体1個のフェイス (壁用, 回転なし)."""
    part = Part(name, material, size, center=(0, 0, 0))
    return faces_for_parts([part], center, 0.0)
