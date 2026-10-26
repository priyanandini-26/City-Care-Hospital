
import sqlite3
from datetime import date
from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DATABASE = "hospital.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def add_missing_columns(conn, table, columns):
    existing = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
    for name, datatype in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {datatype}")


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            specialization TEXT,
            full_name TEXT,
            email TEXT
        )
    """)

    add_missing_columns(conn, "users", {
        "specialization": "TEXT",
        "full_name": "TEXT",
        "email": "TEXT"
    })

    conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            doctor_id INTEGER,
            appointment_date TEXT,
            reason TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT
        )
    """)

    add_missing_columns(conn, "appointments", {
        "patient_id": "INTEGER",
        "doctor_id": "INTEGER",
        "appointment_date": "TEXT",
        "reason": "TEXT",
        "status": "TEXT DEFAULT 'Pending'",
        "created_at": "TEXT"
    })

    defaults = [
        ("Dev", "dev@123", "Admin", "System Administrator"),
        ("dr_smith", "smith@123", "Doctor", "General Physician"),
        ("dr_adams", "adams@123", "Doctor", "Cardiologist"),
        ("ravi", "ravi@123", "Patient", ""),
        ("raju", "raju@123", "Patient", ""),
        ("ramu", "ramu@123", "Patient", ""),
        ("yash", "yash@123", "Patient", "")
    ]

    for username, password, role, specialization in defaults:
        user = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()

        if not user:
            conn.execute("""
                INSERT INTO users
                (username, password, role, specialization, full_name, email)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                username,
                generate_password_hash(password),
                role,
                specialization,
                username,
                ""
            ))

    conn.commit()
    conn.close()


init_db()


BASE = """
<!DOCTYPE html>
<html>
<head>
    <title>City Care Hospital</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<nav class="navbar navbar-dark bg-primary">
    <div class="container">
        <a class="navbar-brand" href="/">City Care Hospital</a>
        <div>
            {% if session.get('user_id') %}
                <span class="text-white me-3">
                    {{ session.get('username') }} ({{ session.get('role') }})
                </span>
                <a class="btn btn-light btn-sm" href="{{ url_for('logout') }}">Logout</a>
            {% else %}
                <a class="btn btn-light btn-sm" href="{{ url_for('login') }}">Login</a>
                <a class="btn btn-warning btn-sm" href="{{ url_for('register') }}">Register</a>
            {% endif %}
        </div>
    </div>
</nav>

<div class="container mt-4">
    {% for category, message in get_flashed_messages(with_categories=true) %}
        <div class="alert alert-{{ category }} alert-dismissible fade show">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    {% endfor %}
    CONTENT
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""


def page(content, **context):
    return render_template_string(BASE.replace("CONTENT", content), **context)


def login_required():
    if not session.get("user_id"):
        flash("Please log in first.", "warning")
        return False
    return True


def role_required(*roles):
    if not login_required():
        return False
    if session.get("role") not in roles:
        flash("You are not authorized to access this page.", "danger")
        return False
    return True


@app.route("/")
def index():
    content = """
    <div class="p-5 bg-white rounded shadow-sm text-center">
        <h1>Welcome to City Care Hospital</h1>
        <p class="lead">Your health is our priority.</p>
        {% if session.get('user_id') %}
            <a class="btn btn-primary" href="{{ url_for('appointments') }}">View Appointments</a>
        {% else %}
            <a class="btn btn-primary" href="{{ url_for('login') }}">Login</a>
            <a class="btn btn-success" href="{{ url_for('register') }}">Create Account</a>
        {% endif %}
    </div>
    """
    return page(content)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        email = request.form.get("email", "").strip()

        if not username or not password:
            flash("Enter a username and password.", "danger")
        else:
            conn = get_db()
            try:
                conn.execute("""
                    INSERT INTO users
                    (username, password, role, specialization, full_name, email)
                    VALUES (?, ?, 'Patient', '', ?, ?)
                """, (
                    username,
                    generate_password_hash(password),
                    username,
                    email
                ))
                conn.commit()
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That username already exists.", "danger")
            finally:
                conn.close()

    content = """
    <div class="card mx-auto p-4 shadow-sm" style="max-width:500px">
        <h3>Patient Registration</h3>
        <form method="post">
            <label class="form-label">Username</label>
            <input class="form-control mb-3" name="username" required>
            <label class="form-label">Email</label>
            <input class="form-control mb-3" type="email" name="email">
            <label class="form-label">Password</label>
            <input class="form-control mb-3" type="password" name="password" required>
            <button class="btn btn-primary w-100">Register</button>
        </form>
    </div>
    """
    return page(content)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Login successful.", "success")
            return redirect(url_for("index"))

        flash("Invalid username or password.", "danger")

    content = """
    <div class="card mx-auto p-4 shadow-sm" style="max-width:450px">
        <h3>Login</h3>
        <form method="post">
            <label class="form-label">Username</label>
            <input class="form-control mb-3" name="username" required>
            <label class="form-label">Password</label>
            <input class="form-control mb-3" type="password" name="password" required>
            <button class="btn btn-primary w-100">Login</button>
        </form>
    </div>
    """
    return page(content)


@app.route("/appointments", methods=["GET", "POST"])
def appointments():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()
    role = session["role"]
    user_id = session["user_id"]

    if request.method == "POST":
        if role != "Patient":
            conn.close()
            flash("Only patients can book appointments.", "danger")
            return redirect(url_for("appointments"))

        doctor_id = request.form.get("doctor_id", type=int)
        appointment_date = request.form.get("appointment_date", "")
        reason = request.form.get("reason", "").strip()

        doctor = conn.execute(
            "SELECT id FROM users WHERE id = ? AND role = 'Doctor'",
            (doctor_id,)
        ).fetchone()

        try:
            selected_date = date.fromisoformat(appointment_date)
        except ValueError:
            selected_date = None

        if not doctor or not selected_date or selected_date < date.today():
            flash("Choose a valid doctor and appointment date.", "danger")
        else:
            count = conn.execute("""
                SELECT COUNT(*) FROM appointments
                WHERE doctor_id = ? AND appointment_date = ?
                AND status != 'Rejected'
            """, (doctor_id, appointment_date)).fetchone()[0]

            if count >= 3:
                flash("This doctor already has three appointments on that date.", "danger")
            else:
                conn.execute("""
                    INSERT INTO appointments
                    (patient_id, doctor_id, appointment_date, reason, status, created_at)
                    VALUES (?, ?, ?, ?, 'Pending', CURRENT_TIMESTAMP)
                """, (user_id, doctor_id, appointment_date, reason))
                conn.commit()
                flash("Appointment booked successfully.", "success")

    if role == "Patient":
        doctors = conn.execute("""
            SELECT id, username, specialization FROM users
            WHERE role = 'Doctor' ORDER BY username
        """).fetchall()

        records = conn.execute("""
            SELECT a.*, u.username AS patient_name, d.username AS doctor_name
            FROM appointments a
            LEFT JOIN users u ON a.patient_id = u.id
            LEFT JOIN users d ON a.doctor_id = d.id
            WHERE a.patient_id = ?
            ORDER BY a.appointment_date DESC, a.id DESC
        """, (user_id,)).fetchall()

        content = """
        <div class="card p-4 mb-4">
            <h3>Book an Appointment</h3>
            <form method="post">
                <label class="form-label">Doctor</label>
                <select class="form-select mb-3" name="doctor_id" required>
                    {% for d in doctors %}
                    <option value="{{ d.id }}">{{ d.username }} - {{ d.specialization or 'General' }}</option>
                    {% endfor %}
                </select>
                <label class="form-label">Date</label>
                <input class="form-control mb-3" type="date" name="appointment_date"
                       min="{{ today }}" required>
                <label class="form-label">Reason</label>
                <input class="form-control mb-3" name="reason" required>
                <button class="btn btn-primary">Book Appointment</button>
            </form>
        </div>
        <h3>My Appointments</h3>
        {{ table|safe }}
        """
        table = make_table(records, False)
        conn.close()
        return page(content, doctors=doctors, today=date.today().isoformat(), table=table)

    if role == "Doctor":
        records = conn.execute("""
            SELECT a.*, u.username AS patient_name, d.username AS doctor_name
            FROM appointments a
            LEFT JOIN users u ON a.patient_id = u.id
            LEFT JOIN users d ON a.doctor_id = d.id
            WHERE a.doctor_id = ?
            ORDER BY a.appointment_date DESC, a.id DESC
        """, (user_id,)).fetchall()
    elif role == "Admin":
        records = conn.execute("""
            SELECT a.*, u.username AS patient_name, d.username AS doctor_name
            FROM appointments a
            LEFT JOIN users u ON a.patient_id = u.id
            LEFT JOIN users d ON a.doctor_id = d.id
            ORDER BY a.appointment_date DESC, a.id DESC
        """).fetchall()
    else:
        conn.close()
        flash("Invalid account role.", "danger")
        return redirect(url_for("index"))

    table = make_table(records, role in ("Admin", "Doctor"))
    conn.close()
    content = "<h3>Appointments</h3>{{ table|safe }}"
    if role == "Admin":
        content += '<p><a class="btn btn-secondary mt-3" href="{{ url_for(\'admin_users\') }}">Manage Users</a></p>'
    return page(content, table=table)


def make_table(records, can_manage):
    if not records:
        return "<p>No appointments found.</p>"

    html = """
    <div class="table-responsive"><table class="table table-bordered bg-white">
    <thead><tr><th>Patient</th><th>Doctor</th><th>Date</th>
    <th>Reason</th><th>Status</th><th>Actions</th></tr></thead><tbody>
    """
    for a in records:
        html += "<tr>"
        html += f"<td>{a['patient_name'] or 'Unknown'}</td>"
        html += f"<td>{a['doctor_name'] or 'Unknown'}</td>"
        html += f"<td>{a['appointment_date'] or ''}</td>"
        html += f"<td>{a['reason'] or ''}</td>"
        html += f"<td>{a['status'] or 'Pending'}</td><td>"

        if can_manage and a["status"] == "Pending":
            html += f"""
            <form method="post" action="/appointment/{a['id']}/approve" class="d-inline">
                <button class="btn btn-success btn-sm">Approve</button>
            </form>
            <form method="post" action="/appointment/{a['id']}/reject" class="d-inline">
                <button class="btn btn-danger btn-sm">Reject</button>
            </form>
            """
        else:
            html += "-"

        html += "</td></tr>"

    html += "</tbody></table></div>"
    return html


def update_appointment(appt_id, new_status):
    if not login_required():
        return redirect(url_for("login"))

    if session.get("role") not in ("Admin", "Doctor"):
        flash("You are not authorized to change appointments.", "danger")
        return redirect(url_for("appointments"))

    conn = get_db()
    appointment = conn.execute(
        "SELECT * FROM appointments WHERE id = ?", (appt_id,)
    ).fetchone()

    if not appointment:
        conn.close()
        flash("Appointment not found.", "danger")
        return redirect(url_for("appointments"))

    if session["role"] == "Doctor" and appointment["doctor_id"] != session["user_id"]:
        conn.close()
        flash("You can only manage your own appointments.", "danger")
        return redirect(url_for("appointments"))

    conn.execute(
        "UPDATE appointments SET status = ? WHERE id = ?",
        (new_status, appt_id)
    )
    conn.commit()
    conn.close()
    flash(f"Appointment {new_status.lower()}.", "success")
    return redirect(url_for("appointments"))


@app.route("/appointment/<int:appt_id>/approve", methods=["POST"])
def approve(appt_id):
    return update_appointment(appt_id, "Approved")


@app.route("/appointment/<int:appt_id>/reject", methods=["POST"])
def reject(appt_id):
    return update_appointment(appt_id, "Rejected")


@app.route("/admin/users")
def admin_users():
    if not role_required("Admin"):
        return redirect(url_for("login"))

    conn = get_db()
    users = conn.execute("""
        SELECT id, username, role, specialization, email
        FROM users ORDER BY id
    """).fetchall()
    conn.close()

    content = """
    <h3>Manage Users</h3>
    <a class="btn btn-primary mb-3" href="{{ url_for('admin_add_user') }}">Add User</a>
    <div class="table-responsive"><table class="table table-bordered bg-white">
    <tr><th>ID</th><th>Username</th><th>Role</th><th>Specialization</th><th>Email</th></tr>
    {% for u in users %}
    <tr>
        <td>{{ u.id }}</td><td>{{ u.username }}</td><td>{{ u.role }}</td>
        <td>{{ u.specialization or '' }}</td><td>{{ u.email or '' }}</td>
    </tr>
    {% endfor %}
    </table></div>
    """
    return page(content, users=users)


@app.route("/admin/users/add", methods=["GET", "POST"])
def admin_add_user():
    if not role_required("Admin"):
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        specialization = request.form.get("specialization", "").strip()
        email = request.form.get("email", "").strip()

        if not username or not password or role not in ("Admin", "Doctor", "Patient"):
            flash("Enter valid user details.", "danger")
        else:
            conn = get_db()
            try:
                conn.execute("""
                    INSERT INTO users
                    (username, password, role, specialization, full_name, email)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    username,
                    generate_password_hash(password),
                    role,
                    specialization,
                    username,
                    email
                ))
                conn.commit()
                flash("User added successfully.", "success")
                return redirect(url_for("admin_users"))
            except sqlite3.IntegrityError:
                flash("That username already exists.", "danger")
            finally:
                conn.close()

    content = """
    <div class="card p-4 mx-auto" style="max-width:500px">
        <h3>Add User</h3>
        <form method="post">
            <label class="form-label">Username</label>
            <input class="form-control mb-3" name="username" required>
            <label class="form-label">Password</label>
            <input class="form-control mb-3" type="password" name="password" required>
            <label class="form-label">Role</label>
            <select class="form-select mb-3" name="role" required>
                <option>Patient</option><option>Doctor</option><option>Admin</option>
            </select>
            <label class="form-label">Specialization (for doctors)</label>
            <input class="form-control mb-3" name="specialization">
            <label class="form-label">Email</label>
            <input class="form-control mb-3" type="email" name="email">
            <button class="btn btn-primary">Add User</button>
        </form>
    </div>
    """
    return page(content)


@app.route("/admin/users/update/<int:user_id>", methods=["POST"])
def admin_update_user(user_id):
    if not role_required("Admin"):
        return redirect(url_for("login"))

    role = request.form.get("role", "")
    specialization = request.form.get("specialization", "").strip()
    email = request.form.get("email", "").strip()

    if role not in ("Admin", "Doctor", "Patient"):
        flash("Invalid role.", "danger")
        return redirect(url_for("admin_users"))

    conn = get_db()
    conn.execute("""
        UPDATE users SET role = ?, specialization = ?, email = ?
        WHERE id = ?
    """, (role, specialization, email, user_id))
    conn.commit()
    conn.close()

    flash("User updated successfully.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
def admin_delete_user(user_id):
    if not role_required("Admin"):
        return redirect(url_for("login"))

    if user_id == session["user_id"]:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("admin_users"))

    conn = get_db()
    linked = conn.execute("""
        SELECT COUNT(*) FROM appointments
        WHERE patient_id = ? OR doctor_id = ?
    """, (user_id, user_id)).fetchone()[0]

    if linked:
        conn.close()
        flash("This user has appointments and cannot be deleted.", "danger")
        return redirect(url_for("admin_users"))

    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash("User deleted successfully.", "success")
    return redirect(url_for("admin_users"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=3000)
