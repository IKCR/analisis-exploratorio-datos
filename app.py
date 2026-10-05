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
