// Fuegos artificiales en tiempo real: cohetes que suben y explotan en chispas con estela.
// Port en vivo del motor de particles/fireworks.py (arrastre, gravedad, estelas, paleta rosa).
import * as THREE from "three";

const PALETTE = ["#ff3d8b", "#ff3d8b", "#ffb3d1", "#ffd2a8", "#ffe6f0", "#ff6fa8"].map((c) => new THREE.Color(c));
const MAX = 16000;          // puntos dibujables por frame (cabezas + estelas)
const TRAIL = 7;            // posiciones guardadas por chispa
const GRAVITY = 0.95;
const DRAG = 1.25;

const vertexShader = /* glsl */ `
  uniform float uScale;
  attribute float aSize;
  attribute float aAlpha;
  attribute vec3 aColor;
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = max(aSize * uScale / -mv.z, 1.0);
    gl_Position = projectionMatrix * mv;
    vColor = aColor;
    vAlpha = aAlpha;
  }`;

const fragmentShader = /* glsl */ `
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5) * 2.0;
    float a = (exp(-d * d * 7.0) + 0.3 * exp(-d * d * 1.8)) * vAlpha;
    if (a < 0.004) discard;
    gl_FragColor = vec4(vColor * a * 3.2, a);   // HDR: lo brillante alimenta el bloom
  }`;

export function makePointMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: { uScale: { value: 500 } },
    vertexShader, fragmentShader,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
}

const rand = (a, b) => a + Math.random() * (b - a);
const pick = (arr) => arr[(Math.random() * arr.length) | 0];

