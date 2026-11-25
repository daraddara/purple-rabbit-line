"""
うさぎ隊列ゲームのロジック (Pyxel非依存・テスト可能). v2

- プレイヤーは紫うさぎの隊列. 先頭が進み, 後続は先頭が
  通った軌跡 (trail) を一定間隔で辿って1列に歩く.
- 移動はグリッド単位ではなく連続: 頭は毎ステップ
  forward * SPEED * dt だけ進み, 旋回も角速度で連続的に変わる.
- 餌はリスとオレンジの子が同時に1体ずつ存在し,
  どちらを食べても隊列が1体伸びる (食べた方だけが再配置される).
  ただし先頭が高く跳んでいる間 (高さ 0.5 超) は食べられない.
  ジャンプで餌を飛び越すと取り逃がす (餌はその場に残る).
- ジャンプ: 先頭が跳ぶと, 後続は「先頭がその地点で跳んでいた
  高さ」を距離遅れでトレースし, ジャンプが波のように伝わる.
  先頭が十分に高く跳んでいる間は自分の隊列と衝突しない
  (隊列を飛び越して回避できる). 壁は跳んでも越えられない高さ
  なので, 空中でも激突すればゲームオーバー.
- 壁 (エリア境界) または自分の隊列に頭が触れるとゲームオーバー.
- 障害物のペンギンが, 開始時に 1 体, 以後 10 秒ごとに
  1 体ずつ出現する.
  頭が触れるとミス (ゲームオーバー). 隊列と同じくジャンプで
  飛び越してかわせる (回避ラインは隊列より低めで, タイミングに
  余裕を持たせてある).

フィールドは電車のループをイメージした正12角形で, 1辺が
車両1両に対応する. 境界は車両 (壁) で, 跳んでも越えられない.

座標系: x=右, z=奥行き. yaw=0 で -Z (奥) へ進む.
forward(yaw) = (sin(yaw), -cos(yaw))  [xz平面]
"""
import math
import random

FIELD_SIDES = 12         # フィールドは正12角形 (1辺 = 車両1両)
FIELD_APOTHEM = 13.9     # 中心から各辺 (車両の内側面) までの距離
FIELD_SIDE = 2 * FIELD_APOTHEM * math.tan(math.pi / FIELD_SIDES)
                         # 1辺の長さ ≒ 7.45 (車両1両の長さに相当)


def field_limit(x, z, margin):
    """中心から (x, z) 方向を見たときの, margin 分内側の境界までの距離."""
    sector = 2 * math.pi / FIELD_SIDES
    local = (math.atan2(z, x) + sector / 2) % sector - sector / 2
    return (FIELD_APOTHEM - margin) / math.cos(local)


def inside_field(x, z, margin):
    """点 (x, z) が margin 分内側のフィールド内にあるか."""
    return math.hypot(x, z) <= field_limit(x, z, margin)
SEG_SPACING = 1.05       # 隊列の各個体間の軌跡上の距離
HEAD_RADIUS = 0.55
SELF_HIT_DIST = 0.78     # 頭と体の距離がこれ未満で自己衝突
SELF_SKIP = 4            # 頭に近いこの数の個体は自己衝突の対象外
EAT_DIST = 1.05
FOOD_CLEAR_H = 0.5       # 先頭の高さがこれを超えていると餌を食べられない
                         # (ジャンプで餌を飛び越すと取り逃がす)
TURN_RATE = 2.7          # rad/s
SPEED = 6.0              # units/s
SPEED_UP_PER_EAT = 0.01  # 餌1つごとに基本速度 +1% (スコア連動)
SPEED_UP_MAX = 1.50      # 速度倍率の上限 (+50%, 50個で到達)
START_UNITS = 1          # スタート時は先頭の1体だけ. 食べて増える
FOOD_KINDS = ("A", "C")  # リス / オレンジの子

