"""
Migration script to add co-surfactant volume columns to existing database.
Adds volume_CoSurfStock1 and volume_CoSurfStock2 columns to measurements table.
"""

import sqlite3
from pathlib import Path


def migrate_database(db_path):
    """
    Add co-surfactant volume columns to the measurements table.
    
    Args:
        db_path: Path to the SQLite database file
    """
    print(f"Migrating database: {db_path}")
    
    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current schema
    cursor.execute("PRAGMA table_info(measurements)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    print(f"Current columns: {len(column_names)}")
    
    # Check if co-surfactant volume columns already exist
    has_cosurf1 = 'volume_CoSurfStock1' in column_names
    has_cosurf2 = 'volume_CoSurfStock2' in column_names
    
    if has_cosurf1 and has_cosurf2:
        print("✓ Co-surfactant volume columns already exist. No migration needed.")
        conn.close()
        return True
    
    # Add volume_CoSurfStock1 column if missing
    if not has_cosurf1:
        print("  Adding volume_CoSurfStock1 column...")
        cursor.execute("""
            ALTER TABLE measurements 
            ADD COLUMN volume_CoSurfStock1 REAL
        """)
        print("  ✓ Added volume_CoSurfStock1")
    
    # Add volume_CoSurfStock2 column if missing
    if not has_cosurf2:
        print("  Adding volume_CoSurfStock2 column...")
        cursor.execute("""
            ALTER TABLE measurements 
            ADD COLUMN volume_CoSurfStock2 REAL
        """)
        print("  ✓ Added volume_CoSurfStock2")
    
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
    return True


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
