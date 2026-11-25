"""
リスとオレンジの子のモデルと, うさぎの描画アダプタ.

リスとオレンジの子は色がほぼ同じオレンジ (実色 リス #F08D4C /
オレンジの子 #F0871C) なので,
色だけでなく形の特徴で確実に分かれるように作ってある:

リス
  - とがった耳が上向き, 額から背中を通って尻尾の先まで黒い一本ライン
    (額の黒帯 + 背中の黒線 + 尻尾先端の黒帯で表現)
  - 大きな白い楕円の目, クリーム色のお腹, 横に広げた腕
  - 後ろに立ち上がるリスの尻尾
オレンジの子
  - 横に大きな丸い耳 + ピンクの内耳 (一番の目印)
  - 小さな点目, 赤い点の鼻, 波形の口
  - 黒い斜めストラップ + ポシェット, 中から茶色いモグラが顔を出す
  - 黒いブーツ, 尻尾なし, 卵型の体

紫うさぎは rabbit_model.py (歩行デモのモデル) をそのまま使い,
ここでは隊列1体分のスケール・回転・配置を行う.
"""
import math
from models import Part, faces_for_parts
import rabbit_model

RABBIT_SCALE = 0.50              # 隊列1体の大きさ (高さ約1.54になる)

# キャラのサイズ感の統一 (描画時の倍率). 高さが約1.5にそろうよう
# リスは少し小さく, うさぎは大きくした. ペンギンは元から約1.49で不変.
FOOD_SCALES = {"A": 0.85, "C": 0.96}
PENGUIN_SCALE = 1.0


# ---------- リス ----------
def squirrel_parts():
    P = []
    add = lambda *a, **k: P.append(Part(*a, **k))
    # 脚・足 (オレンジ)
    add("foot_l", "squirrel", (0.27, 0.22, 0.36), center=(-0.17, 0.11, -0.02))
    add("foot_r", "squirrel", (0.27, 0.22, 0.36), center=(0.17, 0.11, -0.02))
    # 体
    add("body", "squirrel", (0.80, 0.62, 0.56), center=(0, 0.55, 0))
    # お腹のクリーム色パッチ
    add("belly", "belly", (0.50, 0.48, 0.06), center=(0, 0.52, -0.29))
    # 腕: 横に広げる
    add("arm_l", "squirrel", (0.52, 0.18, 0.18), center=(-0.62, 0.80, 0),
        tilt=(0.0, 0.0, -0.18))
    add("arm_r", "squirrel", (0.52, 0.18, 0.18), center=(0.62, 0.80, 0),
        tilt=(0.0, 0.0, 0.18))
    # 頭
    add("head", "squirrel", (0.74, 0.62, 0.62), center=(0, 1.14, 0))
    # とがった耳 (上向き, 少し外へ)
    add("ear_l", "squirrel", (0.20, 0.36, 0.16), center=(-0.24, 1.58, 0),
        tilt=(0.0, 0.0, 0.16))
    add("ear_r", "squirrel", (0.20, 0.36, 0.16), center=(0.24, 1.58, 0),
        tilt=(0.0, 0.0, -0.16))
    # 黒い一本ライン: 額の帯 -> 頭頂 -> 背中 -> 尻尾の先
    add("stripe_forehead", "black", (0.22, 0.34, 0.06), center=(0, 1.34, -0.31))
    add("stripe_top", "black", (0.20, 0.06, 0.55), center=(0, 1.47, -0.02))
    add("stripe_back", "black", (0.18, 0.72, 0.06), center=(0, 0.88, 0.29))
    # 目: 大きな白い楕円 + 黒い瞳
    add("eye_l", "white", (0.17, 0.26, 0.05), center=(-0.18, 1.20, -0.31))
    add("eye_r", "white", (0.17, 0.26, 0.05), center=(0.18, 1.20, -0.31))
    add("pupil_l", "black", (0.09, 0.15, 0.03), center=(-0.18, 1.18, -0.34))
    add("pupil_r", "black", (0.09, 0.15, 0.03), center=(0.18, 1.18, -0.34))
    # 鼻と笑口
    add("nose", "black", (0.13, 0.09, 0.04), center=(0, 1.06, -0.32))
    add("mouth", "black", (0.22, 0.07, 0.04), center=(0, 0.95, -0.32))
    # 尻尾: 後ろで立ち上がり, 先端は黒帯 (ラインの終点)
    add("tail_low", "squirrel", (0.32, 0.52, 0.26), center=(0, 0.52, 0.40),
        tilt=(-0.30, 0.0, 0.0))
    add("tail_high", "squirrel", (0.34, 0.52, 0.26), center=(0, 1.02, 0.52),
        tilt=(0.35, 0.0, 0.0))
    add("tail_tip", "black", (0.36, 0.24, 0.28), center=(0, 1.32, 0.46),
        tilt=(0.35, 0.0, 0.0))
    return P


