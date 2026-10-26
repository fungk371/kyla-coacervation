"""
Migration script to add water_hardness_gpg column to existing databases.
Defaults all existing records to 7 gpg (standard water hardness).
Then attempts to extract actual hardness from filenames containing '0gpg' or '7gpg'.
"""

import sqlite3
from pathlib import Path
import re


def add_water_hardness_column(db_path):
    """Add water_hardness_gpg column to existing database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if measurements table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='measurements'")
    if cursor.fetchone() is None:
        print(f"  Table 'measurements' does not exist in {db_path} - skipping")
        conn.close()
        return False
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(measurements)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'water_hardness_gpg' in columns:
        print(f"  Column 'water_hardness_gpg' already exists in {db_path}")
        conn.close()
        return False
    
    print(f"  Adding 'water_hardness_gpg' column to {db_path}...")
    
    # Add the column with default value
    cursor.execute("""
        ALTER TABLE measurements 
        ADD COLUMN water_hardness_gpg REAL DEFAULT 7.0
    """)
    
    # Set all existing records to 7 gpg
    cursor.execute("UPDATE measurements SET water_hardness_gpg = 7.0")
    rows_updated = cursor.rowcount
    
    print(f"  ✓ Added column and set {rows_updated} existing records to 7.0 gpg")
    
    conn.commit()
    conn.close()
    return True


def extract_gpg_from_filename(filename):
    """
    Extract water hardness from filename.
    Looks for patterns like '0gpg' or '7gpg' (case insensitive).
    Returns float or None if not found.
    """
    if not filename:
        return None
    
    # Search for pattern: digit(s) followed by 'gpg'
    match = re.search(r'(\d+)gpg', str(filename), re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    return None


def update_water_hardness_from_filenames(db_path):
    """Update water hardness by parsing excel and transmission filenames."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if measurements table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='measurements'")
    if cursor.fetchone() is None:
        print(f"  Table 'measurements' does not exist - skipping filename analysis")
        conn.close()
        return []
    
    # Get all unique experiments with their filenames
    cursor.execute("""
        SELECT DISTINCT experiment_id, excel_filename, transmission_filename
        FROM measurements
        WHERE excel_filename IS NOT NULL OR transmission_filename IS NOT NULL
    """)
    
    experiments = cursor.fetchall()
    updated_experiments = []
    
    if len(experiments) == 0:
        print(f"  No experiments with filenames found")
        conn.close()
        return []
    
    print(f"\n  Analyzing {len(experiments)} experiments for water hardness...")
    
    for exp_id, excel_file, trans_file in experiments:
        # Try to extract from either filename
        gpg = extract_gpg_from_filename(excel_file) or extract_gpg_from_filename(trans_file)
        
        if gpg is not None:
            # Update all records for this experiment
            cursor.execute("""
                UPDATE measurements 
                SET water_hardness_gpg = ? 
                WHERE experiment_id = ?
            """, (gpg, exp_id))
            
            rows_updated = cursor.rowcount
            print(f"  ✓ {exp_id}: Set to {gpg} gpg ({rows_updated} records)")
            updated_experiments.append(exp_id)
        else:
            print(f"  - {exp_id}: No GPG found in filenames, keeping default 7.0 gpg")
    
    conn.commit()
    conn.close()
    
    return updated_experiments


def migrate_database(db_path):
    """Run complete migration on a database."""
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        return
    
    print(f"\n{'='*70}")
    print(f"Migrating: {db_path}")
    print(f"{'='*70}\n")
    
    # Step 1: Add column
    added = add_water_hardness_column(db_path)
    
    if not added:
        print("Column already exists. Proceeding to update values from filenames...")
    
    # Step 2: Update from filenames
    updated = update_water_hardness_from_filenames(db_path)
    
    print(f"\n{'='*70}")
    print(f"Migration Complete!")
    print(f"  Experiments updated from filenames: {len(updated)}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    # Migrate all databases in current directory
    import sys
    
    if len(sys.argv) > 1:
        # Specific database provided
        migrate_database(sys.argv[1])
    else:
        # Find all .db files in current directory
        db_files = list(Path('.').glob('*.db'))
        
        if not db_files:
            print("No database files found in current directory.")
            print("\nUsage: python migrate_add_water_hardness.py [database_path]")
        else:
            print(f"Found {len(db_files)} database file(s)")
            for db_file in db_files:
                migrate_database(str(db_file))
