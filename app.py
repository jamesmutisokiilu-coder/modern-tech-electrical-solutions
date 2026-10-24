
import os
import sqlite3
from functools import wraps
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or "dev-only-change-this-secret-key",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "true").lower() == "true",
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
)

BASE_DIR = Path(__file__).resolve().parent
# On Render, set DATABASE_PATH=/var/data/modern_tech.db and mount a persistent disk at /var/data.
# Locally, the database is stored beside app.py.
DATABASE = os.environ.get("DATABASE_PATH", str(BASE_DIR / "modern_tech.db"))

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "joseph123")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "extravaganza")

SERVICE_STATUSES = ("Pending", "Approved", "Rejected", "Completed")
QUOTE_STATUSES = ("Pending", "Approved", "Rejected", "Completed")


# ============================================================
# DATABASE
# ============================================================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_db():
    # Ensure the database directory exists (needed for a Render persistent disk path).
    db_path = Path(DATABASE)
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def initialize_database():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS service_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                service_name TEXT NOT NULL,
                description TEXT,
                location TEXT,
                preferred_date TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                admin_note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contact_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                subject TEXT,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'New',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                description TEXT,
                price REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0,
                image_url TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                service_name TEXT NOT NULL,
                project_description TEXT,
                location TEXT,
                estimated_budget TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                admin_note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Create/update the configured administrator.
        db.execute("""
            INSERT INTO admin_users (username, password_hash, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash
        """, (
            ADMIN_USERNAME,
            generate_password_hash(ADMIN_PASSWORD),
            now()
        ))


initialize_database()


# ============================================================
# HELPERS
# ============================================================

