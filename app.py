from flask import Flask, render_template, request, redirect, url_for, flash, session

from threading import Lock

from db_utils import *
app = Flask(__name__)
app.secret_key = "tenx_secure_key"

DATA_FILE = 'parking_data.xlsx'
VIOLATION_FILE = 'violations.xlsx'

excel_lock = Lock()  # Prevent Excel write conflicts

# ---------------------- SAFE EXCEL WRITE ---------------------- #
import tempfile
import shutil

def safe_write_excel(df, path):
    """Safely write DataFrame to Excel with timezone and file lock handling."""
    try:
        # Remove timezone info (Excel can't store tz-aware timestamps)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce').dt.tz_localize(None)

        # Convert all numpy / non-string columns safely
        df = df.copy()
        for c in df.columns:
            if df[c].dtype == 'object':
                continue
            df[c] = df[c].astype(str)

        # Use temp file + atomic rename to avoid WinError 32
        tmp_path = tempfile.mktemp(suffix=".xlsx")
        df.to_excel(tmp_path, index=False)
        shutil.move(tmp_path, path)

        print(f"✅ Safe write success: {path}")
        return True
    except Exception as e:
        print(f"⚠️ Safe write failed for {path}: {e}")
        return False


# ---------------------- HOME ---------------------- #
@app.route('/')
@app.route('/home')
def index():
    return render_template('index.html')



# ---------------------- ADMIN LOGIN ---------------------- #
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username in ["tenxhabitat_societyadmin", "tenxhabitat_securityadmin"] and password == "tenx_parking_secure":
            session['admin_logged_in'] = True
            session['admin_user'] = username
            flash('Login successful', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('admin_login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))


# ---------------------- HOME ---------------------- #
# @app.route('/')
# @app.route('/home')
# def index():
#     return render_template('index.html')




############# CURRENTLY USED UPLOAD FUNC ##################
# @app.route('/upload', methods=['POST'])
# def upload():
#     try:
#         parking_slot = request.form.get('parking_slot', '').strip().upper()
#         entered_digits = request.form.get('last4', '').strip()
#
#         uploaded_files = request.files.getlist('image')
#         image_paths = []
#
#         # ✅ Upload to Supabase (also local copy)
#         if uploaded_files:
#             image_paths = upload_images_to_supabase(uploaded_files, save_local=True)
#
#         image_path = ','.join(image_paths) if image_paths else None
#
#         if not parking_slot:
#             return render_template('index.html', message="⚠️ Please provide your parking slot.")
#         if not entered_digits and not image_paths:
#             return render_template('index.html', message="⚠️ Please provide either last 4 digits or upload at least one image.")
#
#         if not os.path.exists(DATA_FILE):
#             return render_template('index.html', message="🚨 Registry file missing. Please contact admin.")
#
#         reg = pd.read_excel(DATA_FILE, dtype=str)
#         reg['Last4'] = reg['VehicleNo'].astype(str).str[-4:]
#
#         match = reg[reg['Last4'].str.upper() == entered_digits.upper()] if entered_digits else pd.DataFrame()
#
#         # --- Unregistered Vehicle ---
#         if match.empty:
#             record = {
#                 'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                 'detected_number': f'Unknown-{entered_digits}',
#                 'parked_slot': parking_slot,
#                 'allotted_slot': 'N/A',
#                 'fine': 1000,
#                 'image_path': image_path,
#                 'Status': 'Pending',
#                 'Owner': 'UNKNOWN',
#                 'FlatNo': 'UNKNOWN'
#             }
#
#             with excel_lock:
#                 if os.path.exists(VIOLATION_FILE):
#                     existing = pd.read_excel(VIOLATION_FILE)
#                     updated = pd.concat([existing, pd.DataFrame([record])], ignore_index=True)
#                 else:
#                     updated = pd.DataFrame([record])
#                 updated.to_excel(VIOLATION_FILE, index=False)
#
#             log_violation(record)
#
#             result = {
#                 'status': 'Pending',
#                 'fine': 1000,
#                 'image_path': image_path,
#                 'vehicle_no': f'Unknown-{entered_digits}',
#                 'owner': 'UNKNOWN',
#                 'flat': 'UNKNOWN',
#                 'allotted_slot': 'N/A',
#                 'parked_slot': parking_slot,
#                 'timestamp': record['timestamp']
#             }
#             return render_template('index.html', message="🚨 Vehicle Not Registered — Logged for Admin Verification.", result=result)
#
#         # --- Registered Vehicle ---
#         vehicle_info = match.iloc[0]
#         print("vehicle_info : ------>\n", vehicle_info)
#         vehicle_no = vehicle_info['VehicleNo']
#         owner = vehicle_info['OwnerName']
#         flat = vehicle_info['FlatNo']
#         allotted_slot = str(vehicle_info['ParkingSlot']).strip().upper()
#         vehicle_type = str(vehicle_info['VehicleType']).lower()
#         OwnerContact = vehicle_info['OwnerContact']
#
#         if allotted_slot != parking_slot:
#             fine = 100 if 'bike' in vehicle_type else 500
#             past_count = 0
#             if os.path.exists(VIOLATION_FILE):
#                 past = pd.read_excel(VIOLATION_FILE, dtype=str)
#                 past_count = len(past[past['detected_number'] == vehicle_no])
#                 if past_count > 3:
#                     fine = 5000
#             message = f"❌ VIOLATION DETECTED!\n\n{vehicle_no} ({owner}, Flat {flat}) parked in {parking_slot} instead of {allotted_slot}. Fine ₹{fine}."
#             status = "Pending"
#         else:
#             message = f"✅ No violation — Vehicle {vehicle_no} is correctly parked in {parking_slot}."
#             fine = 0
#             status = "OK"
#
#         record = {
#             'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#             'detected_number': vehicle_no,
#             'parked_slot': parking_slot,
#             'allotted_slot': allotted_slot,
#             'fine': fine,
#             'image_path': image_path,
#             'Status': status,
#             'Owner': owner,
#             'FlatNo': flat,
#             'OwnerContact':OwnerContact
#         }
#
#         with excel_lock:
#             if os.path.exists(VIOLATION_FILE):
#                 existing = pd.read_excel(VIOLATION_FILE)
#                 updated = pd.concat([existing, pd.DataFrame([record])], ignore_index=True)
#             else:
#                 updated = pd.DataFrame([record])
#             updated.to_excel(VIOLATION_FILE, index=False)
#
#         log_violation(record)
#
#         result = {
#             'status': status,
#             'fine': fine,
#             'image_path': image_path,
#             'vehicle_no': vehicle_no,
#             'owner': owner,
#             'flat': flat,
#             'allotted_slot': allotted_slot,
#             'parked_slot': parking_slot,
#             'timestamp': record['timestamp'],
#             'OwnerContact': OwnerContact
#         }
#         print(">>> Upload result sent:", result)
#         return render_template('index.html', message=message, result=result)
#
#     except Exception as e:
#         return render_template('index.html', message=f"⚠️ Error: {e}")




@app.route('/upload', methods=['POST'])
def upload():
    from zoneinfo import ZoneInfo
    try:
        parking_slot = request.form.get('parking_slot', '').strip().upper()
        entered_digits = request.form.get('last4', '').strip()

        uploaded_files = request.files.getlist('image')
        image_paths = []

        # ✅ Upload to Supabase (also local copy)
        if uploaded_files:
            image_paths = upload_images_to_supabase(uploaded_files, save_local=True)

        image_path = ','.join(image_paths) if image_paths else None

        # --- Validation ---
        if not parking_slot:
            return render_template('index.html', message="⚠️ Please provide your parking slot.")
        if not entered_digits and not image_paths:
            return render_template('index.html', message="⚠️ Please provide either last 4 digits or upload at least one image.")

        # ===================================================================
        # 🔥 NEW: DB-FIRST PARKING REGISTRY LOOKUP (parking_data table)
        # ===================================================================
        reg_df = None
        try:
            with engine.connect() as conn:
                q = text("""
                    SELECT "FlatNo", "OwnerName", "VehicleType", "VehicleNo",
                           "ParkingSlot", "TotalFines", "OwnerContact"
                    FROM parking_data
                    WHERE RIGHT("VehicleNo", 4) = :last4
                """)
                df_db = pd.read_sql(q, conn, params={"last4": entered_digits})
                if not df_db.empty:
                    reg_df = df_db
        except Exception as e:
            print("⚠️ DB registry lookup failed → will fall back to Excel:", e)

        # ===================================================================
        # 🟡 Excel fallback (NO CHANGE TO YOUR EXISTING LOGIC)
        # ===================================================================
        # if reg_df is None:
        #     if not os.path.exists(DATA_FILE):
        #         return render_template('index.html', message="🚨 Registry file missing. Please contact admin.")
        #
        #     xdf = pd.read_excel(DATA_FILE, dtype=str)
        #     xdf['Last4'] = xdf['VehicleNo'].astype(str).str[-4:]
        #     reg_df = xdf[xdf['Last4'].str.upper() == entered_digits.upper()]

        match = reg_df
        # ===================================================================

        # --- Unregistered Vehicle ---
        if match is None or match.empty:
            record = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'detected_number': f'Unknown-{entered_digits}',
                'parked_slot': parking_slot,
                'allotted_slot': 'N/A',
                'fine': 1000,
                'image_path': image_path,
                'Status': 'Pending',
                'Owner': 'UNKNOWN',
                'FlatNo': 'UNKNOWN',
                'OwnerContact': ''
            }

            # with excel_lock:
            #     if os.path.exists(VIOLATION_FILE):
            #         existing = pd.read_excel(VIOLATION_FILE)
            #         updated = pd.concat([existing, pd.DataFrame([record])], ignore_index=True)
            #     else:
            #         updated = pd.DataFrame([record])
            #     updated.to_excel(VIOLATION_FILE, index=False)

            # Log in Supabase DB also
            log_violation(record)

            result = {
                'status': 'Pending',
                'fine': 1000,
                'image_path': image_path,
                'vehicle_no': f'Unknown-{entered_digits}',
                'owner': 'UNKNOWN',
                'flat': 'UNKNOWN',
                'allotted_slot': 'N/A',
                'parked_slot': parking_slot,
                # 'timestamp': record['timestamp']
                'timestamp' : datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
            }
            return render_template('index.html', message="🚨 Vehicle Not Registered — Logged for Admin Verification.", result=result)

        # --- Registered Vehicle ---
        vehicle_info = match.iloc[0]
        print("vehicle_info : ------>\n", vehicle_info)

        vehicle_no = vehicle_info['VehicleNo']
        owner = vehicle_info['OwnerName']
        flat = vehicle_info['FlatNo']
        allotted_slot = str(vehicle_info['ParkingSlot']).strip().upper()
        vehicle_type = str(vehicle_info['VehicleType']).lower()
        OwnerContact = vehicle_info.get('OwnerContact', '')

        # --- Fine Calculation (UNCHANGED) ---
        if allotted_slot != parking_slot:
            fine = 100 if 'bike' in vehicle_type else 500
            past_count = 0
            try:
                with engine.connect() as conn:
                    q = text("""
                                    SELECT COUNT(*) AS cnt FROM violations WHERE detected_number = :vehicle_no
                                """)
                    past_cnt_df = pd.read_sql(q, conn, params={"vehicle_no": vehicle_no})
                    past_count = int(past_cnt_df.at[0, 'cnt']) if not past_cnt_df.empty else 0
                    if past_count > 3:
                        fine = 5000
            except Exception as e:
                print("⚠️ Past violation count lookup failed:", e)
            message = f"❌ VIOLATION DETECTED!\n\n{vehicle_no} ({owner}, Flat {flat}) parked in {parking_slot} instead of {allotted_slot}. Fine ₹{fine}."
            status = "Pending"
        else:
            message = f"✅ No violation — Vehicle {vehicle_no} is correctly parked in {parking_slot}."
            fine = 0
            status = "OK"

        record = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'detected_number': vehicle_no,
            'parked_slot': parking_slot,
            'allotted_slot': allotted_slot,
            'fine': fine,
            'image_path': image_path,
            'Status': status,
            'Owner': owner,
            'FlatNo': flat,
            'OwnerContact': OwnerContact
        }

        # # --- Excel Write (UNCHANGED) ---
        # with excel_lock:
        #     if os.path.exists(VIOLATION_FILE):
        #         existing = pd.read_excel(VIOLATION_FILE)
        #         updated = pd.concat([existing, pd.DataFrame([record])], ignore_index=True)
        #     else:
        #         updated = pd.DataFrame([record])
        #     updated.to_excel(VIOLATION_FILE, index=False)

        # --- Log to Supabase Violations Table (UNCHANGED) ---
        # log_violation(record)
        try:
            log_violation(record)
        except Exception as e:
            print("⚠️ Failed to log violation to Violation Table in DB (registered):", e)
            return render_template('index.html', message="⚠️ Failed to record violation. Please contact admin.")

        result = {
            'status': status,
            'fine': fine,
            'image_path': image_path,
            'vehicle_no': vehicle_no,
            'owner': owner,
            'flat': flat,
            'allotted_slot': allotted_slot,
            'parked_slot': parking_slot,
            # 'timestamp': record['timestamp'],
            'timestamp': datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S"),
            'OwnerContact': OwnerContact
        }
        print(">>> Upload result sent (db time is utc but display is IST):", record)

        return render_template('index.html', message=message, result=result)

    except Exception as e:
        return render_template('index.html', message=f"⚠️ Error: {e}")