# ペンギン (障害物): 一定時間ごとに1体ずつ増える. 頭が触れるとミス.
# 隊列と同じくジャンプで飛び越してかわせる. ただしタイミングが
# シビアにならないよう, ペンギン用の回避ラインは隊列用 (CLEAR_H)
# より低めに設定する (高さ 0.5 を超えている間は回避可能で,
# その持続時間は約0.87秒 = 隊列用の約0.70秒より長め)
PENGUIN_INTERVAL = 10.0  # 出現間隔 (秒). 開始時にも1体配置される
PENGUIN_HIT_DIST = 0.85  # 頭とペンギンの距離がこれ未満で接触
# 出現位置の安全ゾーン: 頭の正面 ±80°・距離8未満には湧かせない.
# 「目の前にいきなり出て避けられない」理不尽な激突を防ぐため.
# 最高速 9.0 u/s でも約0.9秒の反応時間を確保する距離.
SPAWN_FRONT_SAFE_DIST = 8.0
SPAWN_FRONT_COS = math.cos(math.radians(80.0))
PENGUIN_CLEAR_H = 0.5    # 先頭の高さがこれを超えていればペンギンを飛び越せる

# ジャンプ (先頭の物理と, 飛び越せる高さ)
JUMP_V = 5.6             # 初速 units/s
GRAVITY = 10.5           # units/s^2 -> 最高点 約1.49, 滞空 約1.07秒
CLEAR_H = 0.85           # 先頭の高さがこれを超えていれば隊列を飛び越せる
PHASE_PER_DIST = 2.4     # 歩行フェーズの進み (rad / unit)


def forward(yaw):
    return (math.sin(yaw), -math.cos(yaw))


def yaw_of(dx, dz):
    """移動方向ベクトル (dx, dz) に対応する yaw."""
    return math.atan2(dx, -dz)