def form_value(*names, default=""):
    for name in names:
        value = request.form.get(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def get_json_or_form():
    return request.get_json(silent=True) or request.form.to_dict()


def wants_json():
    return (
        request.is_json
        or request.path.startswith("/api/")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


def success_response(message, redirect_to=None, data=None, status=200):
    if wants_json():
        result = {"success": True, "message": message}
        if data is not None:
            result["data"] = data
        return jsonify(result), status

    flash(message, "success")
    return redirect(redirect_to or request.referrer or url_for("home"))


def error_response(message, status=400):
    if wants_json():
        return jsonify({"success": False, "error": message}), status

    flash(message, "error")
    return redirect(request.referrer or url_for("home"))


def render_admin_login(status_code=None, message=""):
    """Use an existing login template, or display a working fallback login form."""
    templates_dir = BASE_DIR / "templates"
    if (templates_dir / "admin_login.html").is_file():
        response = render_template("admin_login.html", message=message)
    elif (templates_dir / "login.html").is_file():
        response = render_template("login.html", message=message)
    else:
        from flask import render_template_string
        response = render_template_string("""
        <!doctype html>
        <html lang="en"><head>
          <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Administrator Login | Modern Tech Electrical Solutions</title>
          <style>
            *{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;
            font-family:Arial,sans-serif;background:#101827;color:#172033;padding:20px}
            .panel{width:100%;max-width:420px;background:#fff;border-radius:16px;padding:30px;
            box-shadow:0 18px 55px #0004}h1{margin-top:0;font-size:24px}
            p{color:#64748b;line-height:1.5}label{display:block;font-weight:700;margin:16px 0 7px}
            input{width:100%;padding:12px;border:1px solid #cbd5e1;border-radius:8px;font-size:16px}
            button{width:100%;padding:13px;margin-top:20px;border:0;border-radius:8px;
            background:#0f766e;color:white;font-weight:700;font-size:16px;cursor:pointer}
            .message{padding:10px;border-radius:8px;background:#fef2f2;color:#991b1b;margin:12px 0}
            a{color:#0f766e}
          </style></head><body><main class="panel">
          <h1>Administrator Login</h1><p>Modern Tech Electrical Solutions</p>
          {% if message %}<div class="message">{{ message }}</div>{% endif %}
          <form method="post" action="">
            <label for="username">Username</label>
            <input id="username" name="username" autocomplete="username" required>
            <label for="password">Password</label>
            <input id="password" name="password" type="password" autocomplete="current-password" required>
            <button type="submit">Log in</button>
          </form><p><a href="/">Return to website</a></p>
        </main></body></html>
        """, message=message)
    if status_code is not None:
        return response, status_code
    return response


def admin_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_id"):
            if wants_json():
                return jsonify({
                    "success": False,
                    "error": "Please log in as an administrator."
                }), 401
            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return decorated_function




@app.route("/gallery")
def gallery():
    return render_template("gallery.html")



# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
@app.route("/home")
@app.route("/index.html")
def home():
    with get_db() as db:
        products = db.execute("""
            SELECT * FROM products
            WHERE active = 1
            ORDER BY id DESC
            LIMIT 8
        """).fetchall()

    return render_template("index.html", products=products)


# ============================================================
# PUBLIC DASHBOARD
# IMPORTANT: THIS IS THE NORMAL WEBSITE DASHBOARD.
# DO NOT ADD ANOTHER FUNCTION NAMED dashboard().
# ============================================================

@app.route("/dashboard")
@app.route("/dashboard.html")
def dashboard():
    with get_db() as db:
        service_requests = db.execute("""
            SELECT id, service_name, description, status, created_at
            FROM service_requests
            ORDER BY id DESC
        """).fetchall()

    total_count = len(service_requests)

    pending_count = sum(
        1 for r in service_requests
        if (r["status"] or "").strip().lower() == "pending"
    )

    approved_count = sum(
        1 for r in service_requests
        if (r["status"] or "").strip().lower() == "approved"
    )

    progress_count = sum(
        1 for r in service_requests
        if (r["status"] or "").strip().lower()
        in ("in progress", "in_progress")
    )

    completed_count = sum(
        1 for r in service_requests
        if (r["status"] or "").strip().lower() == "completed"
    )

    return render_template(
        "dashboard.html",
        service_requests=service_requests,
        total_count=total_count,
        pending_count=pending_count,
        approved_count=approved_count,
        progress_count=progress_count,
        completed_count=completed_count
    )

# ============================================================
# SERVICES
# ============================================================


@app.route("/services", methods=["GET", "POST"])
@app.route("/services.html", methods=["GET", "POST"])
@app.route("/service", methods=["GET", "POST"])
def services():

    if request.method == "GET":
        return render_template("services.html")

    customer_name = form_value(
        "customer_name", "name", "full_name", "client_name"
    )
    phone = form_value("phone", "phone_number", "mobile", "telephone")
    email = form_value("email", "email_address")
    service_name = form_value(
        "service_name", "service", "service_type", "category"
    )
    description = form_value(
        "description", "message", "details", "problem", "requirements"
    )
    location = form_value("location", "address", "site_location")
    preferred_date = form_value(
        "preferred_date", "date", "service_date", "appointment_date"
    )

    if not customer_name or not phone or not service_name:
        return error_response(
            "Name, phone number and service are required.", 400
        )

    timestamp = now()

    try:
        with get_db() as db:
            cursor = db.execute("""
                INSERT INTO service_requests (
                    customer_name, phone, email, service_name,
                    description, location, preferred_date,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
            """, (
                customer_name,
                phone,
                email,
                service_name,
                description,
                location,
                preferred_date,
                timestamp,
                timestamp
            ))

            request_id = cursor.lastrowid

    except sqlite3.Error:
        app.logger.exception("Could not save service request")
        return error_response(
            "We could not save your request. Please try again.", 500
        )

    return success_response(
        "Your service request was saved successfully.",
        redirect_to=url_for("services"),
        data={
            "id": request_id,
            "status": "Pending",
            "customer_name": customer_name,
            "phone": phone,
            "email": email,
            "service_name": service_name,
            "description": description,
            "location": location,
            "preferred_date": preferred_date,
            "created_at": timestamp
        },
        status=201
    )



# ============================================================
# CONTACT
# ============================================================

@app.route("/contact", methods=["GET", "POST"])
@app.route("/contact.html", methods=["GET", "POST"])
def contact():
    if request.method == "GET":
        return render_template("contact.html")

    name = form_value("name", "full_name", "customer_name")
    email = form_value("email", "email_address")
    phone = form_value("phone", "phone_number", "mobile")
    subject = form_value("subject", "title")
    message = form_value("message", "details", "inquiry")

    if not name or not email or not message:
        return error_response(
            "Please provide your name, email address and message."
        )

    with get_db() as db:
        cursor = db.execute("""
            INSERT INTO contact_messages (
                name, email, phone, subject, message, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, 'New', ?)
        """, (name, email, phone, subject, message, now()))
        message_id = cursor.lastrowid

    return success_response(
        "Your message has been sent successfully.",
        redirect_to=url_for("contact"),
        data={"id": message_id},
        status=201
    )


# ============================================================
# ABOUT
# ============================================================

@app.route("/about")
@app.route("/about.html")
def about():
    return render_template("about.html")


# ============================================================
# PRODUCTS
# ============================================================

@app.route("/products")
@app.route("/products.html")
@app.route("/product")
def products():
    with get_db() as db:
        items = db.execute("""
            SELECT * FROM products
            WHERE active = 1
            ORDER BY id DESC
        """).fetchall()

    return render_template("products.html", products=items, items=items)


@app.route("/api/products")
def api_products():
    with get_db() as db:
        rows = db.execute("""
            SELECT id, name, category, description, price, stock, image_url
            FROM products
            WHERE active = 1
            ORDER BY id DESC
        """).fetchall()

    data = [dict(row) for row in rows]
    return jsonify({"success": True, "products": data, "data": data})


# ============================================================
# QUOTATIONS
# ============================================================

@app.route("/quotations", methods=["GET", "POST"])
@app.route("/quotations.html", methods=["GET", "POST"])
@app.route("/quotation", methods=["GET", "POST"])
@app.route("/quote", methods=["GET", "POST"])
def quotations():
    if request.method == "GET":
        return render_template("quotations.html")

    customer_name = form_value(
        "customer_name", "name", "full_name", "client_name"
    )
    phone = form_value("phone", "phone_number", "mobile")
    email = form_value("email", "email_address")
    service_name = form_value(
        "service_name", "service", "service_type", "project_type"
    )
    description = form_value(
        "project_description", "description", "message", "requirements"
    )
    location = form_value("location", "address", "site_location")
    budget = form_value(
        "estimated_budget", "budget", "project_budget", "price_range"
    )

    if not customer_name or not phone or not service_name:
        return error_response(
            "Please provide your name, phone number and project/service type."
        )

    timestamp = now()

    with get_db() as db:
        cursor = db.execute("""
            INSERT INTO quotations (
                customer_name, phone, email, service_name,
                project_description, location, estimated_budget,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
        """, (
            customer_name, phone, email, service_name,
            description, location, budget, timestamp, timestamp
        ))
        quote_id = cursor.lastrowid

    return success_response(
        f"Your quotation request has been submitted. Reference number: {quote_id}.",
        redirect_to=url_for("quotations"),
        data={"id": quote_id, "status": "Pending"},
        status=201
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

# =========================
# ADMIN LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
@app.route("/admin", methods=["GET", "POST"])
@app.route("/admin/login", methods=["GET", "POST"])
@app.route("/admin_login", methods=["GET", "POST"])
@app.route("/admin_login.html", methods=["GET", "POST"])
def admin_login():

    # If the administrator is already logged in, open dashboard
    if session.get("admin_id"):
        return redirect(url_for("admin_dashboard"))

    # Display login form when Admin Login is clicked
    if request.method == "GET":
        return render_admin_login()

    # Collect login details
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash("Please enter both username and password.", "error")
        return render_admin_login(400, "Please enter both username and password.")

    # Check administrator credentials in database
    try:
        with get_db() as db:
            admin = db.execute(
                """
                SELECT id, username, password_hash
                FROM admin_users
                WHERE username = ?
                """,
                (username,)
            ).fetchone()

    except sqlite3.Error:
        app.logger.exception("Administrator login database error")
        flash("A database error occurred. Please try again.", "error")
        return render_admin_login(500, "A database error occurred. Please try again.")

    # Verify password
    if admin and check_password_hash(admin["password_hash"], password):

        # Start a fresh authenticated session
        session.clear()
        session["admin_id"] = admin["id"]
        session["admin_username"] = admin["username"]

        flash("Login successful. Welcome to the admin dashboard!", "success")

        # Redirect to the protected administrator dashboard
        return redirect(url_for("admin_dashboard"))

    # Incorrect credentials
    flash("Invalid administrator username or password.", "error")
    return render_admin_login(401, "Invalid administrator username or password.")


# ============================================================
# ADMIN DASHBOARD — SEPARATE FROM THE PUBLIC DASHBOARD
# ============================================================


@app.route("/admin/dashboard")
@app.route("/admin_dashboard")
@app.route("/admin_dashboard.html")
@admin_required
def admin_dashboard():
    with get_db() as db:
        service_requests = db.execute("""
            SELECT * FROM service_requests
            ORDER BY id DESC
        """).fetchall()

        quotations = db.execute("""
            SELECT * FROM quotations ORDER BY id DESC
        """).fetchall()

        contact_messages = db.execute("""
            SELECT * FROM contact_messages ORDER BY id DESC
        """).fetchall()

        products = db.execute("""
            SELECT * FROM products ORDER BY id DESC
        """).fetchall()

    return render_template(
        "admin_dashboard.html",
        service_requests=service_requests,
        quotations=quotations,
        contact_messages=contact_messages,
        products=products
    )



# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin_logout", methods=["GET", "POST"])
@app.route("/admin/logout", methods=["GET", "POST"])
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("dashboard"))


# ============================================================
# ADMIN SERVICE REQUESTS API
# ============================================================

@app.route("/api/admin/service-requests")
@admin_required
def api_service_requests():
    status = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()

    query = "SELECT * FROM service_requests WHERE 1=1"
    parameters = []

    if status and status.lower() != "all":
        query += " AND status = ?"
        parameters.append(status)

    if search:
        query += """
            AND (
                customer_name LIKE ? OR phone LIKE ? OR email LIKE ?
                OR service_name LIKE ? OR location LIKE ?
            )
        """
        term = f"%{search}%"
        parameters.extend([term] * 5)

    query += " ORDER BY id DESC"

    with get_db() as db:
        rows = db.execute(query, parameters).fetchall()

    data = [dict(row) for row in rows]
    return jsonify({"success": True, "requests": data, "data": data})


def change_service_status(request_id, status, admin_note=""):
    if status not in SERVICE_STATUSES:
        return jsonify({
            "success": False, "error": "Invalid service request status."
        }), 400

    with get_db() as db:
        result = db.execute("""
            UPDATE service_requests
            SET status = ?, admin_note = ?, updated_at = ?
            WHERE id = ?
        """, (status, admin_note, now(), request_id))

        if result.rowcount == 0:
            return jsonify({
                "success": False, "error": "Service request not found."
            }), 404

        updated = db.execute(
            "SELECT * FROM service_requests WHERE id = ?", (request_id,)
        ).fetchone()

    return jsonify({
        "success": True,
        "message": f"Service request updated to {status}.",
        "request": dict(updated)
    })


@app.route(
    "/api/admin/service-requests/<int:request_id>/status",
    methods=["POST", "PATCH"]
)
@app.route(
    "/admin/service-requests/<int:request_id>/status",
    methods=["POST", "PATCH"]
)
@admin_required
def update_service_status(request_id):
    data = get_json_or_form()
    status = str(data.get("status", "")).strip().title()
    note = str(data.get("admin_note", data.get("note", ""))).strip()
    return change_service_status(request_id, status, note)


@app.route(
    "/admin/service-requests/<int:request_id>/approve", methods=["POST"]
)
@admin_required
def approve_service_request(request_id):
    data = get_json_or_form()
    note = str(data.get("admin_note", data.get("note", ""))).strip()

    result = change_service_status(request_id, "Approved", note)
    if isinstance(result, tuple) and result[1] >= 400:
        return result

    if wants_json():
        return result

    return success_response("Service request approved.")


@app.route(
    "/admin/service-requests/<int:request_id>/reject", methods=["POST"]
)
@admin_required
def reject_service_request(request_id):
    data = get_json_or_form()
    note = str(data.get("admin_note", data.get("note", ""))).strip()

    result = change_service_status(request_id, "Rejected", note)
    if isinstance(result, tuple) and result[1] >= 400:
        return result

    if wants_json():
        return result

    return success_response("Service request rejected.")


@app.route(
    "/admin/service-requests/<int:request_id>/complete", methods=["POST"]
)
@admin_required
def complete_service_request(request_id):
    data = get_json_or_form()
    note = str(data.get("admin_note", data.get("note", ""))).strip()

    result = change_service_status(request_id, "Completed", note)
    if isinstance(result, tuple) and result[1] >= 400:
        return result

    if wants_json():
        return result

    return success_response("Service request marked as completed.")


# ============================================================
# ADMIN CONTACT MESSAGES API
# ============================================================

@app.route("/api/admin/contact-messages")
@admin_required
def api_contact_messages():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM contact_messages ORDER BY id DESC"
        ).fetchall()

    data = [dict(row) for row in rows]
    return jsonify({"success": True, "messages": data, "data": data})


@app.route(
    "/api/admin/contact-messages/<int:message_id>/status",
    methods=["POST", "PATCH"]
)
@admin_required
def update_contact_message_status(message_id):
    data = get_json_or_form()
    status = str(data.get("status", "Read")).strip()

    if not status:
        return jsonify({
            "success": False, "error": "Message status is required."
        }), 400

    with get_db() as db:
        result = db.execute("""
            UPDATE contact_messages SET status = ? WHERE id = ?
        """, (status, message_id))

    if result.rowcount == 0:
        return jsonify({
            "success": False, "error": "Contact message not found."
        }), 404

    return jsonify({"success": True, "message": "Message status updated."})


# ============================================================
# ADMIN QUOTATIONS API
# ============================================================

@app.route("/api/admin/quotations")
@admin_required
def api_quotations():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM quotations ORDER BY id DESC"
        ).fetchall()

    data = [dict(row) for row in rows]
    return jsonify({"success": True, "quotations": data, "data": data})


