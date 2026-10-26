"""
Test ingestion of 50_50 Surfactant_CoSurfactant experiment.
Automatically generates descriptive names including surfactant:co-surfactant ratio.
"""

from ingest_experiment import ingest_experiment, read_compositions
from cosurfactant_utils import calculate_surfactant_ratio, format_surfactant_system_name
from pathlib import Path
import sys
from datetime import datetime

# Configuration
DB_PATH = 'data/phase_diagrams.db'
EXCEL_FILE = '50_50 Surfactant_CoSurfactant Dilution Scheme.xlsx'

# You need to specify the transmission data folder
TRANSMISSION_FOLDER = None  # SET THIS to your transmission data folder path

if __name__ == "__main__":
    if TRANSMISSION_FOLDER is None:
        print("ERROR: Please set TRANSMISSION_FOLDER in this script")
        print("\nExample:")
        print("  TRANSMISSION_FOLDER = '50_50 transmission data'")
        print("\nOr provide it as a command line argument:")
        print(f"  python {sys.argv[0]} <transmission_folder_path>")
        
        if len(sys.argv) > 1:
            TRANSMISSION_FOLDER = sys.argv[1]
        else:
            sys.exit(1)
    
    # Check if files exist
    if not Path(EXCEL_FILE).exists():
        print(f"ERROR: Excel file not found: {EXCEL_FILE}")
        sys.exit(1)
    
    if not Path(TRANSMISSION_FOLDER).exists():
        print(f"ERROR: Transmission folder not found: {TRANSMISSION_FOLDER}")
        sys.exit(1)
    
    # Read composition to get names and calculate ratio
    print("Analyzing experiment composition...")
    comp_df = read_compositions(EXCEL_FILE)
    
    # Extract names
    surfactant_name = comp_df['surfactant_name'].iloc[0]
    cosurfactant_name = comp_df['cosurfactant_name'].iloc[0]
    polymer_name = comp_df['polymer_name'].iloc[0]
    
    # Calculate ratio
    surf_ratio, cosurf_ratio = calculate_surfactant_ratio(comp_df)
    
    # Format system name
    surf_system = format_surfactant_system_name(surfactant_name, cosurfactant_name, 
                                                 surf_ratio, cosurf_ratio)
    
    # Generate experiment ID and name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create short ID from names
    surf_short = surfactant_name[:3].upper() if surfactant_name else "UNK"
    cosurf_short = cosurfactant_name[:4].upper() if cosurfactant_name else ""
    poly_short = polymer_name[:5].upper() if polymer_name else "UNK"
    
    if cosurfactant_name:
        experiment_id = f"{timestamp}_{surf_short}_{cosurf_short}_{poly_short}"
        experiment_name = f"{surf_system} with {polymer_name}"
    else:
        experiment_id = f"{timestamp}_{surf_short}_{poly_short}"
        experiment_name = f"{surfactant_name} with {polymer_name}"
    
    print(f"\nExperiment ID: {experiment_id}")
    print(f"Experiment Name: {experiment_name}")
    print(f"Surfactant System: {surf_system}")
    
    # Ingest the experiment
    ingest_experiment(
        db_path=DB_PATH,
        experiment_id=experiment_id,
        experiment_name=experiment_name,
        excel_file=EXCEL_FILE,
        transmission_folder=TRANSMISSION_FOLDER
    )
    
    print("\n" + "="*70)
    print("SUCCESS! Experiment ingested")
    print(f"  ID: {experiment_id}")
    print(f"  Name: {experiment_name}")
    print("="*70)
