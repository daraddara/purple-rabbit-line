"""
Pyxel 3.0 のネイティブ3Dエンジン (pyxel.cube) による描画. v1.4

- キャラクター4体 (餌2体・うさぎ・障害物ペンギン) は GLB
  (assets/*.glb) を Mesh.from_glb で読み込む.
  GLB は gen_models.py がパーツ定義から生成したもので, ノード名 =
  パーツ名, うさぎは歩行アニメ用の関節ノード (leg_l 等) を持つ.
  Blockbench 用の .bbmodel も同じ定義から生成され, 構成が一致する.
- うさぎの歩行は, 関節ノードの回転で再現する
  (rabbit_model.anim_angles の角度をそのまま使う).
- 地面と壁は静的ジオメトリを Primitive にマージして描く.
- 深度バッファがあるので描画順ソートは不要.
"""
import math
import os
from pyxel.cube import Camera, Mat4, Mesh, Node, Primitive, Shading, Vec3
import pyxel

from models import GROUND_COLORS, cuboid_faces
from characters import RABBIT_SCALE, FOOD_SCALES, PENGUIN_SCALE
import rabbit_model
from snake_logic import (FIELD_SIDES, FIELD_APOTHEM, FIELD_SIDE,
                         forward, yaw_of)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
DEG = 180.0 / math.pi
BODY_Y = 0.5                     # うさぎの体全体の傾きの支点 (GLBの body ノード)
BODY_TILT = 0.06                 # 体全体の前傾 (rad)
ANIM_GROUPS = ("leg_l", "leg_r", "arm_l", "arm_r", "ear_l", "ear_r")
OUTLINE_COLOR = 0                # モデル縁取りの色 (パレット番号, 黒)
                                 # Pyxel 3.0.4 の Node.outline を使用


def _prim_from_faces(faces):
    """(verts, normal, material, name) の面リスト -> Primitive."""
    positions = []
    indices = []
    for verts, _n, _m, _name in faces:
        base = len(positions) // 3
        for x, y, z in verts:
            positions += [x, y, z]
        indices += [base, base + 1, base + 2, base, base + 2, base + 3]
    prim = Primitive(Primitive.MODE_TRIANGLES, positions, indices,
                     cull=Primitive.CULL_BACK)
    prim.compute_normals()
    return prim


def _ground_prims():
    """緑と白のチェッカー. 12角形フィールドと車両の下まで敷く."""
    prims = {}
    tile = FIELD_SIDE / 3
    reach = FIELD_APOTHEM + TRAIN_T + 0.4
    n = int(reach / tile) + 1
    for color in (0, 1):
        faces = []
        for ix in range(-n, n + 1):
            for iz in range(-n, n + 1):
                if (ix + iz) % 2 != color:
                    continue
                cx, cz = ix * tile, iz * tile
                if math.hypot(cx, cz) > reach:
                    continue
                x0, z0 = cx - tile / 2, cz - tile / 2
                x1, z1 = x0 + tile, z0 + tile
                # 上から見て反時計回り (法線が +Y) でないと背面カリングで消える
                quad = [(x0, 0.0, z0), (x0, 0.0, z1),
                        (x1, 0.0, z1), (x1, 0.0, z0)]
                faces.append((quad, (0, 1, 0), "ground", "ground"))
        prims[GROUND_COLORS[color]] = _prim_from_faces(faces)
    return prims


# ---------- 壁: 電車の車両で正12角形に囲む ----------
TRAIN_GREEN = 8                  # 緑 (CUSTOM_COLORS で #80C241)
TRAIN_SILVER = 6                 # ステンレス車体
TRAIN_PANEL = 7                  # 空調 (やや明るい銀)
TRAIN_DARK = 5                   # 線路盤
TRAIN_BLACK = 0                  # 窓・スカート
CAR_LEN = FIELD_SIDE + 0.7       # 描画上の車両長 (角で隣と重ねて隙間を防ぐ)
TRAIN_T = CAR_LEN * 2.95 / 19.5  # 車両の厚み: 実寸比 (幅 2.95m / 長さ 19.5m)


