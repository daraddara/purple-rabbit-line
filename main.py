"""
PURPLE RABBIT LINE — 紫うさぎの隊列スネーク (pyxel.cube版)

正式タイトルは「PURPLE RABBIT LINE」。「3D SNAKE」は開発中の
呼称で, 画面には出さず識別用にだけ残す (CODENAME 定数・起動ログ・
README 冒頭)。

- プレイヤーは紫うさぎの隊列.
  先頭が歩き, 後続は軌跡を辿って1列に歩行する (歩行アニメ付き)
- 餌は「リス」と「オレンジの子」の3Dモデルが同時に
  1体ずつ存在し, どちらを食べても隊列が1体伸びる
- 移動はグリッド単位ではなく連続的: ←→で滑らかに旋回
- SPACE でジャンプ. 後続も距離遅れでトレースして波のように跳ぶ.
  高く跳んでいる間は自分の隊列を飛び越せるが, 壁は跳んでも
  越えられない高さで, 激突するとゲームオーバー.
  高く跳んでいる間は餌も食べられない (飛び越すと取り逃がす)
- エリアは正12角形で, 電車が1辺に1両ずつループ状にグルッと
  囲んでいる. 地面は緑と白のチェッカー
  (銀の車体・黒い窓・緑色のドア). 車両が壁の役割をする.
  カメラは三人称視点で先頭の後ろから追従する. 右上にミニマップ
  も表示する
- 障害物のペンギンが, 開始時に 1 体, 以後 10 秒ごとに
  1 体ずつ出現する. 触れるとミス. 隊列と同じくジャンプで
  飛び越してかわせる (ペンギン用の回避ラインは低めで,
  タイミングに余裕あり)
- モデルの縁取り (Pyxel 3.0.4 の Node.outline) は常時 ON
  (切り替えキーは無い)
- 状態遷移: タイトル -> 開始待機 (初期配置を表示して1秒)
  -> ゲーム中 -> ゲームオーバー -> タイトル
  (ゲームオーバーから直接リスタートはしない)

実行:  pip install pyxel
       python main.py

操作 (カーソルキーと WASD の両方に対応):
  ENTER / SPACE : スタート / ゲームオーバー画面ではタイトルへ
  ← → または A/D : 旋回
  SPACE (プレイ中) : ジャンプ
  ↑/W (押している間) : 加速    ↓/S : 減速
  M      : サウンド ON/OFF

サウンド:
  BGM はチップチューン風ループ (メロディ/ベース/リズムの3ch,
  SE専用の ch0 と分けてあるので効果音で BGM が途切れない).
  効果音は リンゴ取得・スタート・ゲームオーバー・旋回開始.
"""
import math

import pyxel
from models import CUSTOM_COLORS
from cube_render import Scene, CamFollow, TRAIN_T, EFFECT_FRAMES
from snake_logic import (SnakeGame, FIELD_SIDES, FIELD_APOTHEM)

VERSION = "0.07"                  # 表示はこの定義値を参照する (直書きしない)
GAME_TITLE = "PURPLE RABBIT LINE"  # 正式タイトル (タイトルロゴと窓タイトル)
CODENAME = "3D SNAKE"  # 開発中の呼称. 画面には出さず識別用に残す

W, H = 256, 256
FPS = 30

# サウンド番号. BGM は ch1-3, 効果音は ch0 (SE_CH) で鳴らす
SE_CH = 0
SND_EAT, SND_OVER, SND_START, SND_TURN, SND_JUMP = 0, 1, 2, 3, 7
SND_ALERT = 8                    # ペンギン出現の警告音
ALERT_FRAMES = 60                # 警告表示の長さ (2秒)
SND_MELODY, SND_BASS, SND_RHYTHM = 4, 5, 6


