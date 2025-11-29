import os
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import psycopg2
from psycopg2.extras import RealDictCursor
from io import BytesIO

# =========================================
# 🔧 CONFIGURATION
# =========================================
SUPABASE_URL = "https://rkjebswwcflbxwotoocu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJramVic3d3Y2ZsYnh3b3Rvb2N1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI0NTIyMDAsImV4cCI6MjA3ODAyODIwMH0.RBEznkop9zn3mQUtDP4UssYLQ6cYZKjNV3GNXeP1tCI"
SUPABASE_BUCKET = "vehicle-images"

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Connection string for Postgres (through Supabase)
# POSTGRES_CONN = "postgresql://postgres:parking_system@db.rkjebswwcflbxwotoocu.supabase.co:5432/postgres"

POSTGRES_CONN = "postgresql://postgres.rkjebswwcflbxwotoocu:parking_system@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"


# =========================================
# 🧠 DATABASE UTILITIES
# =========================================

def get_connection():
    """Create a direct psycopg2 connection to Supabase Postgres."""
    return psycopg2.connect(POSTGRES_CONN, cursor_factory=RealDictCursor)


def safe_write_excel(df, file_path):
    import os
    import tempfile
    import shutil
    """
    Safely write Excel files atomically to avoid corruption during simultaneous writes.
    Writes to a temporary file and replaces the original after success.
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    try:
        df.to_excel(temp_file.name, index=False)
        temp_file.close()
        shutil.move(temp_file.name, file_path)
    except Exception as e:
        print(f"⚠️ Safe write failed for {file_path}: {e}")
    finally:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)


# =========================================================
# 🔹 PARKING DATA TABLE OPERATIONS
# =========================================================
def get_parking_registry():
    """Fetch entire parking registry as a DataFrame."""
    query = "SELECT * FROM parking_data"
    with get_connection() as conn:
        df = pd.read_sql(query, conn)
    return df


# def upsert_parking_record(flat_no, owner_name, vehicle_type, vehicle_no, slot, total_fines=0):
#     """Insert or update a parking record."""
#     query = """
#         INSERT INTO parking_data ("FlatNo", "OwnerName", "VehicleType", "VehicleNo", "ParkingSlot", "TotalFines")
#         VALUES (%s, %s, %s, %s, %s, %s)
#         ON CONFLICT ("VehicleNo")
#         DO UPDATE SET "FlatNo" = EXCLUDED."FlatNo",
#                       "OwnerName" = EXCLUDED."OwnerName",
#                       "ParkingSlot" = EXCLUDED."ParkingSlot",
#                       "VehicleType" = EXCLUDED."VehicleType",
#                       "TotalFines" = EXCLUDED."TotalFines";
#     """
#     with get_connection() as conn:
#         with conn.cursor() as cur:
#             cur.execute(query, (flat_no, owner_name, vehicle_type, vehicle_no, slot, total_fines))
#             conn.commit()


def upsert_parking_record(flat_no, owner_name, owner_contact, vehicle_type, vehicle_no, slot, total_fines=0):
    """
    Insert or update parking record safely (works even if no unique constraint exists in Supabase).
    """
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Check if the record already exists
        cur.execute('SELECT COUNT(*) FROM parking_data WHERE "VehicleNo" = %s;', (vehicle_no,))
        row = cur.fetchone()
        exists = row and (row.get('count') > 0 or list(row.values())[0] > 0)

        if exists:
            # ✅ Update existing record
            cur.execute('''
                UPDATE parking_data
                SET "FlatNo" = %s,
                    "OwnerName" = %s,
                    "OwnerContact" = %s,
                    "VehicleType" = %s,
                    "ParkingSlot" = %s,
                    "TotalFines" = %s
                WHERE "VehicleNo" = %s;
            ''', (flat_no, owner_name, owner_contact, vehicle_type, slot, total_fines, vehicle_no))
        else:
            # ✅ Insert new record
            cur.execute('''
                INSERT INTO parking_data 
                ("FlatNo", "OwnerName", "OwnerContact", "VehicleType", "VehicleNo", "ParkingSlot", "TotalFines")
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            ''', (flat_no, owner_name, owner_contact, vehicle_type, vehicle_no, slot, total_fines))

        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Parking record synced for {vehicle_no}")

    except Exception as e:
        import traceback
        print("⚠️ Error syncing parking record to Supabase:")
        traceback.print_exc()
        print("⚠️ Error syncing parking record to Supabase:", e)


