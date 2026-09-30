# Reglas de trabajo del equipo

Estas reglas son obligatorias para todos los integrantes del Grupo 1.

## 1. Nadie sube cambios directamente a main

La rama `main` es la versión oficial y siempre debe funcionar. Todo cambio entra por medio de un pull request revisado por el integrante 1.

## 2. Cada integrante trabaja en su propia rama

| Integrante | Rama |
|------------|------|
| 1 | `feature/dimension-poblacional` |
| 2 | `feature/dimension-territorial` |
| 3 | `feature/dimension-temporal` |
| 4 | `feature/dimension-multivariada` |

El integrante 2 puede usar además una rama `feature/estructura-flask` para la configuración inicial de Flask.

## 3. Flujo de trabajo

1. Actualizar `main` antes de empezar.
2. Crear o actualizar la rama asignada desde `main`.
3. Desarrollar el tablero de la dimensión.
4. Hacer commits descriptivos (mínimo tres por integrante).
5. Subir la rama al repositorio.
6. Crear un pull request hacia `main`.
7. Solicitar la revisión del integrante 1.
8. Aplicar las correcciones solicitadas.
9. Esperar la aprobación y la fusión.

## 4. Mensajes de commit

- Escribir en español.
- Describir qué se hizo, empezando con un verbo.
- Ejemplos correctos: `Agrega gráfica de distribución por departamento`, `Corrige filtro de año en dimensión temporal`.
- Ejemplos incorrectos: `cambios`, `ya`, `nombres`, `asdf`.

## 5. Cada quien modifica solo sus archivos

Cada integrante trabaja en los archivos de su dimensión. 
Los archivos compartidos (`app.py`, `templates/base.html`, `requirements.txt` y el archivo de datos) solo se modifican después de avisar al equipo, para evitar conflictos.

## 6. Datos

- El conjunto de datos está en `data/educacion_municipios.csv`.
- No se debe modificar el archivo original. Las limpiezas y transformaciones se hacen en el código.