export class Fireworks {
  constructor(scene, camera) {
    this.camera = camera;
    this.pos = new Float32Array(MAX * 3);
    this.col = new Float32Array(MAX * 3);
    this.size = new Float32Array(MAX);
    this.alpha = new Float32Array(MAX);
    const g = (this.geo = new THREE.BufferGeometry());
    g.setAttribute("position", new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute("aColor", new THREE.BufferAttribute(this.col, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute("aSize", new THREE.BufferAttribute(this.size, 1).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute("aAlpha", new THREE.BufferAttribute(this.alpha, 1).setUsage(THREE.DynamicDrawUsage));
    g.setDrawRange(0, 0);
    this.material = makePointMaterial();
    this.points = new THREE.Points(g, this.material);
    this.points.frustumCulled = false;
    scene.add(this.points);

    // el destello de cada explosion ilumina el ramo
    this.light = new THREE.PointLight(0xff7fb0, 0, 40, 1.6);
    scene.add(this.light);
    this.flash = 0;

    this.rockets = [];
    this.sparks = [];
    this.autoTimer = 1.2;
  }

  setScale(px) { this.material.uniforms.uScale.value = px; }

  /** Lanza un cohete que explota en `target`. type: 'peony' | 'ring' | 'heart' */
  launch(target, type = Math.random() < 0.22 ? "heart" : Math.random() < 0.3 ? "ring" : "peony") {
    const start = new THREE.Vector3(target.x + rand(-0.6, 0.6), -1.6, target.z + rand(-0.6, 0.6));
    const T = rand(1.0, 1.4);
    const vel = target.clone().sub(start).divideScalar(T);
    vel.y += 0.5 * GRAVITY * 0.35 * T;
    this.rockets.push({ p: start, v: vel, t: 0, T, type, color: pick(PALETTE), trail: [] });
  }

  explode(r) {
    const n = r.type === "heart" ? 170 : (130 + Math.random() * 40) | 0;
    const speed = rand(2.0, 2.9);
    const c2 = pick(PALETTE);
    // base del plano de la camara para que el corazon siempre se vea de frente
    const right = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 0);
    const up = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 1);
    const ringAxis = new THREE.Vector3(rand(-1, 1), 1, rand(-1, 1)).normalize();
    const ringU = new THREE.Vector3(1, 0, 0).cross(ringAxis).normalize();
    const ringV = ringAxis.clone().cross(ringU);
    for (let i = 0; i < n; i++) {
      const v = new THREE.Vector3();
      if (r.type === "heart") {
        const t = (i / n) * Math.PI * 2;
        const x = 16 * Math.sin(t) ** 3;
        const y = 13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t);
        v.addScaledVector(right, x / 16).addScaledVector(up, y / 16).multiplyScalar(speed * 0.95);
        v.addScaledVector(right.clone().cross(up), rand(-0.15, 0.15));
      } else if (r.type === "ring") {
        const t = (i / n) * Math.PI * 2;
        v.addScaledVector(ringU, Math.cos(t)).addScaledVector(ringV, Math.sin(t)).multiplyScalar(speed);
      } else {
        v.randomDirection().multiplyScalar(speed * (0.55 + 0.45 * Math.sqrt(Math.random())));
      }
      const life = rand(1.6, 2.6);
      this.sparks.push({
        p: r.p.clone(), v, age: 0, life,
        color: Math.random() < 0.7 ? r.color : c2,
        size: rand(0.045, 0.075),
        trail: new Float32Array(TRAIL * 3).fill(0).map((_, k) => r.p.getComponent(k % 3)),
        flicker: Math.random() < 0.35,
      });
    }
    this.flash = 1;
    this.light.position.copy(r.p);
    this.light.color.copy(r.color);
  }

  /** Lanzamiento automatico detras del ramo (lado opuesto a la camara) para no deslumbrar. */
  autoLaunch(center) {
    const cam = this.camera.position;
    const a = Math.atan2(cam.z - center.z, cam.x - center.x) + Math.PI + rand(-1.1, 1.1);
    const rad = rand(4.5, 8);
    this.launch(new THREE.Vector3(center.x + Math.cos(a) * rad, rand(2.6, 5.4), center.z + Math.sin(a) * rad));
  }

  update(dt, center, auto = true) {
    if (auto) {
      this.autoTimer -= dt;
      if (this.autoTimer <= 0) { this.autoLaunch(center); this.autoTimer = rand(0.9, 2.3); }
    }

    for (let i = this.rockets.length - 1; i >= 0; i--) {
      const r = this.rockets[i];
      r.t += dt;
      r.v.y -= GRAVITY * 0.35 * dt;
      r.p.addScaledVector(r.v, dt);
      r.trail.unshift(r.p.clone());
      if (r.trail.length > 14) r.trail.pop();
      if (r.t >= r.T) { this.explode(r); this.rockets.splice(i, 1); }
    }

    const drag = Math.exp(-DRAG * dt);
    for (let i = this.sparks.length - 1; i >= 0; i--) {
      const s = this.sparks[i];
      s.age += dt;
      if (s.age >= s.life) { this.sparks.splice(i, 1); continue; }
      s.v.multiplyScalar(drag);
      s.v.y -= GRAVITY * dt;
      s.trail.copyWithin(3, 0, (TRAIL - 1) * 3);
      s.p.addScaledVector(s.v, dt);
      s.trail[0] = s.p.x; s.trail[1] = s.p.y; s.trail[2] = s.p.z;
    }

    this.flash *= Math.exp(-3.2 * dt);
    this.light.intensity = this.flash * 14;
    this.write();
  }

  write() {
    const { pos, col, size, alpha } = this;
    let n = 0;
    const put = (x, y, z, c, s, a) => {
      if (n >= MAX) return;
      pos[n * 3] = x; pos[n * 3 + 1] = y; pos[n * 3 + 2] = z;
      col[n * 3] = c.r; col[n * 3 + 1] = c.g; col[n * 3 + 2] = c.b;
      size[n] = s; alpha[n] = a; n++;
    };
    for (const r of this.rockets) {
      r.trail.forEach((p, k) => put(p.x, p.y, p.z, r.color, 0.07 * (1 - k / 16), 0.9 * (1 - k / r.trail.length)));
    }
    for (const s of this.sparks) {
      const k = s.age / s.life;
      let a = (1 - k) ** 1.4;
      if (s.flicker && k > 0.5) a *= 0.4 + 0.6 * Math.abs(Math.sin(s.age * 38));
      for (let t = 0; t < TRAIL; t++) {
        const f = 1 - t / TRAIL;
        put(s.trail[t * 3], s.trail[t * 3 + 1], s.trail[t * 3 + 2], s.color, s.size * (0.4 + 0.6 * f), a * f * f);
      }
    }
    this.geo.setDrawRange(0, n);
    for (const name of ["position", "aColor", "aSize", "aAlpha"]) this.geo.attributes[name].needsUpdate = true;
  }

  clear() { this.rockets.length = 0; this.sparks.length = 0; this.flash = 0; }
}