def _train_prims():
    """
    正12角形の各辺に電車を1両ずつ置き, ループ状に囲む.
    側面の特徴: 銀の車体に, 黒い窓と, ドア自体が緑の両開きドア.
    緑はドア上部の屋根際まで伸びる.
    ドアと窓の配置は実寸比 (車体長 19.5m 換算): ドアは片側4か所で
    幅 1.3m, 中心は車端から 2.25 / 7.25 / 12.25 / 17.25m (間隔 5.0m).
    ドアの間には窓 (幅 1.8m), 車両端とドアの間には狭い窓 (幅 0.8m).
    色ごとに Primitive を返す.
    """
    s = FIELD_SIDE / 19.5          # m → 単位
    panel_t = TRAIN_T + 0.06       # ドア (車体より少し張り出す)
    window_t = TRAIN_T + 0.05      # 窓
    # 1両分の部品: (色, 車両中心からの沿線位置, y, 沿線長, 厚み, 高さ)
    parts = [
        (TRAIN_DARK, 0.0, 0.11, CAR_LEN + 0.3, TRAIN_T + 0.3, 0.22),  # 線路盤
        (TRAIN_BLACK, 0.0, 0.36, CAR_LEN, TRAIN_T - 0.25, 0.28),      # スカート
        (TRAIN_SILVER, 0.0, 1.50, CAR_LEN, TRAIN_T, 2.0),             # 車体
        (TRAIN_SILVER, 0.0, 2.61, CAR_LEN, TRAIN_T - 0.15, 0.22),     # 屋根
        (TRAIN_PANEL, 0.0, 2.81, 2.4, 0.5, 0.18),                     # 空調
    ]
    for wp, w in ((0.8, 0.8), (18.7, 0.8),          # 車両端の狭い窓
                  (4.75, 1.8), (9.75, 1.8), (14.75, 1.8)):  # ドア間の窓
        parts.append((TRAIN_BLACK, (wp - 9.75) * s, 1.88,
                      w * s, window_t, 0.56))
    for dp in (2.25, 7.25, 12.25, 17.25):           # ドア (緑, 両開き)
        dc = (dp - 9.75) * s
        parts.append((TRAIN_GREEN, dc, 1.50, 1.3 * s, panel_t, 2.0))
        parts.append((TRAIN_BLACK, dc - 0.325 * s, 1.88,
                      0.45 * s, panel_t + 0.03, 0.58))
        parts.append((TRAIN_BLACK, dc + 0.325 * s, 1.88,
                      0.45 * s, panel_t + 0.03, 0.58))

    buckets = {}
    sector = 2 * math.pi / FIELD_SIDES
    rc = FIELD_APOTHEM + TRAIN_T / 2                # 車両中心の半径
    for k in range(FIELD_SIDES):
        phi = k * sector                            # 辺の外向き法線の角度
        nx, nz = math.cos(phi), math.sin(phi)
        tx, tz = nz, -nx                            # 沿線方向 (回転行列の行列式が
                                                    # +1 になる向き. 鏡像にすると
                                                    # 面の表裏が反転して壊れる)
        cx, cz = nx * rc, nz * rc                   # 車両中心
        for color, a, y, al, t, h in parts:
            faces = cuboid_faces((a, y, 0.0), (al, h, t), "train", "train")
            moved = []
            for verts, nrm, mat, name in faces:
                wv = [(cx + tx * vx + nx * vz, vy, cz + tz * vx + nz * vz)
                      for vx, vy, vz in verts]
                moved.append((wv, nrm, mat, name))
            buckets.setdefault(color, []).extend(moved)
    return {color: _prim_from_faces(faces)
            for color, faces in buckets.items()}


class CamFollow:
    """先頭うさぎの後方から追従するカメラの平滑化 (位置と注視点)."""

    def __init__(self):
        self.pos = None
        self.target = None

    def desired(self, game):
        hx, hz = game.head
        fx, fz = forward(game.yaw)
        pos = (hx - fx * 9.5, 5.0, hz - fz * 9.5)
        tgt = (hx + fx * 2.5, 0.6 + game.hop_y * 0.35, hz + fz * 2.5)
        return pos, tgt

    def snap(self, game):
        self.pos, self.target = self.desired(game)

    def follow(self, game, k_pos=0.20, k_tgt=0.30):
        if self.pos is None:
            self.snap(game)
            return
        (dx, dy, dz), (tx, ty, tz) = self.desired(game)
        self.pos = tuple(p + (d - p) * k_pos
                         for p, d in zip(self.pos, (dx, dy, dz)))
        self.target = tuple(t + (g - t) * k_tgt
                            for t, g in zip(self.target, (tx, ty, tz)))


