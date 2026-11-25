"""キャラクターモデルを Wavefront OBJ (.obj + .mtl) に書き出す. v2

うさぎ隊列1体 (歩行ポーズなしの素立ち), リス, オレンジの子を
横に並べて配置する. ゲーム内の描画と同じフェイス生成を
使うので, ゲームで見える形そのままが書き出される.

実行: python tools/gen_obj.py  ->  assets/characters.obj / .mtl
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

from models import PALETTE_RGB, faces_for_parts
from characters import rabbit_faces, food_parts
from models import MATERIALS as _M
import rabbit_model as _R
ALL_MATERIALS = {**_M, **_R.MATERIALS}

GAP = 3.0


def hexcol(idx):
    r, g, b = PALETTE_RGB[idx]
    return (r / 255, g / 255, b / 255)


def build():
    faces = []           # (verts, material_name, rgb)
    models = []
    models += [(v, m) for v, _n, m, _name in
               rabbit_faces(0.0, 0.0, (-GAP, 0.0), 0.0)]
    models += [(v, m) for v, _n, m, _name in
               faces_for_parts(food_parts("A"), (0.0, 0.0, 0.0), yaw=0.0)]
    models += [(v, m) for v, _n, m, _name in
               faces_for_parts(food_parts("C"), (GAP, 0.0, 0.0), yaw=0.0)]
    for verts, mat in models:
        faces.append((verts, mat, hexcol(ALL_MATERIALS[mat][1])))
    return faces


def main():
    faces = build()
    mats = {}
    for _v, m, rgb in faces:
        mats[m] = rgb
    with open(os.path.join(OUT, "characters.mtl"), "w") as f:
        for name, (r, g, b) in sorted(mats.items()):
            f.write(f"newmtl {name}\nKd {r:.3f} {g:.3f} {b:.3f}\n\n")
    nv = 0
    with open(os.path.join(OUT, "characters.obj"), "w") as f:
        f.write("mtllib characters.mtl\n")
        for verts, mat, _rgb in faces:
            for x, y, z in verts:
                f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
            f.write(f"usemtl {mat}\n")
            idx = " ".join(str(nv + i + 1) for i in range(len(verts)))
            f.write(f"f {idx}\n")
            nv += len(verts)
    print(f"wrote characters.obj ({nv} verts, {len(faces)} faces) / characters.mtl")


if __name__ == "__main__":
    main()