class SnakeGame:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.reset()

    def reset(self):
        self.head = (0.0, 6.0)           # (x, z)
        self.yaw = 0.0                   # -Z (奥) 向き
        self.length = START_UNITS        # 隊列の総数 (先頭を含む)
        self.score = 0
        self.eaten = {"A": 0, "C": 0}
        self.last_eaten = None           # (種類, 位置, フレーム) 演出用
        self.game_over = False
        self.over_reason = None          # "wall" / "self" / "penguin"
        self.frame = 0
        self.penguins = []               # 障害物ペンギンの位置 [(x, z), ...]
        self.elapsed = 0.0               # プレイ経過時間 (秒)
        self.next_penguin_at = PENGUIN_INTERVAL
        self.distance = 0.0              # 先頭の累積移動距離
        self.hop_y = 0.0                 # 先頭のジャンプ高さ
        self.hop_v = 0.0
        # 軌跡: 頭の通過点の履歴 (古い順). 初期は真後ろへ直線状に置く
        fx, fz = forward(self.yaw)
        self.trail = []
        d = self.total_length_dist()
        while d >= 0.0:
            self.trail.append((self.head[0] - fx * d, self.head[1] - fz * d))
            d -= 0.2
        # ジャンプ履歴: (累積距離, その時の先頭の高さ). 後続が距離遅れで読む
        self.hop_hist = [(-self.total_length_dist() - 2.0, 0.0), (0.0, 0.0)]
        self.foods = {}
        for kind in FOOD_KINDS:
            self.spawn_food(kind)
        # ペンギンは開始時にも1体配置する
        self.spawn_penguin()

    # ---------- 基本量 ----------
    @property
    def unit_count(self):
        """隊列の総数."""
        return self.length

    def total_length_dist(self):
        return (self.unit_count - 1) * SEG_SPACING

    # ---------- 軌跡と各個体の状態 ----------
    def _trail_points(self):
        pts = [self.head]
        for p in reversed(self.trail):
            if p != pts[-1]:
                pts.append(p)
        return pts

    def unit_positions(self):
        """[(x, z, yaw, kind), ...] 先頭から最後尾の順. kind: head/body/tail"""
        pts = self._trail_points()
        out = []
        for i in range(self.unit_count):
            target = i * SEG_SPACING
            acc = 0.0
            x, z = pts[-1]
            for j in range(len(pts) - 1):
                ax, az = pts[j]
                bx, bz = pts[j + 1]
                dd = math.hypot(bx - ax, bz - az)
                if acc + dd >= target:
                    t = 0.0 if dd == 0 else (target - acc) / dd
                    x, z = ax + (bx - ax) * t, az + (bz - az) * t
                    break
                acc += dd
            if i == 0:
                uyaw = self.yaw
            else:
                qx, qz, _, _ = out[i - 1]
                uyaw = yaw_of(qx - x, qz - z) if (qx, qz) != (x, z) else out[i - 1][2]
            kind = "head" if i == 0 else ("tail" if i == self.unit_count - 1 else "body")
            out.append((x, z, uyaw, kind))
        return out

    def hop_at(self, distance):
        """累積距離 distance の地点を先頭が通過した時のジャンプ高さ."""
        hist = self.hop_hist
        if distance <= hist[0][0]:
            return hist[0][1]
        if distance >= hist[-1][0]:
            return hist[-1][1]
        for j in range(len(hist) - 1):
            d0, h0 = hist[j]
            d1, h1 = hist[j + 1]
            if d0 <= distance <= d1:
                if d1 == d0:
                    return h1
                t = (distance - d0) / (d1 - d0)
                return h0 + (h1 - h0) * t
        return hist[-1][1]

    def unit_states(self):
        """[(x, z, yaw, kind, phase, hop), ...] 描画用 (歩行+ジャンプ付き)."""
        out = []
        for i, (x, z, uyaw, kind) in enumerate(self.unit_positions()):
            dist_i = self.distance - i * SEG_SPACING
            phase = dist_i * PHASE_PER_DIST
            hop = self.hop_y if i == 0 else self.hop_at(dist_i)
            out.append((x, z, uyaw, kind, phase, hop))
        return out

    # ---------- 餌 ----------
    def spawn_food(self, kind):
        units = self.unit_positions()
        others = [p for k, p in self.foods.items() if k != kind]
        for _ in range(200):
            ang = self.rng.uniform(0, 2 * math.pi)
            rad = (FIELD_APOTHEM - 2.0) * math.sqrt(self.rng.uniform(0, 1))
            x, z = rad * math.cos(ang), rad * math.sin(ang)
            if math.hypot(x - self.head[0], z - self.head[1]) < 5.0:
                continue
            if any(math.hypot(x - ux, z - uz) < 2.0 for ux, uz, _, _ in units):
                continue
            if any(math.hypot(x - ox, z - oz) < 3.0 for ox, oz in others):
                continue
            if any(math.hypot(x - px, z - pz) < 2.0 for px, pz in self.penguins):
                continue
            self.foods[kind] = (x, z)
            return
        self.foods[kind] = (0.0, -FIELD_APOTHEM + 3.0)

    # ---------- ペンギン (障害物) ----------
    def spawn_penguin(self):
        """頭・隊列・餌・他のペンギンから離れた空き場所に1体置く.

        頭の正面の危険ゾーン (SPAWN_FRONT_SAFE_DIST 未満) にも置かない.
        """
        units = self.unit_positions()
        fx, fz = forward(self.yaw)
        for _ in range(200):
            ang = self.rng.uniform(0, 2 * math.pi)
            rad = (FIELD_APOTHEM - 1.5) * math.sqrt(self.rng.uniform(0, 1))
            x, z = rad * math.cos(ang), rad * math.sin(ang)
            dx, dz = x - self.head[0], z - self.head[1]
            dist_head = math.hypot(dx, dz)
            if dist_head < 3.0:
                continue
            if dist_head < SPAWN_FRONT_SAFE_DIST and dist_head > 0.0:
                # 正面 (±80°以内) なら近距離の出現を禁止する
                if (dx * fx + dz * fz) / dist_head > SPAWN_FRONT_COS:
                    continue
            if any(math.hypot(x - ux, z - uz) < 1.5 for ux, uz, _, _ in units):
                continue
            if any(math.hypot(x - fx, z - fz) < 2.0
                   for fx, fz in self.foods.values()):
                continue
            if any(math.hypot(x - px, z - pz) < 2.0 for px, pz in self.penguins):
                continue
            self.penguins.append((x, z))
            return

    # ---------- ジャンプ ----------
    def start_jump(self):
        """接地している時だけ跳べる. 跳べたら True."""
        if self.game_over or self.hop_y > 0.0 or self.hop_v != 0.0:
            return False
        self.hop_v = JUMP_V
        return True

    # ---------- 更新 ----------
    @property
    def speed_factor(self):
        """スコア連動の速度倍率 (食べるほど速くなる)."""
        return min(1.0 + SPEED_UP_PER_EAT * self.score, SPEED_UP_MAX)

    def update(self, dt, turn=0, speed_mul=1.0):
        """turn: -1 (左) .. +1 (右) の連続入力."""
        if self.game_over:
            return
        self.frame += 1
        self.yaw += turn * TURN_RATE * dt
        fx, fz = forward(self.yaw)
        step = SPEED * self.speed_factor * speed_mul * dt
        self.head = (self.head[0] + fx * step, self.head[1] + fz * step)
        self.distance += step
        self.trail.append(self.head)
        self._trim_trail()

        # ジャンプの物理 (先頭)
        if self.hop_v != 0.0 or self.hop_y > 0.0:
            self.hop_y += self.hop_v * dt
            self.hop_v -= GRAVITY * dt
            if self.hop_y <= 0.0:
                self.hop_y, self.hop_v = 0.0, 0.0
        self.hop_hist.append((self.distance, self.hop_y))
        self._trim_hop_hist()

        # ペンギン: 10秒ごとに1体ずつ出現 (開始時にも1体いる)
        self.elapsed += dt
        while self.elapsed >= self.next_penguin_at - 1e-9:  # 浮動小数の誤差吸収
            self.spawn_penguin()
            self.next_penguin_at += PENGUIN_INTERVAL

        # 餌: どちらを食べても1体伸び, 食べた方だけ再配置.
        # ただし高く跳んでいる間は食べられない (飛び越すと取り逃がす.
        # 餌はその場に残るので, 地面で戻れば食べ直せる)
        for kind in FOOD_KINDS:
            pos = self.foods.get(kind)
            if pos is None:
                continue
            if self.hop_y > FOOD_CLEAR_H:
                continue
            if math.hypot(pos[0] - self.head[0], pos[1] - self.head[1]) < EAT_DIST:
                self.score += 1
                self.eaten[kind] += 1
                self.length += 1
                self.last_eaten = (kind, pos, self.frame)
                self.spawn_food(kind)

        # 壁 (車両): ジャンプしても越えられない高さ. 空中でも激突で終わり
        hx, hz = self.head
        if not inside_field(hx, hz, HEAD_RADIUS):
            self.game_over = True
            self.over_reason = "wall"
            return

        # ペンギン: 頭が触れるとミス. 十分高く跳んでいる間は飛び越せる
        if self.hop_y <= PENGUIN_CLEAR_H:
            for px, pz in self.penguins:
                if math.hypot(px - hx, pz - hz) < PENGUIN_HIT_DIST:
                    self.game_over = True
                    self.over_reason = "penguin"
                    return

        # 自分の隊列: 十分高く跳んでいる間は飛び越せる
        if self.hop_y > CLEAR_H:
            return
        units = self.unit_positions()
        for ux, uz, _, _ in units[SELF_SKIP:]:
            if math.hypot(ux - hx, uz - hz) < SELF_HIT_DIST:
                self.game_over = True
                self.over_reason = "self"
                return

    def _trim_trail(self):
        need = self.total_length_dist() + 2.0
        acc = 0.0
        keep_from = 0
        for j in range(len(self.trail) - 1, 0, -1):
            ax, az = self.trail[j]
            bx, bz = self.trail[j - 1]
            acc += math.hypot(ax - bx, az - bz)
            if acc >= need:
                keep_from = j - 1
                break
        if keep_from > 0:
            del self.trail[:keep_from]

    def _trim_hop_hist(self):
        need_from = self.distance - self.total_length_dist() - 2.0
        drop = 0
        for j in range(len(self.hop_hist) - 1):
            if self.hop_hist[j + 1][0] <= need_from:
                drop = j + 1
            else:
                break
        if drop > 0:
            del self.hop_hist[:drop]