# ---------- オレンジの子 ----------
def kid_parts():
    P = []
    add = lambda *a, **k: P.append(Part(*a, **k))
    # 黒いブーツ
    add("boot_l", "black", (0.30, 0.17, 0.44), center=(-0.21, 0.09, -0.03))
    add("boot_r", "black", (0.30, 0.17, 0.44), center=(0.21, 0.09, -0.03))
    # 卵型の体 (3段)
    add("body_low", "kid", (0.86, 0.55, 0.64), center=(0, 0.44, 0))
    add("body_mid", "kid", (0.96, 0.58, 0.70), center=(0, 0.84, 0))
    add("body_top", "kid", (0.80, 0.50, 0.62), center=(0, 1.24, 0))
    # 大きな丸い耳 (横) + ピンクの内耳
    add("ear_l", "kid", (0.44, 0.44, 0.17), center=(-0.63, 1.34, 0))
    add("ear_r", "kid", (0.44, 0.44, 0.17), center=(0.63, 1.34, 0))
    add("inner_l", "pink", (0.31, 0.31, 0.05), center=(-0.63, 1.34, -0.10))
    add("inner_r", "pink", (0.31, 0.31, 0.05), center=(0.63, 1.34, -0.10))
    # 顔: 小さな点目, 赤い鼻, 波形の口 (3ピース)
    add("eye_l", "black", (0.09, 0.11, 0.04), center=(-0.19, 1.30, -0.32))
    add("eye_r", "black", (0.09, 0.11, 0.04), center=(0.19, 1.30, -0.32))
    add("nose", "red", (0.10, 0.09, 0.04), center=(0, 1.21, -0.33))
    add("mouth", "black", (0.15, 0.05, 0.04), center=(0, 1.08, -0.32))
    add("mouth_l", "black", (0.12, 0.05, 0.04), center=(-0.13, 1.10, -0.32),
        tilt=(0.0, 0.0, 0.5))
    add("mouth_r", "black", (0.12, 0.05, 0.04), center=(0.13, 1.10, -0.32),
        tilt=(0.0, 0.0, -0.5))
    # 腕: 体の横に垂れる
    add("arm_l", "kid", (0.17, 0.56, 0.17), center=(-0.56, 0.64, 0))
    add("arm_r", "kid", (0.17, 0.56, 0.17), center=(0.56, 0.64, 0))
    # 黒い斜めストラップ (元絵: 左肩 -> 右腰, 4ピース)
    # ※モデルの +X は正面から見て左側に出る
    # ベルトの向き (肩->腰) に長軸を合わせ, 重ねて並べて破線にしない
    add("strap1", "black", (0.13, 0.34, 0.05), center=(-0.24, 1.01, -0.35),
        tilt=(0.0, 0.0, 0.81))
    add("strap2", "black", (0.13, 0.34, 0.05), center=(-0.07, 0.85, -0.35),
        tilt=(0.0, 0.0, 0.81))
    add("strap3", "black", (0.13, 0.34, 0.05), center=(0.10, 0.69, -0.35),
        tilt=(0.0, 0.0, 0.81))
    add("strap4", "black", (0.13, 0.34, 0.05), center=(0.27, 0.53, -0.35),
        tilt=(0.0, 0.0, 0.81))
    # ポシェット (黒) と, 中から顔を出すモグラ (茶 + ピンクの鼻)
    add("pouch", "black", (0.44, 0.36, 0.20), center=(0.31, 0.40, -0.33))
    add("mole", "mole", (0.27, 0.21, 0.15), center=(0.31, 0.66, -0.35))
    add("mole_nose", "pink", (0.09, 0.07, 0.04), center=(0.31, 0.63, -0.44))
    add("mole_eye_l", "black", (0.05, 0.05, 0.03), center=(0.24, 0.70, -0.43))
    add("mole_eye_r", "black", (0.05, 0.05, 0.03), center=(0.38, 0.70, -0.43))
    return P