# ---------------------- ADMIN LOGIN ---------------------- #
# @app.route('/admin_login', methods=['GET', 'POST'])
# def admin_login():
#     if request.method == 'POST':
#         username = request.form.get('username', '').strip()
#         password = request.form.get('password', '').strip()
#
#         if username in ["tenxhabitat_societyadmin", "tenxhabitat_securityadmin"] and password == "tenx_parking_secure":
#             session['admin_logged_in'] = True
#             session['admin_user'] = username
#             flash('Login successful', 'success')
#             return redirect(url_for('admin_dashboard'))
#         else:
#             flash('Invalid credentials', 'danger')
#     return render_template('admin_login.html')


# @app.route('/logout')
# def logout():
#     session.clear()
#     flash('Logged out successfully', 'info')
#     return redirect(url_for('index'))

# ---------------------- ADMIN DASHBOARD (DB-FIRST) ---------------------- #
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_user' not in session:
        flash('Please log in to access admin dashboard.', 'danger')
        return redirect(url_for('admin_login'))

    try:
        # Try fetching directly from Supabase (Postgres)
        with engine.connect() as conn:
            df = pd.read_sql(
                text("""
                    SELECT
                        "id",                       -- ✅ primary key included
                        "timestamp",
                        "detected_number",
                        "parked_slot",
                        "allotted_slot",
                        "fine",
                        "image_path",
                        "Status",
                        "Owner",
                        "FlatNo",
                        COALESCE("VerifiedBy", '') AS "VerifiedBy",
                        COALESCE("VerifiedAt", NULL::timestamptz) AS "VerifiedAt",
                        COALESCE("OwnerContact", 'N/A') AS "OwnerContact"
                    FROM violations
                    ORDER BY "timestamp" DESC;
                """),
                conn
            )
        print(f"✅ Loaded {len(df)} violations from Supabase DB")
        print("COLUMNS →", df.columns.tolist())
        print(df.head(5).to_dict(orient='records'))


    except Exception as e:
        print(f"⚠️ Supabase fetch failed, falling back to Excel: {e}")
        # Fallback: Excel load
        # with excel_lock:
        #     df = pd.read_excel(VIOLATION_FILE, dtype=str) if os.path.exists(VIOLATION_FILE) else pd.DataFrame()

    try:
        # Normalize / Clean DataFrame
        if df.empty:
            pending_df = actioned_df = clamped_df = pd.DataFrame()
        else:
            df['image_path'] = df['image_path'].fillna("")
            df['image_paths'] = df['image_path'].apply(lambda x: [p.strip() for p in str(x).split(',') if p.strip()])
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            # Convert timestamps to IST for display
            df = force_df_timestamps_to_ist(df, col="timestamp", fmt="%d-%b-%Y %H:%M")
            df = df.sort_values(by='timestamp', ascending=False).reset_index(drop=True)
            # df['record_id'] = df.index

            # Split by Status
            pending_df = df[~df['Status'].isin(['Verified', 'Dismissed', 'CLAMPED','UNKNOWN'])]
            # ---------------------------
            # NEW: Attach Watchman Observations
            # ---------------------------
            try:
                with engine.connect() as conn:
                    obs_df = pd.read_sql(text("""
                        SELECT wa.violation_id,
                               wa.watchman_name,
                               wa.action,
                               wa.created_at
                        FROM watchman_actions wa
                        ORDER BY wa.created_at DESC
                    """), conn)
            except:
                obs_df = pd.DataFrame()

            # Map last observation per violation
            obs_map = (
                obs_df.sort_values("created_at")
                    .groupby("violation_id")
                    .tail(1)
                    .reset_index(drop=True)
            )

            obs_map['watchman_observation'] = obs_map.apply(
                lambda r: f"{r['action']} by {r['watchman_name']} at {r['created_at']}",
                axis=1
            )

            pending_df = pending_df.merge(
                obs_map[['violation_id', 'watchman_observation']],
                left_on='id',
                right_on='violation_id',
                how='left'
            )

            actioned_df = df[df['Status'].isin(['Verified', 'Dismissed','CLAMPED'])]
            clamped_df = df[df['Status'].eq('UNKNOWN')]

    except Exception as e:
        flash(f"⚠️ Error processing dashboard data: {e}", "danger")
        pending_df = actioned_df = clamped_df = pd.DataFrame()

    # Render as before
    return render_template(
        'admin.html',
        pending_records=pending_df.to_dict(orient='records'),
        actioned_records=actioned_df.to_dict(orient='records'),
        clamped_records=clamped_df.to_dict(orient='records'),
        active_tab='pending'
    )


