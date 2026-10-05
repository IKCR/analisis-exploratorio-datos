"""
Dimensión poblacional
Pregunta: ¿Cómo está compuesta y distribuida la población analizada
según sus principales características?

Este archivo hace la limpieza de los datos y todos los cálculos
de la dimensión poblacional. Solo usa librerías que ya trae Python.
"""

import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "data" / "educacion_municipios.csv"

# Grupos de municipios según su población de 5 a 16 años
GRUPOS_TAMANO = [
    ("Menos de 2.000", 0, 2000),
    ("2.000 a 5.000", 2000, 5000),
    ("5.000 a 10.000", 5000, 10000),
    ("10.000 a 50.000", 10000, 50000),
    ("Más de 50.000", 50000, float("inf")),
]

# Niveles de cobertura neta
NIVELES_COBERTURA = [
    ("Baja (menos de 70 %)", 0, 70),
    ("Media (70 % a 90 %)", 70, 90),
    ("Alta (90 % o más)", 90, float("inf")),
]

# Nombres de departamento escritos de dos formas distintas en el archivo
NOMBRES_DEPARTAMENTO = {
    "Bogotá D.C.": "Bogotá, D.C.",
    "Archipiélago de San Andrés. Providencia y Santa Catalina":
        "Archipiélago de San Andrés, Providencia y Santa Catalina",
}

_CACHE = None


# ---------------------------------------------------------------
# 1. Limpieza de datos
# ---------------------------------------------------------------

def limpiar_poblacion(valor, anio):
    """Convierte la población a número entero.

    En el archivo la población viene escrita de varias formas:
    - "3524"       -> 3524 (forma normal)
    - "1,174,274"  -> 1174274 (comas como separador de miles)
    - "3.5"        -> 3500 (en 2021: punto de miles sin los ceros finales)
    - "1"          -> 1000 (en 2021: "1.000" quedó escrito como "1")
    """
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        return None
    if "," in texto:
        texto = texto.replace(",", "")
        return int(texto) if texto.isdigit() else None
    if "." in texto:
        entero, miles = texto.split(".", 1)
        miles = miles.ljust(3, "0")
        numero = entero + miles
        return int(numero) if numero.isdigit() else None
    if not texto.isdigit():
        return None
    numero = int(texto)
    if anio == 2021 and numero < 10:
        numero = numero * 1000
    return numero