# =========================================================
# 🔸 VIOLATIONS TABLE OPERATIONS
# =========================================================
# def log_violation(record: dict):
#     print("🟢 Logging violation record to Supabase:", record)
#     """Insert a new violation record into Supabase."""
#     # df = pd.DataFrame([record])
#     # with get_connection() as conn:
#     #     df.to_sql("violations", conn, if_exists="append", index=False)
#     try:
#         df = pd.DataFrame([record])
#         with get_connection() as conn:
#             df.to_sql("violations", conn, if_exists="append", index=False)
#         print("✅ Supabase insert success")
#     except Exception as e:
#         print("❌ Supabase insert error:", e)


from sqlalchemy import create_engine

# Create SQLAlchemy engine globally for performance
engine = create_engine(POSTGRES_CONN)

def log_violation(record):
    """
    Inserts a violation record into Supabase Postgres DB (safe).
    Falls back to Excel automatically if DB fails.
    """
    try:
        print("🟢 Logging violation record to Violation Table:", record)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO violations (
                "timestamp", "detected_number", "parked_slot", "allotted_slot",
                "fine", "image_path", "Status", "Owner", "FlatNo","OwnerContact"
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        ''', (
            record.get("timestamp"),
            record.get("detected_number"),
            record.get("parked_slot"),
            record.get("allotted_slot"),
            record.get("fine"),
            record.get("image_path"),
            record.get("Status"),
            record.get("Owner"),
            record.get("FlatNo"),
            record.get("OwnerContact")
        ))
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Supabase insert success")
        return True
    except Exception as e:
        print("❌ Supabase insert error:", e)
        try:
            import pandas as pd, os
            df = pd.DataFrame([record])
            if os.path.exists("violations.xlsx"):
                old = pd.read_excel("violations.xlsx")
                df = pd.concat([old, df], ignore_index=True)
            df.to_excel("violations.xlsx", index=False)
            print("✅ Excel fallback saved")
        except Exception as ex:
            print("⚠️ Excel fallback failed:", ex)
        return False


import pandas as pd

def fetch_violations_from_db():
    """Fetch all violations from Supabase database with fallback to Excel."""
    try:
        query = 'SELECT * FROM violations ORDER BY "timestamp" DESC;'
        df = pd.read_sql(query, engine)
        # df.columns = [c.lower() for c in df.columns]  # ✅ normalize names
        print(f"✅ Loaded {len(df)} violations from DB")
        return df
    except Exception as e:
        print("⚠️ DB read failed, falling back to Excel:", e)
        # if os.path.exists("violations.xlsx"):
        #     df = pd.read_excel("violations.xlsx", dtype=str)
        #     df.columns = [c.lower() for c in df.columns]
        #     return df
        return pd.DataFrame()



def fetch_parking_record(vehicle_no):
    """
    Fetch parking record by VehicleNo from Supabase Postgres.
    Returns a dict with keys matching the table columns or None if not found.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT "FlatNo", "OwnerName",  "OwnerContact","VehicleType", "VehicleNo", "ParkingSlot", "TotalFines"
            FROM parking_data
            WHERE "VehicleNo" = %s;
        ''', (vehicle_no,))
        row = cur.fetchone()
        print("row: ----------------> ", row)
        cur.close()
        conn.close()

        if row:
            # ✅ row is already a dict because of RealDictCursor
            return {
                "FlatNo": row.get("FlatNo", ""),
                "OwnerName": row.get("OwnerName", ""),
                "OwnerContact": row.get("OwnerContact", "") or row.get("Owner_Contact", "") or "",  # ✅ added
                "VehicleType": row.get("VehicleType", ""),
                "VehicleNo": row.get("VehicleNo", ""),
                "ParkingSlot": row.get("ParkingSlot", ""),
                "TotalFines": row.get("TotalFines", 0),
            }
        return None

    except Exception as e:
        print(f"⚠️ Error fetching parking record from Supabase: {e}")
        return None

def get_all_violations():
    """Fetch all violation records as a DataFrame."""
    query = "SELECT * FROM violations"
    with get_connection() as conn:
        df = pd.read_sql(query, conn)
    return df


