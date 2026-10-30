# rosas3d

Un ramo de rosas 3D para **Karla Mariel, de Jhonas**: rosas realistas, fuegos artificiales, pétalos que caen, un anillo de espinas luminoso, una canción de fondo en bucle y un mensaje romántico. Todo corre en tiempo real en el navegador (three.js) y se publica en Netlify.

## Estructura

```
rosas3d/
├── README.md
├── NOTAS.md
├── netlify.toml             Netlify publica la carpeta web/
├── web/                     SITIO WEB (lo que se sube)
│   ├── index.html
│   ├── css/style.css
│   ├── js/main.js           escena, cámara, luces, bloom, carga del ramo
│   ├── js/fireworks.js      fuegos artificiales en vivo
│   ├── js/ambient.js        cielo, destellos, pétalos, anillo de espinas
│   ├── js/story.js          portada, frases, música, reiniciar/silenciar
│   ├── models/rosas.glb     ramo exportado desde Blender (generado)
│   └── audio/cancion.mp3    música de fondo
├── src/                     PIPELINE (código que genera recursos)
│   ├── blender/
│   │   ├── build_realistic.py   ramo realista -> web/models/rosas.glb
│   │   └── build_scene.py       ramo neón original (frames para el video)
│   └── particles/               motor Python de partículas + video mp4 + visor pygame
└── assets/                  RECURSOS (fuentes y resultados)
    ├── models/pink-rose/    rosa escaneada (texturas + OBJ original)
    ├── blender/             rosas_realista.blend, rosas.blend
    ├── camera.json
    ├── audio/               canción original
    ├── render/ layers/ out/ resultados del video (no van a git)
    └── ref/                 referencia visual
```

## Ver la web en local

Los módulos JS y el `.glb` necesitan un servidor; con doble clic en `index.html` no carga.

```bash
python -m http.server 8080 --directory web
```

Después abre <http://localhost:8080>. Con `?debug` (<http://localhost:8080/?debug>) el canvas se puede capturar y la escena queda accesible en `window.__rosas`.

En VS Code también sirve la extensión **Live Server**: clic derecho en `web/index.html` → *Open with Live Server*.

Controles: arrastrar para girar · rueda o pellizco para zoom · clic o toque en el cielo para lanzar un fuego · **R** o botón ↺ para reiniciar la canción y el mensaje · **M** o botón ♪ para silenciar.

## Regenerar el ramo desde Blender

```bash
blender -b --python src/blender/build_realistic.py -- --export
```

Crea `assets/blender/rosas_realista.blend` y `web/models/rosas.glb` (Draco, texturas JPEG 2048). Para una imagen de control añade `--preview ruta.png`.

Ajustes del material en `rose_material()`: rugosidad, sheen (el brillo aterciopelado del pétalo) y la saturación del color, que va horneada en la textura con `saturation=`.

## Publicar en Netlify (desde GitHub)

1. Sube el repo a GitHub (`https://github.com/JhonasDIVRGENT/rosas3d`).
2. En Netlify: **Add new site → Import an existing project → GitHub** y elige `rosas3d`.
3. Netlify lee `netlify.toml`: sin comando de build, carpeta de publicación `web`. Pulsa **Deploy**.
4. Cada `git push` a `main` vuelve a publicar el sitio.

## Pipeline del video (opcional)

```bash
pip install numpy pillow scipy imageio-ffmpeg pygame-ce
python src/particles/fireworks.py --frame 120
python src/particles/compose.py --frame 120
python src/particles/viewer.py
blender -b --python src/blender/build_scene.py -- --all
```

Salidas en `assets/layers`, `assets/out` y `assets/render`.

## Créditos

- Rosa: modelo "Pink rose" (escaneo con retopología) de Sketchfab; revisa su licencia y su autor antes de publicar.
- Música: "Con Las Ganas", de Zahara. Es una obra con derechos de autor.
