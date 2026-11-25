import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

"""
ロジックの自動テスト v2. 実行: python test_snake.py (または pytest)
Pyxelは使わず, snake_logic のみを検証する.
"""
import math
from snake_logic import (SnakeGame, FIELD_APOTHEM, inside_field,
                         SEG_SPACING, CLEAR_H,
                         FOOD_CLEAR_H, PENGUIN_CLEAR_H, forward)

DT = 1.0 / 30.0


def test_continuous_not_grid():
    g = SnakeGame(seed=1)
    x0, z0 = g.head
    g.update(DT)
    x1, z1 = g.head
    assert (x1, z1) != (x0, z0)
    assert not float(z1).is_integer()
    assert abs(math.hypot(x1 - x0, z1 - z0) - 6.0 * DT) < 1e-9
    g.update(DT, turn=1)
    assert 0 < g.yaw < 0.2
    assert g.head[0] > 0.0


def _set_length(g, n):
    """まっすぐな軌跡のまま隊列の長さだけ変える (テスト用)."""
    g.length = n
    fx, fz = forward(g.yaw)
    g.trail = []
    d = g.total_length_dist()
    while d >= 0.0:
        g.trail.append((g.head[0] - fx * d, g.head[1] - fz * d))
        d -= 0.2


def test_start_with_one_unit():
    g = SnakeGame(seed=1)
    assert g.unit_count == 1
    states = g.unit_states()
    assert len(states) == 1 and states[0][3] == "head"


def test_units_follow_trail_and_phase():
    g = SnakeGame(seed=1)
    _set_length(g, 6)
    for _ in range(60):
        g.update(DT, turn=0.5)
    units = g.unit_positions()
    assert len(units) == g.unit_count == 6
    assert units[0][3] == "head" and units[-1][3] == "tail"
    for a, b in zip(units, units[1:]):
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        assert abs(d - SEG_SPACING) < 0.35, d
    # 歩行フェーズは後続ほど遅れている (距離に比例)
    states = g.unit_states()
    phases = [s[4] for s in states]
    assert all(a > b for a, b in zip(phases, phases[1:]))


def test_both_foods_exist():
    for seed in range(20):
        g = SnakeGame(seed=seed)
        assert set(g.foods) == {"A", "C"}          # リスとオレンジの子が同時存在
        for x, z in g.foods.values():
            assert inside_field(x, z, 2.0)
        ax, az = g.foods["A"]
        cx, cz = g.foods["C"]
        assert math.hypot(ax - cx, az - cz) >= 3.0 - 1e-9


def _feed(g, kind):
    """指定した種類の餌を頭の正面に置いて食べさせる."""
    fx, fz = forward(g.yaw)
    g.foods[kind] = (g.head[0] + fx * 2.0, g.head[1] + fz * 2.0)
    other_before = g.foods["C" if kind == "A" else "A"]
    before_score, before_units = g.score, g.unit_count
    for _ in range(30):
        g.update(DT)
        if g.score > before_score:
            break
    assert g.score == before_score + 1
    assert g.unit_count == before_units + 1       # 隊列が1体伸びた
    assert g.eaten[kind] == 1
    # 食べた方だけが再配置され, もう一方はそのまま
    assert g.foods["C" if kind == "A" else "A"] == other_before


def test_eat_each_kind_grows():
    _feed(SnakeGame(seed=2), "A")
    _feed(SnakeGame(seed=3), "C")


def test_wall_game_over():
    g = SnakeGame(seed=3)
    for _ in range(30 * 10):
        g.update(DT)
        if g.game_over:
            break
    assert g.game_over and g.over_reason == "wall"


def test_wall_game_over_even_when_jumping():
    g = SnakeGame(seed=3)
    # 壁の近くで跳んでも激突する (壁は跳び越えられない)
    for _ in range(30 * 10):
        if abs(g.head[1]) < 6.0 and g.hop_y == 0.0:
            g.start_jump()
        g.update(DT)
        if g.game_over:
            break
    assert g.game_over and g.over_reason == "wall"


def _long_game(seed=4):
    g = SnakeGame(seed=seed)
    _set_length(g, 26)
    g.foods = {"A": (-11.0, -11.0), "C": (11.0, 11.0)}
    return g