# ---------------------- VERIFY / DISMISS ---------------------- #
# ---------------------- VERIFY / DISMISS ---------------------- #
@app.route('/verify/<int:id>', methods=['POST'])
def verify(id):
    """Mark a violation as Verified using the DB primary key `id`."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin_login'))

    try:
        admin = session.get("admin_user", "Admin")

        # 🔥 Update directly using ID from DB
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE violations
                SET "Status" = 'Verified',
                    "VerifiedBy" = :admin,
                    "VerifiedAt" = (now() AT TIME ZONE 'Asia/Kolkata')
                WHERE id = :id;
            """), {"admin": admin, "id": id})

        # Excel fallback
        # try:
        #     if os.path.exists(VIOLATION_FILE):
        #         xdf = pd.read_excel(VIOLATION_FILE)
        #         if "id" in xdf.columns:
        #             xdf.loc[xdf["id"] == id, "Status"] = "Verified"
        #         safe_write_excel(xdf, VIOLATION_FILE)
        # except Exception as e:
        #     print("⚠️ Excel fallback verify failed:", e)

        flash("✅ Record verified successfully", "success")

    except Exception as e:
        flash(f"⚠️ Error verifying: {e}", "danger")

    return redirect(url_for('admin_dashboard'))



@app.route('/dismiss/<int:id>', methods=['POST'])
def dismiss(id):
    """Mark a violation as Dismissed using DB primary key `id`."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin_login'))

    try:
        admin = session.get("admin_user", "Admin")

        # Update using PK
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE violations
                SET "Status" = 'Dismissed',
                    "VerifiedBy" = :admin,
                    "VerifiedAt" = (now() AT TIME ZONE 'Asia/Kolkata')
                WHERE id = :id;
            """), {"admin": admin, "id": id})

        # Excel fallback
        # try:
        #     if os.path.exists(VIOLATION_FILE):
        #         xdf = pd.read_excel(VIOLATION_FILE)
        #         if "id" in xdf.columns:
        #             xdf.loc[xdf["id"] == id, "Status"] = "Dismissed"
        #         safe_write_excel(xdf, VIOLATION_FILE)
        # except Exception as e:
        #     print("⚠️ Excel fallback dismiss failed:", e)

        flash("ℹ️ Record dismissed successfully", "info")

    except Exception as e:
        flash(f"⚠️ Error dismissing: {e}", "danger")

    return redirect(url_for('admin_dashboard'))



@app.route('/dismiss_unknown/<int:id>', methods=['POST'])
def dismiss_unknown(id):
    row_id = id
    """
    Dismiss an UNKNOWN/unregistered vehicle violation.
    Moves it to Actioned tab with Status='Dismissed'.
    """
    try:
        from db_utils import update_violation_status

        # Fetch record info (optional but good for safety/logging)
        # update_violation_status uses timestamp + number, so better to update by id here.

        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE violations
                SET "Status" = 'Dismissed'
                WHERE id = :id;
            """), {"id": row_id})

        # Excel fallback
        # try:
        #     if os.path.exists("violations.xlsx"):
        #         df = pd.read_excel("violations.xlsx", dtype=str)
        #         if "id" in df.columns:
        #             df.loc[df["id"].astype(str) == str(row_id), "Status"] = "Dismissed"
        #             safe_write_excel(df, "violations.xlsx")
        # except Exception as e:
        #     print("⚠️ Excel fallback failed:", e)

        flash("Record dismissed successfully.", "secondary")
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error dismissing record: {e}", "danger")

    return redirect(url_for('admin_actioned'))


# --- Paste into app.py near other admin endpoints (after existing verify/dismiss routes) ---

from urllib.parse import urlencode

@app.route('/verifyAndNotify/<int:id>', methods=['POST'])
def verifyAndNotify(id):
    """
    Verify the violation (same logic as /verify/<id>) and return JSON with data
    needed to notify the owner (owner contact, vehicle, flat, fine, image URLs).
    This does NOT change any existing verify logic — it performs the same DB+Excel updates.
    """
    if 'admin_user' not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 403

    try:
        print("I am calllleddddd................................................")
        admin = session.get("admin_user", "Admin")

        # 1) Update DB (same update used in /verify/<id>)
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE violations
                    SET "Status" = 'Verified',
                        "VerifiedBy" = :admin,
                        "VerifiedAt" = (now() AT TIME ZONE 'Asia/Kolkata')
                    WHERE id = :id;
                """), {"admin": admin, "id": id})
        except Exception as e:
            # If DB update fails we still try excel fallback below (and will return error if both fail)
            print("⚠️ DB update in verify_notify failed:", e)

        # 2) Excel fallback (mirror of existing verify flow)
        # try:
        #     if os.path.exists(VIOLATION_FILE):
        #         xdf = pd.read_excel(VIOLATION_FILE)
        #         if "id" in xdf.columns:
        #             xdf.loc[xdf["id"] == id, "Status"] = "Verified"
        #             safe_write_excel(xdf, VIOLATION_FILE)
        # except Exception as e:
        #     print("⚠️ Excel fallback verify in verify_notify failed:", e)

        # 3) Fetch the (updated) violation row to build notify payload.
        # Prefer DB; fall back to Excel.
        rec = None
        try:
            with engine.connect() as conn:
                q = text("""
                    SELECT id, "timestamp", "detected_number", "Owner", "FlatNo",
                           "allotted_slot", "parked_slot", "fine", "image_path", "OwnerContact"
                    FROM violations
                    WHERE id = :id
                    LIMIT 1;
                """)
                dfv = pd.read_sql(q, conn, params={"id": id})
                if not dfv.empty:
                    rec = dfv.iloc[0].to_dict()
        except Exception as e:
            print("⚠️ DB fetch for notify payload failed:", e)

        # if rec is None:
        #     # excel fallback
        #     try:
        #         if os.path.exists(VIOLATION_FILE):
        #             xdf = pd.read_excel(VIOLATION_FILE, dtype=str)
        #             if "id" in xdf.columns:
        #                 row = xdf[xdf["id"].astype(str) == str(id)]
        #                 if not row.empty:
        #                     rec = row.iloc[0].to_dict()
        #     except Exception as e:
        #         print("⚠️ Excel fetch fallback failed:", e)

        if rec is None:
            return jsonify({"success": False, "error": "Record not found after verify."}), 404

        # Normalize fields
        vehicle_no = str(rec.get("detected_number") or "")
        owner = str(rec.get("Owner") or "Owner")
        flat = str(rec.get("FlatNo") or "")
        fine = rec.get("fine") if rec.get("fine") is not None else 0
        owner_contact = str(rec.get("OwnerContact") or "").strip()
        image_path = rec.get("image_path") or ""
        # produce list of image URLs
        images = [p.strip().replace("\\", "/") for p in str(image_path).split(",") if p.strip()]


        # Send the payload back to frontend to let it open WhatsApp with prefilled message.
        payload = {
            "success": True,
            "id": id,
            "vehicle_no": vehicle_no,
            "owner": owner,
            "flat": flat,
            "fine": float(fine) if isinstance(fine, (int, float, str)) else 0,
            "owner_contact": owner_contact,
            "images": images,
            "parked_slot": rec.get("parked_slot") or "",
            "allotted_slot": rec.get("allotted_slot") or "",
            "qr_image": "https://rkjebswwcflbxwotoocu.supabase.co/storage/v1/object/sign/QR_Image/qrcode_chrome.png?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV9mNjY2NDMyZC1hMzllLTQ4MGItODgxZS0zZDU0Yjg0ZDg5YzMiLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJRUl9JbWFnZS9xcmNvZGVfY2hyb21lLnBuZyIsImlhdCI6MTc2MzI5MjI5MCwiZXhwIjoxNzk0ODI4MjkwfQ.vZE9FL3u2VtLywfJ9yEZxZcwXgSp35uRBy2PQz9ZcCw"
        }

        return jsonify(payload)

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# --- add to app.py ---
from flask import abort, send_file, make_response  # already probably present
# ... other imports ...

