"""
Utility functions for handling experiments with co-surfactants.
These help generate descriptive names and titles without modifying validated plotting code.

The co-surfactant is present at a fixed ratio to the primary surfactant.
Plots continue to use surfactant_pct vs polymer_pct axes.
Co-surfactant info is displayed in titles and metadata for clarity.
"""

import pandas as pd
import sqlite3
from pathlib import Path


def calculate_surfactant_ratio(df):
    """
    Calculate the surfactant:co-surfactant ratio from experiment data.
    
    Args:
        df: DataFrame with surfactant_pct and cosurfactant_pct columns
        
    Returns:
        tuple: (surf_ratio, cosurf_ratio) as integers (e.g., (50, 50) or (2, 1))
               Returns (None, None) if no co-surfactant present
    """
    # Check if co-surfactant is present
    if 'cosurfactant_pct' not in df.columns or df['cosurfactant_pct'].isna().all():
        return None, None
    
    # Get rows with both surfactant and co-surfactant
    valid_rows = df[(df['surfactant_pct'] > 0) & (df['cosurfactant_pct'] > 0)]
    
    if len(valid_rows) == 0:
        return None, None
    
    # Calculate ratio (should be constant across all wells)
    ratio = valid_rows['surfactant_pct'] / valid_rows['cosurfactant_pct']
    mean_ratio = ratio.mean()
    
    # Convert to simple integer ratio
    # Common cases: 1:1 (50:50), 2:1, 1:2, 3:1, etc.
    if 0.9 < mean_ratio < 1.1:  # ~1:1
        return 1, 1
    elif 1.8 < mean_ratio < 2.2:  # ~2:1
        return 2, 1
    elif 0.45 < mean_ratio < 0.55:  # ~1:2
        return 1, 2
    elif 2.8 < mean_ratio < 3.2:  # ~3:1
        return 3, 1
    elif 0.3 < mean_ratio < 0.37:  # ~1:3
        return 1, 3
    elif 3.8 < mean_ratio < 4.2:  # ~4:1
        return 4, 1
    elif 0.23 < mean_ratio < 0.27:  # ~1:4
        return 1, 4
    else:
        # Return as rounded values (1 decimal for non-standard ratios)
        return round(mean_ratio, 1), 1


def format_surfactant_system_name(surfactant_name, cosurfactant_name=None, 
                                   surf_ratio=None, cosurf_ratio=None):
    """
    Format surfactant system name with co-surfactant ratio.
    
    Args:
        surfactant_name: Primary surfactant name
        cosurfactant_name: Co-surfactant name (optional)
        surf_ratio: Surfactant ratio number (optional)
        cosurf_ratio: Co-surfactant ratio number (optional)
        
    Returns:
        str: Formatted name like "SLS-CAPB (50:50)" or just "Rhamnolipid"
    """
    if cosurfactant_name is None or surf_ratio is None or cosurf_ratio is None:
        return surfactant_name
    
    # Format ratio - use integers when possible
    if isinstance(surf_ratio, int) and isinstance(cosurf_ratio, int):
        ratio_str = f"{surf_ratio}:{cosurf_ratio}"
    elif surf_ratio == int(surf_ratio) and cosurf_ratio == int(cosurf_ratio):
        ratio_str = f"{int(surf_ratio)}:{int(cosurf_ratio)}"
    else:
        ratio_str = f"{surf_ratio}:{cosurf_ratio}"
    
    return f"{surfactant_name}-{cosurfactant_name} ({ratio_str})"


def generate_experiment_title(experiment_id=None, df=None, db_path='data/phase_diagrams.db'):
    """
    Generate a descriptive title for an experiment, including co-surfactant info.
    
    Args:
        experiment_id: Experiment ID to look up
        df: DataFrame with experiment data (if not provided, will query from db)
        db_path: Path to database
        
    Returns:
        str: Descriptive title like "Rhamnolipid-Excel 7gpg" or "SLS-CAPB (50:50) with KG30M, 7gpg"
    """
    # Get experiment data if not provided
    if df is None and experiment_id is not None:
        conn = sqlite3.connect(db_path)
        query = """
        SELECT DISTINCT surfactant_name, cosurfactant_name, polymer_name, 
               water_hardness_gpg, surfactant_pct, cosurfactant_pct
        FROM measurements
        WHERE experiment_id = ?
        """
        df = pd.read_sql_query(query, conn, params=[experiment_id])
        conn.close()
    
    if df is None or len(df) == 0:
        return "Unknown Experiment"
    
    # Extract info
    surfactant_name = df['surfactant_name'].iloc[0] if 'surfactant_name' in df.columns else "Unknown"
    cosurfactant_name = df['cosurfactant_name'].iloc[0] if 'cosurfactant_name' in df.columns else None
    polymer_name = df['polymer_name'].iloc[0] if 'polymer_name' in df.columns else "Unknown"
    hardness = df['water_hardness_gpg'].iloc[0] if 'water_hardness_gpg' in df.columns else 7
    
    # Handle None values
    if pd.isna(cosurfactant_name):
        cosurfactant_name = None
    if pd.isna(surfactant_name) or surfactant_name == 'None':
        surfactant_name = "Unknown"
    if pd.isna(polymer_name) or polymer_name == 'None':
        polymer_name = "Unknown"
    
    # Calculate ratio if co-surfactant present
    surf_ratio, cosurf_ratio = calculate_surfactant_ratio(df)
    
    # Format surfactant system name
    surf_system = format_surfactant_system_name(surfactant_name, cosurfactant_name, 
                                                 surf_ratio, cosurf_ratio)
    
    # Build title
    title = f"{surf_system} with {polymer_name}, {int(hardness)}gpg"
    
    return title


