import base64
import csv
import io
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from flask import Flask, render_template, request, send_file

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "data" / "educacion_municipios.csv"


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
	return render_template(
		"analisis/territorial.html",
		titulo="Dimensión territorial",
		resumen=resumen,
		top_municipios=top_municipios(),
	)


def _fig_to_b64(fig):
	buf = io.BytesIO()
	fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
	buf.seek(0)
	data = base64.b64encode(buf.read()).decode("utf-8")
	plt.close(fig)
	return data


def _colores_lineas():
	return ["#1ea86a", "#ff7b54", "#8c6bff", "#ffc857"]


def _procesar_temporal(departamento=None, rango=None):
	rows = load_dataset()
	if not rows:
		return {}, {}, {}, [], {}

	anio_min, anio_max = 2011, 2024
	if rango == "2011-2018":
		anio_max = 2018
	elif rango == "2019-2024":
		anio_min = 2019

	filtrados = []
	for row in rows:
		try:
			anio = int(row.get("AÑO", 0))
		except ValueError:
			continue
		if not (anio_min <= anio <= anio_max):
			continue
		if departamento and departamento != "TODOS":
			if row.get("DEPARTAMENTO", "").strip() != departamento:
				continue
		filtrados.append(row)

	# Agrupación por año
	por_anio = defaultdict(lambda: {"cob": [], "des": [], "con": [],
									"cob_t": [], "cob_p": [], "cob_s": [], "cob_m": []})
	for row in filtrados:
		anio = int(row.get("AÑO", 0))
		por_anio[anio]["cob"].append(_to_float(row.get("COBERTURA_NETA")))
		por_anio[anio]["des"].append(_to_float(row.get("DESERCIÓN")))
		por_anio[anio]["con"].append(_to_float(row.get("SEDES_CONECTADAS_A_INTERNET")))
		por_anio[anio]["cob_t"].append(_to_float(row.get("COBERTURA_NETA_TRANSICIÓN")))
		por_anio[anio]["cob_p"].append(_to_float(row.get("COBERTURA_NETA_PRIMARIA")))
		por_anio[anio]["cob_s"].append(_to_float(row.get("COBERTURA_NETA_SECUNDARIA")))
		por_anio[anio]["cob_m"].append(_to_float(row.get("COBERTURA_NETA_MEDIA")))

	anios = sorted(por_anio.keys())

	def _promedio(lista):
		validos = [v for v in lista if v > 0]
		return round(sum(validos) / len(validos), 2) if validos else 0.0

	series = {
		"anios": anios,
		"cobertura": [_promedio(por_anio[a]["cob"]) for a in anios],
		"desercion": [_promedio(por_anio[a]["des"]) for a in anios],
		"conectividad": [_promedio(por_anio[a]["con"]) for a in anios],
		"cob_transicion": [_promedio(por_anio[a]["cob_t"]) for a in anios],
		"cob_primaria": [_promedio(por_anio[a]["cob_p"]) for a in anios],
		"cob_secundaria": [_promedio(por_anio[a]["cob_s"]) for a in anios],
		"cob_media": [_promedio(por_anio[a]["cob_m"]) for a in anios],
	}

	# KPIs globales del período filtrado
	kpis = {
		"cobertura": _promedio([_to_float(r.get("COBERTURA_NETA")) for r in filtrados]),
		"desercion": _promedio([_to_float(r.get("DESERCIÓN")) for r in filtrados]),
		"conectividad": _promedio([_to_float(r.get("SEDES_CONECTADAS_A_INTERNET")) for r in filtrados]),
	}

	return series, kpis, filtrados