class RabbitActor:
    """うさぎ1体分の GLB アクターと関節ノードへの参照."""

    def __init__(self, scene, mesh):
        self.node = Node.from_mesh(mesh)
        self.node.outline = OUTLINE_COLOR if scene.outline_on else None
        scene.add_child(self.node)
        self.body = self.node.find_by_name("body")[0]
        self.joints = {}
        for name in ANIM_GROUPS:
            found = self.node.find_by_name(name)
            if found:
                self.joints[name] = found[0]
        # 関節ノードの基準位置 (pivot - body原点) は GLB の初期 transform から
        self.joint_pos = {n: j.transform.pos for n, j in self.joints.items()}

    def pose(self, x, z, yaw, phase, hop):
        self.node.visible = True
        self.node.transform = (
            Mat4.from_translation(Vec3(x, hop, z))
            * Mat4.from_euler(Vec3(0, (math.pi - yaw) * DEG, 0))
            * Mat4.from_scale(Vec3(RABBIT_SCALE, RABBIT_SCALE, RABBIT_SCALE)))
        bob = abs(math.sin(phase)) * 0.07
        self.body.transform = (
            Mat4.from_translation(Vec3(0, BODY_Y + bob, 0))
            * Mat4.from_euler(Vec3(BODY_TILT * DEG, 0, 0)))
        angles = rabbit_model.anim_angles(phase)
        for name, joint in self.joints.items():
            ang = angles.get(name, (0.0, 0.0, 0.0))
            joint.transform = (
                Mat4.from_translation(self.joint_pos[name])
                * Mat4.from_euler(Vec3(ang[0] * DEG, ang[1] * DEG,
                                       ang[2] * DEG)))

    def hide(self):
        self.node.visible = False