def test_self_collision_game_over():
    g = _long_game()
    hit = False
    for _ in range(30 * 20):
        g.update(DT, turn=1)
        if g.game_over:
            hit = True
            break
    assert hit and g.over_reason == "self", g.over_reason


def test_jump_physics_and_trace():
    g = SnakeGame(seed=6)
    _set_length(g, 6)
    assert g.start_jump() is True
    assert g.start_jump() is False              # 空中では二段ジャンプ不可
    peak = 0.0
    wave_seen = False
    for i in range(60):
        g.update(DT)
        peak = max(peak, g.hop_y)
        states = g.unit_states()
        # 先頭が着地した後も, 後続の誰かがまだ跳んでいる (波のトレース)
        if g.hop_y == 0.0 and any(s[5] > 0.3 for s in states[1:]):
            wave_seen = True
    assert peak > 1.3, peak                      # 隊列 (高さ約1.34) を越える高さ
    assert g.hop_y == 0.0                        # 着地している
    assert wave_seen, "後続へのジャンプの波が見られない"


def test_jump_over_own_queue_avoids_game_over():
    # 軌跡を小さな円 (半径0.9) にして, 隊列が1周して頭の進路に
    # 戻ってくる状態を作る. 地面では衝突, ジャンプ中は飛び越せる
    def setup():
        g = SnakeGame(seed=7)
        _set_length(g, 6)
        R = 0.9
        C = (0.0, -R)
        g.head = (0.0, 0.0)
        g.yaw = math.pi / 2                      # 東向き
        pts = []
        s = g.total_length_dist()
        while s >= 0.0:
            a = math.pi / 2 + s / R
            pts.append((C[0] + R * math.cos(a), C[1] + R * math.sin(a)))
            s -= 0.2
        g.trail = pts
        g.foods = {"A": (-11.0, -11.0), "C": (11.0, 11.0)}
        return g

    g = setup()
    g.update(DT)
    assert g.game_over and g.over_reason == "self", "地面では衝突するはず"

    g = setup()
    g.hop_y, g.hop_v = CLEAR_H + 0.5, 5.0        # 十分な高さで上昇中
    g.update(DT)
    assert not g.game_over, "跳んでいるのに隊列に衝突した"


def test_jump_over_food_misses_it():
    # 高く跳んで餌の真上を通過しても食べられない (飛び越し = 取り逃がし)
    g = SnakeGame(seed=31)
    g.penguins = []
    g.foods = {"A": (0.0, 2.5), "C": (-11.0, -11.0)}
    assert g.start_jump() is True
    crossed_high = False
    for _ in range(40):
        g.update(DT)
        d = math.hypot(g.head[0] - 0.0, g.head[1] - 2.5)
        if d < 1.05 and g.hop_y > FOOD_CLEAR_H:
            crossed_high = True
    assert crossed_high, "高いジャンプで餌の上を通過していない"
    assert g.score == 0 and g.length == 1, "飛び越したのに食べてしまった"
    assert g.foods["A"] == (0.0, 2.5), "餌が残っていない"
    # 地面で戻れば同じ餌を食べ直せる
    g.head = (0.0, 6.0)
    g.yaw = 0.0
    _set_length(g, g.length)
    for _ in range(30):
        g.update(DT)
        if g.score > 0:
            break
    assert g.score == 1 and g.length == 2


def test_penguin_spawn_interval():
    # 開始時に1体, 以後10秒ごとに1体ずつ増えることを確認
    g = SnakeGame(seed=11)
    assert len(g.penguins) == 1, len(g.penguins)
    g.penguins = [(-11.0, -11.0)]            # 衝突回避のため遠くへ移す
    for _ in range(300):                     # 10秒 (旋回して安全に周回)
        g.update(DT, turn=1.0)
    assert not g.game_over
    assert len(g.penguins) == 2, len(g.penguins)
    g.penguins = [(-11.0, -11.0)]
    for _ in range(300):                     # さらに10秒
        g.update(DT, turn=1.0)
    assert len(g.penguins) == 2, len(g.penguins)


