# Phase Diagram Database System

## Coacervation App on BeautyFast

The current coacervation application is `coacervation_app.py`, served locally at
`http://localhost:5001`. BeautyFast starts `coacervation_app:app` on port 5000.
Its approved catalog tags are All Beauty and Beauty Revealed.

The deployment uses one Gunicorn worker and a writable `/tmp/coacervation`
directory. JSON stores, both SQLite databases, raw plate uploads, Lasentec files,
and microscopy images are restored from the app's private Azure container before
requests and saved before responses finish. An Azure lease serializes requests
across deployments. Storage failures return HTTP 503 instead of reporting a
successful save. Exports are temporary and can be regenerated. Local runs keep
using their existing files beside the source code.

Provision storage with `bf storage create --json` after the first deployment has
created `beautyfast.yaml`. Then migrate the existing local files once:

```powershell
python -c "from coacervation_storage import prepare_runtime, seed_storage; prepare_runtime(); seed_storage()"
```

Migration never overwrites existing cloud files. Keep `.env`, databases, uploads,
and JSON state out of Git. BeautyFast provides its storage credentials directly;
other nonempty `.env` settings are supplied by `bf deploy --json` as secrets.
The existing Azure SAS data connection remains separate from private app storage.
Databricks host and warehouse are set in the build config; authentication uses
the signed-in user's forwarded token when available, otherwise the `.env` token.

## Reports

### Rhamnolipid Water-Hardness Study (March 2026)

**[View the compiled PDF](Reports/rhamnolipid_hardness_report/main.pdf)**

This report characterises the effect of water hardness (0 gpg soft water vs. 7 gpg hard water) on coacervation and precipitation between rhamnolipid and five conditioning polymers (AMT/PQ-76, DADMAC/PQ-6, Excel Guar, JR-30M, KG-30M) and a no-polymer baseline. It includes transmission contour maps, dilution curves, kinetic profiles, a hardness-effect summary, and a data quality section discussing liquid-handling artifacts.

**To read the report:** Click the PDF link above — GitHub will render it in the browser.

