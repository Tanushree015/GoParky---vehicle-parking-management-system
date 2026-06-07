import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from functools import wraps
from flask import (
    Flask, request, jsonify, session,
    redirect, url_for, send_file, send_from_directory, make_response
)
import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta

# ------------------------ Basic Config ------------------------

BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    static_url_path='',
    static_folder=str(BASE_DIR),
    template_folder=str(BASE_DIR)
)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "change-me-in-prod")
APP_ENV = os.getenv("APP_ENV", "dev").lower()  # dev | prod

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     int(os.getenv("DB_PORT", "3306")),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "Tanu@123"),
    "database": os.getenv("DB_NAME", "goparky"),
}

# ------------------------ Logging Setup ------------------------

def setup_logging():
    app.logger.setLevel(logging.DEBUG if APP_ENV == "dev" else logging.INFO)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if APP_ENV == "dev" else logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    app.logger.addHandler(ch)

    fh = RotatingFileHandler(
        BASE_DIR / "goparky.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    app.logger.addHandler(fh)

setup_logging()

# ------------------------ Security Filter ------------------------

@app.before_request
def block_source_files():
    path = request.path.lower()
    for ext in ['.py', '.sql', '.zip', '.log', '.git', '.env']:
        if path.endswith(ext):
            return "Forbidden", 403

# ------------------------ Helpers ------------------------

def get_conn():
    conn = mysql.connector.connect(**DB_CONFIG)
    app.logger.debug(f"DB Connection: {conn.is_connected()}")
    return conn

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_get"))
        return view(*args, **kwargs)
    return wrapped

def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("user_role", "").lower() != role.lower():
                return redirect(url_for("login_get"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

# ------------------------ Slot APIs ------------------------

@app.get("/api/slots")
@login_required
def get_slots():
    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT slot_id, status FROM parkslot ORDER BY slot_id")
        rows = cur.fetchall()
        app.logger.debug(f"Fetched {len(rows)} slots")
        return jsonify(success=True, data=rows)
    except Exception as e:
        app.logger.exception("Error fetching slots")
        return jsonify(success=False, error=f"DB error: {e}"), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.patch("/api/slots/<slot_id>")
@login_required
@role_required("admin")
def update_slot(slot_id):
    conn = cur = None
    try:
        payload = request.get_json()
        if not payload:
            return jsonify(success=False, error="No payload"), 400

        status = payload.get("status", "").lower()
        app.logger.debug(f"Updating slot {slot_id} to {status}")

        if status not in ("available", "occupied", "not-available"):
            return jsonify(success=False, error="Invalid status"), 400

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE parkslot SET status=%s WHERE slot_id=%s", (status, slot_id))
        conn.commit()

        if cur.rowcount == 0:
            return jsonify(success=False, error="Slot not found"), 404

        app.logger.info(f"Updated slot {slot_id} to {status}")
        return jsonify(success=True)
    except Exception as e:
        app.logger.exception(f"Error updating slot {slot_id}")
        return jsonify(success=False, error=f"DB error: {e}"), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

# ------------------------ Slot Status API for slot.html (includes vehicle number) ------------------------

@app.get("/api/slot_status")
@login_required
def slot_status():
    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        # For each slot, get its type, status, and vehicle_id if occupied
        cur.execute("""
            SELECT 
                s.slot_id,
                IF(s.slot_id LIKE 'C%', 'Car', 'Bike') as type,
                s.status,
                (
                    SELECT p.vehicle_id 
                    FROM parklog p
                    WHERE p.slot_id = s.slot_id AND p.exit_time IS NULL
                    ORDER BY p.entry_time DESC
                    LIMIT 1
                ) as vehicle_id
            FROM parkslot s
            ORDER BY s.slot_id
        """)
        slots = cur.fetchall()
        for slot in slots:
            if slot["status"] != "occupied":
                slot["vehicle_id"] = None
        return jsonify(success=True, slots=slots)
    except Exception as e:
        app.logger.exception("Error fetching slot status")
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

# ------------------------ Staff Management APIs ------------------------

@app.get("/admin/staff_list")
@login_required
@role_required("admin")
def staff_list():
    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, name, email, contact, gender
            FROM users
            WHERE role = 'staff'
            ORDER BY id DESC
        """)
        staff_data = cur.fetchall()
        return jsonify(success=True, data=staff_data)
    except Exception as e:
        app.logger.exception("Error fetching staff list")
        return jsonify(success=False, error=f"Database error: {e}"), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.post("/admin/add_staff")
@login_required
@role_required("admin")
def add_staff():
    conn = cur = None
    try:
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        contact = data.get("contact", "").strip()
        email = data.get("email", "").strip().lower()
        gender = data.get("gender", "").strip().lower()
        password = data.get("password", "").strip()

        # Validation
        if not all([name, contact, email, password]):
            return jsonify(success=False, error="All fields are required"), 400
        if gender not in ("male", "female"):
            return jsonify(success=False, error="Invalid gender"), 400
        if len(password) < 6:
            return jsonify(success=False, error="Password must be at least 6 characters"), 400

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return jsonify(success=False, error="Email already exists"), 400

        cur.execute("""
            INSERT INTO users (name, role, gender, contact, email, password)
            VALUES (%s, 'staff', %s, %s, %s, %s)
        """, (name, gender, contact, email, password))
        conn.commit()
        return jsonify(
            success=True,
            id=cur.lastrowid,
            message="Staff added successfully"
        )
    except Exception as e:
        app.logger.exception("Error adding staff")
        return jsonify(success=False, error=f"Database error: {e}"), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.delete("/admin/delete_staff/<int:staff_id>")
@login_required
@role_required("admin")
def delete_staff(staff_id):
    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM users WHERE id = %s AND role = 'staff'", (staff_id,))
        if not cur.fetchone():
            return jsonify(success=False, error="Staff not found"), 404

        cur.execute("DELETE FROM users WHERE id = %s", (staff_id,))
        conn.commit()

        if cur.rowcount == 0:
            return jsonify(success=False, error="Failed to delete staff"), 500

        return jsonify(success=True, message="Staff deleted successfully")
    except Exception as e:
        app.logger.exception(f"Error deleting staff {staff_id}")
        return jsonify(success=False, error=f"Database error: {e}"), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.get("/api/parklog")
def get_parklog():
    count = request.args.get("count", type=int)
    period_type = request.args.get("type", type=str)

    where_clause = ""
    params = []

    if count and period_type in ("days", "months", "years"):
        now = datetime.now()
        if period_type == "days":
            start_date = now - timedelta(days=count)
        elif period_type == "months":
            start_date = now - timedelta(days=30 * count)
        elif period_type == "years":
            start_date = now - timedelta(days=365 * count)
        where_clause = "WHERE entry_time >= %s"
        params.append(start_date.strftime("%Y-%m-%d %H:%M:%S"))

    query = f"""
        SELECT 
            pl.log_id,
            pl.vehicle_id,
            v.type AS vehicle_type,
            pl.slot_id,
            DATE_FORMAT(pl.entry_time, '%%Y-%%m-%%d %%H:%%i:%%s') AS entry_time,
            DATE_FORMAT(pl.exit_time, '%%Y-%%m-%%d %%H:%%i:%%s') AS exit_time,
            pl.payment,
            pl.id
        FROM parklog pl
        LEFT JOIN vehicle v ON pl.vehicle_id = v.vehicle_id
        {where_clause}
        ORDER BY pl.entry_time DESC
    """

    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute(query, params)
        logs = cur.fetchall()
        return jsonify(success=True, data=logs)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.get("/api/slot_counts")
@login_required
def slot_counts():
    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) AS car_count FROM parkslot WHERE slot_id LIKE 'C%' AND status='available'")
        car_count = cur.fetchone()["car_count"]
        cur.execute("SELECT COUNT(*) AS bike_count FROM parkslot WHERE slot_id LIKE 'B%' AND status='available'")
        bike_count = cur.fetchone()["bike_count"]
        return jsonify(success=True, car=car_count, bike=bike_count)
    except Exception as e:
        app.logger.exception("Error fetching slot counts")
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.get("/api/search_vehicle")
@login_required
def search_vehicle():
    query = request.args.get("query", "").strip()
    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        if not query:
            return jsonify(success=True, results=[])
        # Search by vehicle number, owner name, or slot id (case-insensitive)
        cur.execute("""
            SELECT 
                v.owner, v.vehicle_id, v.type, v.contact,
                pl.slot_id,
                pl.payment AS bill_amount
            FROM vehicle v
            LEFT JOIN (
                SELECT p1.*
                FROM parklog p1
                INNER JOIN (
                    SELECT vehicle_id, MAX(entry_time) AS max_entry
                    FROM parklog
                    GROUP BY vehicle_id
                ) p2 ON p1.vehicle_id = p2.vehicle_id AND p1.entry_time = p2.max_entry
            ) pl ON v.vehicle_id = pl.vehicle_id
            WHERE LOWER(v.vehicle_id) LIKE %s
               OR LOWER(v.owner) LIKE %s
               OR LOWER(pl.slot_id) LIKE %s
            ORDER BY pl.entry_time DESC
            LIMIT 50
        """, (f"%{query.lower()}%", f"%{query.lower()}%", f"%{query.lower()}%"))
        results = cur.fetchall()
        return jsonify(success=True, results=results)
    except Exception as e:
        app.logger.exception("Error in search_vehicle")
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.get("/api/available_slots")
@login_required
def available_slots():
    vehicle_type = request.args.get("vehicle_type", "").lower()
    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        if vehicle_type == "car":
            cur.execute("SELECT slot_id FROM parkslot WHERE slot_id LIKE 'C%' AND status='available'")
        elif vehicle_type == "bike":
            cur.execute("SELECT slot_id FROM parkslot WHERE slot_id LIKE 'B%' AND status='available'")
        else:
            return jsonify(success=False, error="Invalid vehicle type"), 400
        slots = [row["slot_id"] for row in cur.fetchall()]
        return jsonify(success=True, slots=slots)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.get("/api/parked_vehicles")
@login_required
def parked_vehicles():
    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        # Get vehicles whose latest parklog entry has exit_time IS NULL
        cur.execute("""
            SELECT v.vehicle_id, v.owner, v.contact, v.type, pl.slot_id, DATE_FORMAT(pl.entry_time, '%Y-%m-%d %H:%i:%s') AS entry_time
            FROM vehicle v
            JOIN (
                SELECT vehicle_id, slot_id, entry_time
                FROM parklog
                WHERE exit_time IS NULL
                AND log_id IN (
                    SELECT MAX(log_id) FROM parklog GROUP BY vehicle_id
                )
            ) pl ON v.vehicle_id = pl.vehicle_id
            ORDER BY pl.entry_time DESC
        """)
        vehicles = cur.fetchall()
        return jsonify(success=True, data=vehicles)
    except Exception as e:
        app.logger.exception("Error fetching parked vehicles")
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.get("/api/all_vehicles")
@login_required
def all_vehicles():
    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT v.vehicle_id, v.owner, v.contact, v.type,
                   (SELECT slot_id FROM parklog WHERE vehicle_id = v.vehicle_id AND exit_time IS NULL ORDER BY entry_time DESC LIMIT 1) AS slot_id,
                   DATE_FORMAT((SELECT entry_time FROM parklog WHERE vehicle_id = v.vehicle_id AND exit_time IS NULL ORDER BY entry_time DESC LIMIT 1), '%Y-%m-%d %H:%i:%s') AS entry_time
            FROM vehicle v
            ORDER BY v.vehicle_id
        """)
        vehicles = cur.fetchall()
        return jsonify(success=True, data=vehicles)
    except Exception as e:
        app.logger.exception("Error fetching all vehicles")
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.get("/api/bill_vehicle")
@login_required
def bill_vehicle():
    vehicle_id = request.args.get("vehicle_id", "").strip()
    if not vehicle_id:
        return jsonify(success=False, error="Vehicle number is required"), 400

    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT v.vehicle_id, v.owner, v.type, v.contact, pl.entry_time, pl.slot_id
            FROM vehicle v
            JOIN parklog pl ON v.vehicle_id = pl.vehicle_id
            WHERE LOWER(v.vehicle_id) = LOWER(%s) AND pl.exit_time IS NULL
            ORDER BY pl.entry_time DESC LIMIT 1
        """, (vehicle_id,))
        info = cur.fetchone()
        if info:
            if info["entry_time"] and isinstance(info["entry_time"], (str,)):
                pass
            elif info["entry_time"]:
                info["entry_time"] = info["entry_time"].strftime("%Y-%m-%dT%H:%M:%S")
            return jsonify(success=True, data=info)
        else:
            return jsonify(success=False, error="Vehicle not found or already exited"), 404
    except Exception as e:
        app.logger.exception("Error fetching bill vehicle info")
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

# ------------------------ Vehicle Exit & Billing API ------------------------

@app.post("/api/vehicle_exit")
@login_required
@role_required("staff")
def vehicle_exit():
    data = request.get_json(silent=True) or {}
    vehicle_id = data.get("vehicle_id", "").strip()
    if not vehicle_id:
        return jsonify(success=False, error="Vehicle number is required"), 400

    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        # Find the latest active parklog for this vehicle
        cur.execute("""
            SELECT pl.log_id, pl.entry_time, v.owner, v.type, v.contact, pl.slot_id
            FROM parklog pl
            JOIN vehicle v ON pl.vehicle_id = v.vehicle_id
            WHERE LOWER(pl.vehicle_id) = LOWER(%s)
              AND pl.exit_time IS NULL
            ORDER BY pl.entry_time DESC
            LIMIT 1
        """, (vehicle_id,))
        row = cur.fetchone()
        if not row:
            return jsonify(success=False, error="No active entry found for this vehicle."), 404

        log_id = row["log_id"]
        entry_time = row["entry_time"]
        exit_time = datetime.now()
        vehicle_type = row["type"].lower()

        # Calculate duration and fee (ceiling hours)
        duration_hours = (exit_time - entry_time).total_seconds() / 3600
        duration_hours_ceil = int(-(-duration_hours // 1))
        if vehicle_type == "car":
            rate = 20
        elif vehicle_type == "bike":
            rate = 10
        elif vehicle_type == "truck":
            rate = 30
        else:
            rate = 20

        payment = rate * duration_hours_ceil

        # Update the parklog with exit time and payment
        cur.execute("""
            UPDATE parklog
            SET exit_time = %s, payment = %s
            WHERE log_id = %s
        """, (exit_time.strftime("%Y-%m-%d %H:%M:%S"), payment, log_id))

        # Free the slot
        cur.execute("""
            UPDATE parkslot SET status = 'available' WHERE slot_id = %s
        """, (row["slot_id"],))

        conn.commit()

        # Return receipt info
        return jsonify(success=True, data={
            "vehicle_id": vehicle_id,
            "owner": row["owner"],
            "type": row["type"],
            "contact": row["contact"],
            "slot_id": row["slot_id"],
            "entry_time": entry_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "exit_time": exit_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "payment": round(payment, 2)
        })
    except Exception as e:
        app.logger.exception("Error processing vehicle exit")
        return jsonify(success=False, error=f"Server/DB error: {e}"), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

# ------------------------ Routes ------------------------

@app.get("/")
def home():
    return send_file(BASE_DIR / "homepg.html")

@app.get("/login")
def login_get():
    return send_file(BASE_DIR / "login.html")

@app.post("/login")
def login_post():
    conn = cur = None
    try:
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        password = data.get("password", "")

        if not name or not password:
            return jsonify(success=False, error="Missing credentials"), 400

        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, role, password FROM users WHERE name=%s LIMIT 1", (name,))
        row = cur.fetchone()

        if not row or row["password"] != password:
            return jsonify(success=False, error="Invalid username or password"), 401

        session["user_id"] = row["id"]
        session["user_role"] = row["role"]
        session["user_name"] = row["name"]

        if row["role"].lower() == "admin":
            return jsonify(success=True, redirect=url_for("admin_dashboard"))
        else:
            cur.execute("INSERT INTO staff_logins (user_id) VALUES (%s)", (row["id"],))
            conn.commit()
            return jsonify(success=True, redirect=url_for("staff_dashboard"))

    except Exception as e:
        app.logger.exception("Error during login")
        return jsonify(success=False, error=f"Server/DB error: {e}"), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.get("/admin")
@app.get("/admin.html")
@login_required
@role_required("admin")
def admin_dashboard():
    return send_file(BASE_DIR / "admin.html")

@app.get("/report2.html")
@login_required
@role_required("admin")
def report2_html():
    return send_file(BASE_DIR / "report2.html")

@app.get("/profile.html")
@login_required
@role_required("admin")
def profile_html():
    return send_file(BASE_DIR / "profile.html")

@app.get("/mslot.html")
@login_required
@role_required("admin")
def manage_slots():
    return send_file(BASE_DIR / "mslot.html")

@app.get("/2d.html")
@login_required
def view_2d():
    return send_file(BASE_DIR / "2d.html")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_get"))

@app.get("/staffmag.html")
@login_required
@role_required("admin")
def staff_management():
    return send_file(BASE_DIR / "staffmag.html")

@app.get("/staff_profile.html")
@login_required
@role_required("staff")
def staff_profile():
    return send_file(BASE_DIR / "staff_profile.html")

@app.get("/search.html")
@login_required
@role_required("staff")
def search_html():
    return send_file(BASE_DIR / "search.html")

@app.get("/generate.html")
@login_required
@role_required("staff")
def generate_html():
    return send_file(BASE_DIR / "generate.html")

@app.get("/slot.html")
@login_required
@role_required("staff")
def slot_html():
    return send_file(BASE_DIR / "slot.html")

@app.get("/receipt.html")
@login_required
def receipt_html():
    return send_file(BASE_DIR / "receipt.html")

@app.get("/terms.html")
def terms_html():
    return send_file(BASE_DIR / "terms.html")

@app.get("/login.html")
def login_html_get():
    return redirect(url_for("login_get"))

@app.route("/api/profile")
def api_profile():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, role, gender, contact, email FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        return jsonify({"success": True, "data": user})
    else:
        return jsonify({"success": False, "error": "User not found"}), 404

@app.get("/admin/stats")
@login_required
@role_required("admin")
def admin_stats():
    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)
        today = datetime.now().strftime("%Y-%m-%d")

        cur.execute("""
            SELECT 
                SUM(payment) AS revenue,
                COUNT(DISTINCT vehicle_id) AS vehicles
            FROM parklog
            WHERE DATE(entry_time) = %s
        """, (today,))
        stats = cur.fetchone()
        revenue = float(stats["revenue"] or 0)
        vehicles = int(stats["vehicles"] or 0)

        cur.execute("""
            SELECT u.id, u.name, DATE_FORMAT(l.login_time, '%Y-%m-%d %H:%i:%s') AS login_time
            FROM staff_logins l
            JOIN users u ON l.user_id = u.id
            WHERE DATE(l.login_time) = %s
            ORDER BY l.login_time ASC
        """, (today,))
        staff_logins = cur.fetchall()

        return jsonify(
            revenue=revenue,
            vehicles=vehicles,
            staff_logins=staff_logins
        )
    except Exception as e:
        app.logger.exception("Error fetching admin stats")
        return jsonify(error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.get("/staff.html")
@login_required
@role_required("staff")
def staff_dashboard():
    return send_file(BASE_DIR / "staff.html")

@app.post("/api/vehicle_entry")
@login_required
@role_required("staff")
def vehicle_entry():
    data = request.get_json(silent=True) or {}
    owner = data.get("owner", "").strip()
    vehicle_id = data.get("vehicle_id", "").strip()
    contact = data.get("contact", "").strip()
    vehicle_type = data.get("vehicle_type", "").strip().lower()
    slot_id = data.get("slot_id", "").strip()

    if not all([owner, vehicle_id, contact, vehicle_type, slot_id]):
        return jsonify(success=False, error="All fields are required"), 400

    entry_time = datetime.now()  # Set now!

    conn = cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Check if vehicle is already parked (active entry exists)
        cur.execute("SELECT slot_id FROM parklog WHERE LOWER(vehicle_id) = LOWER(%s) AND exit_time IS NULL", (vehicle_id,))
        if cur.fetchone():
            return jsonify(success=False, error="Vehicle is already parked! Please exit the vehicle first."), 400

        cur.execute("""
            INSERT INTO vehicle (vehicle_id, owner, contact, type)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE owner=%s, contact=%s, type=%s
        """, (vehicle_id, owner, contact, vehicle_type, owner, contact, vehicle_type))
        cur.execute("UPDATE parkslot SET status='occupied' WHERE slot_id=%s AND status='available'", (slot_id,))
        if cur.rowcount == 0:
            conn.rollback()
            return jsonify(success=False, error="Slot not available"), 400
        cur.execute("""
            INSERT INTO parklog (vehicle_id, slot_id, entry_time, exit_time)
            VALUES (%s, %s, %s, NULL)
        """, (vehicle_id, slot_id, entry_time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return jsonify(success=True, message="Vehicle entry stored and slot assigned!")
    except Exception as e:
        app.logger.exception("Error storing vehicle entry")
        return jsonify(success=False, error=f"Database error: {e}"), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)