# Co-Surfactant Handling Guide

## Overview

Your experiment with co-surfactants will be automatically named to include:
- Primary surfactant name
- Co-surfactant name  
- The ratio between them (e.g., 2:1)
- Polymer name
- Water hardness

**Example:** `SLS-CAPB (2:1) with KG30M, 7gpg`

## How It Works

### 1. **Validated Code Remains Unchanged**
   - All data analysis and plotting functions remain as-is
   - Plots continue to show `Surfactant %` vs `Polymer %` on axes
   - The co-surfactant is present at a fixed ratio and not plotted separately

### 2. **Co-Surfactant Info in Titles**
   - Experiment names automatically include surfactant:co-surfactant ratio
   - Plot titles show the complete surfactant system name
   - Export filenames include this information for clarity

### 3. **Ratio Calculation**
   - Automatically calculated from actual well concentrations
   - Detects common ratios: 1:1, 2:1, 3:1, 1:2, 1:3, 4:1, 1:4
   - Example from your file: **SLS:CAPB = 2:1**

## Database Schema

New columns added to `measurements` table:
- `cosurfactant_name` - Co-surfactant identity (e.g., "CAPB")
- `cosurfactant_pct` - Co-surfactant concentration (weight %)

## Using the Utility Functions

### In Python Scripts:

```python
from cosurfactant_utils import (
    calculate_surfactant_ratio,
    format_surfactant_system_name,
    generate_experiment_title,
    get_experiment_cosurfactant_info
)

# Calculate ratio from experiment data
surf_ratio, cosurf_ratio = calculate_surfactant_ratio(df)
# Returns: (2, 1) for 2:1 ratio

# Format system name
system_name = format_surfactant_system_name('SLS', 'CAPB', 2, 1)
# Returns: "SLS-CAPB (2:1)"

# Generate full descriptive title
title = generate_experiment_title(experiment_id='exp_001')
# Returns: "SLS-CAPB (2:1) with KG30M, 7gpg"

# Get all co-surfactant info for an experiment
info = get_experiment_cosurfactant_info(experiment_id='exp_001')
# Returns dict with: has_cosurfactant, surfactant_name, cosurfactant_name,
#                    surf_ratio, cosurf_ratio, ratio_string, system_name
```

### Adding Co-Surfactant Info to Plot Titles:

```python
from cosurfactant_utils import add_cosurfactant_to_plot_title

# Existing plot title
base_title = "Phase Boundary Map"

# Add co-surfactant info
full_title = add_cosurfactant_to_plot_title(base_title, experiment_id='exp_001')
# Returns: "Phase Boundary Map\nSLS-CAPB (2:1) System"

plt.title(full_title)
```

## Ingestion

When ingesting a new experiment with co-surfactants:

```bash
# Set the transmission folder path in ingest_cosurfactant_experiment.py
python ingest_cosurfactant_experiment.py <transmission_folder>
```

The script will:
1. Read the Excel file
2. Auto-detect surfactant, co-surfactant, and polymer names
3. Calculate the ratio from actual concentrations
4. Generate descriptive experiment ID and name
5. Ingest with all metadata properly labeled

## Your Current Experiment

**File:** `50_50 Surfactant_CoSurfactant Dilution Scheme.xlsx`

**Detected:**
- Primary Surfactant: **SLS**
- Co-surfactant: **CAPB**  
- Ratio: **2:1** (SLS:CAPB)
- Polymer: **KG30M**
- Water Hardness: **7 gpg**

**Concentration Ranges:**
- SLS: 0.13% - 5.00%
- CAPB: 0.05% - 2.50% (maintains 2:1 ratio)
- KG30M: 0.0001% - 0.10%

**Will be named:** `SLS-CAPB (2:1) with KG30M, 7gpg`

## Backward Compatibility

Experiments without co-surfactants work exactly as before:
- `cosurfactant_name` = NULL
- `cosurfactant_pct` = NULL  
- Names display as: `Rhamnolipid with Excel, 7gpg`
- All existing validated analysis code continues to work

## Notes

- The co-surfactant ratio is **fixed** across all wells in an experiment
- Plots show **total surfactant** on the axis (primary + co-surfactant)
- Individual surfactant and co-surfactant concentrations are stored separately in the database
- The ratio makes it clear what system you're looking at in plots and exports
