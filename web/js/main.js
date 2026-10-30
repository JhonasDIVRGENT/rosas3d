// rosas3d en tiempo real: ramo (GLB exportado desde Blender) + fuegos + anillo + petalos + musica.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { Fireworks } from "./fireworks.js";
import { createSky, createGlitter, createPetals, createThornRing, setPointScale } from "./ambient.js";
import { setupStory } from "./story.js";

const CENTER = new THREE.Vector3(0, 1.1, 0);    // centro del ramo (Blender (0,0,1.1) -> Y arriba)
const FOV = 38;
const MODEL_BYTES = 1.3e6;                       // tamano aproximado del GLB para la barra de carga

// ---------------------------------------------------------------- render
const DEBUG = new URLSearchParams(location.search).has("debug");   // ?debug: permite capturar el canvas
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance", preserveDrawingBuffer: DEBUG });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
document.getElementById("stage").appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color("#060208");
scene.fog = new THREE.FogExp2("#060208", 0.012);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.55;

const camera = new THREE.PerspectiveCamera(FOV, innerWidth / innerHeight, 0.05, 300);
camera.position.set(0, 2.2, 6.4);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.copy(CENTER);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.enablePan = false;
controls.minDistance = 2.6;
controls.maxDistance = 12;
controls.minPolarAngle = 0.45;
controls.maxPolarAngle = 1.78;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.55;

// luces equivalentes a la vista previa de Blender (key calida, rim rosa, fill frio)
const key = new THREE.DirectionalLight("#fff0e0", 2.6); key.position.set(3, 4.5, 4);
const rim = new THREE.DirectionalLight("#ff8fb5", 2.4); rim.position.set(-2.5, 3.2, -3.5);
const fill = new THREE.DirectionalLight("#c8d4ff", 0.5); fill.position.set(-4, 1.2, 3);
scene.add(key, rim, fill, new THREE.HemisphereLight("#ffd6e6", "#100510", 0.55));

// ---------------------------------------------------------------- escena
const bouquet = new THREE.Group();
scene.add(bouquet);

const ring = createThornRing();
ring.position.set(CENTER.x, 0.95, CENTER.z);
ring.rotation.x = THREE.MathUtils.degToRad(-20);
scene.add(ring);

const sky = createSky();
const glitter = createGlitter(CENTER);
const petals = createPetals();
scene.add(sky, glitter, petals);

const fireworks = new Fireworks(scene, camera);
const pointObjects = [sky, glitter, fireworks.points];
if (DEBUG) window.__rosas = { THREE, renderer, scene, camera, controls, fireworks, bouquet };

// ---------------------------------------------------------------- post
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.6, 0.55, 0.88);
composer.addPass(bloom);
composer.addPass(new OutputPass());

// ---------------------------------------------------------------- historia y musica
let started = false;
/** Punto detras del ramo visto desde la camara actual, a la altura y dada. */
function behind(y) {
  const away = CENTER.clone().sub(camera.position).setY(0).normalize();
  return CENTER.clone().addScaledVector(away, 4).setY(y);
}
const story = setupStory({
  onOpen() {
    started = true;
    fireworks.launch(behind(4.2), "heart");
  },
  onRestart() {
    fireworks.clear();
    controls.reset();
    fitCamera();
    fireworks.launch(behind(4.2), "heart");
  },
  onLine(i, last) {
    if (last) {   // final: corazon grande y una salva
      fireworks.launch(behind(4.4), "heart");
      for (let k = 0; k < 4; k++) setTimeout(() => fireworks.autoLaunch(CENTER), 500 + k * 380);
    }
  },
});

// ---------------------------------------------------------------- modelo
const draco = new DRACOLoader().setDecoderPath("https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/");
new GLTFLoader().setDRACOLoader(draco).load(
  "models/rosas.glb",
  (gltf) => {
    const aniso = renderer.capabilities.getMaxAnisotropy();
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      const m = o.material;
      for (const t of [m.map, m.normalMap, m.aoMap]) if (t) t.anisotropy = aniso;
      if (m.name === "RosePetal") m.envMapIntensity = 0.8;
    });
    bouquet.add(gltf.scene);
    story.ready();
  },
  (xhr) => story.progress(xhr.loaded / (xhr.total || MODEL_BYTES)),
  (err) => { console.error("No se pudo cargar el ramo", err); story.failed(); },
);

// ---------------------------------------------------------------- interaccion: clic/toque = fuego
const down = new THREE.Vector2();
let downTime = 0;
renderer.domElement.addEventListener("pointerdown", (e) => { down.set(e.clientX, e.clientY); downTime = performance.now(); });
renderer.domElement.addEventListener("pointerup", (e) => {
  if (!started) return;
  if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6 || performance.now() - downTime > 350) return;
  const ndc = new THREE.Vector2((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
  const ray = new THREE.Raycaster();
  ray.setFromCamera(ndc, camera);
  const p = ray.ray.at(camera.position.distanceTo(CENTER) + 3, new THREE.Vector3());
  p.y = Math.max(p.y, 1.2);
  fireworks.launch(p);
});

// ---------------------------------------------------------------- tamano
function fitCamera() {
  // en pantallas verticales alejamos la camara para que el ramo quepa a lo ancho
  const aspect = innerWidth / innerHeight;
  const hfov = 2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(FOV / 2)) * aspect);
  const dist = Math.max(6.4, 1.3 / Math.tan(hfov / 2));
  const dir = camera.position.clone().sub(controls.target).normalize();
  camera.position.copy(controls.target).addScaledVector(dir, dist);
}

function resize() {
  const w = innerWidth, h = innerHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  composer.setSize(w, h);
  bloom.setSize(w, h);
  const px = (h * renderer.getPixelRatio()) / (2 * Math.tan(THREE.MathUtils.degToRad(FOV / 2)));
  setPointScale(pointObjects, px);
  fireworks.setScale(px);
}
addEventListener("resize", () => { resize(); fitCamera(); });
resize();
fitCamera();
controls.saveState();

// ---------------------------------------------------------------- bucle
const clock = new THREE.Clock();
let t = 0;
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.05);
  t += dt;
  controls.update(dt);
  bouquet.rotation.z = Math.sin(t * 0.55) * 0.015;          // leve balanceo
  ring.rotation.y = -t * 0.12;
  ring.position.y = 0.95 + Math.sin(t * 0.8) * 0.04;
  ring.userData.update(t);
  glitter.userData.update(t);
  petals.userData.update(dt, t);
  sky.material.uniforms.uTime.value = t;
  glitter.material.uniforms.uTime.value = t;
  fireworks.update(dt, CENTER, started);
  composer.render();
});
