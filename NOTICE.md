# Procedencia y licencias

SAM Audio Lab añade una interfaz y herramientas locales al código de
[SAM Audio](https://github.com/facebookresearch/sam-audio) de Meta.
La base utilizada es `bb4c6999d2677c7402360e426afc01ddfad6dce0`.
Se conserva el historial Git, los encabezados de autoría y la [SAM License](LICENSE).
La interfaz, API, adaptación a Metal y documentación del Lab son aportaciones
de Juan Terven y colaboradores, distribuidas bajo esa misma licencia.
SAM Audio Lab es un proyecto independiente, sin afiliación o patrocinio de Meta.

## SAM Audio y SAM 3

SAM Audio y SAM 3 se publican bajo **SAM License**, versión del 19 de noviembre
de 2025. Este repositorio incluye el acuerdo original de SAM Audio en
[LICENSE](LICENSE) y una copia exacta del acuerdo de SAM 3 en
[licenses/SAM3-LICENSE](licenses/SAM3-LICENSE). Sus condiciones coinciden;
solo difiere el espaciado de los archivos oficiales consultados.

La sección 1.b.i exige distribuir los materiales SAM y sus obras derivadas bajo
ese acuerdo y acompañarlos de una copia. La sección 1.b.ii exige reconocer el
uso de SAM Materials en publicaciones de investigación. El acuerdo completo
también contiene condiciones sobre usos permitidos, controles de comercio,
garantías y terminación; este aviso no lo reemplaza.

Los checkpoints **Small, Base, Large y SAM 3** no se incluyen en Git. Se descargan
desde Hugging Face utilizando el acceso del usuario. Este debe obtener acceso y
aceptar los términos aplicables en los repositorios oficiales. Una licencia de
una biblioteca de inferencia no sustituye la licencia de los pesos que carga.

## Componentes principales

| Componente | Uso en el Lab | Licencia / fuente |
| --- | --- | --- |
| SAM Audio y código derivado del Lab | Separación de audio y aplicación local | [SAM License](LICENSE); [fuente base](https://github.com/facebookresearch/sam-audio/tree/bb4c6999d2677c7402360e426afc01ddfad6dce0) |
| SAM Audio Small, Base y Large | Checkpoints descargados por el usuario | SAM License; [Small](https://huggingface.co/facebook/sam-audio-small), [Base](https://huggingface.co/facebook/sam-audio-base), [Large](https://huggingface.co/facebook/sam-audio-large) |
| SAM 3 de Meta | Localización de objetos y seguimiento | [SAM License incluida](licenses/SAM3-LICENSE); [modelo oficial](https://huggingface.co/facebook/sam3) |
| Hugging Face Transformers | Implementaciones `Sam3Model` y `Sam3TrackerVideoModel`, entre otras | [Apache 2.0](https://github.com/huggingface/transformers/blob/v5.19.0/LICENSE); independiente de la licencia SAM de los pesos |
| Perception Encoder (PE) | Encoder visual importado desde `core.vision_encoder.pe` | [Apache 2.0 incluida](licenses/PERCEPTION-ENCODER-LICENSE); [fuente fijada](https://github.com/facebookresearch/perception_models/tree/e72b6810b1133e1c879f2cc965d276eb73803f1f) |
| DACVAE | Códec de audio de SAM Audio | [Apache 2.0 incluida](licenses/DACVAE-LICENSE); [fuente fijada](https://github.com/facebookresearch/dacvae/tree/414c20785fc3a28373073ea8ef7a1316eeeaca6e) |

**Perception Encoder y Perception Language Model son componentes distintos.**
El repositorio Perception Models incluye `LICENSE.PE` (Apache 2.0) y
[`LICENSE.PLM`](https://github.com/facebookresearch/perception_models/blob/e72b6810b1133e1c879f2cc965d276eb73803f1f/LICENSE.PLM)
(FAIR Noncommercial Research License). El Lab utiliza PE y no carga modelos PLM.
Aunque el `setup.py` del paquete declara una licencia no comercial, su README
identifica por separado las licencias de PE y PLM; por eso este inventario
distingue los componentes en lugar de asignar esa restricción a todo PE.

PyTorch, FFmpeg, T5, React, WaveSurfer y las demás dependencias conservan sus
licencias y avisos, incluidos con sus respectivas distribuciones. Esta tabla
identifica los componentes principales; no es un inventario exhaustivo de
dependencias transitivas. Los textos copiados y las revisiones de origen se
documentan en [licenses/README.md](licenses/README.md).

## Medios y capturas

`examples/assets/office.mp4` y `assets/sam_audio_main_model.png` se conservaron
del repositorio original, bajo sus avisos y condiciones originales. Las capturas
en `docs/assets/` muestran la interfaz del Lab con ese ejemplo público y sus
pruebas locales; no incluyen archivos privados del usuario. `office-32s.mp4`,
visible en el historial capturado, es una repetición del ejemplo para validar
recortes largos, no otro medio del usuario.

Los checkpoints, tokens y el directorio `.lab-data/` no se publican. Las capturas
solo muestran los resultados y tiempos del ejemplo. La documentación upstream
se conserva en `docs/upstream/`; las guías del Lab están en la raíz y en `docs/`.
