"""
紫のうさぎのローポリモデル定義. v2

デザインの特徴:
- 全身ほぼ一色の鮮やかな紫 (#9F40F4). 白い部分は
  顔の小さな白パッチだけ. ピンクやクリーム色の部分は無い.
- 頭と体は一体のずんぐりしたシルエット (腹の色分けも無い).
- 耳は太く, 根元から上がったあと横へ垂れる. 左右に大きく張り出す.
- 顔パッチの中に, 黒い点目 x2 / 小さい黒い鼻 / 大きく笑う黒い口.
- 腕は長く体の横に垂れ, 手は膝あたりまで届く. 脚は短く足は大きめ, 全部紫.
- しっぽは背面の小さい紫の丸 (白くない).

※ 紫うさぎ歩行デモ (別プロジェクト) のモデルを流用し,
パレット番号だけこのゲームに合わせて変更したもの.
座標系: x=右, y=上, z=手前(正面).
"""
import math
from dataclasses import dataclass

# マテリアル名 -> (暗, 中, 明) Pyxelカラー番号
MATERIALS = {
    "purple": (2, 11, 12),       # 2=濃紫#7326C7, 11=主色#9F40F4, 12=明紫#BC7FFF (このゲームのパレットに合わせた割当)
    "purple_dark": (2, 2, 11),   # 足裏・しっぽの丸など
    "white": (6, 7, 7),          # 顔パッチ (唯一の白)
    "black": (0, 0, 0),          # 目・鼻・口
}


@dataclass
class Part:
    name: str
    material: str
    size: tuple          # (sx, sy, sz)
    center: tuple = (0.0, 0.0, 0.0)
    pivot: tuple = None  # 回転の支点
    anim: str = None     # leg_l/leg_r/arm_l/arm_r/ear_l/ear_r
    tilt: tuple = (0.0, 0.0, 0.0)   # 静止時の傾き (rad)
    # True: center は最終位置 (tilt は自中心の回転, anim は pivot 周り)
    # False: center は pivot からの相対位置 (tilt+anim で pivot 周り)
    absolute: bool = False


def build_parts():
    P = []
    add = lambda *a, **k: P.append(Part(*a, **k))

    # --- 頭+体: 一体のずんぐりした塊 (3段重ね, 全部同じ紫) ---
    add("body_top", "purple", (1.25, 0.75, 0.95), center=(0, 2.05, 0))
    add("body_mid", "purple", (1.45, 0.70, 1.05), center=(0, 1.45, 0))
    add("body_low", "purple", (1.55, 0.70, 1.10), center=(0, 0.82, 0))
    # しっぽ: 背面の小さい紫の丸
    add("tail", "purple_dark", (0.30, 0.30, 0.10), center=(0, 0.95, -0.58))

    # --- 顔: 小さな白パッチ + 黒い目・鼻・口 (白はここだけ) ---
    add("face", "white", (0.62, 0.52, 0.08), center=(0, 2.14, 0.51))
    add("eye_l", "black", (0.10, 0.11, 0.05), center=(-0.14, 2.26, 0.57))
    add("eye_r", "black", (0.10, 0.11, 0.05), center=(0.14, 2.26, 0.57))
    add("nose", "black", (0.12, 0.06, 0.05), center=(0, 2.15, 0.57))
    # 口は笑顔の弧: 中央 + 両端を上げた3ピース
    add("mouth", "black", (0.20, 0.07, 0.05), center=(0, 1.97, 0.57))
    add("mouth_l", "black", (0.16, 0.07, 0.05), center=(-0.16, 2.00, 0.57),
        tilt=(0.0, 0.0, 0.55), absolute=True)
    add("mouth_r", "black", (0.16, 0.07, 0.05), center=(0.16, 2.00, 0.57),
        tilt=(0.0, 0.0, -0.55), absolute=True)

    # --- 耳: 太く, 上がってから横へ垂れる (2節/片耳, 全て紫) ---
    # 節1: 根元から外へ傾いて上がる
    add("ear_l_1", "purple", (0.42, 0.58, 0.38),
        center=(-0.36, 2.62, 0), pivot=(-0.28, 2.38, 0), anim="ear_l",
        tilt=(0.0, 0.0, 0.28), absolute=True)
    add("ear_r_1", "purple", (0.42, 0.58, 0.38),
        center=(0.36, 2.62, 0), pivot=(0.28, 2.38, 0), anim="ear_r",
        tilt=(0.0, 0.0, -0.28), absolute=True)
    # 節2: 横へ張り出し, 先が少し垂れる (節1と大きく重ねて継ぎ目を消す)
    add("ear_l_2", "purple", (0.44, 0.85, 0.38),
        center=(-0.70, 2.86, 0), pivot=(-0.28, 2.38, 0), anim="ear_l",
        tilt=(0.0, 0.0, 1.72), absolute=True)
    add("ear_r_2", "purple", (0.44, 0.85, 0.38),
        center=(0.70, 2.86, 0), pivot=(0.28, 2.38, 0), anim="ear_r",
        tilt=(0.0, 0.0, -1.72), absolute=True)

    # --- 腕: 肩から外へ開いて垂れる (pivot=肩, 脇の下に隙間ができる角度) ---
    # ※下向きの腕は, 上向きの耳と rz の符号が逆で外へ開く
    add("arm_l", "purple", (0.36, 1.15, 0.36),
        center=(0, -0.50, 0.05), pivot=(-0.86, 1.62, 0.15), anim="arm_l",
        tilt=(0.0, 0.0, -0.34))
    add("arm_r", "purple", (0.36, 1.15, 0.36),
        center=(0, -0.50, 0.05), pivot=(0.86, 1.62, 0.15), anim="arm_r",
        tilt=(0.0, 0.0, 0.34))

    # --- 脚+足: 短い脚に大きめの足, 全部紫 (pivot=股関節) ---
    add("leg_l", "purple", (0.44, 0.36, 0.44),
        center=(0, -0.14, 0), pivot=(-0.36, 0.55, 0), anim="leg_l")
    add("foot_l", "purple", (0.50, 0.20, 0.62),
        center=(0, -0.38, 0.10), pivot=(-0.36, 0.55, 0), anim="leg_l")
    add("leg_r", "purple", (0.44, 0.36, 0.44),
        center=(0, -0.14, 0), pivot=(0.36, 0.55, 0), anim="leg_r")
    add("foot_r", "purple", (0.50, 0.20, 0.62),
        center=(0, -0.38, 0.10), pivot=(0.36, 0.55, 0), anim="leg_r")
    return P


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