def _generar_graficas(series):
	colores = _colores_lineas()
	anios = series["anios"]
	graficas = {}

	# Gráfica 1: Cobertura Neta vs. Deserción (doble eje)
	fig, ax1 = plt.subplots(figsize=(9, 4))
	ax1.set_facecolor("#f8fbf9")
	fig.patch.set_facecolor("#ffffff")
	ax1.plot(anios, series["cobertura"], color=colores[0], linewidth=2.2,
			 marker="o", markersize=5, label="Cobertura Neta (%)")
	ax1.set_ylabel("Cobertura Neta (%)", color=colores[0], fontsize=9)
	ax1.tick_params(axis="y", labelcolor=colores[0], labelsize=8)
	ax1.tick_params(axis="x", labelsize=8)
	ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
	ax2 = ax1.twinx()
	ax2.plot(anios, series["desercion"], color=colores[1], linewidth=2.2,
			 marker="s", markersize=5, linestyle="--", label="Deserción (%)")
	ax2.set_ylabel("Deserción (%)", color=colores[1], fontsize=9)
	ax2.tick_params(axis="y", labelcolor=colores[1], labelsize=8)
	ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
	lines1, labels1 = ax1.get_legend_handles_labels()
	lines2, labels2 = ax2.get_legend_handles_labels()
	ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper right")
	ax1.set_xticks(anios)
	ax1.set_xticklabels([str(a) for a in anios], rotation=45, ha="right")
	ax1.grid(axis="y", linestyle="--", alpha=0.4)
	ax1.axvspan(2019, 2021, alpha=0.08, color="#ff7b54", label="Período COVID-19")
	fig.tight_layout()
	graficas["g1"] = _fig_to_b64(fig)

	# Gráfica 2: Conectividad a Internet
	fig, ax = plt.subplots(figsize=(9, 4))
	ax.set_facecolor("#f8fbf9")
	fig.patch.set_facecolor("#ffffff")
	ax.fill_between(anios, series["conectividad"], alpha=0.18, color=colores[2])
	ax.plot(anios, series["conectividad"], color=colores[2], linewidth=2.4,
			marker="D", markersize=5, label="Sedes conectadas (%)")
	for x, y in zip(anios, series["conectividad"]):
		if y > 0:
			ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points",
						xytext=(0, 7), ha="center", fontsize=7.5, color=colores[2])
	ax.set_ylabel("Sedes conectadas (%)", fontsize=9)
	ax.set_xticks(anios)
	ax.set_xticklabels([str(a) for a in anios], rotation=45, ha="right")
	ax.tick_params(labelsize=8)
	ax.grid(axis="y", linestyle="--", alpha=0.4)
	ax.legend(fontsize=8)
	fig.tight_layout()
	graficas["g2"] = _fig_to_b64(fig)

	# Gráfica 3: Cobertura por nivel educativo
	fig, ax = plt.subplots(figsize=(9, 4))
	ax.set_facecolor("#f8fbf9")
	fig.patch.set_facecolor("#ffffff")
	niveles = [
		("Transición", series["cob_transicion"], colores[0]),
		("Primaria", series["cob_primaria"], colores[1]),
		("Secundaria", series["cob_secundaria"], colores[2]),
		("Media", series["cob_media"], colores[3]),
	]
	for nombre, datos, color in niveles:
		ax.plot(anios, datos, linewidth=2, marker="o", markersize=4,
				label=nombre, color=color)
	ax.set_ylabel("Cobertura Neta (%)", fontsize=9)
	ax.set_xticks(anios)
	ax.set_xticklabels([str(a) for a in anios], rotation=45, ha="right")
	ax.tick_params(labelsize=8)
	ax.grid(axis="y", linestyle="--", alpha=0.4)
	ax.legend(fontsize=8, ncol=2)
	fig.tight_layout()
	graficas["g3"] = _fig_to_b64(fig)

	return graficas


@app.route("/analisis/temporal")
def temporal():
	departamento = request.args.get("departamento", "TODOS")
	rango = request.args.get("rango", "2011-2024")

	rows = load_dataset()
	departamentos = sorted(
		{r.get("DEPARTAMENTO", "").strip() for r in rows if r.get("DEPARTAMENTO", "").strip()},
	)

	series, kpis, _ = _procesar_temporal(departamento, rango)
	graficas = _generar_graficas(series) if series.get("anios") else {}

	return render_template(
		"analisis/temporal.html",
		titulo="Dimensión temporal",
		departamentos=departamentos,
		departamento_sel=departamento,
		rango_sel=rango,
		kpis=kpis,
		graficas=graficas,
	)


@app.route("/analisis/multivariada")
def multivariada():
	return render_template(
		"analisis/multivariada.html",
		titulo="Dimensión multivariada",
	)


if __name__ == "__main__":
	app.run(debug=True)
