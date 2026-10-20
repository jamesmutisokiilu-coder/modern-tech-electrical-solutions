from flask import Flask, render_template, request, redirect, session, url_for
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# ==========================================
# CONFIG
# ==========================================
app.secret_key = os.environ.get("SECRET_KEY", "jemo_secret_key")
DATABASE_URL = os.environ.get("DATABASE_URL")


# ==========================================
# DB CONNECTION (SAFE)
# ==========================================
def get_db():
    """
    Works ONLY if DATABASE_URL is set (Render PostgreSQL).
    """
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not set. Add PostgreSQL on Render.")

    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


# ==========================================
# INIT DB (SAFE FOR RENDER)
# ==========================================
def init_db():
    """
    Runs only when DATABASE_URL exists.
    On Render, PostgreSQL is already available.
    """
    if not DATABASE_URL:
        print("Skipping DB init (no DATABASE_URL)")
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS support(
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        category TEXT,
        priority TEXT,
        message TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS training_requests(
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        course TEXT NOT NULL,
        email TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings(
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        service TEXT NOT NULL,
        date TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# Run DB init safely
try:
    init_db()
except Exception as e:
    print("DB init skipped:", e)


# ==========================================
# ADMIN LOGIN
# ==========================================
ADMIN_USER = "admin"
ADMIN_PASS = "1234"


# ==========================================
# HOME
# ==========================================
@app.route("/")
def home():
    return render_template("index.html")


# ==========================================
# REGISTER
# ==========================================
@app.route("/register", methods=["GET", "POST"])
def register():
    message = ""

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO users(username,email,password)
                VALUES(%s,%s,%s)
            """, (username, email, password))

            conn.commit()
            conn.close()

            message = "Registration Successful"

        except Exception:
            message = "Email already exists or DB error"

    return render_template("register.html", message=message)


# ==========================================
# LOGIN
# ==========================================
@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT * FROM users
            WHERE email=%s AND password=%s
        """, (email, password))

        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = user["username"]
            return redirect(url_for("dashboard"))
        else:
            message = "Invalid login details"

    return render_template("login.html", message=message)


# ==========================================
# DASHBOARD
# ==========================================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html", username=session["user"])


# ==========================================
# LOGOUT
# ==========================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==========================================
# PROTECTED PAGES
# ==========================================
def protected(page):
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template(page)


@app.route("/services")
def services():
    return protected("services.html")


@app.route("/portfolio")
def portfolio():
    return protected("portfolio.html")


@app.route("/blog")
def blog():
    return protected("blog.html")


@app.route("/downloads")
def downloads():
    return protected("downloads.html")


@app.route("/about")
def about():
    return protected("about.html")


@app.route("/contact")
def contact():
    return protected("contact.html")


# ==========================================
# SUPPORT (FIXED)
# ==========================================
@app.route("/support", methods=["GET", "POST"])
def support():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        category = request.form["category"]
        priority = request.form["priority"]
        message = request.form["message"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO support(name,email,phone,category,priority,message)
            VALUES(%s,%s,%s,%s,%s,%s)
        """, (name, email, phone, category, priority, message))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("support.html")


# ==========================================
# TRAINING
# ==========================================
@app.route("/training", methods=["GET", "POST"])
def training():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        course = request.form["course"]
        email = request.form["email"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO training_requests(name,course,email)
            VALUES(%s,%s,%s)
        """, (name, course, email))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("training.html")


# ==========================================
# BOOKING
# ==========================================
@app.route("/booking", methods=["GET", "POST"])
def booking():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        service = request.form["service"]
        date = request.form["date"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO bookings(name,service,date)
            VALUES(%s,%s,%s)
        """, (name, service, date))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("booking.html")


# ==========================================
# ADMIN LOGIN
# ==========================================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USER and password == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))

    return render_template("admin_login.html")


# ==========================================
# ADMIN DASHBOARD
# ==========================================
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users ORDER BY id DESC")
    users = cur.fetchall()

    cur.execute("SELECT * FROM support ORDER BY id DESC")
    support = cur.fetchall()

    cur.execute("SELECT * FROM training_requests ORDER BY id DESC")
    training = cur.fetchall()

    cur.execute("SELECT * FROM bookings ORDER BY id DESC")
    bookings = cur.fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        users=users,
        support=support,
        training=training,
        bookings=bookings
    )


# ==========================================
# ADMIN LOGOUT
# ==========================================
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin"))


# ==========================================
# DELETE ROUTES
# ==========================================
@app.route("/delete_user/<int:id>", methods=["POST"])
def delete_user(id):
    if not session.get("admin"):
        return redirect(url_for("admin"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE id=%s", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/delete_support/<int:id>", methods=["POST"])
def delete_support(id):
    if not session.get("admin"):
        return redirect(url_for("admin"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM support WHERE id=%s", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/delete_training/<int:id>", methods=["POST"])
def delete_training(id):
    if not session.get("admin"):
        return redirect(url_for("admin"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM training_requests WHERE id=%s", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/delete_booking/<int:id>", methods=["POST"])
def delete_booking(id):
    if not session.get("admin"):
        return redirect(url_for("admin"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM bookings WHERE id=%s", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


# ==========================================
# RUN (RENDER READY)
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)