# def update_violation_status(timestamp, detected_number, status):
#     """Update the status of a violation (Verified / Dismissed / CLAMPED)."""
#     query = """
#         UPDATE violations
#         SET "Status" = %s
#         WHERE "timestamp" = %s AND "detected_number" = %s
#     """
#     with get_connection() as conn:
#         with conn.cursor() as cur:
#             cur.execute(query, (status, timestamp, detected_number))
#             conn.commit()


# =========================================================
# 🖼️ IMAGE HANDLING - SUPABASE STORAGE + LOCAL BACKUP
# =========================================================
# def upload_images_to_supabase(files, save_local=True):
#     """
#     Upload images to Supabase storage and optionally also save locally.
#     Returns a list of public URLs (and local paths if save_local=True).
#     """
#     image_urls = []
#     local_paths = []
#     upload_folder = "static/uploads"
#     os.makedirs(upload_folder, exist_ok=True)
#
#     for i, file in enumerate(files[:4]):
#         if not file.filename:
#             continue
#
#         # Unique filename
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         filename = f"{timestamp}_{i+1}_{file.filename.replace(' ', '_')}"
#         file_bytes = file.read()
#         file.seek(0)
#
#         # ---- Supabase upload ----
#         try:
#             supabase.storage.from_(SUPABASE_BUCKET).upload(filename, BytesIO(file_bytes))
#             public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
#             image_urls.append(public_url)
#         except Exception as e:
#             print("⚠️ Error uploading to Supabase:", e)
#
#         # ---- Local backup ----
#         if save_local:
#             local_path = os.path.join(upload_folder, filename)
#             file.save(local_path)
#             local_paths.append(local_path)
#
#     # Combine local + public URLs for compatibility
#     combined_paths = local_paths + image_urls if save_local else image_urls
#     return combined_paths



# def upload_images_to_supabase(files, save_local=True):
#     """
#     Upload images to Supabase storage and optionally also save locally.
#     Returns a list of public URLs (and local paths if save_local=True).
#     """
#     image_urls = []
#     local_paths = []
#     upload_folder = "static/uploads"
#     os.makedirs(upload_folder, exist_ok=True)
#
#     for i, file in enumerate(files[:4]):
#         if not file.filename:
#             continue
#
#         # Unique filename
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         filename = f"{timestamp}_{i+1}_{file.filename.replace(' ', '_')}"
#
#         try:
#             # Read bytes once
#             file_bytes = file.read()
#             file.seek(0)
#
#             # ✅ FIX: Send raw bytes, not BytesIO object
#             supabase.storage.from_(SUPABASE_BUCKET).upload(
#                 path=filename,
#                 file=file_bytes,
#                 file_options={"content-type": "image/jpeg"}
#             )
#
#             public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
#             image_urls.append(public_url)
#
#         except Exception as e:
#             print("⚠️ Error uploading to Supabase:", e)
#
#         # ---- Local backup (same as before) ----
#         if save_local:
#             local_path = os.path.join(upload_folder, filename)
#             file.save(local_path)
#             local_paths.append(local_path)
#
#     # Combine local + public URLs for compatibility
#     # combined_paths = local_paths + image_urls if save_local else image_urls
#     combined_paths = image_urls
#     return combined_paths


def upload_images_to_supabase(files, save_local=False):
    """
    Upload images to Supabase storage and optionally also save locally.
    Returns only the public URLs (local save optional).
    """
    image_urls = []
    # upload_folder = "static/uploads"
    # os.makedirs(upload_folder, exist_ok=True)

    for i, file in enumerate(files[:4]):
        if not file.filename:
            continue

        # Unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{i+1}_{file.filename.replace(' ', '_')}"

        try:
            file_bytes = file.read()
            file.seek(0)

            # ✅ Upload image bytes directly
            supabase.storage.from_(SUPABASE_BUCKET).upload(
                path=filename,
                file=file_bytes,
                file_options={"content-type": file.mimetype or "image/jpeg"}
            )

            # ✅ Get the public URL
            public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
            image_urls.append(public_url)

        except Exception as e:
            print("⚠️ Error uploading to Supabase:", e)

        # ✅ Local backup (kept separate so you can comment out easily later)
        # if save_local:
        #     local_path = os.path.join(upload_folder, filename)
        #     file.save(local_path)

    # ✅ Return only Supabase URLs (avoids duplicate image display)
    return image_urls


