# Phase Diagram Data Structure and Analysis Notes

## Data Format Overview

### Input Files Structure

Each experiment consists of:
1. **Excel file** with two sheets (e.g., `10_minute_input.xlsx`)
2. **Transmission folder** with multiple `.txt` files (e.g., `10 minute run data/`)

### Excel File Format

**Sheet 1: "Volumes"**
- 192 rows (2 plates × 96 wells each)
- Columns: SW1, PS1, PS2, AS1, AS2, AS3, ADD1
- Units: microliters (μL)
- Each row represents one well

**Sheet 2: "Test Solutions"**
- Solution metadata
- Columns: Solution, Description, Concentration
- Solution IDs: SW1, PS1, PS2, AS1, AS2, AS3, ADD1
- Concentrations in weight percent (%)
- Description contains surfactant/polymer names

Example Test Solutions:
```
Solution | Description           | Concentration
---------|-----------------------|--------------
SW1      | Salt Water            | 0
PS1      | Polyol Polymer (Excel)| 0.5
PS2      | Polyol Polymer (Excel)| 5.0
AS1      | Rhamnolipid          | 5.0
AS2      | Rhamnolipid          | 50.0
AS3      | Rhamnolipid          | 100.0
ADD1     | Additional Component  | 0
```

### Transmission Files Format

**File Naming Convention:**
```
YYYYMMDD Description HH.MMMMM 001-096.txt  (Plate 1)
YYYYMMDD Description HH.MMMMM 097-192.txt  (Plate 2)
```

Example: `20251121 Excel_RL 02 17.01267 001-096.txt`
- Date: 2025-11-21
- Description: Excel_RL 02
- Timepoint: 17.01267 minutes
- Wells: 001-096 (Plate 1)

**File Encoding:** UTF-16 (CRITICAL - must use this encoding)

**File Structure:**
- Variable header section
- Data section starts with line: `Sample\tWell\tValues`
- Tab-separated values
- Columns: Sample, Well, Values
- Well format: A1, A2, ..., H12
- Values are transmission percentages (0-100%)

## Well Assignment Logic

**CRITICAL: Wells are filled COLUMN-WISE, not row-wise!**

Order for 192 wells (matching instrument dispensing):
```
Plate 1 (rows 1-96 in Excel):
  Column 1: A1, B1, C1, D1, E1, F1, G1, H1
  Column 2: A2, B2, C2, D2, E2, F2, G2, H2
  ...
  Column 12: A12, B12, C12, D12, E12, F12, G12, H12

Plate 2 (rows 97-192 in Excel):
  Column 1: A1, B1, C1, D1, E1, F1, G1, H1
  ...
  Column 12: A12, B12, C12, D12, E12, F12, G12, H12
```

**DO NOT change this logic!** It matches the physical dispensing order of the instrument.

## Concentration Calculations

Final concentrations are calculated as volume-weighted averages:

```python
# Total volume per well
total_volume = SW1 + PS1 + PS2 + AS1 + AS2 + AS3 + ADD1

# Surfactant concentration
surfactant_pct = (AS1×[AS1] + AS2×[AS2] + AS3×[AS3]) / total_volume × 100

# Polymer concentration  
polymer_pct = (PS1×[PS1] + PS2×[PS2]) / total_volume × 100
```

Where [AS1], [PS1], etc. are the stock concentrations from Test Solutions sheet (converted from % to fraction).

### Verified Concentration Ranges (Rhamnolipid-Excel System)

From completed analysis of three experiments:
- **Rhamnolipid (AS)**: 0.15 - 4.0 wt%
- **Excel (PS)**: 0.004 - 0.10 wt%
- **Transmission**: 28 - 93%

These ranges have been independently verified and are correct.

## Time-Series Data

### Timepoint Characteristics

Experiments typically have 6-8 timepoints ranging from ~1.5 to ~65 minutes.

**IMPORTANT FINDINGS:**
1. **Quasi-equilibrium time**: ≥10 minutes
   - System reaches ~94% of steady state by 10 minutes
   - Fully equilibrated by ~60 minutes
   - Use `timepoint >= 10.0` filter for quasi-equilibrium analysis

