# SAM Audio en esta Mac

Preparación local del 9 de octubre de 2026 para separación mediante texto.
El entorno se llama `sam3`, pero el modelo instalado es **SAM Audio**.

## Equipo y entorno

- MacBook Pro con Apple M4 Max, 16 núcleos CPU, 40 núcleos GPU y 128 GB de memoria unificada.
- macOS 27.0.1, arquitectura arm64.
- Anaconda: `/opt/anaconda3/envs/sam3`, Python 3.11.17.
- PyTorch 2.14.1, torchvision 0.29.1, torchaudio 2.11.0, TorchCodec 0.17.0.
- FFmpeg 7.1.1 instalado en el entorno mediante conda-forge.
- La GPU se usa a través de `mps` (Apple Metal), sin CUDA.

## Estado y alcance

La importación del paquete y la lectura del audio de ejemplo funcionan. El script
`check_macos.py` comprueba el códec DACVAE con su arquitectura por defecto y un DiT
reducido, con pesos aleatorios, comparando CPU y MPS. Estas pruebas comprueban
compatibilidad de operaciones; **no prueban calidad de separación, rendimiento del
modelo completo ni viabilidad en tiempo real**. El informe se guarda en
`outputs/macos-check.json` cuando todas las comprobaciones terminan.

**Resultado obtenido:** códec y DiT reducido ejecutados en `mps:0`, con salidas
finitas y comparación CPU/MPS aprobada (`rtol=2e-3`, `atol=2e-4`). La prueba no
necesitó mantener el códec en CPU.

**Inferencia completa confirmada:** después de autorizar la cuenta de Hugging
Face, se descargaron los pesos oficiales de `facebook/sam-audio-small` y se
ejecutó la separación en Metal. Base y Large también están descargados y validados en Metal mediante SAM Audio
Lab. El informe actualizado está en `outputs/lab-validation.json`.

Prueba real del 9 de octubre de 2026:

| Parámetro | Resultado |
| --- | --- |
| Entrada | Primeros 5 segundos de `examples/assets/office.mp4` |
| Descripción | `man speaking` |
| Modelo | `facebook/sam-audio-small` |
| Dispositivo | `mps`, Apple M4 Max |
| Tiempo de separación | **6.472 segundos** |
| Tiempo de separación / duración de entrada | **1.294** |
| Salidas | Mono, 48 kHz, 240 000 muestras cada una |

Esta primera ejecución fue algo más lenta que la duración del audio. El tiempo
de separación excluye descarga y carga del modelo. La fase de carga duró 66.263
segundos e incluyó la descarga inicial del codificador T5; la descarga previa
del checkpoint SAM Audio (4.75 GiB) tampoco forma parte del tiempo de separación.
No es un benchmark de ejecuciones repetidas ni de otros tamaños de modelo.

Los archivos están en `outputs/small-mps-5s/`: `original.wav`, `target.wav`,
`residual.wav`, `run.json` y `validation.json`. Las salidas tienen la duración
correcta, contienen señal, son distintas entre sí y del original y no contienen
NaN ni infinitos. La calidad perceptual no se calificó; se incluyen las pistas
para comparación auditiva.

La descarga por Xet avanzaba lentamente; se completó por HTTP usando
`HF_HUB_DISABLE_XET=1 HF_HUB_DOWNLOAD_TIMEOUT=60`. Los pesos ya están en la caché
habitual de Hugging Face. No guardes tokens en este repositorio.

## Repetir las pruebas

```bash
conda activate sam3
# Desde la raíz del clon de sam-audio-lab
python check_macos.py --check-access
```

Ejecuta las pruebas desde una Terminal con acceso a Metal; algunos entornos de
aislamiento impiden que PyTorch detecte la GPU. No se activa automáticamente el
fallback de operaciones MPS a CPU.

## Separar audio

```bash
conda activate sam3
# Desde la raíz del clon de sam-audio-lab
# Solo si necesitas iniciar sesión o cambiar de cuenta:
hf auth login

python separate_macos.py examples/assets/office.mp4 "man speaking" --seconds 5
```

El comando comprueba primero el acceso al modelo. Después descarga los pesos y
su codificador de texto, procesa los primeros cinco segundos y escribe
`target.wav`, `residual.wav` y `run.json` en `outputs/separation/`. Este último
registra tiempos de carga e inferencia por separado. Sin `--seconds`, procesa
los primeros diez segundos. `--device cpu` permite probar CPU explícitamente.
El comando completo se validó con Small y el fragmento de cinco segundos descrito
arriba. Para conservar los resultados de esa prueba se usó
`--output outputs/small-mps-5s`.

## Ajustes locales

- Carga diferida de Judge, CLAP, ImageBind y predicción de intervalos: la ruta de
  texto no importa sus dependencias opcionales, incluidas las orientadas a CUDA.
- El códec solo abre un contexto cuDNN cuando el tensor está en CUDA.
- El ejecutor desactiva `span_predictor`, `text_ranker` y `visual_ranker`, y usa
  `predict_spans=False`, `reranking_candidates=1` y precisión float32.
- La prueba conserva el estado aleatorio antes de cada decodificación: DACVAE
  incorpora una marca de agua aleatoria, que debe ser idéntica para comparar CPU y GPU.

SAM 3 visual está instalado en el entorno independiente `sam3-vision`; la
detección por texto, el seguimiento y las correcciones mediante clics fueron
validados en Metal. La interfaz web se documenta en [LAB.md](LAB.md). Judge,
reranking y la predicción automática de intervalos siguen desactivados.

SAM Audio y Perception Models se instalaron con `--no-deps`; se instalaron las
dependencias necesarias para esta ruta concreta. **`pip check` reporta las
dependencias opcionales omitidas**, como xformers, decord e ImageBind, porque los
paquetes oficiales las declaran obligatorias para su instalación completa.
No ejecutes `pip install .` sin estas consideraciones en macOS.

## Reproducir la instalación

Los scripts requieren esta copia con los ajustes locales. Versiones del código:

- SAM Audio: `bb4c6999d2677c7402360e426afc01ddfad6dce0` más los cambios locales.
- Perception Models: `e72b6810b1133e1c879f2cc965d276eb73803f1f`, rama `unpin-deps`.
- DACVAE: `414c20785fc3a28373073ea8ef7a1316eeeaca6e`.

`requirements-macos.lock.txt` registra las versiones del entorno original como
referencia histórica. Para instalaciones nuevas usa la [guía por sistema
operativo](docs/INSTALLATION.md), que incluye los entornos de audio y visión,
Hugging Face, FFmpeg y la compilación web. No copies rutas de esta máquina.

## Interfaz web

```bash
conda activate sam3
python run_lab.py
```

Abre `http://127.0.0.1:8765`. Consulta [LAB.md](LAB.md) para selección de
objetos, regiones temporales, historial, exportación y pruebas de integración.