# =========================================================
# 🔍 UTILITY HELPERS
# =========================================================
def to_dict(df):
    """Safe DataFrame → list of dicts."""
    if df is None or df.empty:
        return []
    return df.to_dict(orient="records")


def update_violation_details(timestamp, old_vehicle_no, new_vehicle_no, flat_no, owner, slot, fine, status):
    """
    Update existing violation in both Supabase and Excel when an unknown vehicle is later assigned an owner.
    Keeps both sources in sync safely.
    """
    import pandas as pd
    import os
    from datetime import datetime

    try:
        # 1️⃣ Update Supabase
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE violations
            SET "detected_number" = %s,
                "FlatNo" = %s,
                "Owner" = %s,
                "allotted_slot" = %s,
                "fine" = %s,
                "Status" = %s
            WHERE "timestamp" = %s AND "detected_number" = %s;
        ''', (new_vehicle_no, flat_no, owner, slot, fine, status, timestamp, old_vehicle_no))
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Updated existing violation {old_vehicle_no} → {new_vehicle_no} in Supabase")

        # 2️⃣ Also Update Excel Fallback
        # VIOLATION_FILE = "violations.xlsx"
        # if os.path.exists(VIOLATION_FILE):
        #     vdf = pd.read_excel(VIOLATION_FILE, dtype=str)
        #     vdf['timestamp'] = pd.to_datetime(vdf['timestamp'], errors='coerce')
        #
        #     mask = (vdf['timestamp'] == pd.to_datetime(timestamp)) & (vdf['detected_number'] == old_vehicle_no)
        #     if mask.any():
        #         vdf.loc[mask, 'detected_number'] = new_vehicle_no
        #         vdf.loc[mask, 'FlatNo'] = flat_no
        #         vdf.loc[mask, 'Owner'] = owner
        #         vdf.loc[mask, 'allotted_slot'] = slot
        #         vdf.loc[mask, 'fine'] = str(fine)
        #         vdf.loc[mask, 'Status'] = status
        #         from app import safe_write_excel
        #         safe_write_excel(vdf, VIOLATION_FILE)
        #         print("✅ Excel violation file updated successfully")
        #     else:
        #         print("⚠️ No matching Excel row found for update")
        # else:
        #     print("⚠️ Excel file missing, skipping Excel update")

    except Exception as e:
        print(f"⚠️ Error updating violation details: {e}")





# ===============================
# 🧍 WATCHMAN MANAGEMENT HELPERS
# ===============================

# ✅ What this enables
# Watchmen can register and login with a 3-digit PIN.
# Their actions update both Excel and Supabase, adding VerifiedBy and VerifiedAt automatically.

def register_watchman(name, pin, phone=None):
    """Register a new watchman with name and 3-digit PIN."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO watchman ("name", "pin", "phone","created_at", "is_active") VALUES (%s, %s,%s, NOW(), TRUE) RETURNING id;',
            (name, pin, phone)
        )
        # print(cur.fetchone())
        # watchman_id = cur.fetchone()[0]
        result = cur.fetchone()
        watchman_id = result['id'] if result else None

        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Watchman '{name}' registered successfully (ID {watchman_id})")
        return watchman_id
    except Exception as e:
        import traceback
        print("⚠️ Error registering watchman:", e)
        traceback.print_exc()
        print("⚠️ Error registering watchman:", e)
        return None


def authenticate_watchman(pin):
    """Validate watchman PIN and return their record (id, name)."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, name FROM watchman WHERE pin = %s AND is_active = TRUE;', (pin,))
        row = cur.fetchone()
        print("row : ", row)
        # watchman_id = row['id'] if row else None
        cur.close()
        conn.close()
        if row:
            return {"id": row['id'], "name": row['name']}
        return None
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("⚠️ Error authenticating watchman:", e)
        return None


# def update_violation_status_by_rowid(row_id, action, watchman_name):
#     """
#     Update violation record (in Excel + Supabase) when watchman takes action.
#     Actions: 'Verified', 'Dismissed', 'CLAMPED'
#     """
#     try:
#         import pandas as pd
#         from datetime import datetime
#
#         # Load Excel safely
#         viol_path = 'violations.xlsx'
#         if not os.path.exists(viol_path):
#             print("⚠️ Violations file not found.")
#             return False
#         df = pd.read_excel(viol_path, dtype=str)
#
#         if row_id >= len(df):
#             print("⚠️ Invalid row_id.")
#             return False
#
#         # Update local Excel record
#         df.at[row_id, 'Status'] = action
#         df.at[row_id, 'VerifiedBy'] = watchman_name
#         df.at[row_id, 'VerifiedAt'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#
#         safe_write_excel(df, viol_path)
#
#         # Update Supabase record
#         conn = get_connection()
#         cur = conn.cursor()
#         cur.execute(f'''
#             UPDATE violations
#             SET "Status" = %s,
#                 "VerifiedBy" = %s,
#                 "VerifiedAt" = NOW()
#             WHERE "timestamp" = %s
#               AND "detected_number" = %s;
#         ''', (
#             action,
#             watchman_name,
#             str(df.at[row_id, 'timestamp']),
#             str(df.at[row_id, 'detected_number'])
#         ))
#         conn.commit()
#         cur.close()
#         conn.close()
#         print(f"✅ Violation updated by {watchman_name}: {action}")
#         return True
#     except Exception as e:
#         print("⚠️ Error updating violation:", e)
#         return False



