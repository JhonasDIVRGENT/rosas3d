"""Visor interactivo en tiempo real (pygame-ce) del motor de particulas.

Controles: arrastrar = orbitar | rueda = zoom | clic = lanzar fuego artificial |
           Espacio = pausa | R = reiniciar camara | Esc = salir
El anillo con espinas es un marcador 3D provisional hasta tener el de Blender.
"""
import os
import time

import numpy as np
import pygame

from fireworks import FPS, N, Camera, build_scene, collect, make_firework

VW, VH = 1280, 720
SIZES = (3, 5, 9, 15, 25, 41, 67)
_cache = {}

def sprite(rgb, px):
    key = (tuple(np.round(np.clip(rgb, 0, 1) * 10).astype(int)), px)
    if key not in _cache:
        y, x = np.mgrid[:px, :px] - (px - 1) / 2
        g = np.exp(-(x * x + y * y) / (2 * (px / 5.0) ** 2))
        arr = (g[..., None] * np.clip(rgb, 0, 1) * 255).astype(np.uint8)
        _cache[key] = pygame.surfarray.make_surface(arr.swapaxes(0, 1))
    return _cache[key]

def ring_points(center, n=160, radius=1.25, tilt_deg=20.0):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    p = np.stack([radius * np.cos(t), 0.6 * radius * np.sin(t), np.zeros(n)], 1)
    a = np.radians(tilt_deg)
    rot = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    return p @ rot.T + center

def main():
    pygame.init()
    scr = pygame.display.set_mode((VW, VH))
    pygame.display.set_caption("rosas3d - visor interactivo")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 14)
    cam = Camera(w=VW, h=VH)
    center = cam.center.copy()
    home = dict(yaw=0.0, pitch=0.28, dist=7.4)
    st = dict(home)
    fws, amb = build_scene()
    rng = np.random.default_rng()
    shots = []                                  # fuegos lanzados con clic (age relativo a 'f')
    ring = ring_points(center)
    f, paused, drag, moved = 0.0, False, None, 0.0
    last = time.time()

    def set_cam():
        d = st["dist"]
        pos = center + d * np.array([np.sin(st["yaw"]) * np.cos(st["pitch"]),
                                     -np.cos(st["yaw"]) * np.cos(st["pitch"]), np.sin(st["pitch"])])
        cam.set(pos, center, 35.0, center, VW, VH)

    def draw_points(P, C, R):
        pos = np.concatenate([np.atleast_2d(p) for p in P])
        col = np.concatenate([np.atleast_2d(c) for c in C])
        rad = np.concatenate([np.full(len(np.atleast_2d(p)), r) for p, r in zip(P, R)])
        x, y, z = cam.project(pos)
        size = np.clip(rad * cam.focal / z * 2.2, 2, 67)
        ok = (x > -70) & (x < VW + 70) & (y > -70) & (y < VH + 70) & (col.max(1) > 0.03)
        px = np.asarray(SIZES)[np.abs(size[ok, None] - np.asarray(SIZES)).argmin(1)]
        cm = col[ok].max(1, keepdims=True)
        tint = col[ok] / np.maximum(cm, 1) * np.minimum(cm * 0.9, 1.0)
        scr.blits([(sprite(c, int(q)), (xi - q / 2, yi - q / 2), None, pygame.BLEND_ADD)
                   for xi, yi, q, c in zip(x[ok], y[ok], px, tint)], False)

    set_cam()
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                paused = not paused
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                st.update(home); set_cam()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                drag, moved = e.pos, 0.0
            elif e.type == pygame.MOUSEMOTION and drag:
                dx, dy = e.rel
                moved += abs(dx) + abs(dy)
                st["yaw"] -= dx * 0.006
                st["pitch"] = float(np.clip(st["pitch"] + dy * 0.006, -1.2, 1.4))
                set_cam()
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                if moved < 5:                  # clic sin arrastre: lanzar fuego en ese rayo
                    mx, my = e.pos
                    d = cam.f + cam.r * (mx - VW / 2) / cam.focal - cam.u * (my - VH / 2) / cam.focal
                    burst = cam.pos + d / np.linalg.norm(d) * cam.center_depth / max(d @ cam.f / np.linalg.norm(d), 1e-3)
                    launch = burst * [1, 1, 0] + [0, 0, -0.5]
                    shots.append(make_firework(rng, f, burst, launch, once=True))
                drag = None
            elif e.type == pygame.MOUSEWHEEL:
                st["dist"] = float(np.clip(st["dist"] * (0.9 ** e.y), 2.0, 20.0)); set_cam()

        now = time.time()
        if not paused:
            f += (now - last) * FPS
        last = now
        scr.fill((0, 0, 0))
        P, C, R = collect(f % N, fws, amb, trail=14, step=1.0)
        shots[:] = [s for s in shots if f - s["t0"] < s["t_rise"] + s["life"]]
        for s in shots:
            p2, c2, r2 = collect(f, [s], dict(amb, base=amb["base"][:0], ph=amb["ph"][:0], n=amb["n"][:0],
                                              rad=amb["rad"][:0], cols=amb["cols"][:0]), trail=14, step=1.0)
            P += p2; C += c2; R += r2
        ring_c = np.array([1.0, 0.24, 0.55]) * 0.9
        P.append(ring); C.append(np.tile(ring_c, (len(ring), 1))); R.append(0.02)
        draw_points(P, C, R)
        scr.blit(font.render(f"{clock.get_fps():4.0f} fps | arrastrar: orbitar | rueda: zoom | clic: fuego | espacio: pausa | R: reset",
                             True, (160, 120, 140)), (8, 6))
        pygame.display.flip()
        if os.environ.get("VIEWER_SHOT") and f > 100:   # captura sin interaccion (pruebas)
            pygame.image.save(scr, os.environ["VIEWER_SHOT"])
            running = False
        clock.tick(60)
    pygame.quit()

if __name__ == "__main__":
    main()