# ---------- NEW: Preview page used in WhatsApp message (short links) ----------
@app.route('/notify/preview/<int:id>')
def notify_preview(id):
    """
    Small preview page showing the violation photos and short details.
    Used by admin WhatsApp message as "View Images" link.
    """
    try:
        # Prefer DB first
        rec = None
        try:
            with engine.connect() as conn:
                q = text("""
                    SELECT id, "timestamp", "detected_number", "Owner", "FlatNo",
                           "parked_slot", "allotted_slot", "fine", "image_path", "OwnerContact"
                    FROM violations
                    WHERE id = :id
                    LIMIT 1;
                """)
                dfv = pd.read_sql(q, conn, params={"id": id})
                if not dfv.empty:
                    rec = dfv.iloc[0].to_dict()
        except Exception:
            rec = None

        # Excel fallback
        # if rec is None:
        #     try:
        #         if os.path.exists(VIOLATION_FILE):
        #             xdf = pd.read_excel(VIOLATION_FILE, dtype=str)
        #             if "id" in xdf.columns:
        #                 row = xdf[xdf["id"].astype(str) == str(id)]
        #                 if not row.empty:
        #                     rec = row.iloc[0].to_dict()
        #     except Exception:
        #         rec = None

        if rec is None:
            return "<h3>Record not found</h3>", 404

        # prepare image list
        image_path = rec.get("image_path") or ""
        images = [p.strip().replace("\\", "/") for p in str(image_path).split(",") if p.strip()]

        # timestamp formatting (IST if available)
        ts = rec.get("timestamp")
        try:
            ts = pd.to_datetime(ts)
            if getattr(ts, "tzinfo", None):
                ts = ts.tz_convert("Asia/Kolkata")
            else:
                ts = ts.tz_localize("UTC").tz_convert("Asia/Kolkata")
            ts_str = ts.strftime("%d-%b-%Y %H:%M")
        except Exception:
            ts_str = str(rec.get("timestamp") or "")

        return render_template("notify_preview.html",
                               rec=rec,
                               images=images,
                               timestamp_fmt=ts_str)
    except Exception as e:
        import traceback; traceback.print_exc()
        return f"Error: {e}", 500


# ---------- NEW: QR preview page ----------
@app.route('/notify/qr/<int:id>')
def notify_qr(id):
    """
    Small QR preview page. For now uses the static QR URL saved in your verifyAndNotify payload.
    """
    # default QR (same as used in verifyAndNotify) - keep in sync if you change it later
    QR_URL = "https://rkjebswwcflbxwotoocu.supabase.co/storage/v1/object/sign/QR_Image/qrcode_chrome.png?token=eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV9mNjY2NDMyZC1hMzllLTQ4MGItODgxZS0zZDU0Yjg0ZDg5YzMiLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJRUl9JbWFnZS9xcmNvZGVfY2hyb21lLnBuZyIsImlhdCI6MTc2MzI5MjI5MCwiZXhwIjoxNzk0ODI4MjkwfQ.vZE9FL3u2VtLywfJ9yEZxZcwXgSp35uRBy2PQz9ZcCw"
    try:
        # we won't fail if violation row missing — QR page is generic with amount note
        # try to fetch basic details to show the amount if present
        rec = None
        try:
            with engine.connect() as conn:
                q = text("SELECT id, detected_number, Owner, FlatNo, fine FROM violations WHERE id = :id LIMIT 1;")
                dfv = pd.read_sql(q, conn, params={"id": id})
                if not dfv.empty:
                    rec = dfv.iloc[0].to_dict()
        except Exception:
            rec = None

        return render_template("notify_qr.html", rec=rec, qr_url=QR_URL)
    except Exception as e:
        import traceback; traceback.print_exc()
        return f"Error: {e}", 500


# ---------- FIXED: One-click Assign / Clamp endpoint ----------
@app.route('/assign_or_clamp', methods=['POST'])
def assign_or_clamp():
    """
    Called by admin UI when user clicks Assign / Clamp on the Pending list.
    - If vehicle is registered (exists in parking_data) -> immediately CLAMP (Actioned tab),
      apply fine = 5000 if Verified+CLAMPED count > 3 else 1000.
    - If vehicle is not registered -> mark as UNKNOWN (Unregistered tab) with fine 1000.
    """
    try:
        data = request.get_json() or {}
        vehicle = str(data.get("vehicle_no", "")).strip().upper()
        parked_slot = str(data.get("parked_slot", "")).strip().upper()
        admin = session.get("admin_user", "Admin")

        if not vehicle:
            return jsonify({"success": False, "error": "No vehicle provided."})

        last4 = vehicle[-4:]

        from db_utils import fetch_parking_record, upsert_parking_record

        # Try DB first: find the latest pending violation for this vehicle (via last4)
        try:
            q = text("""
                SELECT *
                FROM violations
                WHERE RIGHT("detected_number", 4) = :last4
                  AND COALESCE("Status",'') NOT IN ('Verified','Dismissed','CLAMPED','UNKNOWN')
                ORDER BY "timestamp" DESC
                LIMIT 1;
            """)
            candidate = pd.read_sql(q, engine, params={"last4": last4})
        except Exception as e:
            print("⚠️ DB read failed:", e)
            candidate = pd.DataFrame()

        if candidate.empty:
            return jsonify({"success": False,
                            "error": f"No pending record found for {vehicle} (last 4: {last4})."})

        row = candidate.iloc[0]

        # Normalize timestamp for DB matching
        rec_ts = pd.to_datetime(row["timestamp"], errors="coerce")
        if not pd.isna(rec_ts):
            rec_ts = rec_ts.tz_localize(None) if getattr(rec_ts, "tzinfo", None) else rec_ts
            rec_ts = rec_ts.floor("min")
            ts_str = rec_ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts_str = None

        # -------------------------------------------------------------
        # 1️⃣ REGISTERED VEHICLE → CLAMPED → ACTIONED
        # -------------------------------------------------------------
        parking_rec = fetch_parking_record(vehicle)

        if parking_rec:
            # Count previous Verified + CLAMPED
            try:
                cnt_q = text("""
                    SELECT COUNT(*) AS cnt
                    FROM violations
                    WHERE "detected_number" = :veh
                      AND COALESCE("Status",'') IN ('Verified','CLAMPED');
                """)
                cnt_df = pd.read_sql(cnt_q, engine, params={"veh": vehicle})
                cnt = int(cnt_df.iloc[0]["cnt"]) if not cnt_df.empty else 0
            except:
                cnt = 0
                # Excel fallback
                # try:
                #     vdf = pd.read_excel("violations.xlsx", dtype=str)
                #     cnt = int(((vdf["detected_number"] == vehicle) &
                #                (vdf["Status"].isin(["Verified","CLAMPED"]))).sum())
                # except:
                #     cnt = 0

            fine = 5000 if cnt > 3 else 1000

            owner = parking_rec.get("OwnerName") or ""
            flat = parking_rec.get("FlatNo") or ""
            contact = parking_rec.get("OwnerContact") or ""
            # default_slot = parking_rec.get("ParkingSlot") or ""
            default_slot = parking_rec.get("ParkingSlot") if parking_rec else ""

            # Update DB row → CLAMPED
            try:
                if ts_str:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE violations
                            SET "Owner" = :owner,
                                "OwnerContact" = :contact,
                                "FlatNo" = :flat,
                                "allotted_slot" = :slot,
                                "fine" = :fine,
                                "Status" = 'CLAMPED',
                                "detected_number" = :new_num,
                                "VerifiedBy" = :admin,
                                "VerifiedAt" = (now() AT TIME ZONE 'Asia/Kolkata')
                            WHERE RIGHT("detected_number", 4) = :last4
                              AND DATE_TRUNC('minute',"timestamp")
                                  = DATE_TRUNC('minute', to_timestamp(:ts,'YYYY-MM-DD HH24:MI:SS'));
                        """), {
                            "owner": owner,
                            "contact": contact,
                            "flat": flat,
                            "slot": default_slot,
                            "fine": fine,
                            "new_num": vehicle,
                            "last4": last4,
                            "ts": ts_str,
                            "admin": admin
                        })
                else:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE violations
                            SET "Owner" = :owner,
                                "OwnerContact" = :contact,
                                "FlatNo" = :flat,
                                "allotted_slot" = :slot,
                                "fine" = :fine,
                                "Status" = 'CLAMPED',
                                "detected_number" = :new_num,
                                "VerifiedBy" = :admin,
                                "VerifiedAt" = (now() AT TIME ZONE 'Asia/Kolkata')
                            WHERE ctid IN (
                                SELECT ctid FROM violations
                                WHERE RIGHT("detected_number", 4) = :last4
                                  AND COALESCE("Status",'') NOT IN ('Verified','Dismissed','CLAMPED','UNKNOWN')
                                ORDER BY "timestamp" DESC LIMIT 1
                            );
                        """), {
                            "owner": owner,
                            "contact": contact,
                            "flat": flat,
                            "slot": default_slot,
                            "fine": fine,
                            "new_num": vehicle,
                            "last4": last4,
                            "admin": admin
                        })
            except Exception as e:
                print("⚠️ Registered update DB failed:", e)

            # Excel fallback
            # try:
            #     if os.path.exists("violations.xlsx"):
            #         df = pd.read_excel("violations.xlsx", dtype=str)
            #         df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.floor("min")
            #
            #         if not pd.isna(rec_ts):
            #             mask = (df["detected_number"].str[-4:] == last4) & (df["timestamp"] == rec_ts)
            #         else:
            #             mask = df["detected_number"].str[-4:] == last4
            #
            #         df.loc[mask, ["detected_number","Owner","OwnerContact","FlatNo",
            #                       "allotted_slot","fine","Status"]] = [
            #             vehicle, owner, contact, flat,
            #             parked_slot or default_slot,
            #             str(fine), "CLAMPED"
            #         ]
            #         safe_write_excel(df, "violations.xlsx")
            # except:
            #     pass

            return jsonify({
                "success": True,
                "registered": True,
                "type": "success",
                "message": f"Clamping of Vehicle {vehicle} of {owner} is successful.",
                "vehicle_no": vehicle,
                "owner": owner,
                "owner_contact": contact,
                "flat": flat,
                "parked_slot": parked_slot,
                "allotted_slot": default_slot,
                "fine": fine
            })

        # -------------------------------------------------------------
        # 2️⃣ UNREGISTERED VEHICLE → UNKNOWN → UNKNOWN TAB
        # -------------------------------------------------------------
        fine = 1000
        default_slot = parking_rec.get("ParkingSlot") if parking_rec else ""


        # Update DB row → UNKNOWN (FIXED)
        try:
            if ts_str:
                with engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE violations
                        SET "Owner" = 'UNKNOWN',
                            "OwnerContact" = 'N/A',
                            "FlatNo" = 'UNKNOWN',
                            "allotted_slot" = :slot,
                            "fine" = :fine,
                            "Status" = 'UNKNOWN',
                            "VerifiedBy" = :admin,
                            "VerifiedAt" = (now() AT TIME ZONE 'Asia/Kolkata')
                        WHERE RIGHT("detected_number", 4) = :last4
                          AND DATE_TRUNC('minute',"timestamp")
                              = DATE_TRUNC('minute', to_timestamp(:ts,'YYYY-MM-DD HH24:MI:SS'));
                    """), {"slot": default_slot or 'N/A', "fine": fine, "last4": last4, "ts": ts_str,"admin": admin})
            else:
                with engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE violations
                        SET "Owner" = 'UNKNOWN',
                            "OwnerContact" = 'N/A',
                            "FlatNo" = 'UNKNOWN',
                            "allotted_slot" = :slot,
                            "fine" = :fine,
                            "Status" = 'UNKNOWN',
                            "VerifiedBy" = :admin,
                            "VerifiedAt" = (now() AT TIME ZONE 'Asia/Kolkata')
                        WHERE ctid IN (
                              SELECT ctid FROM violations
                              WHERE RIGHT("detected_number", 4) = :last4
                                AND COALESCE("Status",'') NOT IN ('Verified','Dismissed','CLAMPED','UNKNOWN')
                              ORDER BY "timestamp" DESC LIMIT 1
                        );
                    """), {"slot": default_slot or 'N/A', "fine": fine, "last4": last4,"admin": admin})
        except Exception as e:
            print("⚠️ Unregistered DB update failed:", e)

        # Excel fallback
        # try:
        #     if os.path.exists("violations.xlsx"):
        #         df = pd.read_excel("violations.xlsx", dtype=str)
        #         df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.floor("min")
        #
        #         if not pd.isna(rec_ts):
        #             mask = (df["detected_number"].str[-4:] == last4) & (df["timestamp"] == rec_ts)
        #         else:
        #             mask = (df["detected_number"].str[-4:] == last4)
        #
        #         df.loc[mask, ["Owner","OwnerContact","FlatNo","allotted_slot","fine","Status"]] = [
        #             "UNKNOWN","N/A","UNKNOWN", parked_slot or 'N/A', str(fine),"UNKNOWN"
        #         ]
        #         safe_write_excel(df, "violations.xlsx")
        # except:
        #     pass

        return jsonify({
            "success": True,
            "registered": False,
            "type": "primary",
            "message": f"Vehicle {vehicle} not registered — moved to Unknown Vehicles (fine ₹{fine})."
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})





