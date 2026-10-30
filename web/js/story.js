// Portada, musica en bucle, frases y controles (silenciar / reiniciar).

export const LINES = [
  "Karla Mariel…",
  "Cada rosa de este ramo guarda un instante contigo, y aun así me faltan rosas para todo lo que siento.",
  "Si esta noche el cielo se enciende, es porque mi corazón no sabe latir de otra forma cuando pienso en ti.",
  "Eres mi calma, mi alegría y el lugar al que siempre quiero volver.",
  "Contigo aprendí que el amor no se explica: se cuida, se riega y florece cada día.",
  "Gracias por tu sonrisa, por tu paciencia y por dejarme caminar a tu lado.",
  "Te amo hoy, mañana y en todas las canciones que todavía nos faltan por escuchar.",
  "Con todo mi amor, Jhonas ♥",
];

const FIRST_DELAY = 2600;   // ms tras abrir
const LINE_MS = 7200;       // tiempo por frase
const FADE_MS = 1100;

export function setupStory({ onOpen, onRestart, onLine }) {
  const $ = (id) => document.getElementById(id);
  const audio = $("song"), intro = $("intro"), openBtn = $("open");
  const msg = $("message"), muteBtn = $("mute"), restartBtn = $("restart");
  let timers = [];
  let opened = false;

  const later = (fn, ms) => timers.push(setTimeout(fn, ms));
  const stop = () => { timers.forEach(clearTimeout); timers = []; };

  function show(i) {
    msg.classList.remove("show");
    later(() => {
      msg.textContent = LINES[i];
      msg.classList.toggle("signature", i === LINES.length - 1);
      msg.classList.add("show");
      onLine?.(i, i === LINES.length - 1);
    }, FADE_MS);
  }

  function playLines() {
    stop();
    msg.classList.remove("show");
    LINES.forEach((_, i) => later(() => show(i), FIRST_DELAY + i * LINE_MS));
    later(() => document.body.classList.add("hint-done"), 12000);
  }

  function playSong() {
    audio.currentTime = 0;
    audio.play().catch(() => { /* el navegador puede bloquearlo hasta otra interaccion */ });
  }

  function restart() {
    if (!opened) return;
    playSong();
    playLines();
    onRestart?.();
  }

  function toggleMute() {
    audio.muted = !audio.muted;
    muteBtn.setAttribute("aria-pressed", String(audio.muted));
  }

  openBtn.addEventListener("click", () => {
    opened = true;
    intro.classList.add("hide");
    document.body.classList.add("opened");
    playSong();
    playLines();
    onOpen?.();
  });
  restartBtn.addEventListener("click", restart);
  muteBtn.addEventListener("click", toggleMute);
  addEventListener("keydown", (e) => {
    if (e.key === "r" || e.key === "R") restart();
    if (e.key === "m" || e.key === "M") toggleMute();
  });

  return {
    progress(p) { openBtn.textContent = `Cargando rosas… ${Math.round(Math.min(p, 1) * 100)}%`; },
    ready() { openBtn.disabled = false; openBtn.textContent = "Abrir mi regalo ♥"; },
    failed() { openBtn.disabled = false; openBtn.textContent = "Abrir mi regalo ♥"; },
  };
}
