<h1 align="center">SAM Audio Lab</h1>

<p align="center">
  Separa sonidos de audio y video con texto, regiones y objetos.<br>
  Interfaz web local en español · SAM Audio Small, Base y Large · SAM 3 visual
</p>

<p align="center">
  <a href="https://github.com/jrterven/sam-audio-lab/actions/workflows/ci.yaml"><img src="https://github.com/jrterven/sam-audio-lab/actions/workflows/ci.yaml/badge.svg" alt="Pruebas y compilación"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/Licencia-SAM-345fe5" alt="Licencia SAM"></a>
  <a href="docs/INSTALLATION.md"><img src="https://img.shields.io/badge/macOS-Metal-345fe5" alt="macOS con Metal"></a>
  <a href="docs/INSTALLATION.md#linux"><img src="https://img.shields.io/badge/Linux%20%2F%20WSL2-Gu%C3%ADas-7187b0" alt="Guías para Linux y WSL2"></a>
</p>

<p align="center">
  <a href="#instalar">Instalar</a> ·
  <a href="#correr-la-aplicación">Correr</a> ·
  <a href="#capturas">Capturas</a> ·
  <a href="LAB.md">Uso</a> ·
  <a href="docs/TROUBLESHOOTING.md">Ayuda</a> ·
  <a href="#autoría-y-licencia">Licencia</a>
</p>

![Selección de una persona con SAM 3 y regiones positivas y negativas en SAM Audio Lab](docs/assets/sam-audio-lab.jpg)

<p align="center"><sub>Captura real con el video de ejemplo: máscara de SAM 3, seguimiento y regiones temporales.</sub></p>

## Qué puedes hacer

- **Prompts de texto:** `man speaking`, `dog barking`, `guitar` o tu propia descripción.
- **Regiones temporales:** dibuja, mueve y ajusta intervalos donde el sonido está
  presente (+) o ausente (−). Son referencias; el recorte se controla por separado.
- **Objetos del video:** encuentra objetos por texto, elige una instancia, usa clics
  positivos/negativos y corrige su seguimiento en otros fotogramas.
- **Comparación manual:** selecciona Small, Base o Large; duplica una prueba desde
  el historial para repetir sus entradas con otro modelo.
- **Escucha sincronizada:** cambia entre Original, Aislado y Residual conservando
  la posición. Exporta WAV o el fragmento de video en MP4 con la pista elegida.
- **Historial persistente:** conserva prompts, máscaras, modelo, semilla,
  revisiones y tiempos. La aplicación permite cancelar trabajos y recuperarse.

Los medios se procesan en tu computadora. Se necesita Internet para instalar
dependencias y descargar modelos desde Hugging Face; los archivos cargados no se
envían a un servicio de inferencia. El servidor escucha solo en `127.0.0.1`.

## Capturas

<details>
<summary><strong>Texto y regiones</strong> · describe el sonido y marca dónde aparece</summary>

![Prompt woman speaking con regiones positiva y negativa, recorte independiente y selector de modelo](docs/assets/text-and-regions.jpg)

Texto, regiones y guía visual se pueden combinar en la misma ejecución.
El recorte superior determina la duración de la salida; las regiones inferiores
indican presencia o ausencia del sonido.

</details>

<details open>
<summary><strong>Resultados e historial</strong> · escucha, compara y exporta</summary>

![Resultado con tiempos por etapa, exportaciones WAV y MP4 e historial de pruebas con Small, Base y Large](docs/assets/results-and-history.jpg)

Los tiempos corresponden a ejecuciones reales del ejemplo `office.mp4` y a una
copia repetida para la prueba de 30 segundos. No son un benchmark controlado.

</details>

## Plataformas

| Sistema | Ejecución | Estado de validación |
| --- | --- | --- |
| macOS con Apple Silicon | Metal / MPS, float32 | Small, Base, Large y SAM 3 visual probados en M4 Max, 128 GB |
| Linux | NVIDIA CUDA si PyTorch la detecta; CPU como alternativa | Instalación documentada; inferencia GPU pendiente de validar en hardware Linux |
| Windows 11 / Windows 10 compatible con WSL2 | Ubuntu dentro de WSL2; CUDA o CPU | Instalación documentada; pendiente de validar en Windows |
| Mac Intel | CPU, sujeto a disponibilidad de paquetes | No validado; no es la plataforma recomendada |

**Windows nativo no está soportado por el supervisor actual. Usa WSL2.**
No se ha establecido un mínimo garantizado de RAM/VRAM. Empieza con Small y un clip
de 5 segundos. Los checkpoints ocupan aproximadamente 4.75 GiB (Small),
7.19 GiB (Base) y 13.84 GiB (Large), sin contar encoders, SAM 3 ni los entornos.

## Instalar

Requisitos: Git, Conda (Miniforge, Miniconda o Anaconda), Node.js 22.12+ con npm,
FFmpeg y una cuenta de Hugging Face con acceso aprobado a los modelos.

