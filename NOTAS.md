# NOTAS rosas3d

Ver `README.md` para la estructura, cómo probar y cómo publicar en Netlify.

## Estado
- **Web en tiempo real** (`web/`): three.js 0.170 desde jsDelivr. Ramo GLB realista, bloom, fuegos (cohete + peonía / anillo / corazón), pétalos, destellos, cielo, anillo de espinas con cometas, música en bucle, frases y botones reiniciar/silenciar.
- **Ramo realista** (`src/blender/build_realistic.py`): rosa escaneada de `assets/models/pink-rose`, decimada a ~49k triángulos y compartida por las 9 rosas (duplicados enlazados). 24 hojas, tallos y lazo. Material PBR: color (saturación x1.6 horneada), normal, oclusión y sheen. GLB de ~1.2 MB.
- **Pipeline del video** (neón, Python + Blender): `src/particles/*`, `src/blender/build_scene.py`. Ya no lo usa la web.

## Referencia
El video es un programa **interactivo** en JS/canvas (proyeccion 3D manual, semillas que suben y explotan en chispas con estelas y sprites). La web reproduce eso en vivo.

## Pendiente / ideas
- Confirmar la licencia del modelo de rosa y si se puede publicar la canción.
- `assets/camera.json` sigue siendo provisional (solo lo usa el pipeline del video).
