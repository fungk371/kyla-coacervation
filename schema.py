"""
Database schema for phase diagram experiments.
Single flat table design for easy querying and Azure Blob compatibility.
"""

import sqlite3
from pathlib import Path


def create_database(db_path: str) -> None:
    """
    Create SQLite database with flat table schema.
    
    Args:
        db_path: Path to SQLite database file
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Single flat table with all metadata per measurement
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Experiment metadata
            experiment_id TEXT NOT NULL,
            experiment_name TEXT,
            date_created TEXT,
            
            -- Well identification
            plate INTEGER NOT NULL,
            well TEXT NOT NULL,
            row TEXT NOT NULL,
            column INTEGER NOT NULL,
            
            -- Surfactant and polymer information
            surfactant_name TEXT,
            cosurfactant_name TEXT,
            polymer_name TEXT,
            
            -- Water hardness (grains per gallon)
            water_hardness_gpg REAL DEFAULT 7.0,
            
            -- Volumes (microliters)
            volume_SW1 REAL,
            volume_PS1 REAL,
            volume_PS2 REAL,
            volume_AS1 REAL,
            volume_AS2 REAL,
            volume_AS3 REAL,
            volume_ADD1 REAL,
            total_volume_uL REAL,
            
            -- Solution concentrations (stored as JSON string)
            solution_concentrations_json TEXT,
            
            -- Calculated concentrations (weight percent)
            surfactant_pct REAL,
            cosurfactant_pct REAL,
            polymer_pct REAL,
            
            -- Measurement data
            timepoint_minutes REAL NOT NULL,
            transmission_pct REAL,
            
            -- File tracking
            excel_filename TEXT,
            transmission_filename TEXT,
            
            -- Indexing for efficient queries
            UNIQUE(experiment_id, plate, well, timepoint_minutes)
        )
    """)
    
    # Create indices for common queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_experiment 
        ON measurements(experiment_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_surfactant_polymer 
        ON measurements(surfactant_name, polymer_name)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timepoint 
        ON measurements(timepoint_minutes)
    """)
    
    conn.commit()
    conn.close()
    
    print(f"Database created at: {db_path}")


def get_table_info(db_path: str) -> None:
    """Print schema information."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(measurements)")
    columns = cursor.fetchall()
    
    print("\nTable: measurements")
    print("-" * 80)
    for col in columns:
        print(f"{col[1]:30s} {col[2]:15s} {'NOT NULL' if col[3] else ''}")
    
    cursor.execute("SELECT COUNT(*) FROM measurements")
    count = cursor.fetchone()[0]
    print(f"\nTotal records: {count}")
    
    conn.close()


if __name__ == "__main__":
    # Example usage
    db_path = "phase_diagrams.db"
    create_database(db_path)
    get_table_info(db_path)