def update_violation_status(timestamp, detected_number, status, verified_by=None):
    """
    Updates the violation status in Supabase (Postgres).
    Falls back to Excel if DB update fails.
    """
    try:
        VIOLATION_FILE = 'violations.xlsx'
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE violations
            SET "Status" = %s,
                "VerifiedBy" = %s,
                "VerifiedAt" = NOW()
            WHERE DATE("timestamp") = DATE(%s)
              AND "detected_number" = %s;
        ''', (status, verified_by or 'Admin', timestamp, detected_number))
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Updated {detected_number} to {status} in Supabase.")
        return True
    except Exception as e:
        print("⚠️ Supabase update failed, trying Excel fallback:", e)
        # try:
        #     df = pd.read_excel(VIOLATION_FILE, dtype=str)
        #     mask = (df['detected_number'] == detected_number) & (df['timestamp'] == str(timestamp))
        #     df.loc[mask, 'Status'] = status
        #     df.to_excel(VIOLATION_FILE, index=False)
        #     print("✅ Excel fallback update successful.")
        # except Exception as ex:
        #     print("⚠️ Excel fallback update failed:", ex)
        return False



def log_watchman_action(violation_id=None, watchman_id=None, watchman_name=None, action=None, notes=None):
    """
    Record a watchman observation.
    Tries DB insert into watchman_actions, falls back to local Excel file "watchman_actions.xlsx".
    Returns True on success, False on failure.
    """
    try:
        # Prefer DB connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO watchman_actions (violation_id, watchman_id, watchman_name, action, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, (now() AT TIME ZONE 'Asia/Kolkata'));
        ''', (violation_id, watchman_id, watchman_name, action, notes))
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Watchman action logged (DB): {watchman_name} — {action} (violation_id={violation_id})")
        return True
    except Exception as e:
        print("⚠️ DB insert for watchman action failed :", e)
        # try:
        #     import pandas as pd, os
        #     row = {
        #         "violation_id": violation_id,
        #         "watchman_id": watchman_id,
        #         "watchman_name": watchman_name,
        #         "action": action,
        #         "notes": notes or "",
        #         "created_at": pd.Timestamp.now()
        #     }
        #     fname = "watchman_actions.xlsx"
        #     if os.path.exists(fname):
        #         old = pd.read_excel(fname, dtype=str)
        #         new = pd.DataFrame([row])
        #         out = pd.concat([old, new], ignore_index=True)
        #     else:
        #         out = pd.DataFrame([row])
        #     out.to_excel(fname, index=False)
        #     print("✅ Watchman action saved to watchman_actions.xlsx")
        #     return True
        # except Exception as ex:
        #     print("❌ Failed to save watchman action locally:", ex)
        return False

from sqlalchemy import text
def fetch_watchman_actions(watchman_name):
    """
    Returns watchman actions (DB-first, Excel fallback).
    Ensures compatibility with psycopg2 connection.
    """
    import pandas as pd
    import os

    try:
        conn = get_connection()

        df = pd.read_sql(
            """
            SELECT id,
                   violation_id,
                   watchman_id,
                   watchman_name,
                   action,
                   notes,
                   created_at
            FROM watchman_actions
            WHERE watchman_name = %(name)s
            ORDER BY created_at DESC
            """,
            conn,
            params={"name": watchman_name}
        )
        conn.close()
        return df

    except Exception as e:
        print("⚠️ DB fetch failed for watchman_actions:", e)
        return pd.DataFrame()

        # Excel fallback
        # try:
        #     if os.path.exists("watchman_actions.xlsx"):
        #         df = pd.read_excel("watchman_actions.xlsx")
        #         return df[df["watchman_name"] == watchman_name]
        #     return pd.DataFrame()
        # except:
        #     return pd.DataFrame()