def food_parts(kind):
    return squirrel_parts() if kind == "A" else kid_parts()


# ---------- ペンギン (障害物) ----------
def penguin_parts():
    """
    ペンギン. デザインの特徴:
    - 頭と体が一体化した黒い丸い体, 大きな白いお腹
    - 目は白い円に黒い瞳, くちばしは小さく白い
    - 黒いフリッパー (腕) と黒い足, 色は黒と白のみ
    """
    P = []
    add = lambda *a, **k: P.append(Part(*a, **k))
    # 足 (黒)
    add("foot_l", "black", (0.26, 0.08, 0.46), center=(-0.20, 0.04, -0.05))
    add("foot_r", "black", (0.26, 0.08, 0.46), center=(0.20, 0.04, -0.05))
    # 体 (頭と一体化した丸いフォルムを2段で)
    add("body_low", "black", (0.98, 0.80, 0.84), center=(0, 0.46, 0))
    add("body_top", "black", (0.80, 0.66, 0.72), center=(0, 1.16, 0))
    # 大きな白いお腹
    add("belly", "white", (0.66, 1.02, 0.10), center=(0, 0.60, -0.40))
    # フリッパー (腕): 体の横に沿わせて少し外へ傾ける
    add("flipper_l", "black", (0.16, 0.60, 0.30), center=(-0.56, 0.80, 0),
        tilt=(0.0, 0.0, -0.22))
    add("flipper_r", "black", (0.16, 0.60, 0.30), center=(0.56, 0.80, 0),
        tilt=(0.0, 0.0, 0.22))
    # 尾
    add("tail", "black", (0.36, 0.18, 0.24), center=(0, 0.30, 0.46),
        tilt=(0.35, 0.0, 0.0))
    # 目: 白い円 + 黒い瞳
    add("eye_l", "white", (0.14, 0.17, 0.04), center=(-0.17, 1.26, -0.37))
    add("eye_r", "white", (0.14, 0.17, 0.04), center=(0.17, 1.26, -0.37))
    add("pupil_l", "black", (0.06, 0.08, 0.03), center=(-0.17, 1.26, -0.40))
    add("pupil_r", "black", (0.06, 0.08, 0.03), center=(0.17, 1.26, -0.40))
    # くちばし (小さい白)
    add("beak", "white", (0.22, 0.09, 0.06), center=(0, 1.10, -0.38))
    return P


# ---------- 紫うさぎ (隊列の1体) ----------
def _rabbit_transform(v, yaw):
    """rabbit_model のローカル (正面=+Z) -> ワールドへの回転.
    ローカル +Z が forward(yaw), +X が右手になるようにする."""
    fx, fz = math.sin(yaw), -math.cos(yaw)
    rx, rz = -fz, fx
    x, y, z = v
    return (rx * x + fx * z, y, rz * x + fz * z)


def rabbit_faces(phase, hop, pos, yaw):
    """
    歩行ポーズ済みのうさぎ1体を, 隊列用スケールでワールドへ置く.
    phase: 歩行フェーズ, hop: ジャンプの高さ (ワールド単位),
    pos: (x, z) 地面位置, yaw: 進行方向.
    戻り値は faces_for_parts と同じ形式.
    """
    out = []
    px, pz = pos
    for verts, normal, mat, name in rabbit_model.posed_faces(phase, 0.0):
        wv = []
        for x, y, z in verts:
            r = _rabbit_transform((x * RABBIT_SCALE, y * RABBIT_SCALE,
                                   z * RABBIT_SCALE), yaw)
            wv.append((r[0] + px, r[1] + hop, r[2] + pz))
        wn = _rabbit_transform(normal, yaw)
        out.append((wv, wn, mat, name))
    return out


def count_stats():
    return {"squirrel_parts": len(squirrel_parts()),
            "kid_parts": len(kid_parts()),
            "rabbit_parts": len(rabbit_model.build_parts())}


if __name__ == "__main__":
    print(count_stats())
