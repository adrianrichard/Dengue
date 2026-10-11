# Predicción de brotes de dengue – Entre Ríos

Proyecto base: casos por **departamento y semana**, clima de Open-Meteo, modelo de
Gradient Boosting y mapa de riesgo a `HORIZONTE_SEMANAS` (por defecto 4).

## Instalación
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 1) Probar que todo funciona (datos INVENTADOS)
```bash
python run_all.py --sintetico
```
Genera en `outputs/`: `metricas.json`, `importancia_variables.png/.csv`,
`riesgo_actual.csv`, `mapa_riesgo.png`. Las métricas con datos sintéticos
**no significan nada**: solo prueban que el código corre.

## 2) Usar datos reales
1. **Casos**: en https://datos.salud.gob.ar buscá el dataset *Vigilancia de Dengue y Zika*.
   Hay **un CSV por período** (por ejemplo "1 a 52 - 2024"): descargá todos los que
   haya y guardalos en `data/raw/casos/` (se leen todos los `.csv` de la carpeta).
   Columnas esperadas: `provincia_nombre`, `departamento_nombre`, `anio_min`, `evento`,
   `sepi_min` (semana epidemiológica) y `cantidad` (casos por grupo etario; se suman).
   El script filtra Entre Ríos y el evento "Dengue" (ver `src/config.py`) y muestra
   qué columnas detectó; si alguna no coincide, te lo dice.
2. Si el último archivo es de un año en curso, poné en `CASOS_HASTA` (config) la fecha
   hasta la cual hay datos, para que las semanas siguientes no se cuenten como 0 casos.
3. Corré:
```bash
python run_all.py
```
Descarga el clima (Open-Meteo), arma el dataset y entrena. Para no volver a
bajar el clima: `python run_all.py --sin-descarga`.

**Error 429 (Too Many Requests) de Open-Meteo:** es el límite de la API gratuita.
El script espera y reintenta solo; si el límite es horario/diario, corta con un
mensaje. Cada departamento descargado queda en `data/raw/clima_cache/`, así que
al volver a correr `python run_all.py` continúa donde quedó. Se piden solo los años
que tienen casos, para reducir el volumen.

Solo se modelan los años que tienen archivo de casos. Cuantas más temporadas
cargues (sobre todo las de brote), más confiable será la evaluación.

## 3) Población (INDEC, Censo 2022) – opcional pero recomendado
`data/raw/poblacion_departamentos.csv` viene como plantilla con los 17 departamentos.
1. Completá la columna `poblacion` (y, si querés densidad, `superficie_km2`) con los
   resultados definitivos por departamento: https://censo.gob.ar/index.php/datos_definitivos_entre_rios/
2. Corré `python run_all.py --sin-descarga`. Si el archivo está completo, se agregan
   las variables `log_poblacion`, `incid_media4` (casos por 100.000 hab.) y `densidad`.
   Si falta algún dato, se omiten y el pipeline sigue igual.
3. El script avisa si la suma de los departamentos se aleja más de 1 % del total
   provincial de referencia (1.425.578 habitantes, Censo 2022 definitivo).
   Para regenerar la plantilla vacía: `python src/population.py`.

## 4) Mapa político de Entre Ríos
`outputs/mapa_riesgo.png` colorea cada departamento según la probabilidad de brote
(Bajo < 25 %, Moderado 25–50 %, Alto 50–75 %, Muy alto ≥ 75 %), con su nombre y valor.
- **Límites**: la primera vez se descarga el GeoJSON departamental del IGN publicado por
  Datos Argentina (CC-BY-4.0, https://infra.datos.gob.ar/georef/departamentos.geojson).
  Es un archivo nacional grande: se filtra Entre Ríos (provincia 30) y se guarda en
  `data/raw/departamentos_entre_rios.geojson`, así que se baja una sola vez.
- **Sin internet**: si no se pueden descargar, se dibuja un mapa de puntos. También podés
  poner tu propio GeoJSON en esa ruta (propiedad `nombre` = nombre del departamento).
- **Regenerar solo el mapa** (sin reentrenar): `python src/mapa.py`.
- Los umbrales de color están en `src/mapa.py` (`CORTES`, `COLORES`).

## Estructura
```
src/config.py            parámetros: departamentos, período, horizonte, umbral de brote
src/download_climate.py  clima diario -> semanal (Open-Meteo)
src/load_cases.py        casos del Ministerio -> casos por departamento y semana
src/population.py        carga y validación de población (INDEC)
src/build_dataset.py     unión + rezagos + objetivo (sin fuga de información)
src/mapa.py              mapa coroplético por departamento
src/train.py             baseline vs. modelo, métricas, importancia, mapa
src/synthetic.py         datos de prueba
```

## Decisiones de diseño
- **Validación temporal**: los últimos `ANIOS_TEST` años son test, con un hueco
  de `HORIZONTE_SEMANAS` semanas entre train y test para evitar fuga.
- **Definición de brote**: casos a H semanas ≥ máx(`BROTE_MIN_CASOS`, media + K·desvío
  del departamento), con media y desvío calculados **solo con train**. Es una
  definición operativa; conviene reemplazarla por el canal endémico oficial.
- **Baseline**: "los casos dentro de H semanas serán como los de esta semana".
  Si el modelo no lo supera, no aporta.
- **Métricas**: MAE/RMSE (casos) y precisión, recall, F1, AUC (brote). Priorizá el
  *recall*: un brote no detectado cuesta más que una falsa alarma.
- **Importancia**: por permutación sobre test (`importancia_variables.png`).

## Limitaciones a tener en cuenta
- Coordenadas por departamento: aproximadas (cabecera). Mejorable con centroides reales.
- Semana epidemiológica aproximada con semana ISO (difiere en algunos días).
- Hay pocos eventos de brote en Entre Ríos: los resultados pueden ser inestables;
  mirá varias temporadas y no te quedes con una sola métrica.
- Los casos se corrigen con retraso de notificación.

## Próximos pasos
1. ~~Población (INDEC)~~ (hecho: ver sección 3).
2. Google Trends (`pytrends`, geo `AR-E`) como variable de alerta temprana.
3. Comparar con XGBoost, LSTM y red bayesiana, usando el mismo split temporal.
4. ~~Mapa coroplético~~ (hecho: ver sección 4). Pendiente: tablero en Streamlit.
5. Probabilidades calibradas y umbral de alerta elegido según el costo de errores.