2. **Temporal behavior**:
   - Phase separation occurs rapidly in first 10 minutes
   - Kinetics show biphasic behavior (fast then slow)
   - Reproducibility improves over time:
     * R² = 0.666 at 16 minutes
     * R² = 0.804 at 48 minutes

### Multiple Experiments

Three experiments were analyzed with the same surfactant-polymer system:
1. `8_minute_input.xlsx` → `8 minute data/`
2. `10_minute_input.xlsx` → `10 minute run data/`
3. `zero_excel_input.xlsx` → `zero Excel/`

All use identical data formats and can be combined for reproducibility analysis.

## Data Quality Notes

### Verified Aspects
- ✓ All transmission values are physically valid (0-100%)
- ✓ Concentration calculations independently verified
- ✓ Well assignments match instrument dispensing order
- ✓ UTF-16 encoding correctly handles transmission files
- ✓ Column-wise well assignment is correct (not row-wise)

### Common Issues
- Transmission files MUST be read with UTF-16 encoding
- Well assignment is column-wise (critical for correct composition matching)
- Some wells may have missing transmission data (use inner join to exclude)

## Phase Diagram Analysis

### Phase Boundary

The Rhamnolipid-Excel system shows:
- **One-phase region**: High transmission (>~70%)
- **Two-phase region**: Low transmission (<~42%)
- **Transition zone**: 42-70% transmission

### Valid Interpolation Range

When creating phase diagrams:
- Use `scipy.interpolate.griddata` with `method='linear'`
- **Do NOT use RBF** - it extrapolates wildly beyond data range
- Valid transmission range: 42-92%
- Phase boundary occurs at ~50-60% transmission

### Reproducibility

Across three independent experiments:
- Strong correlation improves with time
- 42-fold surfactant concentration range tested
- Polymer concentration varied independently
- System shows good repeatability at quasi-equilibrium

## Database Schema Design

The flat table includes these key columns:

**Experiment Metadata:**
- experiment_id (unique identifier)
- experiment_name (human-readable)
- date_created (ISO timestamp)

**Well Identification:**
- plate (1 or 2)
- well (A1-H12)
- row (A-H)
- column (1-12)

**Chemical System:**
- surfactant_name (extracted from Description)
- polymer_name (extracted from Description)

**Volumes (μL):**
- volume_SW1, volume_PS1, volume_PS2
- volume_AS1, volume_AS2, volume_AS3, volume_ADD1
- total_volume_uL

**Concentrations:**
- solution_concentrations_json (stock concentrations)
- surfactant_pct (calculated final concentration)
- polymer_pct (calculated final concentration)

**Measurements:**
- timepoint_minutes
- transmission_pct

**Traceability:**
- excel_filename
- transmission_filename

## Typical Analysis Workflow

1. **Ingest experiments** into database
2. **Filter for quasi-equilibrium**: `timepoint >= 10.0`
3. **Query by surfactant/polymer** to combine experiments
4. **Export filtered data** for phase diagram analysis
5. **Use griddata linear interpolation** (not RBF)
6. **Analyze reproducibility** across replicate experiments

## Azure Migration Notes

The SQLite database structure is designed for cloud migration:
- Single flat table optimizes for cloud queries
- All metadata included per row (denormalized)
- Easy export to Parquet format
- Compatible with Azure Data Lake / Synapse Analytics

## Critical Reminders

1. **UTF-16 encoding** for transmission files
2. **Column-wise well assignment** (not row-wise)
3. **Volume-weighted concentration** calculations
4. **Use t ≥ 10 min** for quasi-equilibrium analysis
5. **Griddata linear** interpolation (not RBF)
6. **Inner join** to exclude wells missing transmission data

## Reference Analysis

Completed analysis located in parent directory:
- `build_experiment_datasets.py` - Data reading logic (source of truth)
- `experiment_*_dataset.csv` - Individual experiment datasets
- `combined_equilibrium_dataset.csv` - Merged quasi-equilibrium data
- `create_ppt_presentation.py` - Final analysis with phase diagram

All code in this database package uses the same proven logic from the reference analysis.
