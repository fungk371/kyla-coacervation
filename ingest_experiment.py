"""
Ingest phase diagram experiments into database.
Uses the same proven logic from build_experiment_datasets.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import re
from io import StringIO
import sqlite3
import json
from datetime import datetime


def extract_water_hardness_from_filename(filename):
    """
    Extract water hardness (gpg) from filename.
    Looks for patterns like '0gpg' or '7gpg' (case insensitive).
    Returns float or 7.0 (default) if not found.
    
    Args:
        filename: Filename or path as string or Path object
        
    Returns:
        float: Water hardness in grains per gallon (gpg)
    """
    if not filename:
        return 7.0  # Default to 7 gpg
    
    # Find all matches of pattern: digit(s) followed by 'gpg'
    # Use the LAST match (most specific to the actual file/folder)
    matches = re.findall(r'(\d+)gpg', str(filename), re.IGNORECASE)
    if matches:
        return float(matches[-1])  # Return last match
    
    return 7.0  # Default to 7 gpg


def assign_well_ids(n_rows=192):
    """
    Assign well IDs based on column-wise filling order.
    
    Order: A1, B1, C1, D1, E1, F1, G1, H1 (col 1)
           A2, B2, C2, D2, E2, F2, G2, H2 (col 2)
           ...
           A12, B12, C12, D12, E12, F12, G12, H12 (col 12)
    
    First 96 rows = Plate 1
    Next 96 rows = Plate 2
    """
    wells = []
    plates = []
    rows = []
    columns = []
    
    row_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    
    for plate in [1, 2]:
        for col in range(1, 13):  # Columns 1-12
            for row in range(8):  # Rows A-H (0-7)
                wells.append(f"{row_letters[row]}{col}")
                plates.append(plate)
                rows.append(row_letters[row])
                columns.append(col)
    
    return pd.DataFrame({
        'plate': plates,
        'well': wells,
        'row': rows,
        'column': columns
    })


def extract_surfactant_polymer_names(solutions_df):
    """
    Extract surfactant, co-surfactant, and polymer names from Description column.
    
    Args:
        solutions_df: DataFrame with 'Solution' and 'Description' columns
        
    Returns:
        tuple: (surfactant_name, cosurfactant_name, polymer_name)
    """
    surfactant_name = None
    cosurfactant_name = None
    polymer_name = None
    
    for _, row in solutions_df.iterrows():
        solution_id = str(row['Solution']).upper()
        desc = str(row['Description'])
        
        # Skip if description is nan or empty
        if desc.lower() == 'nan' or not desc.strip():
            continue
        
        # Surfactant solutions: AS (Anionic Surfactant) or Surf
        if (solution_id.startswith('AS') or solution_id.startswith('SURF')) and surfactant_name is None:
            # Extract the surfactant name from the description
            # Format: "SLS, pH5.5, 21510170" or "Rhamnolipid, ..."
            # Take the first part before comma (the actual chemical name)
            parts = desc.split(',')
            if parts and parts[0].strip():
                surfactant_name = parts[0].strip()
        
        # Co-surfactant solutions: CoSurf or CS
        if (solution_id.startswith('COSURF') or solution_id.startswith('CS')) and cosurfactant_name is None:
            # Extract the co-surfactant name from the description
            parts = desc.split(',')
            if parts and parts[0].strip():
                cosurfactant_name = parts[0].strip()
        
        # Polymer solutions: PS (Polymer Solution) or Poly
        if (solution_id.startswith('PS') or solution_id.startswith('POLY')) and polymer_name is None:
            # Extract the polymer name from the description
            # Format: "Excel, pH 6 - 21497798"
            # Take the first part before comma (the actual chemical name)
            parts = desc.split(',')
            if parts and parts[0].strip():
                polymer_name = parts[0].strip()
    
    return surfactant_name, cosurfactant_name, polymer_name
    
    return surfactant_name, cosurfactant_name, polymer_name


def normalize_column_names(volumes_df):
    """
    Normalize column names to a standard format.
    Handles both old naming (SW1, PS1, AS1) and new naming (Buffer, PolymerStock1, SurfStock1).
    
    Returns:
        dict: Mapping of standard names to actual column names in the dataframe
    """
    column_map = {}
    columns = volumes_df.columns.tolist()
    
    # Map water/buffer columns
    if 'SW1' in columns:
        column_map['water'] = 'SW1'
    elif 'Buffer' in columns:
        column_map['water'] = 'Buffer'
    
    # Map polymer columns (up to 2)
    if 'PS1' in columns:
        column_map['polymer_1'] = 'PS1'
    elif 'PolymerStock1' in columns:
        column_map['polymer_1'] = 'PolymerStock1'
    
    if 'PS2' in columns:
        column_map['polymer_2'] = 'PS2'
    elif 'PolymerStock2' in columns:
        column_map['polymer_2'] = 'PolymerStock2'
    
    # Map surfactant columns (up to 3)
    if 'AS1' in columns:
        column_map['surf_1'] = 'AS1'
    elif 'SurfStock1' in columns:
        column_map['surf_1'] = 'SurfStock1'
    
    if 'AS2' in columns:
        column_map['surf_2'] = 'AS2'
    elif 'SurfStock2' in columns:
        column_map['surf_2'] = 'SurfStock2'
    
    if 'AS3' in columns:
        column_map['surf_3'] = 'AS3'
    
    # Map co-surfactant columns (up to 2)
    if 'CoSurfStock1' in columns:
        column_map['cosurf_1'] = 'CoSurfStock1'
    
    if 'CoSurfStock2' in columns:
        column_map['cosurf_2'] = 'CoSurfStock2'
    
    # Map additional component
    if 'ADD1' in columns:
        column_map['additive'] = 'ADD1'
    
    return column_map


def normalize_solution_ids(solutions_df):
    """
    Normalize solution IDs to match the volume column names.
    Handles both old naming (AS1, PS1) and new naming (Surf1, Poly1, CoSurf1).
    
    Returns:
        dict: Mapping of volume column names to solution IDs for concentration lookup
    """
    solution_map = {}
    
    for _, row in solutions_df.iterrows():
        sol_id = str(row['Solution'])
        
        # Old format: AS1 -> AS1, PS1 -> PS1
        if sol_id in ['SW1', 'PS1', 'PS2', 'AS1', 'AS2', 'AS3', 'ADD1']:
            solution_map[sol_id] = sol_id
        
        # New format: Surf1 -> SurfStock1, Poly1 -> PolymerStock1
        if sol_id.startswith('Surf'):
            num = sol_id.replace('Surf', '')
            solution_map[f'SurfStock{num}'] = sol_id
        
        if sol_id.startswith('CoSurf'):
            num = sol_id.replace('CoSurf', '')
            solution_map[f'CoSurfStock{num}'] = sol_id
        
        if sol_id.startswith('Poly'):
            num = sol_id.replace('Poly', '')
            solution_map[f'PolymerStock{num}'] = sol_id
        
        if sol_id == 'Water' or sol_id == 'Buffer':
            solution_map['Buffer'] = sol_id
    
    return solution_map


def read_compositions(excel_file):
    """
    Read volumes and solution metadata from Excel file.
    Returns compositions with calculated concentrations.
    Handles both old and new column naming schemes.
    """
    print(f"  Reading Excel: {Path(excel_file).name}")
    
    # Read volumes
    volumes = pd.read_excel(excel_file, sheet_name='Volumes')
    print(f"    Volumes shape: {volumes.shape}")
    print(f"    Volume columns: {list(volumes.columns)}")
    
    # Read solution metadata
    solutions = pd.read_excel(excel_file, sheet_name='Test Solutions')
    print(f"    Solutions: {len(solutions)} solutions")
    
    # Extract surfactant, co-surfactant, and polymer names
    surfactant_name, cosurfactant_name, polymer_name = extract_surfactant_polymer_names(solutions)
    print(f"    Surfactant: {surfactant_name}")
    print(f"    Co-surfactant: {cosurfactant_name}")
    print(f"    Polymer: {polymer_name}")
    
    # Normalize column names
    col_map = normalize_column_names(volumes)
    sol_map = normalize_solution_ids(solutions)
    print(f"    Column mapping: {col_map}")
    
    # Assign well IDs
    well_info = assign_well_ids(len(volumes))
    
    # Combine volumes with well IDs
    compositions = pd.concat([well_info, volumes], axis=1)
    
    # Get solution concentrations
    sol_conc = {}
    for _, row in solutions.iterrows():
        sol_id = row['Solution']
        conc = row['Concentration']
        units = str(row.get('Units', '')).strip().lower()
        # Optional active-% correction. If the Test Solutions sheet has an
        # "Active" column (e.g. 29 for a 29%-active SLS stock), the recorded
        # Concentration is treated as AS-SUPPLIED and multiplied by the active
        # fraction to get true active %. Prevents the SLE3S/SLS 28-29% error.
        active = None
        for _k in ('Active', 'Active %', 'Active_pct', 'Active%', 'Active_Percent'):
            if _k in row.index and pd.notna(row.get(_k)):
                active = row.get(_k)
                break

        if pd.notna(conc):
            # Determine if this is water/buffer (skip) or a chemical concentration
            is_water = sol_id in ['Water', 'Buffer', 'SW1']
            
            if units == '%' or units == '':
                # Standard percentage - convert to fraction
                sol_conc[sol_id] = conc / 100
            elif units == 'gpg':
                if is_water:
                    # Water hardness - not a concentration, skip
                    sol_conc[sol_id] = 0
                else:
                    # Surfactant/polymer concentration in grams per gallon (treat as %)
                    sol_conc[sol_id] = conc / 100
            else:
                # Unknown unit - treat as already a fraction
                sol_conc[sol_id] = conc

            # Apply the active-% correction (true active = as-supplied x active fraction).
            if active is not None and not is_water:
                try:
                    af = float(active)
                    if af > 1:            # given as a percent, e.g. 29
                        af = af / 100.0
                    if 0 < af <= 1:
                        sol_conc[sol_id] *= af
                        print(f"      [active-correct] {sol_id}: x{af:.3f} (as-supplied -> true active)")
                except (TypeError, ValueError):
                    pass
        else:
            sol_conc[sol_id] = 0
    
    print(f"    Solution concentrations:")
    for sol, conc in sol_conc.items():
        if conc > 0:
            print(f"      {sol}: {conc*100:.3f}%")
    
    # Calculate total volume - use all volume columns present
    volume_cols = [col_map[k] for k in col_map.keys() if k != 'additive']  # All except additive
    if 'additive' in col_map:
        volume_cols.append(col_map['additive'])
    
    # Ensure all volume columns exist
    volume_cols = [c for c in volume_cols if c in volumes.columns]
    compositions['total_volume_uL'] = volumes[volume_cols].sum(axis=1)
    
    # Calculate final concentrations
    # Surfactant concentration
    surf_vol_conc = 0
    for key in ['surf_1', 'surf_2', 'surf_3']:
        if key in col_map:
            vol_col = col_map[key]
            sol_id = sol_map.get(vol_col, None)
            if sol_id and sol_id in sol_conc:
                surf_vol_conc += compositions.get(vol_col, 0) * sol_conc[sol_id]
    
    compositions['surfactant_pct'] = (surf_vol_conc / compositions['total_volume_uL']) * 100
    
    # Co-surfactant concentration
    cosurf_vol_conc = 0
    for key in ['cosurf_1', 'cosurf_2']:
        if key in col_map:
            vol_col = col_map[key]
            sol_id = sol_map.get(vol_col, None)
            if sol_id and sol_id in sol_conc:
                cosurf_vol_conc += compositions.get(vol_col, 0) * sol_conc[sol_id]
    
    compositions['cosurfactant_pct'] = (cosurf_vol_conc / compositions['total_volume_uL']) * 100
    
    # Polymer concentration
    poly_vol_conc = 0
    print(f"    DEBUG: Calculating polymer concentration...")
    for key in ['polymer_1', 'polymer_2']:
        if key in col_map:
            vol_col = col_map[key]
            sol_id = sol_map.get(vol_col, None)
            print(f"      {key}: vol_col={vol_col}, sol_id={sol_id}")
            print(f"        sol_id in sol_conc? {sol_id in sol_conc if sol_id else False}")
            if sol_id:
                print(f"        sol_conc[{sol_id}] = {sol_conc.get(sol_id, 'NOT FOUND')}")
                print(f"        Sample volumes from compositions[{vol_col}]: min={compositions[vol_col].min():.2f}, max={compositions[vol_col].max():.2f}")
            if sol_id and sol_id in sol_conc:
                contribution = compositions[vol_col] * sol_conc[sol_id]
                print(f"        Contribution: min={contribution.min():.6f}, max={contribution.max():.6f}")
                poly_vol_conc += contribution
    
    compositions['polymer_pct'] = (poly_vol_conc / compositions['total_volume_uL']) * 100
    print(f"    DEBUG: Final polymer_pct range: {compositions['polymer_pct'].min():.4f} - {compositions['polymer_pct'].max():.4f}%")
    
    # Print concentration ranges
    if surfactant_name and compositions['surfactant_pct'].max() > 0:
        print(f"    {surfactant_name} range: {compositions['surfactant_pct'].min():.4f} - {compositions['surfactant_pct'].max():.4f}%")
    if cosurfactant_name and compositions['cosurfactant_pct'].max() > 0:
        print(f"    {cosurfactant_name} range: {compositions['cosurfactant_pct'].min():.4f} - {compositions['cosurfactant_pct'].max():.4f}%")
    if polymer_name and compositions['polymer_pct'].max() > 0:
        print(f"    {polymer_name} range: {compositions['polymer_pct'].min():.4f} - {compositions['polymer_pct'].max():.4f}%")
    
    # Add surfactant/polymer names to dataframe
    compositions['surfactant_name'] = surfactant_name
    compositions['cosurfactant_name'] = cosurfactant_name
    compositions['polymer_name'] = polymer_name
    
    # Store solution concentrations as JSON
    compositions['solution_concentrations_json'] = json.dumps(
        {k: v*100 for k, v in sol_conc.items()}  # Store as percentages
    )
    
    return compositions


def parse_transmission_file(file_path):
    """Parse a single transmission data file (UTF-16 encoded)."""
    
    # Read file and find data section
    with open(file_path, 'r', encoding='utf-16') as f:
        lines = f.readlines()
    
    # Find the line with 'Sample\tWell\tValues'
    data_start = None
    for i, line in enumerate(lines):
        if 'Sample\tWell\tValues' in line:
            data_start = i
            break
    
    if data_start is None:
        raise ValueError(f"Could not find data section in {file_path}")
    
    # Read from that point
    data_lines = lines[data_start:]
    df = pd.read_csv(StringIO(''.join(data_lines)), sep='\t')
    
    # Extract timepoint from filename
    filename = Path(file_path).name
    # Support both space and underscore separators: "9.010317 001-096" or "9.010317_001-096"
    match = re.search(r'(\d+\.\d+)[\s_]+(\d{3})-(\d{3})', filename)
    if match:
        timepoint = float(match.group(1))
        start_well = int(match.group(2))
        # Wells 001-096 = Plate 1, Wells 097-192 = Plate 2
        plate = 1 if start_well <= 96 else 2
    else:
        raise ValueError(f"Could not extract timepoint from filename: {filename}")
    
    # Clean up data
    df = df[df['Well'].notna()].copy()
    df = df[['Well', 'Values']].copy()
    df.columns = ['well', 'transmission_pct']
    
    # Add metadata
    df['timepoint_minutes'] = timepoint
    df['plate'] = plate
    df['transmission_filename'] = filename
    
    return df


def read_transmission_data(folder_path):
    """Read all transmission files from a folder."""
    
    folder = Path(folder_path)
    txt_files = list(folder.glob('*.txt'))
    
    print(f"    Found {len(txt_files)} transmission files")
    
    all_data = []
    
    for file in sorted(txt_files):
        try:
            df = parse_transmission_file(file)
            all_data.append(df)
        except Exception as e:
            print(f"      WARNING: Could not parse {file.name}: {e}")
    
    # Combine all timepoints
    combined = pd.concat(all_data, ignore_index=True)
    
    print(f"    Total transmission measurements: {len(combined)}")
    print(f"    Timepoints: {sorted(combined['timepoint_minutes'].unique())}")
    print(f"    Plates: {sorted(combined['plate'].unique())}")
    print(f"    Plate 1 measurements: {len(combined[combined['plate']==1])}")
    print(f"    Plate 2 measurements: {len(combined[combined['plate']==2])}")
    
    return combined


def ingest_experiment(db_path, experiment_id, experiment_name, excel_file, transmission_folder):
    """
    Ingest a complete experiment into the database.
    
    Args:
        db_path: Path to SQLite database
        experiment_id: Unique identifier for this experiment
        experiment_name: Human-readable name
        excel_file: Path to Excel file with Volumes and Test Solutions sheets
        transmission_folder: Path to folder containing transmission .txt files
    """
    print(f"\n{'='*70}")
    print(f"Ingesting: {experiment_name}")
    print(f"ID: {experiment_id}")
    print(f"{'='*70}")
    
    # Read compositions from Excel
    compositions = read_compositions(excel_file)
    
    # Read transmission data
    print(f"\n  Reading transmission data from: {Path(transmission_folder).name}")
    transmission = read_transmission_data(transmission_folder)
    
    # Merge compositions with transmission data
    print(f"\n  Merging data...")
    dataset = pd.merge(
        compositions,
        transmission,
        on=['plate', 'well'],
        how='inner'  # Only keep wells with transmission data
    )
    
    # Add experiment metadata
    dataset['experiment_id'] = experiment_id
    dataset['experiment_name'] = experiment_name
    dataset['date_created'] = datetime.now().isoformat()
    dataset['excel_filename'] = Path(excel_file).name
    
    # Extract water hardness from filenames (look in both excel and transmission folder)
    water_hardness = extract_water_hardness_from_filename(excel_file)
    if water_hardness == 7.0:  # If not found in excel, try transmission folder
        water_hardness = extract_water_hardness_from_filename(transmission_folder)
    dataset['water_hardness_gpg'] = water_hardness
    print(f"  Water Hardness: {water_hardness} gpg")
    
    print(f"    Merged dataset shape: {dataset.shape}")
    print(f"    Unique wells: {dataset[['plate', 'well']].drop_duplicates().shape[0]}")
    print(f"    Timepoints: {dataset['timepoint_minutes'].nunique()}")
    
    # Prepare columns for database
    # Map new column names to standard database column names
    # This ensures compatibility regardless of Excel naming convention
    column_name_mapping = {
        # New naming → Standard database naming
        'Buffer': 'SW1',
        'PolymerStock1': 'PS1',
        'PolymerStock2': 'PS2',
        'SurfStock1': 'AS1',
        'SurfStock2': 'AS2',
        'CoSurfStock1': 'CoSurfStock1',  # These are new columns (from migration)
        'CoSurfStock2': 'CoSurfStock2',  # These are new columns (from migration)
        # Old naming stays the same
        'SW1': 'SW1',
        'PS1': 'PS1',
        'PS2': 'PS2',
        'AS1': 'AS1',
        'AS2': 'AS2',
        'AS3': 'AS3',
        'ADD1': 'ADD1'
    }
    
    db_columns = [
        'experiment_id', 'experiment_name', 'date_created',
        'plate', 'well', 'row', 'column',
        'surfactant_name', 'cosurfactant_name', 'polymer_name', 'water_hardness_gpg',
    ]
    
    # Add volume columns with proper names for database
    for excel_col, db_col in column_name_mapping.items():
        if excel_col in dataset.columns:
            # Map Excel column name to standardized database column name
            dataset[f'volume_{db_col}'] = dataset[excel_col]
            if f'volume_{db_col}' not in db_columns:
                db_columns.append(f'volume_{db_col}')
    
    # Add remaining columns
    db_columns.extend([
        'total_volume_uL',
        'solution_concentrations_json',
        'surfactant_pct', 'cosurfactant_pct', 'polymer_pct',
        'timepoint_minutes', 'transmission_pct',
        'excel_filename', 'transmission_filename'
    ])
    
    # Select only the columns we need
    db_data = dataset[db_columns].copy()
    
    # Insert into database
    print(f"\n  Inserting {len(db_data)} records into database...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert data row by row, replacing duplicates
    inserted_count = 0
    replaced_count = 0
    
    for idx, row in db_data.iterrows():
        # Check if this record already exists
        cursor.execute(
            "SELECT COUNT(*) FROM measurements WHERE experiment_id = ? AND plate = ? AND well = ? AND timepoint_minutes = ?",
            (row['experiment_id'], row['plate'], row['well'], row['timepoint_minutes'])
        )
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            # Delete the old record
            cursor.execute(
                "DELETE FROM measurements WHERE experiment_id = ? AND plate = ? AND well = ? AND timepoint_minutes = ?",
                (row['experiment_id'], row['plate'], row['well'], row['timepoint_minutes'])
            )
            replaced_count += 1
        
        # Insert the new record
        placeholders = ', '.join(['?'] * len(db_columns))
        columns = ', '.join(db_columns)
        values = [row[col] for col in db_columns]
        
        cursor.execute(
            f"INSERT INTO measurements ({columns}) VALUES ({placeholders})",
            values
        )
        inserted_count += 1
    
    conn.commit()
    
    # Get final count
    cursor.execute("SELECT COUNT(*) FROM measurements WHERE experiment_id = ?", (experiment_id,))
    count = cursor.fetchone()[0]
    
    conn.close()
    
    if replaced_count > 0:
        print(f"  ✓ Inserted {inserted_count} records ({replaced_count} replaced existing)")
    else:
        print(f"  ✓ Successfully inserted {inserted_count} records")
    print(f"  ✓ Experiment '{experiment_name}' ingested")
    
    return dataset


def query_experiment(db_path, experiment_id=None, surfactant=None, polymer=None, 
                     min_timepoint=None, water_hardness=None, output_csv=None):
    """
    Query experiments from database.
    
    Args:
        db_path: Path to SQLite database
        experiment_id: Filter by experiment ID (optional)
        surfactant: Filter by surfactant name (optional)
        polymer: Filter by polymer name (optional)
        min_timepoint: Filter by minimum timepoint (optional)
        water_hardness: Filter by water hardness in gpg (optional)
        output_csv: Save results to CSV file (optional)
        
    Returns:
        DataFrame with query results
    """
    conn = sqlite3.connect(db_path)
    
    # Build query
    conditions = []
    params = []
    
    if experiment_id:
        conditions.append("experiment_id = ?")
        params.append(experiment_id)
    
    if surfactant:
        conditions.append("surfactant_name = ?")
        params.append(surfactant)
    
    if polymer:
        conditions.append("polymer_name = ?")
        params.append(polymer)
    
    if min_timepoint is not None:
        conditions.append("timepoint_minutes >= ?")
        params.append(min_timepoint)
    
    if water_hardness is not None:
        conditions.append("water_hardness_gpg = ?")
        params.append(water_hardness)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"SELECT * FROM measurements WHERE {where_clause}"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    print(f"\nQuery returned {len(df)} records")
    if len(df) > 0:
        print(f"  Experiments: {df['experiment_id'].unique()}")
        print(f"  Wells: {df[['plate', 'well']].drop_duplicates().shape[0]}")
        print(f"  Timepoints: {sorted(df['timepoint_minutes'].unique())}")
    
    if output_csv:
        df.to_csv(output_csv, index=False)
        print(f"  ✓ Saved to: {output_csv}")
    
    return df


if __name__ == "__main__":
    print("\nPhase Diagram Database Ingestion Tool")
    print("=" * 70)
    print("\nThis module provides functions to ingest phase diagram experiments.")
    print("\nExample usage:")
    print("""
    from schema import create_database
    from ingest_experiment import ingest_experiment, query_experiment
    
    # Create database
    create_database('phase_diagrams.db')
    
    # Ingest an experiment
    ingest_experiment(
        db_path='phase_diagrams.db',
        experiment_id='exp_001',
        experiment_name='Rhamnolipid-Excel 10min',
        excel_file='10_minute_input.xlsx',
        transmission_folder='10 minute run data'
    )
    
    # Query experiments
    data = query_experiment(
        db_path='phase_diagrams.db',
        experiment_id='exp_001',
        min_timepoint=10.0,
        output_csv='exp_001_filtered.csv'
    )
    """)