@app.route('/assign_owner', methods=['POST'])
def assign_owner():
    print("📩 assign_owner() HIT!")
    print("📩 FORM DATA:", dict(request.form))

    try:
        # -----------------------
        # Read form inputs
        # -----------------------
        vehicle_no_full = request.form.get('vehicle_no_full', '').strip().upper()
        owner_name = request.form.get('owner_name', '').strip()
        owner_contact = request.form.get('owner_contact', '').strip()
        flat_no = request.form.get('flat_no', '').strip().upper()
        slot = request.form.get('slot', '').strip().upper()
        vehicle_type = request.form.get('vehicle_type', '').strip().lower()

        viol_path = 'violations.xlsx'

        # -----------------------
        # Load violations (DB → Excel fallback)
        #------------------------
        try:
            viol = pd.read_sql('SELECT * FROM violations ORDER BY "timestamp" DESC;', engine)
        except:
            print("EXCEPTION - Failed to load Violations Table")
            # viol = pd.read_excel(viol_path, dtype=str) if os.path.exists(viol_path) else pd.DataFrame()
            viol = pd.DataFrame()

        if viol.empty:
            flash("No violations found.", "danger")
            return redirect(url_for('admin_dashboard'))

        # -----------------------
        # Match using last 4 digits
        # -----------------------
        last4 = vehicle_no_full[-4:]
        match_idx = viol.index[viol['detected_number'].astype(str).str[-4:] == last4]

        if len(match_idx) == 0:
            flash(f"No matching violation found for {vehicle_no_full}", "danger")
            return redirect(url_for('admin_dashboard'))

        idx = match_idx[0]
        record = viol.iloc[idx]
        timestamp = pd.to_datetime(record['timestamp']).floor('min')
        parked_slot = str(record.get('parked_slot', '')).strip().upper()

        from db_utils import fetch_parking_record, upsert_parking_record
        parking_rec = fetch_parking_record(vehicle_no_full)

        # ============================================================
        # 1️⃣ UNKNOWN VEHICLE → CONVERT TO REGISTERED
        # ============================================================
        if parking_rec is None:
            print("➡ Converting UNKNOWN → REGISTERED VEHICLE")

            # Insert new record into parking_data
            upsert_parking_record(
                flat_no,
                owner_name,
                owner_contact,
                vehicle_type,
                vehicle_no_full,
                slot,
                0
            )

            # Fine logic (same as registered vehicles)
            fine = 0
            if parked_slot and parked_slot != slot:
                fine = 100 if 'bike' in vehicle_type else 500

                try:
                    count_df = pd.read_sql(
                        text('SELECT COUNT(*) AS cnt FROM violations WHERE "detected_number" = :veh'),
                        engine,
                        params={'veh': vehicle_no_full}
                    )
                    if count_df.iloc[0]['cnt'] > 3:
                        fine = 5000
                except:
                    pass

            # Update violation → make it Pending (not Clamped)
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE violations
                    SET "Owner" = :owner,
                        "OwnerContact" = :contact,
                        "FlatNo" = :flat,
                        "allotted_slot" = :slot,
                        "fine" = :fine,
                        "Status" = 'Pending',
                        "detected_number" = :veh
                    WHERE RIGHT("detected_number", 4) = :last4
                      AND DATE_TRUNC('minute', "timestamp") = :ts;
                """), {
                    "owner": owner_name,
                    "contact": owner_contact,
                    "flat": flat_no,
                    "slot": slot,
                    "fine": fine,
                    "veh": vehicle_no_full,
                    "last4": last4,
                    "ts": timestamp
                })

            # Excel fallback
            try:
                viol['timestamp'] = pd.to_datetime(viol['timestamp'], errors='coerce').dt.floor('min')
                mask = (viol['detected_number'].str[-4:] == last4) & (viol['timestamp'] == timestamp)

                viol.loc[mask, ['detected_number','Owner','OwnerContact','FlatNo',
                                'allotted_slot','fine','Status']] = [
                    vehicle_no_full, owner_name, owner_contact, flat_no, slot, str(fine), "Pending"
                ]
                # safe_write_excel(viol, viol_path)
            except:
                pass

            flash(f"Vehicle {vehicle_no_full} successfully registered & moved to Pending.", "success")
            return redirect(url_for('admin_dashboard'))

        # ============================================================
        # 2️⃣ REGISTERED VEHICLE → NORMAL ASSIGN FLOW
        # ============================================================
        print("➡ Registered Vehicle → Assigning Owner")

        # Autofill missing bits
        owner_name = owner_name or parking_rec.get('OwnerName', '')
        owner_contact = owner_contact or parking_rec.get('OwnerContact', '')
        flat_no = flat_no or parking_rec.get('FlatNo', '')
        slot = slot or parking_rec.get('ParkingSlot', '')
        vehicle_type = vehicle_type or parking_rec.get('VehicleType', '')

        # Fine logic
        fine = 0
        if parked_slot and parked_slot != slot:
            fine = 100 if 'bike' in vehicle_type else 500

            try:
                count_df = pd.read_sql(
                    text('SELECT COUNT(*) AS cnt FROM violations WHERE "detected_number" = :veh'),
                    engine,
                    params={'veh': vehicle_no_full}
                )
                if count_df.iloc[0]['cnt'] > 3:
                    fine = 5000
            except:
                pass

        # Update violation → make it CLAMPED (normal flow)
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE violations
                SET "Owner" = :owner,
                    "OwnerContact" = :contact,
                    "FlatNo" = :flat,
                    "allotted_slot" = :slot,
                    "fine" = :fine,
                    "Status" = 'CLAMPED'
                WHERE RIGHT("detected_number", 4) = :last4
                  AND DATE_TRUNC('minute', "timestamp") = :ts;
            """), {
                "owner": owner_name,
                "contact": owner_contact,
                "flat": flat_no,
                "slot": slot,
                "fine": fine,
                "last4": last4,
                "ts": timestamp
            })

        # Sync parking_data
        upsert_parking_record(flat_no, owner_name, owner_contact,
                              vehicle_type, vehicle_no_full, slot, fine)

        flash(f"Vehicle {vehicle_no_full} clamped successfully.", "success")
        return redirect(url_for('admin_actioned'))

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error assigning owner: {e}", "danger")
        return redirect(url_for('admin_dashboard'))


