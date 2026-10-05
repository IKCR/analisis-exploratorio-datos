import csv
import json
from collections import defaultdict
from pathlib import Path


from flask import Flask, render_template, send_file

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




def territorial_data():
	rows = load_dataset()
	if not rows:
		return {
			"departamentos": [],
			"municipios": [],
			"zonas": [],
			"participacion_departamentos": [],
			"extremos_municipios": {"mayores": [], "menores": []},
		}

	departamento_counts = defaultdict(int)
	municipio_counts = defaultdict(int)
	zona_counts = defaultdict(int)

	for row in rows:
		departamento = (row.get("DEPARTAMENTO") or "").strip()
		municipio = (row.get("MUNICIPIO") or "").strip()
		zona = (row.get("ETC") or "").strip()

		if departamento:
			departamento_counts[departamento] += 1
		if municipio:
			municipio_counts[municipio] += 1
		if zona:
			zona_counts[zona] += 1

	departamentos = [
		{"label": label, "valor": valor}
		for label, valor in sorted(departamento_counts.items(), key=lambda item: (-item[1], item[0]))
	]
	municipios = [
		{"label": label, "valor": valor}
		for label, valor in sorted(municipio_counts.items(), key=lambda item: (-item[1], item[0]))
	]
	zonas = [
		{"label": label, "valor": valor}
		for label, valor in sorted(zona_counts.items(), key=lambda item: (-item[1], item[0]))
	]

	total_registros = sum(item["valor"] for item in departamentos)
	participacion_departamentos = []
	for item in departamentos[:8]:
		participacion_departamentos.append({
			"label": item["label"],
			"valor": item["valor"],
			"porcentaje": round((item["valor"] / total_registros) * 100, 2) if total_registros else 0,
		})
	resto = total_registros - sum(item["valor"] for item in participacion_departamentos)
	if resto > 0:
		participacion_departamentos.append({
			"label": "Resto",
			"valor": resto,
			"porcentaje": round((resto / total_registros) * 100, 2) if total_registros else 0,
		})

	mayores = municipios[:8]
	menores = list(reversed(municipios[-8:])) if len(municipios) > 8 else municipios[:]
	if len(menores) > 8:
		menores = menores[:8]

	return {
		"departamentos": departamentos,
		"municipios": municipios,
		"zonas": zonas,
		"participacion_departamentos": participacion_departamentos,
		"extremos_municipios": {
			"mayores": mayores,
			"menores": menores,
		},
	}