def anim_angles(phase):
    swing = math.sin(phase)
    return {
        "leg_l": (swing * 0.60, 0.0, 0.0),
        "leg_r": (-swing * 0.60, 0.0, 0.0),
        # 腕は脚と逆位相に大きく振る (開いた脇のまま前後へ)
        "arm_l": (-swing * 0.60, 0.0, -0.05),
        "arm_r": (swing * 0.60, 0.0, 0.05),
        # 耳は体の上下動に少し遅れて前後に揺れる
        "ear_l": (math.sin(phase * 2 - 0.9) * 0.13, 0.0, 0.04 * math.sin(phase)),
        "ear_r": (math.sin(phase * 2 - 0.9) * 0.13, 0.0, -0.04 * math.sin(phase)),
    }


def posed_faces(phase=0.0, hop=0.0):
    """
    歩行ポーズ適用後の全フェイスを返す.
    戻り値: [(world_vertices[4], normal, material, part_name), ...]
    """
    angles = anim_angles(phase)
    bob = abs(math.sin(phase)) * 0.07 + hop
    body_tilt = 0.06
    out = []
    for p in build_parts():
        local = [(c[0] * p.size[0] / 2, c[1] * p.size[1] / 2, c[2] * p.size[2] / 2)
                 for c in _CORNERS]
        anim = angles.get(p.anim, (0.0, 0.0, 0.0))
        if p.absolute:
            # tilt で自中心を回し最終位置へ置き, anim で pivot 周りに回す
            verts = []
            for v in local:
                r = _rot(v, *p.tilt)
                w = (r[0] + p.center[0], r[1] + p.center[1], r[2] + p.center[2])
                if p.pivot is not None:
                    rel = (w[0] - p.pivot[0], w[1] - p.pivot[1], w[2] - p.pivot[2])
                    rr = _rot(rel, *anim)
                    w = (rr[0] + p.pivot[0], rr[1] + p.pivot[1], rr[2] + p.pivot[2])
                verts.append(w)
            normals = [_rot(_rot(n, *p.tilt), *anim) for _, n in FACES]
        elif p.pivot is not None:
            rot = tuple(t + a for t, a in zip(p.tilt, anim))
            verts = []
            for v in local:
                rel = (v[0] + p.center[0], v[1] + p.center[1], v[2] + p.center[2])
                r = _rot(rel, *rot)
                verts.append((r[0] + p.pivot[0], r[1] + p.pivot[1], r[2] + p.pivot[2]))
            normals = [_rot(n, *rot) for _, n in FACES]
        else:
            verts = [(v[0] + p.center[0], v[1] + p.center[1], v[2] + p.center[2])
                     for v in local]
            normals = [n for _, n in FACES]
        # 体全体の前傾 + 上下動
        tilted = []
        for x, y, z in verts:
            r = _rot((x, y - 0.5, z), body_tilt, 0.0, 0.0)
            tilted.append((r[0], r[1] + 0.5 + bob, r[2]))
        normals = [_rot(n, body_tilt, 0.0, 0.0) for n in normals]
        for (idx, _), n in zip(FACES, normals):
            out.append(([tilted[i] for i in idx], n, p.material, p.name))
    return out


def count_stats():
    faces = posed_faces(0.0)
    return {"parts": len(build_parts()), "quads": len(faces),
            "triangles": len(faces) * 2, "vertices": len(build_parts()) * 8}


if __name__ == "__main__":
    print(count_stats())