# ---------------------- FETCH VEHICLE DETAILS (AJAX) ---------------------- #
@app.route('/get_vehicle_details/<vehicle_no>', methods=['GET'])
def get_vehicle_details(vehicle_no):
    try:
        vehicle_no = vehicle_no.strip().upper()
        record = fetch_parking_record(vehicle_no)
        if record:
            return jsonify({
                "success": True,
                "data": {
                    "FlatNo": record.get("FlatNo") or "",
                    "OwnerName": record.get("OwnerName") or "",
                    "VehicleType": record.get("VehicleType") or "",
                    "ParkingSlot": record.get("ParkingSlot") or "",
                    "OwnerContact": record.get("OwnerContact") or ""
                }
            })
        return jsonify({
            "success": True,
            "data": {
                "FlatNo": "UNKNOWN",
                "OwnerName": "Unknown Vehicle",
                "VehicleType": "Unknown",
                "ParkingSlot": "N/A",
                "OwnerContact": ""
            }
        })
    except Exception as e:
        print("⚠️ Error in get_vehicle_details:", e)
        return jsonify({"success": False, "error": str(e)})



def normalize_flat(s):
    """
    Normalize flat numbers so input like 'Vista-3005', 'vista 3005',
    'VISTA_3005', 'ViStA3005' all become 'VISTA3005'.
    """
    if not s:
        return ""
    # Convert to uppercase
    s = s.upper()
    # Remove spaces, hyphens, underscores
    for ch in [' ', '-', '_']:
        s = s.replace(ch, '')
    return s


@app.route('/summary', methods=['GET', 'POST'])
def summary():
    flat_no = None
    user_records = []
    total_raised = 0
    total_verified = 0

    try:
        if request.method == 'POST':
            # flat_no = request.form.get('flat_no', '').strip().upper()
            raw_flat = request.form.get('flat_no', '').strip()
            flat_no = normalize_flat(raw_flat)

            if not flat_no:
                flash("⚠️ Please enter your flat number.", "warning")
                return render_template('summary.html')

            # --- Step 1: Try Supabase / DB first ---
            try:
                df = fetch_violations_from_db()  # your DB fetch helper
                if not df.empty:
                    # Normalize column names
                    df.columns = df.columns.str.strip().str.lower()
                    # Ensure FlatNo is string and uppercase
                    # df['flatno'] = df.get('flatno', '').astype(str).str.upper()
                    df['flatno'] = df['flatno'].astype(str).apply(normalize_flat)

                else:
                    raise ValueError("Empty DataFrame from DB")
            except Exception as db_ex:
                print(f"⚠️ DB fetch failed: {db_ex}")
                df = pd.DataFrame()
                # --- Step 2: Excel fallback ---
                # with excel_lock:
                #     if os.path.exists(VIOLATION_FILE):
                #         df = pd.read_excel(VIOLATION_FILE, dtype=str)
                #         df.columns = df.columns.str.strip().str.lower()
                #         df['flatno'] = df.get('flatno', '').astype(str).str.upper()
                #     else:
                #         df = pd.DataFrame()

            # --- Filter for this flat ---
            user_records = df[df['flatno'] == flat_no].to_dict(orient='records')

            # --- Totals ---
            total_raised = len(user_records)
            total_verified = sum(1 for r in user_records if r.get('status', '').lower() == 'verified')

        return render_template(
            'summary.html',
            flat_no=flat_no,
            user_records=user_records,
            total_raised=total_raised,
            total_verified=total_verified
        )

    except Exception as e:
        print("Error in summary route:", e)
        flash(f"⚠️ Error fetching summary: {e}", "danger")
        return render_template('summary.html')


@app.route('/admin_dashboard/actioned')
def admin_actioned():
    """Actioned / Resolved Violations — shows both Verified and Dismissed (DB-first, Excel fallback)."""
    if 'admin_user' not in session:
        flash('Please log in to access admin dashboard.', 'danger')
        return redirect(url_for('admin_login'))

    try:
        # ✅ Step 1: Try fetching from Supabase / DB first
        try:
            df = fetch_violations_from_db()  # your existing DB fetch helper
            print("df: ", df.columns)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                df['timestamp'] = df['timestamp'].dt.floor('min')
                df = df[df['Status'].isin(['Verified', 'Dismissed','CLAMPED'])].copy()
                print(df.head(2))
            else:
                raise ValueError("Empty DataFrame from DB")
        except Exception as db_ex:
            print(f"⚠️ DB fetch failed: {db_ex}")
            import traceback
            traceback.print_exc()
            df = pd.DataFrame()  # fallback trigger

        # ✅ Step 2: Excel fallback if DB data unavailable
        if df.empty:
            df = pd.DataFrame()
            # with excel_lock:
            #     if os.path.exists(VIOLATION_FILE):
            #         df = pd.read_excel(VIOLATION_FILE, dtype=str)
            #     else:
            #         df = pd.DataFrame()

            # Ensure expected columns
            for c in ['timestamp', 'Status', 'image_path']:
                if c not in df.columns:
                    df[c] = ""

            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df[df['Status'].isin(['Verified', 'Dismissed','CLAMPED'])].copy()

        # ✅ Step 3: Clean image paths (works for both DB + Excel)
        def split_images(p):
            if not isinstance(p, str) or not p.strip():
                return []
            return [x.strip().replace("\\", "/") for x in p.split(",") if x.strip()]

        df['image_paths'] = df.get('image_path', "").apply(split_images)

        # ✅ Step 4: Sort newest first
        df = df.sort_values(by='timestamp', ascending=False).reset_index(drop=True)

    except Exception as e:
        print("Error loading actioned records:", e)
        flash(f"⚠️ Error loading actioned records: {e}", "danger")
        df = pd.DataFrame()

    # ✅ Render admin dashboard with only actioned records
    return render_template(
        'admin.html',
        pending_records=[],
        actioned_records=df.to_dict(orient='records'),
        clamped_records=[],
        active_tab='actioned'
    )


@app.route('/admin_dashboard/clamped')
def admin_clamped():
    """Unknown / Unregistered Vehicles tab (Status = 'UNKNOWN')."""
    if 'admin_user' not in session:
        flash('Please log in to access admin dashboard.', 'danger')
        return redirect(url_for('admin_login'))

    try:
        # Try DB fetch
        query = text("""
            SELECT 
                id,
                "timestamp",
                "detected_number",
                "parked_slot",
                "allotted_slot",
                "fine",
                "image_path",
                "Status",
                "Owner",
                "FlatNo"
            FROM violations
            WHERE "Status" = 'UNKNOWN'
            ORDER BY "timestamp" DESC;
        """)
        vdf = pd.read_sql(query, engine)
    except Exception as e:
        print("⚠️ Supabase fetch failed for UNKNOWN tab", e)
        vdf = pd.DataFrame()
        # vdf = pd.read_excel(VIOLATION_FILE, dtype=str) if os.path.exists(VIOLATION_FILE) else pd.DataFrame()
        # if not vdf.empty:
        #     vdf = vdf[vdf['Status'] == 'UNKNOWN'].copy()

    # Normalize
    if not vdf.empty:
        # make sure image_paths exists for template
        vdf['image_path'] = vdf.get('image_path', '').fillna('')
        vdf = vdf.sort_values(by='timestamp', ascending=False)
    else:
        vdf = pd.DataFrame()

    return render_template(
        'admin.html',
        pending_records=[],
        actioned_records=[],
        clamped_records=vdf.to_dict(orient='records'),
        active_tab='clamped'
    )



# ==========================
# 🧍 WATCHMAN LOGIN SYSTEM
# ==========================

@app.route('/watchman_login', methods=['GET', 'POST'])
def watchman_login():
    """Simple watchman login via PIN"""
    if request.method == 'POST':
        pin = request.form.get('pin', '').strip()
        watchman = authenticate_watchman(pin)
        if watchman:
            session['watchman_id'] = watchman['id']
            session['watchman_name'] = watchman['name']
            flash(f"Welcome, {watchman['name']} 👋", "success")
            return redirect(url_for('watchman_dashboard'))
        else:
            flash("⚠️ Invalid PIN. Please try again or register.", "danger")

    return render_template('watchman_login.html')


