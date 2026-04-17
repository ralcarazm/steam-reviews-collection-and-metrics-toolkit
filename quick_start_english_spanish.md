# Quick Start Guide / Guía rápida

## English

### 1. Open the project folder in Windows

Open **Command Prompt** or **PowerShell** and go to the repository folder:

```bash
cd C:\path\to\steam-reviews-collection-and-metrics-toolkit
```

### 2. Create and activate the virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Choose a game configuration file

Game configuration files are stored in:

```text
config/games/
```

Example:

```text
config/games/example_game.json
```

### 5. Easiest option: run the full pipeline

```bash
python scripts/run_pipeline.py --config config/games/example_game.json
```

This runs everything in order:

1. collection  
2. preparation  
3. basic metrics  
4. temporal metrics  
5. text metrics  
6. emotion metrics  
7. theme metrics  
8. Excel figures  
9. word clouds  
10. validation  

### 6. If you want to skip a stage

Examples:

Skip collection:

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --skip-collection
```

Skip figures and word clouds:

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --skip-figures --skip-wordcloud
```

Skip validation:

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --skip-validation
```

Continue even if one stage fails:

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --continue-on-error
```

### 7. If you want to run scripts one by one

#### Collection
```bash
python scripts/01_data_collection/collect_steam_reviews.py --config config/games/example_game.json
```

Generates:
- raw review files
- combined CSV/JSON
- collection metadata
- collection logs

#### Preparation
```bash
python scripts/02_data_preparation/prepare_reviews.py --config config/games/example_game.json
```

Generates:
- cleaned dataset

#### Basic metrics
```bash
python scripts/03_analysis/compute_basic_metrics.py --config config/games/example_game.json
```

Generates:
- basic descriptive tables
- metrics summary JSON
- log

#### Temporal metrics
```bash
python scripts/03_analysis/compute_temporal_metrics.py --config config/games/example_game.json
```

Generates:
- temporal tables
- metrics summary JSON
- log

#### Text metrics
```bash
python scripts/03_analysis/compute_text_metrics.py --config config/games/example_game.json
```

Generates:
- text tables
- metrics summary JSON
- log

#### Emotion metrics
```bash
python scripts/03_analysis/compute_emotion_metrics.py --config config/games/example_game.json
```

Generates:
- emotion tables
- enriched emotion CSV
- metrics summary JSON
- log

#### Theme metrics
```bash
python scripts/03_analysis/compute_theme_metrics.py --config config/games/example_game.json
```

Generates:
- theme tables
- enriched theme CSV
- metrics summary JSON
- log

#### Excel figures
```bash
python scripts/04_visualisation/create_excel_figures.py --config config/games/example_game.json
```

Generates:
- Excel figure workbooks
- figure index CSV
- figures summary JSON
- log

#### Word clouds
```bash
python scripts/04_visualisation/create_word_clouds.py --config config/games/example_game.json

Generates:
- unigram, bigram, and trigram PNG word clouds
- frequency CSV files
- word-cloud summary JSON
- log

#### Validation
```bash
python scripts/validate_outputs.py --config config/games/example_game.json
```

Generates:
- validation summary JSON
- validation log

### 8. Main output locations

Generated files are mainly stored in:

```text
data/raw/steam_reviews/<game_slug>/
data/processed/steam_reviews/<game_slug>/
results/<game_slug>/tables/
results/<game_slug>/figures/
```

---

## Español

### 1. Abrir la carpeta del proyecto en Windows

Abre **Símbolo del sistema** o **PowerShell** y entra en la carpeta del repositorio:

```bash
cd C:\ruta\a\steam-reviews-collection-and-metrics-toolkit
```

### 2. Crear y activar el entorno virtual

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instalar las dependencias

```bash
python -m pip install -r requirements.txt
```

### 4. Elegir un fichero de configuración del juego

Los ficheros de configuración están en:

```text
config/games/
```

Ejemplo:

```text
config/games/example_game.json
```

### 5. Opción más fácil: ejecutar el pipeline completo

```bash
python scripts/run_pipeline.py --config config/games/example_game.json
```

Esto ejecuta todo en este orden:

1. recolección  
2. preparación  
3. métricas básicas  
4. métricas temporales  
5. métricas textuales  
6. métricas emocionales  
7. métricas temáticas  
8. figuras Excel  
9. nubes de etiquetas  
10. validación  

### 6. Si quieres saltar alguna fase

Ejemplos:

Saltar la recolección:

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --skip-collection
```

Saltar figuras y nubes de etiquetas:

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --skip-figures --skip-wordcloud
```

Saltar la validación:

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --skip-validation
```

Continuar aunque falle una fase:

```bash
python scripts/run_pipeline.py --config config/games/example_game.json --continue-on-error
```

### 7. Si quieres ejecutar los scripts uno por uno

#### Recolección
```bash
python scripts/01_data_collection/collect_steam_reviews.py --config config/games/example_game.json
```

Genera:
- ficheros raw de reseñas
- CSV/JSON combinados
- metadatos de recolección
- logs de recolección

#### Preparación
```bash
python scripts/02_data_preparation/prepare_reviews.py --config config/games/example_game.json
```

Genera:
- dataset cleaned

#### Métricas básicas
```bash
python scripts/03_analysis/compute_basic_metrics.py --config config/games/example_game.json
```

Genera:
- tablas descriptivas básicas
- JSON resumen
- log

#### Métricas temporales
```bash
python scripts/03_analysis/compute_temporal_metrics.py --config config/games/example_game.json
```

Genera:
- tablas temporales
- JSON resumen
- log

#### Métricas textuales
```bash
python scripts/03_analysis/compute_text_metrics.py --config config/games/example_game.json
```

Genera:
- tablas textuales
- JSON resumen
- log

#### Métricas emocionales
```bash
python scripts/03_analysis/compute_emotion_metrics.py --config config/games/example_game.json
```

Genera:
- tablas emocionales
- CSV enriquecido de emociones
- JSON resumen
- log

#### Métricas temáticas
```bash
python scripts/03_analysis/compute_theme_metrics.py --config config/games/example_game.json
```

Genera:
- tablas temáticas
- CSV enriquecido de temas
- JSON resumen
- log

#### Figuras Excel
```bash
python scripts/04_visualisation/create_excel_figures.py --config config/games/example_game.json
```

Genera:
- ficheros Excel de figuras
- CSV índice de figuras
- JSON resumen
- log

#### Nubes de etiquetas
```bash
python scripts/04_visualisation/create_word_clouds.py --config config/games/example_game.json
```

Genera:
- nubes de etiquetas PNG de unigramas, bigramas y trigramas
- CSV de frecuencias
- JSON resumen
- log

#### Validación
```bash
python scripts/validate_outputs.py --config config/games/example_game.json
```

Genera:
- JSON resumen de validación
- log de validación

### 8. Principales rutas de salida

Los ficheros generados se guardan principalmente en:

```text
data/raw/steam_reviews/<game_slug>/
data/processed/steam_reviews/<game_slug>/
results/<game_slug>/tables/
results/<game_slug>/figures/
```