def init_sound():
    """BGM (ループ) と効果音を定義する. 全パート 896 tick で揃え,
    ループの継ぎ目でずれないようにしてある."""
    # --- 効果音 ---
    pyxel.sounds[SND_EAT].set(           # リンゴ取得: 上昇アルペジオ
        notes="e3g3c4e4", tones="s", volumes="5", effects="nnnf", speed=6)
    pyxel.sounds[SND_OVER].set(          # ゲームオーバー: 下降フレーズ
        notes="c3b2a2g2f2e2d2c2", tones="p", volumes="5",
        effects="nnnnnnnf", speed=11)
    pyxel.sounds[SND_START].set(         # スタート
        notes="c3e3g3c4", tones="s", volumes="5", effects="nnnf", speed=6)
    pyxel.sounds[SND_TURN].set(          # 旋回開始: 短いブリップ
        notes="g2", tones="s", volumes="2", effects="f", speed=3)
    pyxel.sounds[SND_JUMP].set(          # ジャンプ: スライドで上昇音
        notes="c3g3", tones="s", volumes="4", effects="s", speed=5)
    pyxel.sounds[SND_ALERT].set(         # ペンギン出現: 2連ビープ
        notes="a3ra3r", tones="p", volumes="6", effects="nnnn", speed=5)
    # --- BGM ---
    melody = (
        "c3e3g3e3a3g3e3c3d3e3g3a3g3e3d3r"
        "e3g3a3g3e3d3c3d3e3g3e3d3c3d3e3r"
        "f3a3a3f3g3b3b3g3a3g3e3c3d3e3d3r"
        "c3e3g3e3a3g3e3d3e3g3d3e3c3rrr"
    )                                    # 64音 x speed14 = 896 tick
    pyxel.sounds[SND_MELODY].set(
        notes=melody, tones="s", volumes="3", effects="n", speed=14)
    bass_seg = "c2g1c2g1f1g1c2g1"
    bass = bass_seg * 2 + "a1g1f1g1c2g1c2g1" + bass_seg   # 32音 x 28 = 896
    pyxel.sounds[SND_BASS].set(
        notes=bass, tones="t", volumes="5", effects="n", speed=28)
    pyxel.sounds[SND_RHYTHM].set(        # ノイズのリズム 64音 x 14 = 896
        notes="f0ra4r" * 16, tones="n", volumes="6020" * 16,
        effects="f", speed=14)
    pyxel.musics[0].set([], [SND_MELODY], [SND_BASS], [SND_RHYTHM])


def _make_logo():
    """タイトルロゴ画像. 紫文字に黒フチ, 背景 (色1) は透過させる.
    3倍に拡大した画像を返す (blt の scale は使わず, 画素コピーで
    拡大するので寸法が正確)."""
    src = pyxel.Image(64, 18)
    src.cls(1)
    for s, y in (("PURPLE RABBIT", 1), ("LINE", 10)):
        x = (64 - len(s) * 4) // 2
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            src.text(x + dx, y + dy, s, 0)
        src.text(x, y, s, 11)
    img = pyxel.Image(64 * 3, 18 * 3)
    img.cls(1)
    for y in range(18):
        for x in range(64):
            c = src.pget(x, y)
            if c != 1:
                img.rect(x * 3, y * 3, 3, 3, c)
    return img


def _stage_title_cast(game):
    """タイトル画面専用の配置: キャストを横一列に整列させる.

    本編の初期配置とは別の見せ方で, うさぎ隊列・リス (A)・
    オレンジの子 (C)・ペンギンが集合写真のように寄って並ぶ.
    カメラが -Z 側から +Z を見るため, 画面の左右はワールドの
    X と逆になる. ペンギンは先頭の方を向く仕様なので, 先頭の
    奥に置くと顔がカメラ側を向く.
    """
    game.reset()
    pts = [(0.0, 1.05), (-0.8, 2.1)]  # うさぎ (先頭+1体, 中央)
    game.length = len(pts)
    game.head = pts[0]
    game.yaw = 0.0
    (lx, lz), (px, pz) = pts[-1], pts[-2]
    dx, dz = lx - px, lz - pz
    n = math.hypot(dx, dz) or 1.0
    ext = [(lx + dx / n * d, lz + dz / n * d) for d in (0.2, 1.2, 2.2, 3.2)]
    game.trail = list(reversed((pts + ext)[1:]))
    game.distance = 0.0
    game.hop_hist = [(-10.0, 0.0), (0.0, 0.0)]
    game.foods["A"] = (-2.1, 1.85)    # リス (画面右)
    game.foods["C"] = (2.3, 1.8)      # オレンジの子 (画面左)
    # ペンギンは先頭の奥でカメラ寄りを向き, 子と重ならない位置
    # (顔が正面から見える)
    game.penguins = [(1.0, 3.05)]


