"""Particulas 3D tipo fuegos artificiales con proyeccion y estelas.

Todo es funcion analitica de la edad (frame) -> loop perfecto de N frames, sin estado.
Salida: capas RGB aditivas sobre negro (luz pura), separadas en 'back' (detras del
centro del ramo, respecto a la camara) y 'front' (delante).

Uso:
  python fireworks.py --frame 120          # un frame de prueba -> assets/layers/
  python fireworks.py --all                # los 240 frames
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

W, H, FPS, N = 1920, 1080, 30, 240
ROOT = Path(__file__).resolve().parents[2]      # raiz del proyecto
ASSETS = ROOT / "assets"                        # recursos generados (camara, frames, capas, video)
LAYERS = ASSETS / "layers"

def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0

NEON, LIGHT, PEACH, WHITE = (hex_rgb(c) for c in ("#FF3D8B", "#FFB3D1", "#FFD2A8", "#FFE6F0"))
PALETTE = [NEON, NEON, LIGHT, PEACH, WHITE]

# ---------------------------------------------------------------- camara
class Camera:
    def __init__(self, path=ASSETS / "camera.json", w=W, h=H):
        c = json.loads(Path(path).read_text())
        self.set(c["position"], c["target"], c["hfov_deg"], c["bouquet_center"], w, h)

    def set(self, position, target, hfov_deg, center, w=W, h=H):
        """Tambien lo usa viewer.py para la camara orbital en vivo."""
        self.w, self.h = w, h
        self.pos = np.array(position, np.float64)
        self.center = np.array(center, np.float64)
        f = np.array(target, np.float64) - self.pos
        self.f = f / np.linalg.norm(f)
        r = np.cross(self.f, [0, 0, 1.0])
        self.r = r / np.linalg.norm(r)
        self.u = np.cross(self.r, self.f)
        self.focal = (w / 2) / np.tan(np.radians(hfov_deg) / 2)  # px
        self.center_depth = float((self.center - self.pos) @ self.f)

    def project(self, p):
        d = p - self.pos
        z = d @ self.f
        z = np.maximum(z, 1e-3)
        x = self.w / 2 + self.focal * (d @ self.r) / z
        y = self.h / 2 - self.focal * (d @ self.u) / z
        return x, y, z

# ---------------------------------------------------------------- escena
def build_scene(seed=7, n_fw=9, n_sparks=140, n_amb=70):
    rng = np.random.default_rng(seed)
    fws = []
    for i in range(n_fw):
        t0 = (i * N / n_fw + rng.uniform(-6, 6)) % N       # repartidos en el loop
        d = rng.normal(size=3)
        d[1] *= 0.6
        d /= np.linalg.norm(d)
        burst = np.array([0, 0, 1.0]) + d * rng.uniform(1.0, 1.7)
        launch = np.array([burst[0] * 0.8, burst[1] * 0.8, -0.5])
        t_rise = int(rng.integers(26, 40))
        life = int(rng.integers(70, 105))
        dirs = rng.normal(size=(n_sparks, 3))
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
        speed = rng.uniform(0.012, 0.034, n_sparks) * rng.choice([0.55, 1.0], n_sparks, p=[.3, .7])
        cols = np.array([PALETTE[j] for j in rng.integers(0, len(PALETTE), n_sparks)])
        fws.append(dict(t0=t0, burst=burst, launch=launch, t_rise=t_rise, life=life,
                        vel=dirs * speed[:, None], cols=cols,
                        k=rng.uniform(0.035, 0.06), g=rng.uniform(2.5e-4, 5e-4),
                        life_j=rng.uniform(0.7, 1.0, n_sparks)))
    amb = dict(base=np.array([0, 0, 1.0]) + rng.normal(size=(n_amb, 3)) * [0.9, 0.7, 0.8],
               ph=rng.uniform(0, 2 * np.pi, n_amb), n=rng.integers(1, 4, n_amb),
               rad=rng.uniform(0.03, 0.12, n_amb), cols=np.array([PALETTE[j] for j in rng.integers(0, 5, n_amb)]))
    return fws, amb

def make_firework(rng, t0, burst, launch, n_sparks=140, once=False):
    dirs = rng.normal(size=(n_sparks, 3))
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    speed = rng.uniform(0.012, 0.034, n_sparks) * rng.choice([0.55, 1.0], n_sparks, p=[.3, .7])
    return dict(t0=t0, burst=np.asarray(burst, float), launch=np.asarray(launch, float),
                t_rise=int(rng.integers(26, 40)), life=int(rng.integers(70, 105)),
                vel=dirs * speed[:, None], cols=np.array([PALETTE[j] for j in rng.integers(0, len(PALETTE), n_sparks)]),
                k=rng.uniform(0.035, 0.06), g=rng.uniform(2.5e-4, 5e-4),
                life_j=rng.uniform(0.7, 1.0, n_sparks), once=once)

def spark_pos(fw, a):
    """Posicion de las chispas a 'a' frames tras la explosion (a puede ser array)."""
    k, g = fw["k"], fw["g"]
    return fw["burst"] + fw["vel"] * ((1 - np.exp(-k * a)) / k) - np.array([0, 0, 0.5 * g * a * a])

def collect(f, fws, amb, trail=28, step=0.5):
    """Devuelve lista de puntos (pos[3], rgb[3]*intensidad, radio_mundo)."""
    P, C, R = [], [], []
    for fw in fws:
        age = f - fw["t0"] if fw.get("once") else (f - fw["t0"]) % N
        if age < 0:
            continue
        if age >= fw["t_rise"] + fw["life"]:
            continue
        if age < fw["t_rise"]:  # ascenso de la semilla con estela
            T = fw["t_rise"]
            for s in range(trail + 12):
                a = age - s * step
                if a < 0:
                    break
                u = a / T
                z = fw["launch"][2] + (fw["burst"][2] - fw["launch"][2]) * (1 - (1 - u) ** 2)
                p = np.array([fw["launch"][0] + (fw["burst"][0] - fw["launch"][0]) * u,
                              fw["launch"][1] + (fw["burst"][1] - fw["launch"][1]) * u, z])
                P.append(p); C.append(PEACH * (1.4 * (1 - s / (trail + 12)) ** 2)); R.append(0.022)
        else:
            a = age - fw["t_rise"]
            flash = np.exp(-a / 3.0) * 3.0                       # destello de explosion
            if flash > 0.05:
                P.append(fw["burst"]); C.append(WHITE * flash); R.append(0.25 * min(1, a / 2 + .3))
            for s in range(trail):
                aa = a - s * step
                if aa < 0:
                    break
                pos = spark_pos(fw, aa)
                life = fw["life"] * fw["life_j"]
                fade = np.clip(1 - aa / life, 0, 1) ** 1.6
                tf = (1 - s / trail) ** 1.8
                hot = np.exp(-aa / 12)[:, None] if np.ndim(aa) else np.exp(-aa / 12)
                col = fw["cols"] * (1 - 0.6 * hot) + WHITE * 0.6 * hot
                tw = 0.75 + 0.25 * np.sin(aa * 1.7 + np.arange(len(fade)))
                P.append(pos); C.append(col * (fade * tf * tw * 1.5)[:, None]); R.append(0.012 * (1 if s == 0 else 0.7))
    ang = 2 * np.pi * f / N
    pos = amb["base"] + amb["rad"][:, None] * np.stack(
        [np.cos(amb["n"] * ang + amb["ph"]), np.sin(amb["n"] * ang + amb["ph"]), np.sin(amb["n"] * ang + 2 * amb["ph"])], 1)
    tw = (0.5 + 0.5 * np.sin(amb["n"] * 2 * ang * 2 + amb["ph"])) ** 3
    P.append(pos); C.append(amb["cols"] * (0.9 * tw)[:, None]); R.append(0.008)
    return P, C, R

# ---------------------------------------------------------------- raster
def splat(buf, x, y, rgb):
    """Punto bilineal aditivo."""
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx = (x - x0)[:, None]; fy = (y - y0)[:, None]
    for dx, dy, w in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xi, yi = x0 + dx, y0 + dy
        ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
        np.add.at(buf, (yi[ok], xi[ok]), (rgb * w)[ok])

def bloom(core):
    """Nucleo nitido + halos gaussianos de varias escalas (HDR)."""
    out = core.copy()
    for sigma, gain in ((2.0, 1.6), (6.0, 1.1), (18.0, 0.8), (50.0, 0.5)):
        s = max(1, int(sigma // 6))
        small = core[::s, ::s] if s > 1 else core
        b = np.stack([gaussian_filter(small[..., c], sigma / s, mode="constant") for c in range(3)], -1)
        if s > 1:
            b = np.stack([np.kron(b[..., c], np.ones((s, s)))[:H, :W] for c in range(3)], -1)
        out += b.astype(np.float32) * gain * sigma * 0.55
    return out

def tonemap(x):
    return 1 - np.exp(-x)

def render_layers(f, cam, scene):
    P, C, R = collect(f, *scene)
    pos = np.concatenate([np.atleast_2d(p) for p in P])
    col = np.concatenate([np.atleast_2d(c) for c in C])
    rad = np.concatenate([np.full(len(np.atleast_2d(p)), r) for p, r in zip(P, R)])
    x, y, z = cam.project(pos)
    size = np.clip(rad * cam.focal / z, 0.6, 60)
    gain = np.where(rad > 0.1, size / 24, np.minimum(size, 3.0) / 1.5)
    col = col * gain[:, None] * 0.35        # 0.35: compensa el muestreo mas denso de estelas
    front = z < cam.center_depth
    out = {}
    for name, m in (("back", ~front), ("front", front)):
        buf = np.zeros((H, W, 3), np.float32)
        splat(buf, x[m], y[m], col[m])
        out[name] = tonemap(bloom(buf))
    return out

def save(img, path):
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    LAYERS.mkdir(exist_ok=True)
    cam, scene = Camera(), build_scene()
    frames = range(1, N + 1) if a.all else [a.frame or 120]
    for fr in frames:
        out = render_layers(fr - 1, cam, scene)
        for k, v in out.items():
            save(v, LAYERS / f"{k}_{fr:04d}.png")
        if fr % 20 == 0 or not a.all:
            print("frame", fr, flush=True)