**To edit the report text:**
1. Clone this repo and open it in VS Code (`Git: Clone` → paste the repo URL)
2. Edit `Reports/rhamnolipid_hardness_report/main.tex`
3. Recompile: open a terminal in that folder and run:
   ```
   pdflatex main.tex && biber main && pdflatex main.tex && pdflatex main.tex
   ```
   (requires [MiKTeX](https://miktex.org/download) installed)
4. Commit and push your changes

**To regenerate all figures and tables** from the database (requires Python + repo dependencies):
```
python Reports/build_rhamnolipid_hardness_report.py
```
This regenerates all figures, tables, and `main.tex` from the database, then attempts to compile the PDF.

---

### Single-Surfactant Phase Diagrams at 7 gpg (March 2026)

**[View the compiled PDF](Reports/single_surfactant_7gpg_report/main.pdf)**

This report characterises coacervation behaviour across 15 surfactant–polymer systems at 7 gpg hard water (Rhamnolipid, SCG, SLESS, SLS × DADMAC, AMT, KG30M, Excel + no-polymer control). It includes transmission contour maps, representative kinetics, and coacervation ranking tables.

**To read the report:** Click the PDF link above — GitHub will render it in the browser.

**To edit the report text:**
1. Clone this repo and open it in VS Code (`Git: Clone` → paste the repo URL)
2. Edit `Reports/single_surfactant_7gpg_report/main.tex`
3. Recompile: open a terminal in that folder and run:
   ```
   pdflatex main.tex && biber main && pdflatex main.tex && pdflatex main.tex
   ```
   (requires [MiKTeX](https://miktex.org/download) installed)
4. Commit and push your changes

**To regenerate figures or tables** from the database (requires Python + repo dependencies):
```
python Reports/build_single_surfactant_report.py
```
This will update all figures and tables but will **not** overwrite `main.tex`.

---

Transportable code package for ingesting phase diagram experiments into a SQLite database and analysing them via a web application. Designed for scalability across multiple surfactant-polymer-cosurfactant experiments with the same data format.

## Overview

This system reads Excel-based experimental designs and transmission measurements, stores them in a structured SQLite database, and exposes analysis via a Flask web application.

## Features

- **Single flat table design**: All metadata, compositions, and measurements in one queryable table
- **Automatic name extraction**: Parses surfactant, co-surfactant, and polymer names from the Excel Description column
- **Co-surfactant support**: Tracks surfactant:co-surfactant ratio in experiment IDs and names; stores `cosurfactant_pct` per well
- **Water hardness tracking**: Automatically extracts water hardness (gpg) from filenames (e.g., `0gpg` or `7gpg`)
- **Replicate experiment support**: Automatically handles duplicate experiments with `_rep1`, `_rep2`, `_rep3` suffixes
- **Column-wise well assignment**: Preserves exact logic from working analysis code
- **UTF-16 transmission parsing**: Handles instrument output files correctly
- **Concentration calculations**: Computes final surfactant, co-surfactant, and polymer percentages from volumes and stock concentrations
- **Scalable querying**: Filter by experiment, surfactant, polymer, cosurfactant, timepoint, or water hardness

## Web Application

Start the app with:

```bash
python app.py
```

Then open `http://localhost:5000` in a browser.

### Ingest tab
Upload an Excel layout file and transmission text files to ingest a new experiment. The app auto-detects surfactant, co-surfactant, polymer, and water hardness from the file contents and names, generates a structured experiment ID, and stores all well-level data in the database.

### Query tab
Query stored experiments by surfactant/polymer/hardness and download results as CSV.

### Analysis tab
Interactive analysis of stored phase diagrams:
- **Phase diagram** — GP-interpolated transmission contour map with 75% precipitation threshold
- **Dilution curves** — %T vs. concentration at fixed surfactant:polymer ratios (inverted log x-axis, high→low concentration)
- **Kinetic analysis** — Mean plate transmission vs. time; reports t₉₅
- **Absorbance plot** — Well-level %T vs. [surfactant] at a chosen timepoint
- **3D surface plot** — Transmission surface over the full composition grid
- **Transmission vs. concentration** — 1-D concentration-response curves

### Export tab
- **Database summary** — Counts and ranges for all stored experiments
- **Filtered export** — Download a subset of the database as CSV (filter by surfactant, polymer, hardness, timepoint range)
- **ML-ready export** — Pivot-formatted dataset with equilibrium metrics (precipitate fraction, AUC, t₉₅, coacervation strength) suitable for downstream modelling

## Installation

```bash
pip install -r requirements.txt
```

## Replicate Experiments

When ingesting replicate experiments (same surfactant, polymer, water hardness, and date), the system automatically detects duplicates and assigns unique IDs:

- **First experiment**: `exp_20260212_rl_excel_7gpg` → "Rhamnolipid-Excel 7gpg (2026-02-12)"
- **First replicate**: `exp_20260212_rl_excel_7gpg_rep1` → "Rhamnolipid-Excel 7gpg Rep1 (2026-02-12)"
- **Second replicate**: `exp_20260212_rl_excel_7gpg_rep2` → "Rhamnolipid-Excel 7gpg Rep2 (2026-02-12)"

This allows you to store multiple replicates of the same experimental conditions without conflicts. The GUI automatically detects and numbers replicates when you select files.

## Database Schema

Single table: `measurements`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment primary key |
| experiment_id | TEXT | Unique experiment identifier |
| experiment_name | TEXT | Human-readable name |
| date_created | TEXT | ISO timestamp |
| plate | INTEGER | Plate number (1 or 2) |
| well | TEXT | Well ID (A1-H12) |
| row | TEXT | Row letter (A-H) |
| column | INTEGER | Column number (1-12) |
| surfactant_name | TEXT | Extracted from Description |
| polymer_name | TEXT | Extracted from Description |
| water_hardness_gpg | REAL | Water hardness (grains per gallon) |
| volume_SW1...ADD1 | REAL | Individual volumes (μL) |
| total_volume_uL | REAL | Total well volume |
| solution_concentrations_json | TEXT | Stock concentrations (JSON) |
| surfactant_pct | REAL | Final surfactant concentration (%) |
| polymer_pct | REAL | Final polymer concentration (%) |
| timepoint_minutes | REAL | Measurement time |
| transmission_pct | REAL | Light transmission (%) |
| excel_filename | TEXT | Source Excel file |
| transmission_filename | TEXT | Source transmission file |

**Unique constraint**: `(experiment_id, well, timepoint_minutes)`

**Indices**: 
- experiment_id
- (surfactant_name, polymer_name)
- timepoint_minutes

## Well Assignment Logic

Wells are assigned **column-wise** for 192 wells (2 plates × 96 wells):

```
Plate 1 (rows 1-96):
  A1, B1, C1, D1, E1, F1, G1, H1 (column 1)
  A2, B2, C2, D2, E2, F2, G2, H2 (column 2)
  ...
  A12, B12, C12, D12, E12, F12, G12, H12 (column 12)

Plate 2 (rows 97-192):
  A1, B1, C1, D1, E1, F1, G1, H1 (column 1)
  ...
```

This matches the instrument's dispensing order.

## Files

### Core
- `schema.py` — Database schema definition and creation
- `ingest_experiment.py` — Core ingestion and query functions (single-surfactant)
- `ingest_cosurfactant_experiment.py` — Ingestion for surfactant+co-surfactant experiments
- `app.py` — Flask web application (ingest, query, analysis, export)
- `requirements.txt` — Python dependencies

### Analysis scripts
- `phase_plotting.py` — GP interpolation and contour plotting utilities
- `cosurfactant_utils.py` — Shared utilities for co-surfactant experiment analysis
- `analyze_capb_cosurfactant.py` — Analysis of CAPB co-surfactant series
- `analyze_polymers.py` — Cross-polymer comparison analysis
- `rhamnolipid_analysis.py` — Rhamnolipid-specific analysis helpers

### Report builders
- `Reports/build_rhamnolipid_hardness_report.py` — Generates figures, tables, and `main.tex` for the rhamnolipid water-hardness report
- `Reports/build_single_surfactant_report.py` — Generates figures and tables for the 7 gpg multi-surfactant report

### Migration scripts
- `migrate_add_water_hardness.py` — Adds `water_hardness_gpg` column to databases created before that feature
- `migrate_add_cosurfactant.py` — Adds cosurfactant columns to older databases
- `migrate_add_cosurfactant_volumes.py` — Backfills cosurfactant volume columns
- `migrate_add_new_volume_columns.py` — Adds any new volume columns to existing databases

## Notes

- **Column-wise well assignment**: This is critical — do not change without verifying against instrument dispensing order.
- **UTF-16 encoding**: Transmission files must be read with UTF-16 encoding (instrument default).
- **Unique constraint**: The database prevents duplicate entries for the same well/timepoint in an experiment.
- **Missing data**: Wells without transmission data are excluded (inner join).
- **Timepoint filtering**: Quasi-equilibrium analysis typically uses t ≥ 10 minutes.

## Contact

For questions or issues with this code package, contact the original developer.