@app.route('/register_watchman', methods=['GET', 'POST'])
def watchman_register():
    """Register a new watchman (only name + 3-digit pin)."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        pin = request.form.get('pin', '').strip()
        phone = request.form.get('phone', '').strip()
        if len(pin) != 3 or not pin.isdigit():
            flash("⚠️ PIN must be a 3-digit number.", "danger")
        elif not name or not phone:
            flash("⚠️ Both name and phone number are required.", "danger")
        else:
            if register_watchman(name, pin, phone):
                flash(f"✅ Watchman {name} registered successfully! Please log in.", "success")
                return redirect(url_for('watchman_login', registered='true'))
            else:
                flash("⚠️ Registration failed. Try again.", "danger")

    return render_template('watchman_register.html')


from db_utils import fetch_violations_from_db
import pytz

@app.route('/watchman_dashboard')
def watchman_dashboard():
    """Display today's violations + recent watchman actions."""
    if 'watchman_id' not in session:
        flash("Please log in as watchman first.", "warning")
        return redirect(url_for('watchman_login'))

    try:
        df = fetch_violations_from_db()

        if df.empty:
            return render_template(
                'watchman_dashboard.html',
                today_records=[],
                recent_records=[],
                watchman=session['watchman_name'],
                total_pages=1,
                current_page=1,
                filter_watchman="ALL",
                all_watchmen=[]
            )

        # ------------------------------
        # Convert timestamp → IST
        # ------------------------------
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        # if df["timestamp"].dt.tz is not None:
        #     df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Kolkata")
        # else:
        #     df["timestamp"] = df["timestamp"].dt.tz_localize("Asia/Kolkata")

        df["timestamp"] = df["timestamp"].dt.floor("min")
        # print('df["timestamp"] : \n', df["timestamp"], df["timestamp"].dtype)
        # df["timestamp_fmt"] = df["timestamp"].dt.strftime("%d-%b-%Y %H:%M")
        # Force all timestamps to IST
        df = force_df_timestamps_to_ist(df, col="timestamp", fmt="%d-%b-%Y %H:%M")

        # ------------------------------
        # Today's date in IST
        # ------------------------------
        today = pd.Timestamp.now(tz="Asia/Kolkata").date()
        # print(type(today), today)
        # print("other today : ",pd.Timestamp.now())
        # today = datetime.
        # two_days_ago = today - timedelta(days=2)

        # ------------------------------
        # TODAY'S PENDING VIOLATIONS
        # (Status NOT Verified/Dismissed/CLAMPED/UNKNOWN)
        # ------------------------------
        today_records = df[
            # (df["timestamp"].dt.date == today) &
            (~df["Status"].isin(['Verified', 'Dismissed', 'CLAMPED', 'UNKNOWN'])) &
    (df["WatchmanSuggestedAction"].fillna("") == "")
        ].sort_values(by="timestamp", ascending=True).to_dict(orient="records")

        # ------------------------------
        # 🔥 Load ALL watchman observations
        # ------------------------------
        from db_utils import fetch_all_watchman_actions

        actions = fetch_all_watchman_actions()
        # print("actions: \n",actions)

        if not actions.empty:
            actions["created_at"] = pd.to_datetime(actions["created_at"], errors="coerce")

            # FORCE timezone localization to UTC first (Supabase uses UTC)
            # actions["created_at"] = actions["created_at"].dt.tz_localize("UTC").dt.tz_convert("Asia/Kolkata")
            actions["created_at"] = actions["created_at"].dt.floor("min")

            actions["created_at_fmt"] = actions["created_at"].dt.strftime("%d-%b-%Y %H:%M")

        # ------------------------------
        # Apply optional filter
        # ------------------------------
        selected_watchman = request.args.get("filter_watchman", "ALL")

        if selected_watchman != "ALL":
            actions = actions[actions['watchman_name'] == selected_watchman]

        # ------------------------------
        # Pagination: 5 records per page
        # ------------------------------
        page = int(request.args.get("page", 1))
        page_size = 5

        start = (page - 1) * page_size
        end = start + page_size

        paginated_actions = actions.iloc[start:end].to_dict(orient='records')

        total_pages = max(1, (len(actions) + page_size - 1) // page_size)

        return render_template(
        'watchman_dashboard.html',
        today_records=today_records,
        recent_records=paginated_actions,
        watchman=session['watchman_name'],
        total_pages=total_pages,
        current_page=page,
        filter_watchman=selected_watchman,
        all_watchmen=actions['watchman_name'].dropna().unique()
        )

    except Exception as e:
        flash(f"⚠️ Error loading watchman dashboard: {e}", "danger")
        return render_template(
            'watchman_dashboard.html',
            today_records=[],
            recent_records=[],
            watchman=session['watchman_name'],
            total_pages=1,
            current_page=1,
            filter_watchman="ALL",
            all_watchmen=[]
        )



# -------------------- Daily Entry for Watchman --------------------
from flask import jsonify
from db_utils import find_vehicle_by_last4, log_watchman_entry

@app.route('/daily_entry', methods=['GET', 'POST'])
def daily_entry():
    """
    New page for watchman to record entries (Vehicle or Person).
    GET -> render page
    POST -> accept JSON form post and persist using db_utils.log_watchman_entry
    """
    if 'watchman_id' not in session:
        flash("Please log in as watchman first.", "warning")
        return redirect(url_for('watchman_login'))

    if request.method == 'GET':
        # Render page; watchman name is passed for auto-fill
        return render_template('daily_entry.html', watchman=session.get('watchman_name', ''))

    # # POST handling: expect a JSON body (fetch from fetch/XHR)
    # try:
    #     payload = request.get_json() or request.form.to_dict()
    #     # Extract fields (keys we will send from front-end)
    #     watchman_id = session.get('watchman_id')
    #     watchman_name = session.get('watchman_name')
    #     entry_type = payload.get('type')  # "Vehicle" or "Person"
    #     last4 = payload.get('last4', '') or None
    #     full_plate = payload.get('full_plate', '') or None
    #     vehicle_category = payload.get('vehicle_category', '') or None  # e.g., Car / Bike / Auto (optional)
    #     purpose_category = payload.get('purpose_category', '') or None  # Visitor / Transport / Delivery / Resident etc.
    #     purpose_subtype = payload.get('purpose_subtype', '') or None  # Friend/Relative / Maid / Cab / Food / Parcel / Other
    #     flat_no = payload.get('flat_no', '') or None
    #     description = payload.get('description', '') or None
    #
    #     ok = log_watchman_entry(
    #         watchman_id=watchman_id,
    #         watchman_name=watchman_name,
    #         entry_type=entry_type,
    #         last4=last4,
    #         full_plate=full_plate,
    #         vehicle_category=vehicle_category,
    #         purpose_category=purpose_category,
    #         purpose_subtype=purpose_subtype,
    #         flat_no=flat_no,
    #         description=description
    #     )
    #     if ok:
    #         return jsonify({"status":"success","message":"Entry saved"})
    #     else:
    #         return jsonify({"status":"error","message":"Failed to save entry"}), 500
    #
    # except Exception as ex:
    #     print("❌ daily_entry save failed:", ex)
    #     return jsonify({"status":"error","message":"Exception occurred"}), 500


    # POST handling: accept JSON or multipart/form-data (for file)
    try:
        # Try JSON first (fetch/XHR sends JSON)
        payload = request.get_json(silent=True) or request.form.to_dict()

        # If multipart/form-data (file upload) then payload values may be in request.form
        if not isinstance(payload, dict):
            payload = {}

        # Basic fields (cover both JSON keys and form keys)
        watchman_id = session.get('watchman_id')
        watchman_name = session.get('watchman_name')

        entry_type = payload.get('type') or request.form.get('type')  # "Vehicle" or "Person"
        last4 = (payload.get('last4') or request.form.get('last4') or '').strip() or None
        full_plate = (payload.get('full_plate') or request.form.get('full_plate') or '').strip() or None
        vehicle_category = (payload.get('vehicle_category') or request.form.get('vehicle_category') or '').strip() or None
        purpose_category = (payload.get('purpose_category') or request.form.get('purpose_category') or '').strip() or None
        purpose_subtype = (payload.get('purpose_subtype') or request.form.get('purpose_subtype') or '').strip() or None
        flat_no = (payload.get('flat_no') or request.form.get('flat_no') or '').strip() or None
        # name = (payload.get('name') or request.form.get('name') or '').strip() or None
        name = (payload.get('person_name')
                or request.form.get('person_name')
                or payload.get('full_plate')
                or request.form.get('full_plate')
                or payload.get('last4')
                or request.form.get('last4')
                or '').strip() or None

        # Optional contact (person contact)
        # owner_contact = (payload.get('person_contact') or payload.get('contact') or
        #                  request.form.get('person_contact') or request.form.get('contact') or '').strip() or None

        owner_contact = (
                payload.get('owner_contact')
                or payload.get('person_contact')
                or request.form.get('owner_contact')
                or request.form.get('person_contact')
        )
        owner_contact = (owner_contact or '').strip() or None

        # Optional image(s) - single optional image for daily entry
        uploaded_files = []
        # If JSON body, no files. If multipart/form-data, request.files will have it.
        if request.files:
            # support both 'image' (single) and 'images' (list) naming
            if 'image' in request.files:
                # single or multiple
                f = request.files.getlist('image')
                uploaded_files.extend(f)
            if 'images' in request.files:
                uploaded_files.extend(request.files.getlist('images'))

        image_urls = []
        if uploaded_files:
            # Upload to the dedicated daily-entry bucket
            from db_utils import daily_entry_upload_images_to_supabase
            try:
                image_urls = daily_entry_upload_images_to_supabase(uploaded_files, bucket='daily_entry_images', save_local=False)
            except Exception as e:
                print("⚠️ daily_entry image upload failed:", e)
                image_urls = []

        print("DEBUG image_urls:", image_urls)
        # Pass image_urls and owner_contact through to DB helper
        ok = log_watchman_entry(
            watchman_id=watchman_id,
            watchman_name=watchman_name,
            entry_type=entry_type,
            last4=last4,
            full_plate=full_plate,
            vehicle_category=vehicle_category,
            purpose_category=purpose_category,
            purpose_subtype=purpose_subtype,
            flat_no=flat_no,
            name=name,
            owner_contact = owner_contact,
            image_urls = image_urls
        )


        # --- AFTER INSERT: update row with image_urls and owner_contact (or insert them directly if modifying the function) ---
        # We'll modify log_watchman_entry next to accept owner_contact and image_urls directly.
        return jsonify({"status":"success","message":"Entry saved"}) if ok else (jsonify({"status":"error","message":"Failed to save entry"}), 500)

    except Exception as ex:
        print("❌ daily_entry save failed:", ex)
        return jsonify({"status":"error","message":"Exception occurred"}), 500




@app.route('/api/find_vehicle')
def api_find_vehicle():
    last4 = request.args.get('last4', '').strip()
    if not last4:
        return jsonify({"found": False})
    veh = find_vehicle_by_last4(last4)
    if veh:
        # convert psycopg2 RealDictRow to dict (if needed)
        return jsonify({"found": True, "vehicle": dict(veh)})
    else:
        return jsonify({"found": False})



# @app.route('/api/todays_entries')
# def api_todays_entries():
#     if 'watchman_id' not in session:
#         return jsonify([])
#
#     try:
#         watchman_id = session['watchman_id']
#
#         conn = get_connection()
#         cur = conn.cursor(cursor_factory=RealDictCursor)
#
#         cur.execute("""
#             SELECT *
#             FROM watchman_entries
#             WHERE watchman_id = %s
#               AND created_at::date = (now() AT TIME ZONE 'Asia/Kolkata')::date
#             ORDER BY created_at DESC;
#         """, (watchman_id,))
#
#         rows = cur.fetchall()
#         conn.close()
#
#         return jsonify([dict(r) for r in rows])
#
#     except Exception as e:
#         print("❌ todays_entries error:", e)
#         return jsonify([])

@app.route('/api/todays_entries')
def api_todays_entries():
    if 'watchman_id' not in session:
        return jsonify([])

    try:
        watchman_id = session['watchman_id']

        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT *
            FROM watchman_entries
            WHERE created_at::date = (now() AT TIME ZONE 'Asia/Kolkata')::date
            ORDER BY created_at DESC;
        """)

        rows = cur.fetchall()
        conn.close()

        return jsonify([dict(r) for r in rows])

    except Exception as e:
        print("❌ todays_entries error:", e)
        return jsonify([])



@app.route('/register_vehicle', methods=['POST'])
def register_vehicle():
    if 'admin_logged_in' not in session:
        return redirect(url_for('admin_login'))

    try:
        vehicle_no = request.form.get('vehicle_no_full', '').strip().upper()
        owner_name = request.form.get('owner_name', '').strip()
        owner_contact = request.form.get('owner_contact', '').strip()
        flat_no = request.form.get('flat_no', '').strip().upper()
        vehicle_type = request.form.get('vehicle_type', '').strip()
        slot = request.form.get('slot', '').strip().upper()

        # 1️⃣ CHECK IN SUPABASE FIRST
        existing = fetch_parking_record(vehicle_no)
        if existing:
            popup_msg = (
                f"Vehicle {vehicle_no} already exists and owner is "
                f"{existing.get('OwnerName', '—')}, {existing.get('FlatNo','—')}."
            )
            # Send popup to admin page (no DB change)
            return render_template("admin.html",
                                   pending_records=[],
                                   actioned_records=[],
                                   clamped_records=[],
                                   active_tab="pending",
                                   popup_message=popup_msg)

        # 2️⃣ INSERT INTO SUPABASE (uses db_utils.upsert_parking_record)
        upsert_parking_record(flat_no, owner_name, owner_contact, vehicle_type, vehicle_no, slot, 0)

        # 3️⃣ UPDATE LOCAL EXCEL (ensure OwnerContact column)
        # reg_file = "parking_data.xlsx"
        # if os.path.exists(reg_file):
        #     df = pd.read_excel(reg_file, dtype=str)
        # else:
        #     # include OwnerContact column in initial schema
        #     df = pd.DataFrame(columns=[
        #         "FlatNo", "OwnerName", "OwnerContact", "VehicleType", "VehicleNo", "ParkingSlot", "TotalFines"
        #     ])
        #
        # # Ensure OwnerContact column exists
        # if "OwnerContact" not in df.columns:
        #     df["OwnerContact"] = ""
        #
        # new_row = {
        #     "FlatNo": flat_no,
        #     "OwnerName": owner_name,
        #     "OwnerContact": owner_contact,
        #     "VehicleType": vehicle_type,
        #     "VehicleNo": vehicle_no,
        #     "ParkingSlot": slot,
        #     "TotalFines": 0
        # }

        # df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        # safe_write_excel(df, reg_file)

        # 4️⃣ Show success centered popup (handled by template JS)
        success_msg = f"Vehicle {vehicle_no} registered successfully for {owner_name}."
        return render_template(
            "admin.html",
            pending_records=[],
            actioned_records=[],
            clamped_records=[],
            active_tab="pending",
            registration_success=success_msg
        )

    except Exception as e:
        flash(f"Error registering vehicle: {e}", "danger")
        return redirect(url_for('admin_dashboard'))


@app.route('/check_vehicle_exists', methods=['POST'])
def check_vehicle_exists():
    vehicle_no = request.form.get("vehicle_no", "").strip().upper()

    if not vehicle_no:
        return jsonify({"exists": False})

    # Check Supabase registry
    existing = fetch_parking_record(vehicle_no)

    if existing:
        return jsonify({
            "exists": True,
            "owner": existing.get("OwnerName", "—"),
            "flat": existing.get("FlatNo", "—")
        })

    return jsonify({"exists": False})


from flask import request, jsonify

@app.route('/watchman_observe', methods=['POST'])
def watchman_observe():
    """
    Watchman records: Verify / Dismiss / Clamp / Unknown.
    Does NOT modify violation Status.
    Only logs observation + updates WatchmanNote, WatchmanAt, WatchmanSuggestedAction.
    """
    if 'watchman_id' not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    try:
        data = request.get_json() or {}
        print("Watcham observe in app.py -------> ", data)
        violation_id = data.get('violation_id')
        print("violation_id : ", violation_id)
        action = (data.get('action') or "").strip()
        notes = data.get('notes') or ""
        print("notes in watchman_observe func: ", notes)

        if not action:
            return jsonify({"success": False, "error": "Missing action"}), 400

        wid = session['watchman_id']
        wname = session['watchman_name']

        # -----------------------------
        # 1️⃣ Log in watchman_actions table
        # -----------------------------
        from db_utils import log_watchman_action
        log_watchman_action(
            violation_id=violation_id,
            watchman_id=wid,
            watchman_name=wname,
            action=action,
            notes=notes
        )
        # -----------------------------
        # 2️⃣ Update violations table (watchman fields ONLY)
        # -----------------------------
        df = fetch_violations_from_db()
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df['timestamp'] = df['timestamp'].dt.floor('min')
        df = df.sort_values(by='timestamp', ascending=False).reset_index(drop=True)
        # print("len(df) : ", len(df))
        # df.to_csv("check.csv")

        # if violation_id is None or violation_id >= len(df):
        if violation_id is None:
            return jsonify({"success": False, "error": "Violation not found"}), 404

        rec = df[df['id'] == violation_id].iloc[0]

        detected_number = rec['detected_number']
        ts = rec['timestamp'].floor("min")

        # Update violation record with watchman note
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE violations
                SET 
                    "WatchmanNote" = :note,
                    "WatchmanSuggestedAction" = :act,
                    "WatchmanAt" = NOW()
                WHERE id = :vid;
            """), {
                "note": f"{wname} suggested: {action}",
                "act": action,
                "vid": violation_id
            })

        return jsonify({
            "success": True,
            "message": f"Recorded: {action}"
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500



# ---------------------- MAIN ---------------------- #
if __name__ == '__main__':
    app.run(debug=True)