def test_penguin_spawn_position_rules():
    g = SnakeGame(seed=12)
    _set_length(g, 5)
    for _ in range(30):
        g.spawn_penguin()
    assert len(g.penguins) == 31             # 開始時の1体 + 追加30体
    for x, z in g.penguins:
        assert inside_field(x, z, 1.5)
        assert math.hypot(x - g.head[0], z - g.head[1]) >= 3.0
    for i in range(len(g.penguins)):
        for j in range(i + 1, len(g.penguins)):
            d = math.hypot(g.penguins[i][0] - g.penguins[j][0],
                           g.penguins[i][1] - g.penguins[j][1])
            assert d >= 2.0


def test_penguin_never_spawns_in_front_zone():
    # 頭の正面 ±80°・距離8未満には出現しない (理不尽な激突の防止)
    import math as _m
    from snake_logic import (SPAWN_FRONT_SAFE_DIST, SPAWN_FRONT_COS,
                             forward)
    g = SnakeGame(seed=99)
    g.penguins = []
    g.head = (0.0, 0.0)
    g.yaw = 2.1                      # 適当な向きを正面とする
    fx, fz = forward(g.yaw)
    for _ in range(25):
        g.spawn_penguin()
    assert len(g.penguins) == 25     # 出現自体は成立している
    for x, z in g.penguins:
        dx, dz = x - g.head[0], z - g.head[1]
        d = _m.hypot(dx, dz)
        if d < SPAWN_FRONT_SAFE_DIST:
            cosang = (dx * fx + dz * fz) / d
            assert cosang <= SPAWN_FRONT_COS, (x, z, d, cosang)


def test_penguin_collision_is_miss():
    g = SnakeGame(seed=13)
    g.penguins = [(0.0, 4.0)]                # 進路の真上 (頭は -Z へ進行)
    for _ in range(30):
        g.update(DT)
        if g.game_over:
            break
    assert g.game_over and g.over_reason == "penguin", g.over_reason


def test_penguin_can_be_jumped_over():
    # 隊列と同じく, 十分高く跳んでいる間にペンギンを通過すれば回避
    g = SnakeGame(seed=14)
    g.penguins = [(0.0, 2.5)]
    assert g.start_jump() is True
    crossed = False
    for _ in range(60):
        g.update(DT)
        assert not g.game_over, "跳んでいるのにペンギンに衝突した"
        d = math.hypot(g.head[0] - 0.0, g.head[1] - 2.5)
        if d < 0.85 and g.hop_y > PENGUIN_CLEAR_H:
            crossed = True
    assert crossed, "ペンギンの真上を跳んで通過していない"


def test_penguin_low_hop_still_miss():
    # 跳び始めの低い高さでは回避できない (回避ライン未満ならミス)
    g = SnakeGame(seed=15)
    g.penguins = [(0.0, 4.8)]                # 間近に置いて低いうちに接触
    assert g.start_jump() is True
    for _ in range(30):
        g.update(DT)
        if g.game_over:
            break
    assert g.game_over and g.over_reason == "penguin", g.over_reason
    assert g.hop_y <= PENGUIN_CLEAR_H, g.hop_y


if __name__ == "__main__":
    test_continuous_not_grid(); print("ok continuous")
    test_start_with_one_unit(); print("ok start x1")
    test_units_follow_trail_and_phase(); print("ok trail+phase")
    test_both_foods_exist(); print("ok foods A+C")
    test_eat_each_kind_grows(); print("ok eat A/C grow")
    test_wall_game_over(); print("ok wall")
    test_wall_game_over_even_when_jumping(); print("ok wall while jumping")
    test_self_collision_game_over(); print("ok self")
    test_jump_physics_and_trace(); print("ok jump+trace")
    test_jump_over_own_queue_avoids_game_over(); print("ok jump over queue")
    test_jump_over_food_misses_it(); print("ok jump over food misses")
    test_penguin_spawn_interval(); print("ok penguin interval")
    test_penguin_spawn_position_rules(); print("ok penguin placement")
    test_penguin_never_spawns_in_front_zone(); print("ok penguin front zone")
    test_penguin_collision_is_miss(); print("ok penguin collision")
    test_penguin_can_be_jumped_over(); print("ok penguin jump over")
    test_penguin_low_hop_still_miss(); print("ok penguin low hop miss")
    print("ALL TESTS PASSED")
