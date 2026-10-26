"""
Migration: Add new volume columns for new experiment format.

New experiments use different column naming:
- Buffer (instead of SW1)
- PolymerStock1, PolymerStock2 (instead of PS1, PS2)
- SurfStock1, SurfStock2 (instead of AS1, AS2)
- CoSurfStock1, CoSurfStock2 (new co-surfactant columns)
"""

import sqlite3
import sys


def migrate_database(db_path):
    """Add new volume columns to support new experiment format."""
    
    print(f"Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(measurements)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    print(f"Existing columns: {len(existing_columns)}")
    
    # New columns to add
    new_columns = [
        'volume_Buffer',
        'volume_PolymerStock1',
        'volume_PolymerStock2',
        'volume_SurfStock1',
        'volume_SurfStock2',
        'volume_CoSurfStock1',
        'volume_CoSurfStock2'
    ]
    
    # Add missing columns
    added = 0
    for col in new_columns:
        if col not in existing_columns:
            print(f"  Adding column: {col}")
            cursor.execute(f"ALTER TABLE measurements ADD COLUMN {col} REAL")
            added += 1
        else:
            print(f"  Column already exists: {col}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Migration complete: {added} columns added")
    return added


if __name__ == "__main__":
    # Check both possible database locations
    db_path = '/app/data/phase_diagrams.db'
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    elif not os.path.exists(db_path):
        db_path = 'phase_diagrams.db'
    
    import os
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    migrate_database(db_path)
