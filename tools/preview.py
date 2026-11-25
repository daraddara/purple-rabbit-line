"""実機 (pyxel.cube) の画面を撮影してプレビュー PNG を作る. v1.1

Cube版はエンジンが描くため, プレビューも実画面のキャプチャにする.
Xvfb + ffmpeg (x11grab) が必要:

    xvfb-run -a --server-args="-screen 0 800x600x24" python tools/preview.py

出力は previews/ フォルダ:
- preview.png : 3場面 (スタート / 食べた直後の演出 / ジャンプの波)
- preview_start.png : スタート場面
- preview_characters.png : リス・うさぎ・オレンジの子の正面
"""
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "previews")
os.makedirs(OUT, exist_ok=True)

import pyxel
from PIL import Image

from models import CUSTOM_COLORS
from snake_logic import SnakeGame, forward
from cube_render import Scene, CamFollow

WIN = (256, 256)
CROP = (270, 170, 530, 430)      # 800x600画面内のウィンドウ位置


def grab(path):
    disp = os.environ.get("DISPLAY", ":99")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab",
                    "-video_size", "800x600", "-i", disp,
                    "-frames:v", "1", path], check=False)
    im = Image.open(path).crop(CROP)
    im.save(path)
    return im


class Stage:
    """場面を順に進める小さな状態機械."""

    def __init__(self):
        pyxel.init(*WIN, title="preview")
        for idx, rgb in CUSTOM_COLORS.items():
            pyxel.colors[idx] = rgb
        self.game = SnakeGame(seed=7)
        self.scene = Scene(self.game)
        self.follow = CamFollow()
        self.shots = []
        self.plan = [
            (self.setup_start, 14, "start"),
            (self.setup_effect, 8, "effect"),
            (self.setup_wave, 999, "wave"),
            (self.setup_chars, 8, "chars"),
        ]
        self.step = 0
        self.wait = 0
        self.plan[0][0]()

    # --- 場面セットアップ ---
    def _reset_stage(self):
        self.game.reset()
        self.follow.snap(self.game)
        self.scene.set_camera(self.follow.pos, self.follow.target)
        self.scene.effects = []

    def setup_start(self):
        self._reset_stage()
        self.game.penguins = [(6.5, -6.0)]   # 開始時の1体を見える位置に
        fx, fz = forward(self.game.yaw)
        self.game.foods["A"] = (self.game.head[0] + fx * 9.0,
                                self.game.head[1] + fz * 9.0)
        self.game.foods["C"] = (-3.5, -4.0)

    def setup_effect(self):
        self._reset_stage()
        self.game.penguins = [(6.5, -6.0)]
        self.game.foods["A"] = (2.5, -3.5)
        self.game.foods["C"] = (-3.5, -3.5)
        self.scene.effects = [{"kind": "A", "pos": (2.5, -3.5), "age": 8}]

    def setup_wave(self):
        self._reset_stage()
        self.wave_phase = "grow"
        self._placed_score = -1

    def setup_chars(self):
        self._reset_stage()
        g = self.game
        g.penguins = []                      # キャラ確認用にペンギンは除く
        g.head = (0.0, 0.0)
        g.yaw = 0.0                          # 固定カメラ (-Z側) の方を向く
        fx, fz = forward(g.yaw)
        g.trail = []
        d = 4.0
        while d >= 0.0:
            g.trail.append((g.head[0] - fx * d, g.head[1] - fz * d))
            d -= 0.2
        g.foods["A"] = (2.1, 1.4)
        g.foods["C"] = (-2.1, 1.4)
        # 正面用の固定カメラ (シーンのカメラを直接設定し, followしない)
        self.scene.set_camera((0.0, 1.5, -5.4), (0.0, 0.9, 0.0))
        self.fixed_cam = True

    # --- 進行 ---
    def update(self):
        name = self.plan[self.step][2]
        done = False
        if name == "wave":
            done = self._update_wave()
        elif name != "chars":
            self.game.update(1 / 30)
            self.follow.follow(self.game)
            self.scene.set_camera(self.follow.pos, self.follow.target)
        self.scene.frame = pyxel.frame_count
        self.scene.sync()
        self.wait += 1
        _setup, frames, _name = self.plan[self.step]
        if done or self.wait >= frames:
            self.shots.append(grab(f"/tmp/preview_{name}.png"))
            self.step += 1
            self.wait = 0
            if self.step >= len(self.plan):
                self.finish()
                pyxel.quit()
                return
            self.plan[self.step][0]()

    def _update_wave(self):
        """育ててから跳ぶ. 戻り値 True で撮影タイミング."""
        g = self.game
        if self.wave_phase == "grow":
            if g.score != self._placed_score:
                self._placed_score = g.score
                fx, fz = forward(g.yaw)
                kind = "A" if g.score % 2 == 0 else "C"
                g.foods[kind] = (g.head[0] + fx * 3.0, g.head[1] + fz * 3.0)
            g.update(1 / 30, turn=0.3)       # 円を描いて壁を避ける
            if g.score >= 5:
                g.foods["A"] = (-10.0, 10.0)
                g.foods["C"] = (10.0, 10.0)
                g.start_jump()
                self.wave_phase = "jump"
                self.wait = -40              # 跳んでから40フレーム後に撮る
        else:
            g.update(1 / 30, turn=0.3)
            if self.wait >= 0:
                return True
        self.follow.follow(g)
        self.scene.set_camera(self.follow.pos, self.follow.target)
        return False

    def finish(self):
        start, effect, wave, chars = self.shots
        sheet = Image.new("RGB", (WIN[0] * 3, WIN[1]), (0, 0, 0))
        for i, p in enumerate((start, effect, wave)):
            sheet.paste(p, (WIN[0] * i, 0))
        sheet.save(os.path.join(OUT, "preview.png"))
        start.save(os.path.join(OUT, "preview_start.png"))
        chars.save(os.path.join(OUT, "preview_characters.png"))
        print("wrote preview.png / preview_start.png / preview_characters.png")

    def draw(self):
        self.scene.draw(0, 0, *WIN)
        g = self.game
        pyxel.text(8, 8, f"SCORE {g.score}", 7)


if __name__ == "__main__":
    stage = Stage()
    pyxel.run(stage.update, stage.draw)