@app.route(
    "/api/admin/quotations/<int:quote_id>/status",
    methods=["POST", "PATCH"]
)
@admin_required
def update_quotation_status(quote_id):
    data = get_json_or_form()
    status = str(data.get("status", "")).strip().title()
    note = str(data.get("admin_note", data.get("note", ""))).strip()

    if status not in QUOTE_STATUSES:
        return jsonify({
            "success": False, "error": "Invalid quotation status."
        }), 400

    with get_db() as db:
        result = db.execute("""
            UPDATE quotations
            SET status = ?, admin_note = ?, updated_at = ?
            WHERE id = ?
        """, (status, note, now(), quote_id))

    if result.rowcount == 0:
        return jsonify({
            "success": False, "error": "Quotation not found."
        }), 404

    return jsonify({
        "success": True,
        "message": f"Quotation status updated to {status}."
    })


# ============================================================
# ADMIN PRODUCTS API
# ============================================================

@app.route("/api/admin/products", methods=["GET", "POST"])
@admin_required
def api_admin_products():
    if request.method == "GET":
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM products ORDER BY id DESC"
            ).fetchall()

        data = [dict(row) for row in rows]
        return jsonify({"success": True, "products": data, "data": data})

    data = get_json_or_form()
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()
    description = str(data.get("description", "")).strip()
    image_url = str(data.get("image_url", data.get("image", ""))).strip()

    try:
        price = float(data.get("price", 0) or 0)
        stock = int(data.get("stock", 0) or 0)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Price must be numeric and stock must be a whole number."
        }), 400

    if not name:
        return jsonify({
            "success": False, "error": "Product name is required."
        }), 400

    if price < 0 or stock < 0:
        return jsonify({
            "success": False, "error": "Price and stock cannot be negative."
        }), 400

    with get_db() as db:
        cursor = db.execute("""
            INSERT INTO products (
                name, category, description, price, stock,
                image_url, active, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (name, category, description, price, stock, image_url, now()))

    return jsonify({
        "success": True,
        "message": "Product added successfully.",
        "id": cursor.lastrowid
    }), 201


@app.route(
    "/api/admin/products/<int:product_id>", methods=["DELETE", "POST"]
)
@admin_required
def delete_product(product_id):
    with get_db() as db:
        result = db.execute("""
            UPDATE products SET active = 0
            WHERE id = ? AND active = 1
        """, (product_id,))

    if result.rowcount == 0:
        return jsonify({
            "success": False, "error": "Active product not found."
        }), 404

    return jsonify({
        "success": True,
        "message": "Product removed from the public catalogue."
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/api/health")
def health_check():
    return jsonify({
        "success": True,
        "application": "Modern Tech Electrical Solutions",
        "database": "SQLite",
        "status": "running"
    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    if wants_json():
        return jsonify({
            "success": False,
            "error": "The requested route or record was not found."
        }), 404

    return "Page not found. Check the URL or template filename.", 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.error(
        "Unexpected server error",
        exc_info=(type(error), error, error.__traceback__)
    )

    if wants_json():
        return jsonify({
            "success": False,
            "error": "An internal server error occurred."
        }), 500

    return "An internal server error occurred. Check the terminal.", 500


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    )