def add_cosurfactant_to_plot_title(base_title, experiment_id=None, df=None, db_path='data/phase_diagrams.db'):
    """
    Add co-surfactant information to an existing plot title if relevant.
    
    Args:
        base_title: Existing plot title
        experiment_id: Experiment ID to look up
        df: DataFrame with experiment data (if not provided, will query from db)
        db_path: Path to database
        
    Returns:
        str: Title with co-surfactant info added, or original title if no co-surfactant
    """
    # Get experiment data if not provided
    if df is None and experiment_id is not None:
        conn = sqlite3.connect(db_path)
        query = """
        SELECT DISTINCT surfactant_name, cosurfactant_name, surfactant_pct, cosurfactant_pct
        FROM measurements
        WHERE experiment_id = ?
        """
        df = pd.read_sql_query(query, conn, params=[experiment_id])
        conn.close()
    
    if df is None or len(df) == 0:
        return base_title
    
    # Check if co-surfactant present
    cosurfactant_name = df['cosurfactant_name'].iloc[0] if 'cosurfactant_name' in df.columns else None
    if pd.isna(cosurfactant_name) or cosurfactant_name is None:
        return base_title
    
    # Calculate ratio
    surf_ratio, cosurf_ratio = calculate_surfactant_ratio(df)
    if surf_ratio is None:
        return base_title
    
    # Format ratio string
    surfactant_name = df['surfactant_name'].iloc[0]
    surf_system = format_surfactant_system_name(surfactant_name, cosurfactant_name, 
                                                 surf_ratio, cosurf_ratio)
    
    # Add to title
    return f"{base_title}\n{surf_system} System"


def get_experiment_cosurfactant_info(experiment_id, db_path='data/phase_diagrams.db'):
    """
    Get co-surfactant information for an experiment.
    
    Args:
        experiment_id: Experiment ID
        db_path: Path to database
        
    Returns:
        dict: {'has_cosurfactant': bool, 'cosurfactant_name': str, 'ratio': str, ...}
    """
    conn = sqlite3.connect(db_path)
    query = """
    SELECT DISTINCT surfactant_name, cosurfactant_name, polymer_name,
           surfactant_pct, cosurfactant_pct, water_hardness_gpg
    FROM measurements
    WHERE experiment_id = ?
    """
    df = pd.read_sql_query(query, conn, params=[experiment_id])
    conn.close()
    
    if len(df) == 0:
        return {'has_cosurfactant': False}
    
    cosurfactant_name = df['cosurfactant_name'].iloc[0]
    has_cosurfactant = not pd.isna(cosurfactant_name) and cosurfactant_name is not None
    
    info = {
        'has_cosurfactant': has_cosurfactant,
        'surfactant_name': df['surfactant_name'].iloc[0],
        'polymer_name': df['polymer_name'].iloc[0],
        'water_hardness_gpg': df['water_hardness_gpg'].iloc[0]
    }
    
    if has_cosurfactant:
        surf_ratio, cosurf_ratio = calculate_surfactant_ratio(df)
        info.update({
            'cosurfactant_name': cosurfactant_name,
            'surf_ratio': surf_ratio,
            'cosurf_ratio': cosurf_ratio,
            'ratio_string': f"{surf_ratio}:{cosurf_ratio}" if surf_ratio else "Unknown",
            'system_name': format_surfactant_system_name(
                df['surfactant_name'].iloc[0], cosurfactant_name, 
                surf_ratio, cosurf_ratio
            )
        })
    
    return info


if __name__ == "__main__":
    # Example usage
    print("Co-surfactant Utility Functions")
    print("=" * 70)
    
    # Test with mock data
    import numpy as np
    
    # Create test data with 50:50 ratio
    test_df = pd.DataFrame({
        'surfactant_pct': np.linspace(0.5, 5.0, 20),
        'cosurfactant_pct': np.linspace(0.5, 5.0, 20),  # Same as surfactant (50:50)
        'polymer_pct': np.linspace(0.01, 0.1, 20),
        'surfactant_name': 'SLS',
        'cosurfactant_name': 'CAPB',
        'polymer_name': 'KG30M',
        'water_hardness_gpg': 7.0
    })
    
    surf_ratio, cosurf_ratio = calculate_surfactant_ratio(test_df)
    print(f"\nTest Ratio Calculation:")
    print(f"  Surfactant:Co-surfactant = {surf_ratio}:{cosurf_ratio}")
    
    system_name = format_surfactant_system_name('SLS', 'CAPB', surf_ratio, cosurf_ratio)
    print(f"\nFormatted System Name:")
    print(f"  {system_name}")
    
    title = generate_experiment_title(df=test_df)
    print(f"\nGenerated Title:")
    print(f"  {title}")
