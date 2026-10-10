# SAM Audio Lab

Interfaz local en español para experimentar con SAM Audio. La validación de
inferencia se realizó en Apple Silicon; consulta la
[guía de instalación por sistema](docs/INSTALLATION.md) para otras plataformas.

## Iniciar

```bash
conda activate sam3
# Desde la raíz de tu clon:
python run_lab.py
```

Abre http://127.0.0.1:8765. `python run_lab.py --build` recompila la interfaz;
`--port 8766` cambia el puerto. Solo se escucha en loopback.

## Flujo

1. Carga un audio o video, o usa `office.mp4` con el botón de ejemplo.
2. Elige inicio y fin (máximo 30 segundos) y pulsa **Preparar clip**.
3. Describe el sonido. En la línea del tiempo, **Presente** y **Ausente** permiten
   dibujar intervalos; arrastra sus bordes para ajustarlos. El botón del cursor
   permite volver a navegar. Los intervalos son referencias, no recortes.
4. En **Objeto visual**, busca por texto y elige una máscara, o usa clics positivos
   y negativos sobre un fotograma. Pulsa **Seguir objeto en el clip** y revisa la
   máscara al reproducir o avanzar fotogramas. Puedes añadir correcciones y repetir.
5. Selecciona **Small**, **Base** o **Large** y pulsa **Separar sonido**.
6. Alterna Original / Aislado / Residual, descarga WAV o exporta MP4.
   **Duplicar** en el historial recupera los parámetros para probar otro modelo.

Se envía el texto tal como se escribe; hay ejemplos en inglés, sin traducción ni
servicios externos. Los medios se procesan localmente. Hugging Face se usa para
los pesos, con las credenciales del inicio de sesión existente; no hay tokens en
la interfaz ni en los metadatos.

El historial y borrador sobreviven al reinicio. Una ejecución en curso se marca
como interrumpida al reiniciar; puede repetirse. Cancelar detiene el grupo de
procesos del trabajo, incluidos FFmpeg y el modelo. El siguiente trabajo inicia
un proceso limpio. Solo se ejecuta un trabajo a la vez.

## Instalación adicional

La instalación completa se describe en [docs/INSTALLATION.md](docs/INSTALLATION.md).
Si ya tienes SAM Audio instalado en `sam3`, la aplicación agrega:

```bash
conda activate sam3
pip install -r requirements-lab.txt
cd web
npm ci
npm run build
cd ..
conda create -n sam3-vision --override-channels -c conda-forge python=3.12 pip -y
conda run -n sam3-vision pip install -r requirements-vision.txt
```

SAM 3 visual requiere acceso a `facebook/sam3`, además de los repositorios de SAM
Audio. Los checkpoints se descargan automáticamente cuando se usan por primera
vez y se conservan en la caché de Hugging Face. Base y Large ocupan aproximadamente
7.19 y 13.84 GiB respectivamente; son tamaños de checkpoint, no estimaciones de RAM.

Por defecto se usa el Python del servidor, el entorno hermano `sam3-vision` y
FFmpeg del entorno de audio (o de `PATH`). Se pueden configurar con
`SAM_LAB_AUDIO_PYTHON`, `SAM_LAB_VISION_PYTHON`, `SAM_LAB_FFMPEG` y
`SAM_LAB_FFPROBE`. `SAM_LAB_DATA` cambia el directorio de datos.

## Datos y arquitectura

- `lab/`: API FastAPI, SQLite, supervisor de trabajos y trabajadores aislados.
- `web/`: React/TypeScript, Vite, WaveSurfer y superposición visual.
- `.lab-data/`: SQLite, archivos importados, proxies, máscaras, logs y resultados;
  excluido de Git. La API no publica la base de datos ni los logs.
- La API ofrece `/api/media`, `/api/clips`, `/api/vision/detect`,
  `/api/vision/track`, `/api/separate`, `/api/jobs/{id}`, `/api/exports`,
  `/api/models`, `/api/projects/{id}` y eventos SSE `/api/events`.
  El contrato completo está disponible en `/docs`.

Las ejecuciones guardan una copia de sus parámetros y la revisión de los pesos.
Las máscaras referenciadas son archivos inmutables de un trabajo terminado.
El proxy es de 25 fps, hasta 1280 píxeles de ancho; las máscaras se alinean con
los pasos de 40 ms del códec. La exportación usa el fragmento del archivo original
con su resolución original. El audio procesado y los WAV son mono a 48 kHz.

Los modelos usan float32, semilla 42, una candidata y regiones manuales.
El encoder visual de SAM Audio procesa lotes de ocho fotogramas. El modelo de audio
permanece cargado mientras se repite su tamaño; cambiar de tamaño o pasar a visión
libera el anterior. El trabajador visual usa SAM 3 de Transformers 5.19.0, con una
adaptación aplicada después de cargar la clase oficial para conservar los logits
de máscara al corregir mediante clics. Se rechaza cualquier carga con pesos
faltantes; las correcciones exclusivamente negativas conservan una referencia
positiva dentro de la máscara previa.
La convención de máscara sigue `SAMAudioProcessor.mask_videos` de esta revisión:
los píxeles seleccionados se ponen en cero antes del encoder visual.

## Tiempos y límites

Se muestran descarga/comprobación de caché, carga, preparación, procesamiento
visual, separación y total por separado. El factor de tiempo real usa únicamente
la separación de audio dividida por la duración de entrada. No incluye el
seguimiento visual. Una carga de 0 s indica reutilización del modelo en memoria.

La segmentación por objeto es considerablemente más lenta que la separación.
El trabajador selecciona CUDA, Metal o CPU. Ante una operación visual incompatible con Metal, reintenta
esa etapa en CPU y registra el motivo y dispositivo. Una falta de memoria se
reporta como error recuperable; el modelo no se cambia silenciosamente.

Un objeto visual guía el sonido; no garantiza que ese objeto emita sonido ni
que pueda separarse perfectamente. La máscara y las pistas deben revisarse.

## Verificación

```bash
conda activate sam3
pip install -r requirements-lab-dev.txt
python -m pytest tests/test_lab.py -q
npm --prefix web run build
# Con el servidor iniciado, ejecuta inferencias reales y guarda resultados:
python -m tests.smoke_lab
```

La prueba de integración importa el ejemplo y crea un seguimiento inicial si
todavía no existen. Crea resultados reales y un video de prueba extendido usando
exclusivamente el ejemplo incluido. El informe queda en
`outputs/lab-validation.json`.

## Validación realizada en esta Mac

El 9 de octubre de 2026 se completaron 16 pruebas automatizadas del backend y la
compilación TypeScript/Vite. También se ejecutaron inferencias reales en Metal:

| Prueba | Duración de entrada | Separación |
| --- | ---: | ---: |
| Small, texto + regiones + objeto visual | 5 s | 6.45 s |
| Base, texto | 5 s | 13.65 s |
| Large, texto | 5 s | 12.78 s |
| Small, texto + regiones, recorte desde 2 s | 30 s | 24.63 s |

Son mediciones individuales bajo la carga de esta sesión, no un benchmark
controlado ni una comparación de calidad. El seguimiento visual de 125 fotogramas
tardó 379.53 s adicionales, y el encoder visual de SAM Audio, 29.20 s.
Se probaron detección textual, clics positivos/negativos, correcciones sobre una
máscara previa, exportación MP4, cancelación durante inferencia, recuperación,
recortes VFR, persistencia tras reiniciar y cambio de pistas conservando el tiempo.
