// Portada, musica en bucle, frases y controles (silenciar / reiniciar).

export const LINES = [
  "Karla, este es el regalo en el que estuve trabajando hace días. No fue fácil hacerlo.",
  "Solo agradezco la coincidencia de conocernos.",
  "Quiero que sepas que te amo mucho.",
  "Creo que cada pétalo significa cada conversación que tengo contigo: cada «buenos días», cada «buenas noches», cada «no sabes qué pasó».",
  "Para ser honesto, no sé cómo se mira en teléfonos ni si funciona, jejeje.",
  "Cuando estés triste, puedes entrar aquí a escuchar tu canción.",
  "Con mucho cariño, Jhonas ♥",
];

const FIRST_DELAY = 2600;   // ms tras abrir
const FADE_MS = 1100;
// tiempo en pantalla segun lo larga que sea la frase
const lineMs = (text) => 4200 + text.length * 55;

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
    let at = FIRST_DELAY;
    LINES.forEach((text, i) => { later(() => show(i), at); at += lineMs(text); });
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
