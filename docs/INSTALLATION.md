# Instalación de SAM Audio Lab

Esta guía instala la aplicación local. macOS Apple Silicon cuenta con pruebas
reales de los tres modelos y de visión. Las rutas Linux y WSL2 están documentadas,
pero no equivalen a una validación de inferencia en esas plataformas.
Windows nativo no está soportado.

## Antes de empezar

- Instala [Git](https://git-scm.com/downloads),
  [Miniforge](https://github.com/conda-forge/miniforge#install) o una instalación
  existente de Anaconda/Miniconda, y [Node.js](https://nodejs.org/en/download).
- Usa Node.js **22.12 o superior**; se probó Node 26.8.1. Comprueba
  `node --version`, `npm --version`, `git --version` y `conda --version`.
- Conda creará Python 3.11 para audio y 3.12 para visión, sin cambiar el Python
  del sistema. En Apple Silicon, instala herramientas arm64 y evita Rosetta.
- Reserva espacio para entornos, cachés y medios. Los checkpoints de audio por sí
  solos suman unos **25.8 GiB** si descargas los tres. No es el consumo de RAM ni
  el espacio total necesario. No existe un mínimo de memoria validado para todas
  las máquinas; comienza con Small y 5 segundos.

Clona el repositorio y ejecuta los comandos desde su raíz:

```bash
git clone https://github.com/jrterven/sam-audio-lab.git
cd sam-audio-lab
```

## macOS con Apple Silicon

Si faltan las herramientas de línea de comandos de Apple, ejecuta
`xcode-select --install`. Instala Miniforge para macOS arm64 y Node.js desde los
enlaces anteriores. Abre una terminal nueva después de instalarlos.

Crea el entorno de audio con FFmpeg y sus bibliotecas compartidas:

```bash
conda create -n sam3 --override-channels -c conda-forge python=3.11 pip ffmpeg=7.1.1 -y
conda activate sam3
python -m pip install torch==2.14.1 torchvision==0.29.1 torchaudio==2.11.0 torchcodec==0.17.0
```

Estas son las versiones observadas en la instalación validada. TorchCodec 0.17
declara compatibilidad con PyTorch >=2.11 en su
[tabla oficial](https://github.com/meta-pytorch/torchcodec#compatibility-with-torch-versions).
Metal se detecta automáticamente; no instales CUDA en macOS.
Continúa con **Dependencias comunes de audio** y los pasos restantes.

## Linux

Instala Git y las herramientas de compilación de tu distribución. En Ubuntu:

```bash
sudo apt update
sudo apt install -y git build-essential
```

Instala Conda y Node.js desde los enlaces iniciales. Crea el entorno:

```bash
conda create -n sam3 --override-channels -c conda-forge python=3.11 pip ffmpeg=7.1.1 -y
conda activate sam3
```

**Con NVIDIA:** instala un controlador compatible y comprueba `nvidia-smi`.
La distribución de PyTorch debe ser compatible con ese controlador. La ruta
predeterminada de Linux usa los paquetes de PyPI:

```bash
python -m pip install torch==2.14.1 torchvision==0.29.1 torchaudio==2.11.0 torchcodec==0.17.0
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

La segunda salida debe indicar `True` para usar CUDA. Si tu controlador necesita
otra variante, elige el índice adecuado con el
[selector oficial de PyTorch](https://pytorch.org/get-started/locally/) y conserva
una combinación compatible con TorchCodec. No mezcles índices CUDA diferentes
para la familia PyTorch. El Lab decodifica video en CPU; no necesita NVDEC.

**Solo CPU:** instala las ruedas CPU explícitamente:

```bash
python -m pip install torch==2.14.1 torchvision==0.29.1 torchaudio==2.11.0 torchcodec==0.17.0 --index-url https://download.pytorch.org/whl/cpu
```

CPU será más lento. El código selecciona CUDA, después MPS y por último CPU,
según disponibilidad. No se ha validado la inferencia en AMD/ROCm, Intel/XPU
ni Linux ARM. Continúa con los pasos comunes.

## Windows con WSL2

Se usa Ubuntu dentro de WSL2 porque el supervisor cancela grupos de procesos
POSIX. No ejecutes `run_lab.py` desde Python nativo de Windows.

1. Abre PowerShell como administrador y ejecuta:

   ```powershell
   wsl --install -d Ubuntu
   ```

2. Reinicia si Windows lo solicita, abre Ubuntu y crea tu usuario. Comprueba
   en PowerShell que Ubuntu usa la versión 2:

   ```powershell
   wsl --list --verbose
   ```

3. Instala **Git, Conda y Node.js dentro de Ubuntu**, aunque existan en Windows.
   Clona el repositorio en tu directorio Linux, por ejemplo `~/sam-audio-lab`.
4. Sigue **Linux** y todos los pasos comunes desde Ubuntu.
5. Ejecuta el servidor en Ubuntu y abre `http://127.0.0.1:8765/` en el navegador
   de Windows. La instalación normal de WSL2 permite acceder por localhost;
   no hace falta exponer el servidor a la red.

Para NVIDIA, instala un controlador de Windows compatible con CUDA en WSL y
comprueba `nvidia-smi` dentro de Ubuntu. Consulta las instrucciones oficiales de
[WSL](https://learn.microsoft.com/en-us/windows/wsl/install) y
[CUDA en WSL2](https://learn.microsoft.com/en-us/windows/ai/directml/gpu-cuda-in-wsl).
La alternativa sin GPU es la instalación CPU de Linux.

## Dependencias comunes de audio

Con `sam3` activo y PyTorch instalado:

```bash
python -m pip install -r requirements-audio.txt -r requirements-lab.txt
python -m pip install --no-deps 'dacvae @ git+https://github.com/facebookresearch/dacvae.git@414c20785fc3a28373073ea8ef7a1316eeeaca6e'
python -m pip install --no-deps 'perception-models @ git+https://github.com/facebookresearch/perception_models.git@e72b6810b1133e1c879f2cc965d276eb73803f1f'
python -m pip install --no-deps -e .
```

`--no-deps` es intencional: el paquete original declara componentes para Judge,
reranking y otros flujos que esta aplicación no usa. `pip install .` sin esta
opción puede traer dependencias CUDA o versiones incompatibles con Mac.
Los imports diferidos del Lab permiten omitirlas. Por eso, `pip check` puede
reportar dependencias opcionales ausentes; usa el diagnóstico y las pruebas
para verificar el flujo implementado.

`requirements-macos.lock.txt` conserva el entorno completo original como registro.
Para instalaciones nuevas usa esta guía, que separa las dependencias de aplicación
de la selección de PyTorch por plataforma.

## Entorno visual opcional

Necesario para buscar objetos y seguir máscaras. Puedes omitirlo si solo usarás
texto y regiones. No instales Transformers 5 en `sam3`.

```bash
conda create -n sam3-vision --override-channels -c conda-forge python=3.12 pip -y
conda activate sam3-vision
```

En macOS o Linux/WSL con la distribución CUDA predeterminada:

```bash
python -m pip install -r requirements-vision.txt
```

En Linux/WSL **solo CPU**, instala primero PyTorch desde su índice CPU:

```bash
python -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-vision.txt
```

Si elegiste otro índice CUDA para audio, instala también `torch==2.14.1` y
`torchvision==0.29.1` desde ese índice en visión antes del archivo de requisitos.
Se usa Transformers 5.19.0 porque las correcciones del seguimiento dependen de
una interfaz interna. Regresa al entorno principal:

```bash
conda activate sam3
```

## Acceso a Hugging Face

Solicita y acepta las condiciones de cada modelo que quieras usar con la misma
cuenta con la que iniciarás sesión:

- [SAM Audio Small](https://huggingface.co/facebook/sam-audio-small)
- [SAM Audio Base](https://huggingface.co/facebook/sam-audio-base)
- [SAM Audio Large](https://huggingface.co/facebook/sam-audio-large)
- [SAM 3 visual](https://huggingface.co/facebook/sam3), para objetos de video

El acceso a SAM Audio no implica el de SAM 3 visual. Crea un token con permiso
de lectura de los repositorios autorizados e inicia sesión:

```bash
hf auth login
hf auth whoami
```

Pega el token solo en el prompt de la terminal. No lo escribas en el repositorio,
en una URL Git ni en un comando que quede en el historial. Ambos entornos usan
la caché del mismo usuario. En WSL, inicia sesión dentro de Ubuntu; las
credenciales de Windows no se copian automáticamente.

Los pesos se descargan al usarlos y permanecen en caché. La primera ejecución
también puede descargar el encoder de texto. Con todas las dependencias del modelo
ya descargadas, puedes probar `HF_HUB_OFFLINE=1 python run_lab.py`; fallará si
falta algún archivo.

## Compilar, verificar y arrancar

Desde la raíz y con `sam3` activo:

```bash
npm --prefix web ci
npm --prefix web run build
python -m lab.doctor --check-access
python run_lab.py
```

Si omitiste visión, usa `python -m lab.doctor --audio-only --check-access`.
El diagnóstico comprueba imports, FFmpeg, decodificación, dispositivo y permisos,
sin descargar checkpoints. No reemplaza una prueba de inferencia.

Abre **http://127.0.0.1:8765/**. Carga el ejemplo, prepara 5 segundos, escribe
`man speaking`, elige Small y pulsa **Separar sonido**. Detén el servidor con
`Ctrl+C`; el historial se conserva. No se instala un servicio de arranque.

## Configuración

Se usan variables de entorno; **no se carga `.env` automáticamente**. El servidor
y audio usan el Python con el que inicias `run_lab.py`. Visión se busca en el
entorno hermano `sam3-vision`. FFmpeg/ffprobe se buscan primero junto al Python
de audio y después en `PATH`; no hay rutas fijas de Anaconda.

| Variable | Uso |
| --- | --- |
| `SAM_LAB_AUDIO_PYTHON` | Ruta al Python de audio; normalmente no hace falta |
| `SAM_LAB_VISION_PYTHON` | Ruta al Python de visión, útil con Conda `--prefix` o venv |
| `SAM_LAB_FFMPEG` / `SAM_LAB_FFPROBE` | Rutas a los ejecutables de medios |
| `SAM_LAB_DATA` | Directorio de proyectos/resultados; por defecto `.lab-data/` |
| `SAM_LAB_DEVICE` | `auto`, `cuda`, `mps` o `cpu`, para ambos trabajadores |
| `HF_HOME` | Directorio alternativo para caché/credenciales de Hugging Face |
| `HF_HUB_OFFLINE` | `1` para usar exclusivamente archivos ya descargados |

Ejemplos bash/zsh, también dentro de WSL:

```bash
# Falla claramente si Metal no está disponible.
SAM_LAB_DEVICE=mps python -m lab.doctor
# Probar CPU.
SAM_LAB_DEVICE=cpu python run_lab.py
# Entorno visual en un directorio distinto.
export SAM_LAB_VISION_PYTHON="/ruta/al/entorno-visual/bin/python"
python run_lab.py --port 8766
```

Siempre inicia el servidor desde `sam3`. El trabajador visual recibe las rutas
de FFmpeg del entorno de audio.

## Actualizar y desinstalar

Detén el servidor y respalda `.lab-data/`. Actualiza sin sobrescribir cambios:

```bash
git pull --ff-only
conda activate sam3
python -m pip install -r requirements-audio.txt -r requirements-lab.txt
npm --prefix web ci
python run_lab.py --build
```

Si cambia visión, actualiza `requirements-vision.txt` en `sam3-vision`. Revisa
las notas del cambio antes de actualizar PyTorch.

Para desinstalar, detén la app y elimina los entornos con
`conda env remove -n sam3` y `conda env remove -n sam3-vision` solo si no los usa
otro proyecto. Borrar el clon elimina su `.lab-data/` si no la moviste. La caché
de Hugging Face es independiente y puede estar compartida con otras aplicaciones.
