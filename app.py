import csv
import json
from collections import defaultdict
from pathlib import Path
import pandas as pd
import plotly.express as px


from flask import Flask, render_template, request, send_file

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "data" / "educacion_municipios.csv"

_CACHE_TEMPORAL = None


def _to_float(value):
	if value is None:
		return None
	text = str(value).strip()
	if not text or text.lower() in ("nan", "null", "none", "-"):
		return None
	text = text.replace("%", "").replace(".", "").replace(",", ".")
	try:
		return float(text)
	except ValueError:
		return None


def load_dataset():
	if not DATASET_PATH.exists():
		return []
	with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as archivo:
		return list(csv.DictReader(archivo))

def load_dataframe() -> pd.DataFrame:
    """Load the dataset using pandas and normalise numeric columns.

    Returns
    -------
    pd.DataFrame
        DataFrame with cleaned numeric columns.
    """
    df = pd.read_csv(DATASET_PATH, encoding="utf-8-sig")
    # Columns that may contain percentages or formatted numbers
    numeric_cols = ["TASA_MATRICULACIÓN_5_16", "INGRESO_PROMEDIO"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .replace({"": "0", "nan": "0"}, regex=True)
                .astype(float)
            )
    return df


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

	# Excluir registros agregados de nivel nacional
	municipios_rows = [r for r in rows if r.get("DEPARTAMENTO", "").strip().upper() != "NACIONAL"]
	tasas = [_to_float(row.get("TASA_MATRICULACIÓN_5_16")) for row in municipios_rows]
	tasas_validas = [t for t in tasas if t is not None]
	mejor = max(municipios_rows, key=lambda row: _to_float(row.get("TASA_MATRICULACIÓN_5_16")) or 0.0)
	peor = min(municipios_rows, key=lambda row: _to_float(row.get("TASA_MATRICULACIÓN_5_16")) or 0.0)
	promedio = sum(tasas_validas) / len(tasas_validas) if tasas_validas else 0.0

	return {
		"municipios": len(municipios_rows),
		"departamentos": len({row.get("DEPARTAMENTO") for row in municipios_rows if row.get("DEPARTAMENTO")}),
		"promedio_matriculacion": round(promedio, 2),
		"mejor_municipio": mejor.get("MUNICIPIO", "Sin datos"),
		"mejor_tasa": round(_to_float(mejor.get("TASA_MATRICULACIÓN_5_16")) or 0.0, 2),
		"peor_municipio": peor.get("MUNICIPIO", "Sin datos"),
		"peor_tasa": round(_to_float(peor.get("TASA_MATRICULACIÓN_5_16")) or 0.0, 2),
	}


