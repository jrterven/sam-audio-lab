# Diagnóstico y solución de problemas

Desde la raíz del clon, con `conda activate sam3`:

```bash
python -m lab.doctor
# Comprueba también el acceso a los repositorios; requiere Internet.
python -m lab.doctor --check-access
```

Usa `--audio-only` si no instalaste el entorno visual. El diagnóstico no descarga
pesos ni modifica tus proyectos. Los logs de cada trabajo están en
`.lab-data/logs/`; la interfaz muestra el error resumido.

| Síntoma | Qué comprobar |
| --- | --- |
| `conda: command not found` | Instala Conda e inicializa tu shell con las instrucciones de esa distribución; abre una terminal nueva |
| `npm: command not found` o error de versión Node | Instala Node 22.12+ y comprueba que `node` y `npm` estén en `PATH` |
| No existe `web/dist/index.html` | Ejecuta `npm --prefix web ci` y `npm --prefix web run build` |
| `ModuleNotFoundError: core`, `dacvae`, `sam_audio` | Completa las instalaciones `--no-deps` de [INSTALLATION.md](INSTALLATION.md); arranca desde `sam3` |
| `Sam3TrackerVideoModel` no existe | Instala `requirements-vision.txt` en `sam3-vision`; no actualices Transformers del entorno de audio a v5 |
| Falta el entorno visual | Comprueba `conda env list`. Si está en otro directorio, configura `SAM_LAB_VISION_PYTHON` con su ruta absoluta |
| Hugging Face devuelve 401/403 o `GatedRepoError` | Comprueba `hf auth whoami`, la aprobación del repositorio y los permisos de lectura del token. SAM 3 requiere acceso separado |
| `Could not load libtorchcodec`, FFmpeg o símbolos sin resolver | Comprueba compatibilidad PyTorch/TorchCodec y bibliotecas compartidas de FFmpeg. Instala FFmpeg con Conda en `sam3`; un ejecutable estático aislado puede no bastar |
| CUDA no aparece | Ejecuta `nvidia-smi` y comprueba `torch.cuda.is_available()` en ambos entornos. Revisa controlador y variante de PyTorch |
| MPS no aparece en Apple Silicon | Comprueba arquitectura arm64 y ejecuta desde Terminal con acceso a GPU. Algunos entornos aislados ocultan Metal |
| Operación visual incompatible con MPS | El trabajador visual reintenta esa etapa en CPU y registra el motivo. Ese fallback no se aplica a errores de memoria |
| Memoria insuficiente | Cancela, selecciona Small y reduce la duración. Cierra otros procesos que consuman memoria. El Lab no cambia el modelo silenciosamente |
| Video sin pista de audio | Se rechaza de forma explícita. Usa un archivo que incluya audio |
| No encuentra el objeto | Prueba una descripción en inglés o un clic positivo; elige otra instancia/fotograma. Revisa las máscaras antes de separar |
| Botón de separar deshabilitado después de añadir clics | Completa el seguimiento o quita la guía visual |
| Puerto ocupado | Ejecuta `python run_lab.py --port 8766` y abre ese puerto |
| En Windows no se abre localhost | Comprueba que el servidor siga activo en Ubuntu/WSL2 y el puerto sea correcto. No lo ejecutes con Python de Windows |

## Descargas lentas o incompletas

El ejecutor usa `HF_HUB_DISABLE_XET=1` y timeout de descarga de 60 segundos por
defecto. La primera ejecución descarga checkpoint y encoders; las siguientes
reutilizan la caché. Puedes cancelar y repetir. No borres toda la caché de Hugging
Face: puede contener modelos de otros proyectos.

El indicador «descargado» verifica el checkpoint de audio; la descarga de un
encoder aún podría ser necesaria. Si usas modo offline y falta un archivo,
inicia una vez con conexión.

## ¿Por qué visión tarda más que audio?

SAM 3 produce una máscara por fotograma del proxy de 25 fps. Un clip de 30 s
contiene 750 fotogramas. La detección, seguimiento, encoder visual de audio y
separación son etapas distintas. El factor de tiempo real solo mide separación;
no representa el tiempo total del flujo visual.

## Recuperar o mover el historial

1. Detén el servidor para obtener una copia consistente de SQLite y sus archivos WAL.
2. Copia **todo** `.lab-data/`, incluidas subcarpetas y archivos SQLite asociados.
3. En otra instalación, restaura la carpeta o apunta `SAM_LAB_DATA` a ella.
4. Inicia el servidor. Los trabajos que quedaron activos se marcarán interrumpidos.

El historial referencia medios y máscaras: copiar únicamente la base de datos
deja resultados incompletos. Los checkpoints se conservan por separado en la
caché de Hugging Face. Los entornos Conda no forman parte del respaldo.

## Informar un problema

Incluye sistema/arquitectura, RAM/VRAM, versiones, modelo, duración, modalidad y
pasos reproducibles. Adjunta la salida de `lab.doctor` y un error relevante,
eliminando rutas privadas o credenciales. Usa el ejemplo incluido para reproducir
el fallo cuando sea posible. No publiques `.lab-data/` ni medios privados.