def territorial_population_data():
	rows = load_dataset()
	years = [
		int(row["AÑO"])
		for row in rows
		if (row.get("AÑO") or "").strip().isdigit()
	]
	if not years:
		return {
			"anio": None,
			"total_poblacion": 0,
			"departamentos": [],
			"diferencias": [],
			"zonas_particulares": [],
			"top_tres": [],
			"participacion_top_tres": 0,
			"promedios": {},
		}

	anio = max(years)
	rows = [row for row in rows if row.get("AÑO") == str(anio)]
	departamentos = defaultdict(lambda: {
		"poblacion": 0,
		"cobertura": 0.0,
		"matriculacion": 0.0,
		"desercion": 0.0,
		"aprobacion": 0.0,
		"repitencia": 0.0,
		"weight_cobertura": 0.0,
		"weight_matriculacion": 0.0,
		"weight_desercion": 0.0,
		"weight_aprobacion": 0.0,
		"weight_repitencia": 0.0,
	})
	zonas = defaultdict(lambda: {
		"poblacion": 0,
		"desercion": 0.0,
		"cobertura": 0.0,
		"weight_desercion": 0.0,
		"weight_cobertura": 0.0,
		"registros": 0,
	})
	total_poblacion = 0
	totales = defaultdict(float)
	pesos = defaultdict(float)

	indicadores = {
		"cobertura": "COBERTURA_NETA",
		"matriculacion": "TASA_MATRICULACIÓN_5_16",
		"desercion": "DESERCIÓN",
		"aprobacion": "APROBACIÓN",
		"repitencia": "REPITENCIA",
	}
	for row in rows:
		poblacion = _to_float(row.get("POBLACIÓN_5_16"))
		departamento = (row.get("DEPARTAMENTO") or "").strip()
		zona = (row.get("ETC") or "").strip()
		if departamento:
			grupo = departamentos[departamento]
			grupo["poblacion"] += poblacion
			for clave, columna in indicadores.items():
				valor = row.get(columna)
				if valor is not None and str(valor).strip():
					numero = _to_float(valor)
					grupo[clave] += numero * poblacion
					grupo[f"weight_{clave}"] += poblacion
					totales[clave] += numero * poblacion
					pesos[clave] += poblacion
			total_poblacion += poblacion

		if zona:
			grupo_zona = zonas[zona]
			grupo_zona["poblacion"] += poblacion
			grupo_zona["registros"] += 1
			for clave, columna in (("cobertura", "COBERTURA_NETA"), ("desercion", "DESERCIÓN")):
				valor = row.get(columna)
				if valor is not None and str(valor).strip():
					grupo_zona[clave] += _to_float(valor) * poblacion
					grupo_zona[f"weight_{clave}"] += poblacion

	def promedio_ponderado(grupo, clave):
		peso = grupo[f"weight_{clave}"]
		return round(grupo[clave] / peso, 2) if peso else None

	departamentos_ordenados = sorted(
		departamentos.items(),
		key=lambda item: (-item[1]["poblacion"], item[0]),
	)
	top_departamentos = [
		{
			"label": nombre,
			"poblacion": grupo["poblacion"],
			"porcentaje": round(grupo["poblacion"] / total_poblacion * 100, 2) if total_poblacion else 0,
		}
		for nombre, grupo in departamentos_ordenados[:8]
	]
	poblacion_resto = total_poblacion - sum(item["poblacion"] for item in top_departamentos)
	if poblacion_resto > 0:
		top_departamentos.append({
			"label": "Resto de departamentos",
			"poblacion": poblacion_resto,
			"porcentaje": round(poblacion_resto / total_poblacion * 100, 2),
		})
	top_tres = top_departamentos[:3]

	diferencias = [
		{
			"label": nombre,
			"poblacion": grupo["poblacion"],
			"cobertura": promedio_ponderado(grupo, "cobertura"),
			"matriculacion": promedio_ponderado(grupo, "matriculacion"),
		}
		for nombre, grupo in departamentos_ordenados[:10]
	]

	zonas_con_indicadores = []
	for nombre, grupo in zonas.items():
		cobertura = promedio_ponderado(grupo, "cobertura")
		desercion = promedio_ponderado(grupo, "desercion")
		if cobertura is not None and desercion is not None:
			zonas_con_indicadores.append({
				"label": nombre,
				"poblacion": grupo["poblacion"],
				"registros": grupo["registros"],
				"cobertura": cobertura,
				"desercion": desercion,
			})

	seleccionadas = []
	for clave, reverse in (("desercion", True), ("cobertura", False), ("cobertura", True)):
		candidata = sorted(
			zonas_con_indicadores,
			key=lambda zona: zona[clave],
			reverse=reverse,
		)[0] if zonas_con_indicadores else None
		if candidata and candidata not in seleccionadas:
			seleccionadas.append(candidata)

	return {
		"anio": anio,
		"total_poblacion": int(total_poblacion),
		"departamentos": top_departamentos,
		"diferencias": diferencias,
		"zonas_particulares": seleccionadas,
		"top_tres": top_tres,
		"participacion_top_tres": round(
			sum(item["porcentaje"] for item in top_tres),
			2,
		),
		"promedios": {
			clave: round(totales[clave] / pesos[clave], 2) if pesos[clave] else None
			for clave in indicadores
		},
	}


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
	resumen = dataset_summary()
	return render_template(
		"analisis/poblacional.html",
		titulo="Dimensión poblacional",
		resumen=resumen,
		top_municipios=top_municipios(),
	)


@app.route("/analisis/territorial")
def territorial():
	resumen = dataset_summary()
	territorios = territorial_data()
	poblacion_territorial = territorial_population_data()
	return render_template(
		"analisis/territorial.html",
		titulo="Dimensión territorial",
		resumen=resumen,
		top_municipios=top_municipios(),
		territorios=territorios,
		territorios_json=json.dumps(territorios, ensure_ascii=False),
		poblacion_territorial=poblacion_territorial,
		poblacion_territorial_json=json.dumps(poblacion_territorial, ensure_ascii=False),
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