def fetch_all_watchman_actions():
    """
    Returns all watchman observations from watchman_actions table.
    Always uses SQLAlchemy engine for reads.
    """
    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                text("""
                    SELECT 
                        wa.id AS action_id,
                        wa.watchman_name,
                        wa.action,
                        wa.notes,
                        wa.created_at,
        
                        v.id AS violation_id,
                        v.detected_number,
                        v.parked_slot,
                        v.allotted_slot,
                        v."Status",
                        v.fine,
                        v.timestamp,
                        v.image_path 
        
                    FROM watchman_actions wa
                    LEFT JOIN violations v
                        ON wa.violation_id = v.id
                    ORDER BY wa.created_at DESC
                """),
                conn
            )
        print("🔥 DB FETCH SUCCESS — ROWS:", len(df))
        return df

    except Exception as e:
        print("❌ DB FETCH FAILED — USING EXCEL FALLBACK:", e)

        # Excel fallback
        # try:
        #     if os.path.exists("watchman_actions.xlsx"):
        #         df = pd.read_excel("watchman_actions.xlsx")
        #
        #         # Remove bogus header rows
        #         df = df[df["id"].astype(str) != "id"]
        #
        #         return df
        # except:
        #     pass

        return pd.DataFrame()


# helper: force timestamp column to IST and formatted string
def force_df_timestamps_to_ist(df, col='timestamp', fmt='%d-%b-%Y %H:%M'):
    import pandas as pd
    if col not in df.columns:
        return df
    # Parse, interpret as UTC if naive/unknown, then convert to Asia/Kolkata
    df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)  # parse as UTC
    df[col] = df[col].dt.tz_convert('Asia/Kolkata')
    # optional: drop tz info for easier template use (still keep tz-aware object if you prefer)
    df[col] = df[col].dt.tz_localize(None)
    df[col] = df[col].dt.floor('min')
    df[f'{col}_fmt'] = df[col].dt.strftime(fmt)
    return df




# -------------------- Watchman Daily Entry helpers (ADD-ON) --------------------
def find_vehicle_by_last4(last4):
    """
    Returns a dict with vehicle details if found in parking_data table by last 4 digits.
    Returns None if not found.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Using ILIKE to be case-insensitive
        cur.execute("""
            SELECT *
            FROM parking_data
            WHERE RIGHT("VehicleNo", 4) ILIKE %s
            LIMIT 1;
        """, (last4,))
        row = cur.fetchone()
        conn.close()
        return row if row else None
    except Exception as e:
        print("⚠️ find_vehicle_by_last4 failed:", e)
        return None

# def log_watchman_entry(
#     watchman_id=None,
#     watchman_name=None,
#     entry_type=None,
#     last4=None,
#     full_plate=None,
#     vehicle_category=None,
#     purpose_category=None,
#     purpose_subtype=None,
#     flat_no=None,
#     description=None
# ):
#     """
#     Insert a row into watchman_entries table.
#     Creates the table if it doesn't already exist.
#     Returns True on success, False on failure.
#     """
#     try:
#         conn = get_connection()
#         cur = conn.cursor()
#         # Ensure table exists (id SERIAL PRIMARY KEY)
#         cur.execute("""
#             CREATE TABLE IF NOT EXISTS watchman_entries (
#                 id SERIAL PRIMARY KEY,
#                 watchman_id TEXT,
#                 watchman_name TEXT,
#                 entry_type TEXT,
#                 last4 TEXT,
#                 full_plate TEXT,
#                 vehicle_category TEXT,
#                 purpose_category TEXT,
#                 purpose_subtype TEXT,
#                 flat_no TEXT,
#                 description TEXT,
#                 created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'Asia/Kolkata')
#             );
#         """)
#         # Insert record
#         cur.execute("""
#             INSERT INTO watchman_entries
#             (watchman_id, watchman_name, entry_type, last4, full_plate, vehicle_category,
#              purpose_category, purpose_subtype, flat_no, description, created_at)
#             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, (now() AT TIME ZONE 'Asia/Kolkata'));
#         """, (
#             watchman_id,
#             watchman_name,
#             entry_type,
#             last4,
#             full_plate,
#             vehicle_category,
#             purpose_category,
#             purpose_subtype,
#             flat_no,
#             description
#         ))
#         conn.commit()
#         conn.close()
#         return True
#     except Exception as e:
#         print("⚠️ log_watchman_entry failed:", e)
#         # Optional: add fallback to Excel for local env (not added here to keep parity with rest of db_utils)
#         return False