class Scene(Node):
    """ゲーム状態を読んで毎フレーム描くシーンノード."""

    def __init__(self, game):
        super().__init__()
        self.game = game
        self.effects = []                # App が毎フレーム差し替える
        self.frame = 0
        self.shading = Shading(pyxel.colors)
        self.camera = Camera()
        self.camera.clear_color = 1      # 空色
        self.camera.fov = 44.0
        self.camera.near = 0.5
        self.camera.far = 300.0
        self.ground = _ground_prims()
        self.trains = _train_prims()   # 壁 = 電車の車両
        self.outline_on = True           # モデル縁取り (O キーで切替)
        # 餌キャラクター (GLB アクター)
        self.food_actors = {}
        for kind, fname in (("A", "a_squirrel.glb"), ("C", "c_kid.glb")):
            actor = Node.from_mesh(Mesh.from_glb(os.path.join(ASSETS, fname)))
            actor.outline = OUTLINE_COLOR
            self.add_child(actor)
            self.food_actors[kind] = actor
        # うさぎ隊列 (必要数だけ作って使い回す)
        self.rabbit_mesh = Mesh.from_glb(os.path.join(ASSETS, "b_rabbit.glb"))
        self.rabbits = []
        # 障害物ペンギン (必要数だけ作って使い回す)
        self.penguin_mesh = Mesh.from_glb(os.path.join(ASSETS, "d_penguin.glb"))
        self.penguins = []

    def set_camera(self, pos, target):
        self.camera.transform = Mat4.look_at(Vec3(*pos), Vec3(*target))

    def set_outline(self, on):
        """モデル縁取り (Pyxel 3.0.4 の Node.outline) の ON/OFF."""
        self.outline_on = on
        value = OUTLINE_COLOR if on else None
        for actor in self.food_actors.values():
            actor.outline = value
        for rabbit in self.rabbits:
            rabbit.node.outline = value
        for actor in self.penguins:
            actor.outline = value

    def sync(self):
        """ゲーム状態に合わせてアクターの姿勢を更新する (毎フレーム)."""
        game = self.game
        hx, hz = game.head
        for kind in ("A", "C"):
            pos = game.foods.get(kind)
            actor = self.food_actors[kind]
            if pos is None:
                actor.visible = False
                continue
            actor.visible = True
            fx_, fz_ = pos
            face = yaw_of(hx - fx_, hz - fz_)
            sway = 0.15 * math.sin(self.frame * 0.05
                                   + (0 if kind == "A" else 2.0))
            bob = 0.05 * math.sin(self.frame * 0.09
                                  + (0 if kind == "A" else 1.3))
            fs = FOOD_SCALES[kind]
            actor.transform = (
                Mat4.from_translation(Vec3(fx_, bob, fz_))
                * Mat4.from_euler(Vec3(0, (-face + sway) * DEG, 0))
                * Mat4.from_scale(Vec3(fs, fs, fs)))
        states = game.unit_states()
        while len(self.rabbits) < len(states):
            self.rabbits.append(RabbitActor(self, self.rabbit_mesh))
        for i, (ux, uz, uyaw, _kind, phase, hop) in enumerate(states):
            self.rabbits[i].pose(ux, uz, uyaw, phase, hop)
        for extra in self.rabbits[len(states):]:
            extra.hide()
        # ペンギン: その場で先頭の方を向いて立つ (わずかに揺れる)
        while len(self.penguins) < len(game.penguins):
            actor = Node.from_mesh(self.penguin_mesh)
            actor.outline = OUTLINE_COLOR if self.outline_on else None
            self.add_child(actor)
            self.penguins.append(actor)
        for i, (px, pz) in enumerate(game.penguins):
            actor = self.penguins[i]
            actor.visible = True
            face = yaw_of(hx - px, hz - pz)
            sway = 0.08 * math.sin(self.frame * 0.04 + i * 1.7)
            actor.transform = (
                Mat4.from_translation(Vec3(px, 0.0, pz))
                * Mat4.from_euler(Vec3(0, (-face + sway) * DEG, 0))
                * Mat4.from_scale(Vec3(PENGUIN_SCALE, PENGUIN_SCALE,
                                       PENGUIN_SCALE)))
        for extra in self.penguins[len(game.penguins):]:
            extra.visible = False

    def on_draw(self):
        game = self.game
        for col, prim in self.ground.items():
            self.prim(Mat4.IDENTITY, prim, col)
        for col, prim in self.trains.items():
            self.prim(Mat4.IDENTITY, prim, col)
        # 足元の疑似影
        for kind in ("A", "C"):
            pos = game.foods.get(kind)
            if pos is not None:
                self._shadow(pos[0], pos[1], 0.95 * FOOD_SCALES[kind])
        for ux, uz, _uyaw, _kind, _phase, _hop in game.unit_states():
            self._shadow(ux, uz, 0.8 * RABBIT_SCALE / 0.42)
        for px, pz in game.penguins:
            self._shadow(px, pz, 1.0 * PENGUIN_SCALE)
        # 食べた時の演出: 3D空間に小さい箱の粒 + "+1"
        for eff in self.effects:
            for x, y, z, r, col in effect_particles(eff["pos"], eff["kind"],
                                                    eff["age"]):
                self.box(Mat4.from_translation(Vec3(x, y, z)),
                         Vec3(r * 2, r * 2, r * 2), col)
            if eff["age"] <= 20:
                self.depth_offset(-35.0)
                self.text(Vec3(eff["pos"][0], 1.7 + eff["age"] * 0.045,
                               eff["pos"][1]), "+1", 7)

    def _shadow(self, x, z, size):
        # 陰影を切らないと Cube のシェーディングで青みに寄るため,
        # 影だけフラットに描く
        self.shaded(False)
        m = Mat4.from_translation(Vec3(x, 0.02, z))
        self.box(m, Vec3(size, 0.02, size), 5)
        self.shaded(True)


# ---------- 食べた時の演出 (パーティクル配置) ----------
EFFECT_FRAMES = 26               # 演出の持続フレーム (30fpsで約0.87秒)
_EFFECT_COLORS = {"A": (9, 15, 7, 10), "C": (14, 3, 7, 10)}


def _hash(i, k):
    return (math.sin(i * 12.9898 + k * 78.233) * 43758.5453) % 1.0


def effect_particles(pos, kind, age):
    """
    食べた位置から広がる粒の (x, y, z, 半径, 色) を返す.
    age はフレーム数. 決定的な疑似乱数でばらける.
    """
    if age < 0 or age > EFFECT_FRAMES:
        return []
    t = age / 30.0
    out = []
    cols = _EFFECT_COLORS[kind]
    for i in range(14):
        ang = i * 2.39996                       # 黄金角で放射状に
        rad_sp = 1.0 + 1.8 * _hash(i, 1)
        up = 2.4 + 1.6 * _hash(i, 2)
        x = pos[0] + math.cos(ang) * rad_sp * t
        z = pos[1] + math.sin(ang) * rad_sp * t
        y = 0.9 + up * t - 5.0 * t * t
        r = max(0.05, 0.23 * (1.0 - age / (EFFECT_FRAMES + 4)))
        out.append((x, max(y, 0.05), z, r, cols[i % len(cols)]))
    return out
