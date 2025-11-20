#!/usr/bin/env python3
"""
Run database migration to add enhanced fields
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Read migration SQL
with open('migrations/001_add_enhanced_fields.sql', 'r') as f:
    migration_sql = f.read()

# Connect and run migration
print("Connecting to database...")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

print("Running migration...")
try:
    cursor.execute(migration_sql)
    conn.commit()
    print("✅ Migration completed successfully!")

    # Verify new columns exist
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'grants'
        AND column_name IN ('eu_identifier', 'call_title', 'duration', 'deadline_model', 'further_information', 'application_info')
        ORDER BY column_name;
    """)

    new_columns = [row[0] for row in cursor.fetchall()]
    print(f"\n✅ Verified new columns: {', '.join(new_columns)}")

except Exception as e:
    print(f"❌ Migration failed: {e}")
    conn.rollback()
finally:
    cursor.close()
    conn.close()

print("\n✅ Ready to run: python3 ingest_to_production.py")
