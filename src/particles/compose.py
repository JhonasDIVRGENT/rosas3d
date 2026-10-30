"""Composicion final: render de Blender (assets/render/frame_XXXX.png) + capas de particulas.

  back  -> detras del ramo (se ocluye con el alfa del render)
  front -> delante del ramo (suma aditiva)
Si el PNG de Blender no tiene alfa (fondo negro), se suma todo de forma aditiva.
Si un frame de render no existe se usa fondo negro (util para probar solo particulas).

  python compose.py --frame 120            # PNG de prueba -> out/test_0120.png
  python compose.py --all                  # mp4 -> out/rosas_loop.mp4
"""
import argparse
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from fireworks import H, N, W, FPS, LAYERS, ASSETS

RENDER, OUT = ASSETS / "render", ASSETS / "out"

def load(p):
    return np.asarray(Image.open(p).convert("RGBA"), np.float32) / 255.0

def glow(rgb, gain=0.22):
    """Bloom ligero del propio ramo (halos a 1/4 de resolucion)."""
    small = rgb[::4, ::4]
    acc = 0
    for s in (2, 6, 16):
        b = np.stack([gaussian_filter(small[..., c], s, mode="constant") for c in range(3)], -1)
        acc = acc + np.kron(b, np.ones((4, 4, 1), np.float32))[:H, :W] * (0.5 + s / 20)
    return rgb + acc * gain

def compose(fr):
    rp = RENDER / f"frame_{fr:04d}.png"
    back = load(LAYERS / f"back_{fr:04d}.png")[..., :3]
    front = load(LAYERS / f"front_{fr:04d}.png")[..., :3]
    if rp.exists():
        r = load(rp)
        rgb, a = r[..., :3], r[..., 3:4]
        rgb = glow(rgb * a if a.min() < 1 else rgb)
        out = (back * 1.8 * (1 - a) + rgb * 0.85 + front * 1.8) if a.min() < 1 else back * 1.8 + rgb * 0.85 + front * 1.8
    else:
        out = back + front
    return (np.clip(1 - np.exp(-out * 0.9), 0, 1) * 255 + 0.5).astype(np.uint8)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if a.all:
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "16",
               "-pix_fmt", "yuv420p", str(OUT / "rosas_loop.mp4")]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for fr in range(1, N + 1):
            p.stdin.write(compose(fr).tobytes())
            if fr % 20 == 0:
                print("compose", fr, flush=True)
        p.stdin.close(); p.wait()
    else:
        fr = a.frame or 120
        Image.fromarray(compose(fr)).save(OUT / f"test_{fr:04d}.png")
