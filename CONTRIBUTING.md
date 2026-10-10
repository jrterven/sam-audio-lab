# Contribuir a SAM Audio Lab

Este repositorio mantiene la aplicación local. Para cambios en el modelo original,
consulta [SAM Audio upstream](https://github.com/facebookresearch/sam-audio) y sus
[instrucciones de contribución](docs/upstream/CONTRIBUTING.md).

## Preparar y probar

Completa [la instalación](docs/INSTALLATION.md). Desde la raíz:

```bash
conda activate sam3
python -m pip install -r requirements-lab-dev.txt
python -m pytest tests/test_lab.py tests/test_portability.py -q
npm --prefix web ci
npm --prefix web run build
```

Estas pruebas no descargan checkpoints. Comprueban recortes, VFR, exportación,
validación de entradas, persistencia, cancelación en cola, límites de la API,
lotes del encoder y selección/configuración del dispositivo. Las pruebas de
política CUDA no demuestran inferencia CUDA en hardware real.

Para desarrollar el frontend, inicia la API en una terminal con `python run_lab.py`
y, en otra, `npm --prefix web run dev`. Abre la URL que imprime Vite; `/api` se
redirige a la API local en el puerto 8765. La compilación de producción se vuelve
a generar con `python run_lab.py --build`.

## Inferencia real, opcional

Requiere permisos en Hugging Face, modelos descargables y memoria suficiente.
Con el servidor iniciado en 8765:

```bash
python -m tests.smoke_lab
python -m tests.recovery_lab
python -m tests.vision_regression
```

Ejecuta primero `smoke_lab`: importa el ejemplo, prepara seguimiento, ejecuta los
tres tamaños y genera `outputs/lab-validation.json`. Las siguientes pruebas
comprueban recuperación/cancelación y correcciones visuales. Son pruebas costosas,
crean resultados locales y pueden descargar checkpoints. No se ejecutan en CI.
El historial y los informes completos no se suben al repositorio.

## Pull requests

1. Crea una rama desde `main` y mantén el cambio acotado.
2. Describe el problema y el comportamiento resultante.
3. Incluye pruebas relevantes y actualiza las guías si cambia la instalación.
4. Indica sistema, dispositivo, modelo y duración de cualquier inferencia real.
5. No incluyas tokens, pesos, cachés, entornos ni medios privados.

CI compila el frontend y ejecuta pruebas de backend en CPU sin checkpoints.
Una prueba de CI correcta no certifica los modelos en GPU. Las contribuciones a
este repositorio se distribuyen bajo [la licencia incluida](LICENSE). La política
CLA del documento upstream corresponde al proyecto original de Meta.
