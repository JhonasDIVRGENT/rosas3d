// Ambiente: cielo estrellado, destellos que orbitan el ramo, petalos que caen y anillo de espinas.
import * as THREE from "three";

const rand = (a, b) => a + Math.random() * (b - a);

// ---------------------------------------------------------------- puntos que titilan
const twinkleVS = /* glsl */ `
  uniform float uScale;
  uniform float uTime;
  attribute float aSize;
  attribute float aPhase;
  attribute vec3 aColor;
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = max(aSize * uScale / -mv.z, 1.0);
    gl_Position = projectionMatrix * mv;
    vColor = aColor;
    vAlpha = 0.35 + 0.65 * pow(0.5 + 0.5 * sin(uTime * (0.8 + fract(aPhase * 7.3) * 2.2) + aPhase * 6.283), 3.0);
  }`;
const twinkleFS = /* glsl */ `
  uniform float uGain;
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5) * 2.0;
    float a = exp(-d * d * 6.0) * vAlpha;
    if (a < 0.004) discard;
    gl_FragColor = vec4(vColor * a * uGain, a);
  }`;

function twinklePoints(positions, colors, sizes, gain) {
  const n = sizes.length;
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  g.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));
  g.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
  g.setAttribute("aPhase", new THREE.BufferAttribute(Float32Array.from({ length: n }, Math.random), 1));
  const m = new THREE.ShaderMaterial({
    uniforms: { uScale: { value: 500 }, uTime: { value: 0 }, uGain: { value: gain } },
    vertexShader: twinkleVS, fragmentShader: twinkleFS,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const pts = new THREE.Points(g, m);
  pts.frustumCulled = false;
  return pts;
}

export function createSky() {
  const n = 1800;
  const pos = new Float32Array(n * 3), col = new Float32Array(n * 3), size = new Float32Array(n);
  const c = new THREE.Color();
  for (let i = 0; i < n; i++) {
    const v = new THREE.Vector3().randomDirection();
    v.y = Math.abs(v.y) * 0.9 + 0.05;                 // casi todo por encima del horizonte
    v.normalize().multiplyScalar(rand(60, 90));
    pos.set([v.x, v.y, v.z], i * 3);
    c.setHSL(rand(0.88, 1.02) % 1, rand(0.2, 0.6), rand(0.75, 0.95));
    col.set([c.r, c.g, c.b], i * 3);
    size[i] = rand(0.25, 0.7);
  }
  return twinklePoints(pos, col, size, 1.6);
}

/** Destellos pequenos que orbitan alrededor del ramo. */
export function createGlitter(center) {
  const n = 260;
  const pos = new Float32Array(n * 3), col = new Float32Array(n * 3), size = new Float32Array(n);
  const orbit = [];
  const palette = ["#ffb3d1", "#ffe6f0", "#ffd2a8", "#ff6fa8"].map((h) => new THREE.Color(h));
  for (let i = 0; i < n; i++) {
    orbit.push({ a: Math.random() * Math.PI * 2, r: rand(0.9, 2.4), y: rand(0.1, 2.8), w: rand(0.05, 0.22) * (Math.random() < 0.5 ? -1 : 1), bob: rand(0, 6.28) });
    const p = palette[(Math.random() * palette.length) | 0];
    col.set([p.r, p.g, p.b], i * 3);
    size[i] = rand(0.018, 0.04);
  }
  const pts = twinklePoints(pos, col, size, 2.4);
  pts.userData.update = (t) => {
    for (let i = 0; i < n; i++) {
      const o = orbit[i];
      const a = o.a + t * o.w;
      pos[i * 3] = center.x + Math.cos(a) * o.r;
      pos[i * 3 + 1] = o.y + Math.sin(t * 0.6 + o.bob) * 0.12;
      pos[i * 3 + 2] = center.z + Math.sin(a) * o.r;
    }
    pts.geometry.attributes.position.needsUpdate = true;
  };
  return pts;
}

// ---------------------------------------------------------------- petalos que caen
function petalGeometry() {
  const s = new THREE.Shape();
  s.moveTo(0, 0);
  s.bezierCurveTo(0.07, 0.02, 0.075, 0.1, 0, 0.14);
  s.bezierCurveTo(-0.075, 0.1, -0.07, 0.02, 0, 0);
  const g = new THREE.ShapeGeometry(s, 10);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i);
    p.setZ(i, 2.8 * x * x - 0.6 * (y - 0.07) ** 2);   // petalo curvado (copa)
  }
  g.translate(0, -0.07, 0);
  g.computeVertexNormals();
  return g;
}