def top_municipios(limit=5):
	rows = [r for r in load_dataset() if r.get("DEPARTAMENTO", "").strip().upper() != "NACIONAL"]
	rows_ordenadas = sorted(
		rows,
		key=lambda row: _to_float(row.get("TASA_MATRICULACIÓN_5_16")) or 0.0,
		reverse=True,
	)
	return [
		{
			"municipio": row.get("MUNICIPIO", "-"),
			"departamento": row.get("DEPARTAMENTO", "-"),
			"tasa": round(_to_float(row.get("TASA_MATRICULACIÓN_5_16")) or 0.0, 2),
		}
		for row in rows_ordenadas[:limit]
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
		anio_str = row.get("AÑO") or row.get("AO")
		try:
			anio = int(anio_str)
		except (ValueError, TypeError):
			continue

		depto = (row.get("DEPARTAMENTO") or "").strip()
		# Excluir registros agregados de nivel nacional y registros previos a 2011
		if not depto or depto.upper() == "NACIONAL" or anio < 2011:
			continue

		campos = {
			"cob":   _to_float(row.get("COBERTURA_NETA")),
			"des":   _to_float(row.get("DESERCIÓN") or row.get("DESERCIN")),
			"con":   _to_float(row.get("SEDES_CONECTADAS_A_INTERNET")),
			"cob_t": _to_float(row.get("COBERTURA_NETA_TRANSICIÓN") or row.get("COBERTURA_NETA_TRANSICIN")),
			"cob_p": _to_float(row.get("COBERTURA_NETA_PRIMARIA")),
			"cob_s": _to_float(row.get("COBERTURA_NETA_SECUNDARIA")),
			"cob_m": _to_float(row.get("COBERTURA_NETA_MEDIA")),
		}

		for destino in [depto, "TODOS"]:
			g = grupos[destino][anio]
			for campo, v in campos.items():
				# Conservar valores numéricos reales (incluyendo 0.0) y descartar solo nulos
				if v is not None:
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


def multivariate_metrics(df: pd.DataFrame, dep_filter=None, year_range=None) -> dict:
    """Compute multivariate metrics and build Plotly HTML charts.

    Parameters
    ----------
    df         : DataFrame returned by load_dataframe().
    dep_filter : Optional department name to filter rows.
    year_range : Optional (start, end) year tuple (inclusive).

    Returns
    -------
    dict with keys: matrix_html, bubble_html, heatmap_html,
                    total_registros, departamentos, anios_disponibles.
    """
    # ── 1. Apply optional filters ──────────────────────────────────────────
    if dep_filter:
        df = df[df["DEPARTAMENTO"].str.strip().str.upper() == dep_filter.upper()]
    if year_range and "AÑO" in df.columns:
        start, end = year_range
        df = df[(df["AÑO"] >= start) & (df["AÑO"] <= end)]

    # ── 2. Summary metrics ─────────────────────────────────────────────────
    total_registros = int(df.shape[0])
    departamentos_n = int(df["DEPARTAMENTO"].nunique()) if "DEPARTAMENTO" in df.columns else 0
    anios_disponibles = (
        sorted(df["AÑO"].dropna().unique().tolist()) if "AÑO" in df.columns else []
    )

    # ── 3. Numeric columns present in this DataFrame ───────────────────────
    candidatas = [
        "TASA_MATRICULACIÓN_5_16",
        "COBERTURA_NETA",
        "DESERCIÓN",
        "COBERTURA_NETA_PRIMARIA",
        "COBERTURA_NETA_SECUNDARIA",
        "COBERTURA_NETA_MEDIA",
        "SEDES_CONECTADAS_A_INTERNET",
    ]
    numeric_vars = [c for c in candidatas if c in df.columns]

    # Convert those columns to numeric (ignore errors for safety)
    for col in numeric_vars:
        df[col] = pd.to_numeric(
            df[col].astype(str)
            .str.replace("%", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False),
            errors="coerce",
        )
    df_num = df[numeric_vars].dropna(how="all")

    # ── 4. Scatter-matrix (pair-plot) ──────────────────────────────────────
    if len(numeric_vars) >= 2 and not df_num.empty:
        color_col = "DEPARTAMENTO" if "DEPARTAMENTO" in df.columns else None
        fig_matrix = px.scatter_matrix(
            df,
            dimensions=numeric_vars,
            color=color_col,
            title="Relaciones bivariadas entre variables numéricas",
            labels={c: c.replace("_", " ").title() for c in numeric_vars},
        )
        fig_matrix.update_layout(height=620)
        fig_matrix.update_traces(diagonal_visible=False, showupperhalf=False)
        matrix_html = fig_matrix.to_html(full_html=False, include_plotlyjs="cdn")
    else:
        matrix_html = "<p class='text-warning'>No hay suficientes columnas numéricas para el scatter-matrix.</p>"

    # ── 5. Bubble chart: cobertura vs deserción por departamento ───────────
    if "DEPARTAMENTO" in df.columns and "COBERTURA_NETA" in df.columns and "DESERCIÓN" in df.columns:
        agg = (
            df.groupby("DEPARTAMENTO")
            .agg(
                cobertura=("COBERTURA_NETA", "mean"),
                desercion=("DESERCIÓN", "mean"),
                registros=("MUNICIPIO", "count"),
            )
            .reset_index()
            .dropna(subset=["cobertura", "desercion"])
        )
        if not agg.empty:
            fig_bubble = px.scatter(
                agg,
                x="cobertura",
                y="desercion",
                size="registros",
                color="DEPARTAMENTO",
                hover_name="DEPARTAMENTO",
                title="Cobertura neta vs Deserción por departamento (tamaño = nº registros)",
                labels={"cobertura": "Cobertura neta (%)", "desercion": "Deserción (%)"},
            )
            fig_bubble.update_layout(height=500, showlegend=False)
            bubble_html = fig_bubble.to_html(full_html=False, include_plotlyjs=False)
        else:
            bubble_html = "<p class='text-warning'>No hay datos suficientes para el gráfico de burbujas.</p>"
    else:
        bubble_html = "<p class='text-warning'>Columnas requeridas para el gráfico de burbujas no encontradas.</p>"

    # ── 6. Correlation heatmap ─────────────────────────────────────────────
    if len(numeric_vars) >= 2 and not df_num.empty:
        corr = df_num.corr(numeric_only=True)
        fig_heat = px.imshow(
            corr,
            text_auto=".2f",
            aspect="auto",
            color_continuous_scale="RdBu_r",
            zmin=-1, zmax=1,
            title="Matriz de correlación entre variables numéricas",
            labels={"color": "Correlación"},
        )
        fig_heat.update_layout(height=480)
        heatmap_html = fig_heat.to_html(full_html=False, include_plotlyjs=False)
    else:
        heatmap_html = "<p class='text-warning'>No hay suficientes columnas numéricas para la heatmap.</p>"

    return {
        "matrix_html": matrix_html,
        "bubble_html": bubble_html,
        "heatmap_html": heatmap_html,
        "total_registros": total_registros,
        "departamentos": departamentos_n,
        "anios_disponibles": anios_disponibles,
    }


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
    """Render the multivariate analysis page.

    Supports optional URL query parameters:
        ?departamento=ANTIOQUIA   – filter by department (case-insensitive)
        ?anio=2015-2022           – filter by year range (inclusive)
    """
    # Read optional filter params from the URL
    dep = request.args.get("departamento", "").strip() or None
    anio_param = request.args.get("anio", "").strip() or None
    year_range = None
    if anio_param:
        try:
            start, end = map(int, anio_param.split("-"))
            year_range = (start, end)
        except (ValueError, AttributeError):
            year_range = None

    # Load data and compute metrics / charts
    df = load_dataframe()

    # Build list of unique departments for the filter dropdown
    deptos = (
        sorted(df["DEPARTAMENTO"].dropna().unique().tolist())
        if "DEPARTAMENTO" in df.columns
        else []
    )

    metrics = multivariate_metrics(df.copy(), dep_filter=dep, year_range=year_range)

    return render_template(
        "analisis/multivariada.html",
        titulo="Dimensión multivariada",
        matrix_html=metrics["matrix_html"],
        bubble_html=metrics["bubble_html"],
        heatmap_html=metrics["heatmap_html"],
        total_registros=metrics["total_registros"],
        departamentos_n=metrics["departamentos"],
        anios_disponibles=metrics["anios_disponibles"],
        deptos=deptos,
        filtro_depto=dep or "Todos",
        filtro_anio=anio_param or "Todo el rango",
    )



if __name__ == "__main__":
	app.run(debug=True)