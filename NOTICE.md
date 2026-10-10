# Procedencia y licencias

SAM Audio Lab añade una interfaz y herramientas locales al código de
[SAM Audio](https://github.com/facebookresearch/sam-audio) de Meta.
La base utilizada es `bb4c6999d2677c7402360e426afc01ddfad6dce0`.
Se conserva el historial Git, los encabezados de autoría y la [SAM License](LICENSE).
No existe afiliación o patrocinio implícito de Meta.

| Componente | Procedencia / condiciones |
| --- | --- |
| SAM Audio y código derivado del Lab | [SAM License incluida](LICENSE) |
| Pesos Small, Base y Large | Repositorios oficiales de Hugging Face; requieren aceptar sus términos |
| SAM 3 visual | [facebook/sam3](https://huggingface.co/facebook/sam3); acceso y licencia propios |
| Perception Models | [Código y licencia](https://github.com/facebookresearch/perception_models/tree/e72b6810b1133e1c879f2cc965d276eb73803f1f); declara FAIR Noncommercial Research License |
| DACVAE | [Código y licencia](https://github.com/facebookresearch/dacvae/tree/414c20785fc3a28373073ea8ef7a1316eeeaca6e) |
| Transformers, PyTorch, FFmpeg y dependencias web | Conservan sus propias licencias en sus distribuciones |

La licencia del repositorio no sustituye las condiciones de los modelos ni de
las dependencias, incluidas las restricciones no comerciales de Perception
Models. Los checkpoints, tokens, medios del usuario y resultados no se publican.

`examples/assets/office.mp4` y `assets/sam_audio_main_model.png` se conservaron
del repositorio original. La captura `docs/assets/sam-audio-lab.jpg` muestra la
interfaz usando ese ejemplo. La documentación upstream se conserva en
`docs/upstream/`; las guías de instalación y contribución del Lab están en la raíz
y en `docs/`.