def limpiar_porcentaje(valor):
    """Convierte un texto como "56,11%" en el número 56.11.

    Devuelve None si el dato está vacío. Un 0 % se conserva como 0,
    porque es un dato real (por ejemplo, deserción de 0 %).
    """
    if valor is None:
        return None
    texto = str(valor).strip().replace("%", "").replace(",", ".")
    if not texto or texto.lower() == "nan":
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def cargar_datos():
    """Lee el CSV, limpia las columnas que usa esta dimensión
    y excluye las filas de total "NACIONAL"."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    registros = []
    if not DATASET_PATH.exists():
        _CACHE = registros
        return registros

    with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            departamento = (fila.get("DEPARTAMENTO") or "").strip()
            if not departamento or departamento.upper() == "NACIONAL":
                continue
            departamento = NOMBRES_DEPARTAMENTO.get(departamento, departamento)
            try:
                anio = int(fila.get("AÑO"))
            except (TypeError, ValueError):
                continue

            registros.append({
                "anio": anio,
                "municipio": (fila.get("MUNICIPIO") or "").strip(),
                "departamento": departamento,
                "poblacion": limpiar_poblacion(fila.get("POBLACIÓN_5_16"), anio),
                "cobertura_neta": limpiar_porcentaje(fila.get("COBERTURA_NETA")),
                "desercion": limpiar_porcentaje(fila.get("DESERCIÓN")),
                "aprobacion": limpiar_porcentaje(fila.get("APROBACIÓN")),
            })

    _CACHE = registros
    return registros


# ---------------------------------------------------------------
# 2. Funciones de apoyo
# ---------------------------------------------------------------

def _promedio_ponderado(registros, campo):
    """Promedio de una tasa ponderado por la población de cada municipio.
    Así un municipio grande pesa más que uno pequeño."""
    suma = 0
    pesos = 0
    for r in registros:
        if r[campo] is not None and r["poblacion"]:
            suma += r[campo] * r["poblacion"]
            pesos += r["poblacion"]
    return round(suma / pesos, 1) if pesos else None


def _mediana(valores):
    valores = sorted(valores)
    n = len(valores)
    if n == 0:
        return None
    mitad = n // 2
    if n % 2 == 1:
        return valores[mitad]
    return (valores[mitad - 1] + valores[mitad]) / 2


def _resumen_variable(valores, decimales=1):
    valores = [v for v in valores if v is not None]
    if not valores:
        return {"minimo": None, "mediana": None, "promedio": None, "maximo": None}
    return {
        "minimo": round(min(valores), decimales),
        "mediana": round(_mediana(valores), decimales),
        "promedio": round(sum(valores) / len(valores), decimales),
        "maximo": round(max(valores), decimales),
    }


def _porcentaje(parte, total):
    return round(parte / total * 100, 1) if total else 0.0


# ---------------------------------------------------------------
# 3. Cálculo principal del tablero
# ---------------------------------------------------------------

def tablero_poblacional(anio=None, departamento=None):
    """Calcula todo lo que muestra el tablero, según los filtros elegidos."""
    datos = cargar_datos()
    anios = sorted({r["anio"] for r in datos})
    departamentos = sorted({r["departamento"] for r in datos})

    if anio not in anios:
        anio = anios[-1] if anios else None
    if departamento not in departamentos:
        departamento = "Todos"

    seleccion = [r for r in datos if r["anio"] == anio]
    if departamento != "Todos":
        seleccion = [r for r in seleccion if r["departamento"] == departamento]
    con_poblacion = [r for r in seleccion if r["poblacion"]]

    poblacion_total = sum(r["poblacion"] for r in con_poblacion)
    total_municipios = len(seleccion)

    # Indicadores
    indicadores = {
        "poblacion_total": poblacion_total,
        "municipios": total_municipios,
        "cobertura_ponderada": _promedio_ponderado(seleccion, "cobertura_neta"),
        "cobertura_simple": _resumen_variable(
            [r["cobertura_neta"] for r in seleccion])["promedio"],
        "poblacion_mediana": _mediana([r["poblacion"] for r in con_poblacion]),
    }

    # Gráfica 1 y 2: grupos de municipios por tamaño
    grupos = []
    for nombre, minimo, maximo in GRUPOS_TAMANO:
        del_grupo = [r for r in con_poblacion if minimo <= r["poblacion"] < maximo]
        poblacion_grupo = sum(r["poblacion"] for r in del_grupo)
        grupos.append({
            "nombre": nombre,
            "municipios": len(del_grupo),
            "poblacion": poblacion_grupo,
            "pct_municipios": _porcentaje(len(del_grupo), len(con_poblacion)),
            "pct_poblacion": _porcentaje(poblacion_grupo, poblacion_total),
            "cobertura": _promedio_ponderado(del_grupo, "cobertura_neta"),
            "desercion": _promedio_ponderado(del_grupo, "desercion"),
        })

    con_municipios = [g for g in grupos if g["municipios"] > 0]
    predominante = max(con_municipios, key=lambda g: g["municipios"]) if con_municipios else None
    minoritario = min(con_municipios, key=lambda g: g["municipios"]) if con_municipios else None
    mayor_poblacion = max(con_municipios, key=lambda g: g["poblacion"]) if con_municipios else None

    # Gráfica 3: municipios por nivel de cobertura neta
    con_cobertura = [r for r in seleccion if r["cobertura_neta"] is not None]
    niveles = []
    for nombre, minimo, maximo in NIVELES_COBERTURA:
        cantidad = len([r for r in con_cobertura if minimo <= r["cobertura_neta"] < maximo])
        niveles.append({
            "nombre": nombre,
            "municipios": cantidad,
            "pct": _porcentaje(cantidad, len(con_cobertura)),
        })

    # Tabla: distribución de las variables principales
    distribucion = [
        {"variable": "Población de 5 a 16 años",
         **_resumen_variable([r["poblacion"] for r in con_poblacion], 0)},
        {"variable": "Cobertura neta (%)",
         **_resumen_variable([r["cobertura_neta"] for r in seleccion])},
        {"variable": "Deserción (%)",
         **_resumen_variable([r["desercion"] for r in seleccion])},
        {"variable": "Aprobación (%)",
         **_resumen_variable([r["aprobacion"] for r in seleccion])},
    ]

    return {
        "anio": anio,
        "departamento": departamento,
        "anios": anios,
        "departamentos": departamentos,
        "indicadores": indicadores,
        "grupos": grupos,
        "predominante": predominante,
        "minoritario": minoritario,
        "mayor_poblacion": mayor_poblacion,
        "niveles": niveles,
        "distribucion": distribucion,
        "sin_poblacion": total_municipios - len(con_poblacion),
    }
