import csv
import json
from collections import defaultdict
from pathlib import Path

from flask import Flask, render_template, send_file
from flask import request

from poblacional import tablero_poblacional

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "data" / "educacion_municipios.csv"

_CACHE_TEMPORAL = None


def _to_float(value):
	if value is None:
		return 0.0
	text = str(value).strip()
	if not text or text.lower() == "nan":
		return 0.0
	text = text.replace("%", "").replace(".", "").replace(",", ".")
	try:
		return float(text)
	except ValueError:
		return 0.0


def load_dataset():
	if not DATASET_PATH.exists():
		return []
	with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as archivo:
		return list(csv.DictReader(archivo))


def dataset_summary():
	rows = load_dataset()
	if not rows:
		return {
			"municipios": 0,
			"departamentos": 0,
			"promedio_matriculacion": 0.0,
			"mejor_municipio": "Sin datos",
			"mejor_tasa": 0.0,
			"peor_municipio": "Sin datos",
			"peor_tasa": 0.0,
		}

	tasas = [_to_float(row.get("TASA_MATRICULACIÓN_5_16")) for row in rows]
	mejor = max(rows, key=lambda row: _to_float(row.get("TASA_MATRICULACIÓN_5_16")))
	peor = min(rows, key=lambda row: _to_float(row.get("TASA_MATRICULACIÓN_5_16")))
	promedio = sum(tasas) / len(tasas) if tasas else 0.0

	return {
		"municipios": len(rows),
		"departamentos": len({row.get("DEPARTAMENTO") for row in rows if row.get("DEPARTAMENTO")}),
		"promedio_matriculacion": round(promedio, 2),
		"mejor_municipio": mejor.get("MUNICIPIO", "Sin datos"),
		"mejor_tasa": round(_to_float(mejor.get("TASA_MATRICULACIÓN_5_16")), 2),
		"peor_municipio": peor.get("MUNICIPIO", "Sin datos"),
		"peor_tasa": round(_to_float(peor.get("TASA_MATRICULACIÓN_5_16")), 2),
	}


def top_municipios(limit=5):
	rows = sorted(
		load_dataset(),
		key=lambda row: _to_float(row.get("TASA_MATRICULACIÓN_5_16")),
		reverse=True,
	)
	return [
		{
			"municipio": row.get("MUNICIPIO", "-"),
			"departamento": row.get("DEPARTAMENTO", "-"),
			"tasa": round(_to_float(row.get("TASA_MATRICULACIÓN_5_16")), 2),
		}
		for row in rows[:limit]
	]


def _build_datos_temporales():
	global _CACHE_TEMPORAL
	if _CACHE_TEMPORAL is not None:
		return _CACHE_TEMPORAL

	rows = load_dataset()
	grupos = defaultdict(lambda: defaultdict(lambda: {
		"cob": [], "des": [], "con": [],
		"cob_t": [], "cob_p": [], "cob_s": [], "cob_m": [],
	}))

	for row in rows:
		try:
			anio = int(row.get("AÑO", 0))
		except ValueError:
			continue
		depto = row.get("DEPARTAMENTO", "").strip()
		if not depto or anio < 2011:
			continue

		campos = {
			"cob":   _to_float(row.get("COBERTURA_NETA")),
			"des":   _to_float(row.get("DESERCIÓN")),
			"con":   _to_float(row.get("SEDES_CONECTADAS_A_INTERNET")),
			"cob_t": _to_float(row.get("COBERTURA_NETA_TRANSICIÓN")),
			"cob_p": _to_float(row.get("COBERTURA_NETA_PRIMARIA")),
			"cob_s": _to_float(row.get("COBERTURA_NETA_SECUNDARIA")),
			"cob_m": _to_float(row.get("COBERTURA_NETA_MEDIA")),
		}

		for destino in [depto, "TODOS"]:
			g = grupos[destino][anio]
			for campo, v in campos.items():
				if v > 0:
					g[campo].append(v)

	def _avg(lst):
		return round(sum(lst) / len(lst), 2) if lst else None

	resultado = {}
	for depto, por_anio in grupos.items():
		resultado[depto] = {}
		for anio, g in por_anio.items():
			resultado[depto][anio] = {k: _avg(v) for k, v in g.items()}

	_CACHE_TEMPORAL = resultado
	return resultado


@app.route("/")
def inicio():
	return render_template("index.html", titulo="Estadísticas en Educación", resumen=dataset_summary())


@app.route("/data/educacion_municipios.csv")
def dataset_file():
	return send_file(DATASET_PATH, mimetype="text/csv", as_attachment=True, download_name="educacion_municipios.csv")


@app.route("/analisis/poblacional")
def poblacional():
	anio = request.args.get("anio", type=int)
	departamento = request.args.get("departamento")
	return render_template(
		"analisis/poblacional.html",
		titulo="Dimensión poblacional",
		datos=tablero_poblacional(anio, departamento),
	)


@app.route("/analisis/territorial")
def territorial():
	resumen = dataset_summary()
	return render_template(
		"analisis/territorial.html",
		titulo="Dimensión territorial",
		resumen=resumen,
		top_municipios=top_municipios(),
	)


@app.route("/analisis/temporal")
def temporal():
	datos = _build_datos_temporales()
	departamentos = sorted(k for k in datos if k != "TODOS")
	return render_template(
		"analisis/temporal.html",
		titulo="Dimensión temporal",
		departamentos=departamentos,
		datos_json=json.dumps(datos, ensure_ascii=False),
	)


@app.route("/analisis/multivariada")
def multivariada():
	return render_template(
		"analisis/multivariada.html",
		titulo="Dimensión multivariada",
	)


if __name__ == "__main__":
	app.run(debug=True)