export function createPetals(count = 70) {
  const mat = new THREE.MeshPhysicalMaterial({
    color: "#f7a8c2", roughness: 0.55, side: THREE.DoubleSide,
    sheen: 0.7, sheenRoughness: 0.4, sheenColor: new THREE.Color("#ffd6e4"),
  });
  const mesh = new THREE.InstancedMesh(petalGeometry(), mat, count);
  mesh.frustumCulled = false;
  const dummy = new THREE.Object3D();
  const state = Array.from({ length: count }, () => spawn({}, true));
  function spawn(s, anywhere) {
    s.p = new THREE.Vector3(rand(-4, 4), anywhere ? rand(-1, 6) : rand(5, 7), rand(-4, 3));
    s.rot = new THREE.Euler(rand(0, 6.28), rand(0, 6.28), rand(0, 6.28));
    s.spin = new THREE.Vector3(rand(-1.2, 1.2), rand(-1.2, 1.2), rand(-1.2, 1.2));
    s.fall = rand(0.25, 0.5);
    s.sway = rand(0, 6.28);
    s.scale = rand(0.7, 1.15);
    return s;
  }
  mesh.userData.update = (dt, t) => {
    state.forEach((s, i) => {
      s.p.y -= s.fall * dt;
      s.p.x += Math.sin(t * 0.7 + s.sway) * 0.18 * dt;
      s.p.z += Math.cos(t * 0.5 + s.sway) * 0.1 * dt;
      s.rot.x += s.spin.x * dt; s.rot.y += s.spin.y * dt; s.rot.z += s.spin.z * dt;
      if (s.p.y < -1.5) spawn(s, false);
      dummy.position.copy(s.p);
      dummy.rotation.copy(s.rot);
      dummy.scale.setScalar(s.scale);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
  };
  return mesh;
}

// ---------------------------------------------------------------- anillo de espinas
class Ellipse extends THREE.Curve {
  constructor(a, b) { super(); this.a = a; this.b = b; }
  getPoint(t, target = new THREE.Vector3()) {
    const ang = t * Math.PI * 2;
    return target.set(this.a * Math.cos(ang), 0, this.b * Math.sin(ang));
  }
}

/** Anillo luminoso con espinas y tres cometas de luz que lo recorren (como en la referencia). */
export function createThornRing({ a = 1.45, b = 0.95 } = {}) {
  const group = new THREE.Group();
  const curve = new Ellipse(a, b);
  const glow = (hex, k) => new THREE.MeshBasicMaterial({ color: new THREE.Color(hex).multiplyScalar(k), toneMapped: true });

  group.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 260, 0.011, 8, true), glow("#ff3d8b", 2.4)));

  // espinas: conos apuntando hacia fuera, alternando arriba y abajo
  const thornGeo = new THREE.ConeGeometry(0.016, 0.085, 6);
  thornGeo.translate(0, 0.0425, 0);
  const nThorns = 60;
  const thorns = new THREE.InstancedMesh(thornGeo, glow("#ffd0e2", 1.7), nThorns);
  const dummy = new THREE.Object3D();
  for (let k = 0; k < nThorns; k++) {
    const t = (k + rand(-0.2, 0.2)) / nThorns;
    const p = curve.getPoint(t);
    const ang = t * Math.PI * 2;
    const out = new THREE.Vector3(b * Math.cos(ang), 0, a * Math.sin(ang)).normalize();
    out.y = 0.9 * (k % 2 ? 1 : -1);
    out.normalize();
    dummy.position.copy(p);
    dummy.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), out);
    dummy.updateMatrix();
    thorns.setMatrixAt(k, dummy.matrix);
  }
  group.add(thorns);

  // cometas: esferas pequenas con estela que recorren el anillo
  const comets = 3, tail = 16;
  const cometMesh = new THREE.InstancedMesh(new THREE.SphereGeometry(0.022, 10, 8), glow("#ffffff", 4.5), comets * tail);
  group.add(cometMesh);
  const tmp = new THREE.Vector3();
  group.userData.update = (t) => {
    for (let c = 0; c < comets; c++) {
      for (let k = 0; k < tail; k++) {
        const u = ((t * 0.09 + c / comets - k * 0.004) % 1 + 1) % 1;
        curve.getPoint(u, tmp);
        dummy.position.copy(tmp);
        dummy.quaternion.identity();
        dummy.scale.setScalar(1 - k / tail);
        dummy.updateMatrix();
        cometMesh.setMatrixAt(c * tail + k, dummy.matrix);
      }
    }
    cometMesh.instanceMatrix.needsUpdate = true;
  };
  return group;
}

/** Actualiza la escala de tamano en pixeles de todos los puntos (al redimensionar). */
export function setPointScale(objects, px) {
  for (const o of objects) if (o.material?.uniforms?.uScale) o.material.uniforms.uScale.value = px;
}