def _fmt_time(sec):
    """経過秒を M:SS 表記にする."""
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


class App:
    def __init__(self):
        pyxel.init(W, H, title=GAME_TITLE, fps=FPS)
        for idx, rgb in CUSTOM_COLORS.items():
            pyxel.colors[idx] = rgb
        init_sound()
        self.logo = _make_logo()
        print(f"3D Snake ver {VERSION} - if you don't hear "
              "the BGM, check this version is the one running")
        self.game = SnakeGame(seed=None)
        # タイトル専用シーン (キャスト整列, 本編とは別のゲーム状態)
        self.title_game = SnakeGame(seed=7)
        _stage_title_cast(self.title_game)
        self.title_scene = Scene(self.title_game)
        self.title_scene.set_camera((0, 1.5, -5.6), (0, 0.8, 1.1))
        self.title_scene.effects = []
        self.follow = CamFollow()
        self.follow.snap(self.game)
        self.scene = Scene(self.game)
        self.scene.set_camera(self.follow.pos, self.follow.target)
        self.state = "title"           # title / ready / play / over
        self.over_frame = 0            # ゲームオーバーになったフレーム
        self.ready_frame = 0           # 開始待機に入ったフレーム
        self.best = 0
        self.new_best = False          # 今回のプレーでベスト更新したか
        self.frame = 0
        self.prev_turn = 0
        self.effects = []              # 食べた時の演出 [{kind, pos, age}]
        self._seen_eat_frame = -1
        self.alert_frame = -1          # ペンギン出現警告の開始フレーム
        self.alert_pos = None          # 出現したペンギンの位置
        self.muted = False
        self.music_on = False
        self._start_bgm()
        pyxel.run(self.update, self.draw)

    # ---------- サウンド ----------
    def _start_bgm(self):
        if not self.muted:
            pyxel.playm(0, loop=True)
            self.music_on = True

    def _se(self, snd):
        if not self.muted:
            pyxel.play(SE_CH, snd)

    def _toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            pyxel.stop()
            self.music_on = False
        elif self.state not in ("over", "ready"):
            self._start_bgm()

    # ---------- 更新 ----------
    def update(self):
        if pyxel.btnp(pyxel.KEY_M):
            self._toggle_mute()
        self.frame += 1
        if self.state == "title":
            if (pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE)
                    or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_START)
                    or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_A)):
                # いきなり動かず, まず初期配置を見せる開始待機へ
                self.state = "ready"
                self.ready_frame = self.frame
                self.alert_frame = -1
                self.alert_pos = None
            self.title_scene.frame = self.frame
            self.title_scene.sync()
            return
        if self.state == "ready":
            # 初期配置が見える状態で1秒待機してから開始する
            # (タイトルが消えた瞬間, 目の前のペンギンに激突するのを防ぐ)
            if self.frame - self.ready_frame >= FPS:
                self.state = "play"
                self.prev_turn = 0
                if not self.music_on and not self.muted:
                    self._start_bgm()
                self._se(SND_START)
            self._sync_camera()
            return
        if self.state == "over":
            # ゲームオーバーからは必ずタイトルへ戻る
            # (タイトル -> ゲーム中 -> ゲームオーバー -> タイトル)
            # 直後1秒はキーを受け付けない (ジャンプの連打で画面が
            # 一瞬で消えるのを防ぐ). 戻るキーは ENTER / R のみで,
            # SPACE (ジャンプ) では戻らない
            if (self.frame - self.over_frame >= FPS
                    and (pyxel.btnp(pyxel.KEY_RETURN)
                         or pyxel.btnp(pyxel.KEY_R)
                         or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_START)
                         or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_A))):
                self.game.reset()
                self.effects = []
                self._seen_eat_frame = -1
                self.follow.snap(self.game)
                self.scene.set_camera(self.follow.pos, self.follow.target)
                self.state = "title"
                self._sync_camera()
            return
        turn = 0
        if (pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A)
                or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT)):
            turn -= 1
        if (pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D)
                or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)):
            turn += 1
        if (pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.KEY_J)
                or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_A)):
            if self.game.start_jump():
                self._se(SND_JUMP)
        if turn != 0 and turn != self.prev_turn:
            self._se(SND_TURN)           # 旋回を始めた瞬間だけ鳴らす
        self.prev_turn = turn
        speed_mul = 1.0
        if (pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.KEY_W)
                or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_UP)):
            speed_mul = 1.45
        if (pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S)
                or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)):
            speed_mul = 0.6
        prev_score = self.game.score
        prev_penguins = len(self.game.penguins)
        self.game.update(1.0 / FPS, turn=turn, speed_mul=speed_mul)
        if len(self.game.penguins) > prev_penguins:
            # ペンギン出現: 警告音 + 画面表示 + ミニマップ点滅
            self.alert_frame = self.frame
            self.alert_pos = self.game.penguins[-1]
            self._se(SND_ALERT)
        if self.game.score > prev_score:
            self._se(SND_EAT)
            le = self.game.last_eaten
            if le is not None and le[2] != self._seen_eat_frame:
                self._seen_eat_frame = le[2]
                self.effects.append({"kind": le[0], "pos": le[1], "age": 0})
        for eff in self.effects:
            eff["age"] += 1
        self.effects = [e for e in self.effects if e["age"] <= EFFECT_FRAMES]
        self._sync_camera()
        if self.game.game_over:
            self.state = "over"
            self.over_frame = self.frame
            self.new_best = self.game.score > self.best
            self.best = max(self.best, self.game.score)
            pyxel.stop()                 # BGMを止めてからジングル
            self.music_on = False
            self._se(SND_OVER)

    def _sync_camera(self):
        self.follow.follow(self.game)
        self.scene.set_camera(self.follow.pos, self.follow.target)
        self.scene.frame = self.frame
        self.scene.effects = self.effects
        self.scene.sync()

    # ---------- 描画 ----------
    def draw(self):
        if self.state == "title":
            # タイトル専用シーン: キャスト整列 (ミニマップ・スコアなし)
            self.title_scene.draw(0, 0, W, H)
            # タイトルロゴ (紫文字) と緑の帯
            pyxel.blt(32, 14, self.logo, 0, 0, 192, 54, colkey=1)
            pyxel.rect(32, 74, 192, 3, 8)
            self._center_texts([
                (200, "EAT A + C - GROW LONGER", 7),
                (211, "DON'T HIT THE WALL OR YOURSELF", 7),
                (222, "ENTER: START", 10),
                (233, "ARROWS/WASD: TURN + BOOST   M: SOUND", 6),
            ], top=192, height=56, x=8, width=240)
            s = f"VER {VERSION}"
            self._text(W - 6 - len(s) * 4, H - 14, s, 6)
            return
        # 3Dシーン (pyxel.cube, 深度バッファ付き). 背景はカメラの
        # clear_color (空色) で塗られる
        self.scene.draw(0, 0, W, H)
        self._hud()
        if (self.state == "play" and self.alert_frame >= 0
                and self.frame - self.alert_frame < ALERT_FRAMES):
            s = "PENGUIN!"
            self._text(128 - len(s) * 2, 8, s, 13)
        if self.state == "ready":
            s = "READY..."
            pyxel.text(128 - len(s) * 2 + 1, 111, s, 0)
            pyxel.text(128 - len(s) * 2, 110, s, 7)
        elif self.state == "over":
            reason = {"wall": "YOU HIT THE WALL",
                      "penguin": "YOU HIT THE PENGUIN"}.get(
                          self.game.over_reason, "YOU HIT YOURSELF")
            if self.new_best:
                best_line = (153, "NEW BEST!", 10)
            elif self.game.score < self.best:
                gap = self.best - self.game.score
                best_line = (153, f"{gap} PTS TO BEST", 6)
            elif self.best > 0:
                best_line = (153, "TIED WITH BEST", 6)
            else:
                best_line = None
            items = [
                (98, "GAME OVER", 13),
                (114, reason, 7),
                (128, f"SCORE {self.game.score}   BEST {self.best}", 7),
                (140, f"TIME {_fmt_time(self.game.elapsed)}", 7),
            ]
            if best_line is not None:
                items.append(best_line)
            items.append((169, "ENTER: TITLE", 10))
            self._center_texts(items)
        if self.state == "over":
            s = f"VER {VERSION}"
            self._text(W - 6 - len(s) * 4, H - 14, s, 6)


    def _center_texts(self, items, top=88, height=106, x=28, width=200):
        pyxel.rect(x, top, width, height, 0)
        pyxel.rectb(x, top, width, height, 7)
        for y, s, col in items:
            pyxel.text(128 - len(s) * 2, y, s, col)

    @staticmethod
    def _text(x, y, s, col):
        # 明るい背景 (空・砂) でも読めるよう, 黒い影を落としてから描く
        pyxel.text(x + 1, y + 1, s, 0)
        pyxel.text(x, y, s, col)

    def _hud(self):
        g = self.game
        # LENGTH と A/C の取得数は表示しない (内部データは保持している)
        self._text(8, 8, f"SCORE {g.score}", 7)
        # BESTは常時表示. プレイ中に記録を抜いたらその場で反映する
        self._text(8, 18, f"BEST {max(self.best, g.score)}", 7)
        # 生き延びた時間 (プレイ中のみ進む game.elapsed)
        self._text(8, 28, f"TIME {_fmt_time(g.elapsed)}", 7)
        y = 38
        if g.speed_factor > 1.0:
            # スコア連動で上がった基本速度の倍率
            self._text(8, y, f"SPD x{g.speed_factor:.2f}", 7)
            y += 10
        if self.muted:
            self._text(8, y, "SOUND OFF (M)", 13)
            y += 10
        self._minimap()

    def _minimap(self):
        """右上: エリア全体を上から見たミニマップ (12角形)."""
        import math as _math
        S = 46
        x0, y0 = W - S - 8, 8
        cx, cy = x0 + S / 2, y0 + S / 2
        extent = (FIELD_APOTHEM + TRAIN_T) / _math.cos(_math.pi / FIELD_SIDES)
        scale = (S / 2) / (extent + 0.6)
        pyxel.rect(x0 - 1, y0 - 1, S + 2, S + 2, 0)
        pyxel.rectb(x0 - 1, y0 - 1, S + 2, S + 2, 6)
        pyxel.rect(x0, y0, S, S, 10)

        def mp(x, z):
            return (cx + x * scale, cy + z * scale)

        def ring(apothem, col):
            rv = apothem / _math.cos(_math.pi / FIELD_SIDES)
            pts = []
            for k in range(FIELD_SIDES + 1):
                a = (k + 0.5) * 2 * _math.pi / FIELD_SIDES
                pts.append((cx + rv * _math.cos(a) * scale,
                            cy + rv * _math.sin(a) * scale))
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                pyxel.line(ax, ay, bx, by, col)

        ring(FIELD_APOTHEM + TRAIN_T, 8)     # 車両の外周 (緑)
        ring(FIELD_APOTHEM, 7)               # フィールド境界

        for kind, col in (("A", 9), ("C", 14)):
            pos = self.game.foods.get(kind)
            if pos is not None:
                ax, ay = mp(*pos)
                pyxel.circ(ax, ay, 2, col)
        for pxz in self.game.penguins:
            ax, ay = mp(*pxz)
            pyxel.circ(ax, ay, 2, 0)         # ペンギンは黒丸
            if (self.alert_pos is not None and pxz == self.alert_pos
                    and self.alert_frame >= 0
                    and self.frame - self.alert_frame < ALERT_FRAMES
                    and (self.frame // 6) % 2 == 0):
                pyxel.circb(ax, ay, 4, 13)   # 出現直後は赤い輪が点滅
        units = self.game.unit_positions()
        for ux, uz, _yaw, _kind in reversed(units):
            px, py = mp(ux, uz)
            pyxel.circ(px, py, 1, 11)
        hx, hy = mp(*self.game.head)
        pyxel.circ(hx, hy, 2, 7)


if __name__ == "__main__":
    App()