```bash
git clone https://github.com/jrterven/sam-audio-lab.git
cd sam-audio-lab
```

Continúa con la guía de tu sistema:

| macOS | Linux | Windows |
| :---: | :---: | :---: |
| [Apple Silicon / Metal](docs/INSTALLATION.md#macos-con-apple-silicon) | [NVIDIA CUDA o CPU](docs/INSTALLATION.md#linux) | [Ubuntu en WSL2](docs/INSTALLATION.md#windows-con-wsl2) |

La guía crea dos entornos: **`sam3`** para audio/API (Python 3.11, Transformers 4)
y **`sam3-vision`** para segmentación visual (Python 3.12, Transformers 5).
No se deben combinar. El entorno visual es opcional para texto y regiones.

## Correr la aplicación

Una vez instalada, desde la raíz del repositorio:

```bash
conda activate sam3
python -m lab.doctor
python run_lab.py
```

Abre **[127.0.0.1:8765](http://127.0.0.1:8765/)**. Detén el servidor con `Ctrl+C` en la terminal.
También puedes iniciarlo sin activar el entorno:

```bash
conda run --no-capture-output -n sam3 python run_lab.py
```

`python run_lab.py --build` recompila la interfaz; `--port 8766` usa otro puerto.
Los modelos se descargan al usarlos por primera vez. El dropdown indica si el
checkpoint está en caché. Tener el checkpoint no garantiza que todos sus encoders
ya estén descargados.

## Primera prueba

1. Usa el botón de ejemplo para cargar `office.mp4`, o carga tu propio archivo.
2. Selecciona un fragmento de 0 a 5 segundos y prepáralo.
3. Escribe `man speaking`, selecciona **Small** y pulsa **Separar sonido**.
4. Escucha Aislado y Residual; descarga el WAV.
5. Duplica la prueba y selecciona Base o Large para comparar.

Para probar visión, busca `person`, elige una máscara, pulsa **Seguir objeto en
el clip** y revisa el resultado antes de separar. [Guía completa de uso](LAB.md).

## Límites y resultados medidos

Se aceptan archivos largos, procesando recortes de **hasta 30 segundos**. Cada
ejecución separa una fuente/objeto con audio mono a 48 kHz, precisión float32,
semilla 42 y una candidata. No incluye reranking ni predicción automática de
regiones. La máscara visual guía la separación; no garantiza aislamiento perfecto.

Mediciones individuales en M4 Max, 128 GB (9 de octubre de 2026):

| Prueba | Clip | Separación de audio |
| --- | ---: | ---: |
| Small, texto + regiones + objeto | 5 s | 6.45 s |
| Base, texto | 5 s | 13.65 s |
| Large, texto | 5 s | 12.78 s |
| Small, texto + regiones, recorte desde el segundo 2 | 30 s | 24.63 s |

Estas mediciones no son un benchmark controlado ni una evaluación de calidad.
El seguimiento visual de 5 s tardó **379.53 s adicionales**, y el encoder visual
de audio, 29.20 s. El factor de tiempo real divide únicamente el tiempo de
separación por la duración del audio. [Detalles de validación](LAB.md#validación-realizada-en-esta-mac).

## Datos y documentación

Los proyectos, medios y resultados están en `.lab-data/`; los checkpoints usan la
caché de Hugging Face. Ninguno se incluye en Git. Conserva **todo** `.lab-data/`
para respaldar el historial, deteniendo antes el servidor.

- [Instalación, credenciales y configuración](docs/INSTALLATION.md)
- [Uso, tiempos e inferencias reales](LAB.md)
- [Diagnóstico y errores frecuentes](docs/TROUBLESHOOTING.md)
- [API, procesos y almacenamiento](docs/ARCHITECTURE.md)
- [Contribuir y ejecutar pruebas](CONTRIBUTING.md)
- [Registro del entorno Mac original](MACOS.md)
- [Documentación original de SAM Audio](docs/upstream/README.md)

## Autoría y licencia

SAM Audio Lab es una adaptación independiente mantenida por
[Juan Terven](https://github.com/jrterven); no es una aplicación oficial de Meta.
Parte de [facebookresearch/sam-audio](https://github.com/facebookresearch/sam-audio),
commit `bb4c6999d2677c7402360e426afc01ddfad6dce0`, y conserva su historial y avisos.

El código derivado y las aportaciones del Lab se distribuyen bajo la
**[SAM License](LICENSE)** de Meta, conservada sin cambios. **SAM 3 también usa
SAM License**: se incluye una [copia oficial](licenses/SAM3-LICENSE) con su
[procedencia y revisión](licenses/README.md).

La implementación de SAM 3 en Transformers, Perception Encoder y DACVAE tienen
licencias propias; no cambian la licencia de los modelos de Meta. Los pesos se
descargan desde los repositorios oficiales de Hugging Face y no se redistribuyen
aquí. Consulta **[NOTICE.md](NOTICE.md)** para la atribución, el alcance de cada
licencia y las condiciones de redistribución.
