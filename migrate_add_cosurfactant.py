"""
Migration script to add co-surfactant support to existing database.
Adds cosurfactant_name and cosurfactant_pct columns to measurements table.
"""

import sqlite3
from pathlib import Path


def migrate_database(db_path):
    """
    Add co-surfactant columns to the measurements table.
    
    Args:
        db_path: Path to the SQLite database file
    """
    print(f"Migrating database: {db_path}")
    
    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current schema
    cursor.execute("PRAGMA table_info(measurements)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    print(f"Current columns: {len(column_names)}")
    
    # Check if cosurfactant columns already exist
    has_cosurfactant_name = 'cosurfactant_name' in column_names
    has_cosurfactant_pct = 'cosurfactant_pct' in column_names
    
    if has_cosurfactant_name and has_cosurfactant_pct:
        print("✓ Co-surfactant columns already exist. No migration needed.")
        conn.close()
        return
    
    # Add cosurfactant_name column if missing
    if not has_cosurfactant_name:
        print("  Adding cosurfactant_name column...")
        cursor.execute("""
            ALTER TABLE measurements 
            ADD COLUMN cosurfactant_name TEXT
        """)
        print("  ✓ Added cosurfactant_name")
    
    # Add cosurfactant_pct column if missing
    if not has_cosurfactant_pct:
        print("  Adding cosurfactant_pct column...")
        cursor.execute("""
            ALTER TABLE measurements 
            ADD COLUMN cosurfactant_pct REAL
        """)
        print("  ✓ Added cosurfactant_pct")
    
    conn.commit()
    
    # Verify changes
    cursor.execute("PRAGMA table_info(measurements)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    print(f"\nUpdated columns: {len(column_names)}")
    print(f"✓ Migration complete!")
    
    # Show sample of data
    cursor.execute("SELECT COUNT(*) FROM measurements")
    count = cursor.fetchone()[0]
    print(f"Total records: {count}")
    
    conn.close()


if __name__ == "__main__":
    # Migrate the main database
    db_path = "data/phase_diagrams.db"
    
    if Path(db_path).exists():
        migrate_database(db_path)
    else:
        # Try alternate location
        db_path = "phase_diagrams.db"
        if Path(db_path).exists():
            migrate_database(db_path)
        else:
            print("ERROR: Could not find phase_diagrams.db")
            print("Please specify the database path:")
            print("  python migrate_add_cosurfactant.py")