def log_watchman_entry(
    watchman_id=None,
    watchman_name=None,
    entry_type=None,
    last4=None,
    full_plate=None,
    vehicle_category=None,
    purpose_category=None,
    purpose_subtype=None,
    flat_no=None,
    description=None,
    owner_contact=None,
    image_urls=None
):
    """
    Insert a row into watchman_entries table.
    Creates the table if it doesn't already exist.
    Stores optional owner_contact and image_urls (comma separated).
    Returns True on success, False on failure.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Ensure table exists (id SERIAL PRIMARY KEY)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS watchman_entries (
                id SERIAL PRIMARY KEY,
                watchman_id TEXT,
                watchman_name TEXT,
                entry_type TEXT,
                last4 TEXT,
                full_plate TEXT,
                vehicle_category TEXT,
                purpose_category TEXT,
                purpose_subtype TEXT,
                flat_no TEXT,
                description TEXT,
                owner_contact TEXT,
                image_urls TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'Asia/Kolkata')
            );
        """)
        # convert image_urls list -> comma separated string if necessary
        imgs = None
        if image_urls:
            if isinstance(image_urls, (list, tuple)):
                imgs = ",".join(image_urls)
            else:
                imgs = str(image_urls)

        # Insert record
        cur.execute("""
            INSERT INTO watchman_entries
            (watchman_id, watchman_name, entry_type, last4, full_plate, vehicle_category,
             purpose_category, purpose_subtype, flat_no, description, owner_contact, image_urls, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, (now() AT TIME ZONE 'Asia/Kolkata'));
        """, (
            watchman_id,
            watchman_name,
            entry_type,
            last4,
            full_plate,
            vehicle_category,
            purpose_category,
            purpose_subtype,
            flat_no,
            description,
            owner_contact,
            imgs
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("⚠️ log_watchman_entry failed:", e)
        return False






# --- Replace the existing upload_images_to_supabase implementation with this ---
def daily_entry_upload_images_to_supabase(files, bucket='daily_entry_images', save_local=False):
    """
    Upload images to Supabase storage and optionally also save locally.
    Returns only the public URLs (local save optional).

    Args:
      files: list of FileStorage objects (Flask request.files.getlist('image'))
      bucket: optional bucket name string. If None, uses SUPABASE_BUCKET constant.
      save_local: whether to also save a local backup copy in static/uploads
    """
    image_urls = []
    # upload_folder = "static/uploads"
    # os.makedirs(upload_folder, exist_ok=True)

    # choose bucket (default to configured)
    target_bucket = bucket

    for i, file in enumerate(files[:4]):  # limit to 4 files even if provided (keeps existing logic)
        if not file or not getattr(file, "filename", ""):
            continue

        # Unique filename to avoid collisions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = file.filename.replace(' ', '_')
        filename = f"{timestamp}_{i+1}_{safe_name}"
        from io import BytesIO
        try:
            file_bytes = file.read()
            # reset pointer for local save
            file.seek(0)

            # Upload to chosen Supabase bucket
            supabase.storage.from_(target_bucket).upload(
                path=filename,
                file=file_bytes,
                file_options={"content-type": file.mimetype or "image/jpeg"}
            )

            # Get public url
            public_url = supabase.storage.from_(target_bucket).get_public_url(filename)
            image_urls.append(public_url)

        except Exception as e:
            print("⚠️ Error uploading to Supabase:", e)

        # Local backup
        # if save_local:
        #     local_path = os.path.join(upload_folder, filename)
        #     try:
        #         file.save(local_path)
        #     except Exception as ex:
        #         print("⚠️ Failed to save local copy:", ex)

    return image_urls
