import os
import sqlite3
import secrets
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "online-job-portal-secret")
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DB_PATH = os.path.join(app.root_path, "database.db")
ALLOWED_EXTENSIONS = {"pdf", "docx"}
JOB_TYPES = ["Full Time", "Part Time", "Contract", "Remote", "Internship"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            password TEXT NOT NULL,
            resume TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            salary TEXT NOT NULL,
            experience TEXT NOT NULL,
            job_type TEXT NOT NULL,
            skills TEXT NOT NULL,
            description TEXT NOT NULL,
            posted_date TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            applied_date TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS saved_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            UNIQUE(user_id, job_id)
        );
        """
    )

    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing_admin = db.execute("SELECT id FROM admin WHERE username = ?", (admin_username,)).fetchone()
    if not existing_admin:
        db.execute(
            "INSERT INTO admin (username, password) VALUES (?, ?)",
            (admin_username, generate_password_hash(admin_password)),
        )

    if db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0:
        sample_jobs = [
            ("Senior Python Developer", "Northwind Labs", "Remote", "$140k - $180k", "4+ years", "Remote", "Python Flask SQL REST APIs", "Build scalable backend services and collaborate with top engineering teams."),
            ("Frontend Engineer", "Bright Systems", "New York", "$120k - $160k", "3+ years", "Full Time", "JavaScript HTML CSS React", "Create polished, accessible user interfaces for enterprise products."),
            ("Data Analyst", "Insight AI", "Chicago", "$90k - $115k", "2+ years", "Contract", "SQL Excel Power BI", "Turn business data into actionable insights for key clients."),
            ("Product Designer", "Nova Studio", "Austin", "$100k - $130k", "3+ years", "Full Time", "Figma UI UX", "Design intuitive experiences for modern web and mobile products."),
        ]
        db.executemany(
            "INSERT INTO jobs (title, company, location, salary, experience, job_type, skills, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            sample_jobs,
        )

    db.commit()


with app.app_context():
    init_db()


@app.context_processor
def inject_globals():
    return {
        "session_user": session.get("user_id"),
        "session_admin": session.get("admin_id"),
        "job_types": JOB_TYPES,
    }


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Admin access required.", "error")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)

    return decorated_function


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_resume(file_storage):
    if file_storage is None or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        raise ValueError("Only PDF and DOCX files are supported.")
    filename = secure_filename(file_storage.filename)
    unique_name = f"{secrets.token_hex(8)}_{filename}"
    file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
    return unique_name


@app.route("/")
def index():
    db = get_db()
    jobs = db.execute(
        "SELECT * FROM jobs ORDER BY id DESC LIMIT 6"
    ).fetchall()
    return render_template("index.html", jobs=jobs)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not fullname or not email or not phone or not password or not confirm_password:
            flash("All fields are required.", "error")
        elif "@" not in email or "." not in email:
            flash("Please enter a valid email address.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            db = get_db()
            existing_user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing_user:
                flash("Email already exists. Please log in instead.", "error")
            else:
                db.execute(
                    "INSERT INTO users (fullname, email, phone, password) VALUES (?, ?, ?, ?)",
                    (fullname, email, phone, generate_password_hash(password)),
                )
                db.commit()
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["fullname"]
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    jobs_applied = db.execute("SELECT COUNT(*) AS count FROM applications WHERE user_id = ?", (session["user_id"],)).fetchone()["count"]
    jobs_saved = db.execute("SELECT COUNT(*) AS count FROM saved_jobs WHERE user_id = ?", (session["user_id"],)).fetchone()["count"]
    recent_jobs = db.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 4").fetchall()
    return render_template(
        "dashboard.html",
        user=user,
        jobs_applied=jobs_applied,
        jobs_saved=jobs_saved,
        recent_jobs=recent_jobs,
    )


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not fullname or not email or not phone:
            flash("Full name, email, and phone are required.", "error")
        elif "@" not in email or "." not in email:
            flash("Please enter a valid email address.", "error")
        else:
            existing_email = db.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?",
                (email, session["user_id"]),
            ).fetchone()
            if existing_email:
                flash("That email is already in use.", "error")
            else:
                if password:
                    db.execute(
                        "UPDATE users SET fullname = ?, email = ?, phone = ?, password = ? WHERE id = ?",
                        (fullname, email, phone, generate_password_hash(password), session["user_id"]),
                    )
                else:
                    db.execute(
                        "UPDATE users SET fullname = ?, email = ?, phone = ? WHERE id = ?",
                        (fullname, email, phone, session["user_id"]),
                    )
                resume_file = request.files.get("resume")
                if resume_file and resume_file.filename:
                    try:
                        resume_name = save_resume(resume_file)
                    except ValueError as exc:
                        flash(str(exc), "error")
                    else:
                        if resume_name:
                            db.execute("UPDATE users SET resume = ? WHERE id = ?", (resume_name, session["user_id"]))
                db.commit()
                flash("Profile updated successfully.", "success")
                return redirect(url_for("profile"))

    return render_template("profile.html", user=user)


@app.route("/jobs")
def jobs():
    db = get_db()
    q = request.args.get("q", "").strip()
    company = request.args.get("company", "").strip()
    location = request.args.get("location", "").strip()
    skills = request.args.get("skills", "").strip()
    job_type = request.args.get("job_type", "").strip()

    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if q:
        query += " AND (title LIKE ? OR company LIKE ? OR location LIKE ? OR skills LIKE ?)"
        search_term = f"%{q}%"
        params.extend([search_term, search_term, search_term, search_term])
    if company:
        query += " AND company LIKE ?"
        params.append(f"%{company}%")
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    if skills:
        query += " AND skills LIKE ?"
        params.append(f"%{skills}%")
    if job_type:
        query += " AND job_type = ?"
        params.append(job_type)

    query += " ORDER BY id DESC"
    matched_jobs = db.execute(query, params).fetchall()

    page = request.args.get("page", 1, type=int)
    per_page = 6
    total_pages = max(1, (len(matched_jobs) + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    page_jobs = matched_jobs[start:end]

    return render_template(
        "jobs.html",
        jobs=page_jobs,
        page=page,
        total_pages=total_pages,
        q=q,
        company=company,
        location=location,
        skills=skills,
        job_type=job_type,
    )


@app.route("/job/<int:job_id>")
def job_details(job_id):
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        abort(404)

    saved = False
    applied = False
    if session.get("user_id"):
        saved = db.execute("SELECT 1 FROM saved_jobs WHERE user_id = ? AND job_id = ?", (session["user_id"], job_id)).fetchone() is not None
        applied = db.execute("SELECT 1 FROM applications WHERE user_id = ? AND job_id = ?", (session["user_id"], job_id)).fetchone() is not None

    return render_template("job_details.html", job=job, saved=saved, applied=applied)


@app.route("/save-job/<int:job_id>", methods=["POST"])
@login_required
def save_job(job_id):
    db = get_db()
    existing = db.execute("SELECT 1 FROM saved_jobs WHERE user_id = ? AND job_id = ?", (session["user_id"], job_id)).fetchone()
    if not existing:
        db.execute("INSERT INTO saved_jobs (user_id, job_id) VALUES (?, ?)", (session["user_id"], job_id))
        db.commit()
        flash("Job saved to favourites.", "success")
    else:
        flash("This job is already in your favourites.", "error")
    return redirect(url_for("job_details", job_id=job_id))


@app.route("/unsave-job/<int:job_id>", methods=["POST"])
@login_required
def unsave_job(job_id):
    db = get_db()
    db.execute("DELETE FROM saved_jobs WHERE user_id = ? AND job_id = ?", (session["user_id"], job_id))
    db.commit()
    flash("Job removed from favourites.", "success")
    return redirect(url_for("saved_jobs"))


@app.route("/saved-jobs")
@login_required
def saved_jobs():
    db = get_db()
    saved = db.execute(
        """
        SELECT j.*, s.id AS saved_id
        FROM saved_jobs s
        JOIN jobs j ON s.job_id = j.id
        WHERE s.user_id = ?
        ORDER BY s.id DESC
        """,
        (session["user_id"],),
    ).fetchall()
    return render_template("saved_jobs.html", saved_jobs=saved)


@app.route("/apply/<int:job_id>", methods=["GET", "POST"])
@login_required
def apply_job(job_id):
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        abort(404)

    existing = db.execute("SELECT 1 FROM applications WHERE user_id = ? AND job_id = ?", (session["user_id"], job_id)).fetchone()
    if existing:
        flash("You have already applied for this job.", "error")
        return redirect(url_for("applied_jobs"))

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        db.execute(
            "INSERT INTO applications (user_id, job_id, status) VALUES (?, ?, ?)",
            (session["user_id"], job_id, "Pending"),
        )
        db.commit()
        flash("Application submitted successfully.", "success")
        return redirect(url_for("applied_jobs"))

    return render_template("apply.html", job=job, message="")


@app.route("/applied-jobs")
@login_required
def applied_jobs():
    db = get_db()
    applications = db.execute(
        """
        SELECT a.id, a.status, a.applied_date, j.title, j.company
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.user_id = ?
        ORDER BY a.id DESC
        """,
        (session["user_id"],),
    ).fetchall()
    return render_template("applications.html", applications=applications)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = get_db().execute("SELECT * FROM admin WHERE username = ?", (username,)).fetchone()
        if admin and check_password_hash(admin["password"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["username"]
            flash("Admin logged in successfully.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "error")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_name", None)
    flash("Admin logged out.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    jobs_count = db.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"]
    users_count = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    applications_count = db.execute("SELECT COUNT(*) AS count FROM applications").fetchone()["count"]
    latest_jobs = db.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 5").fetchall()
    return render_template(
        "admin_dashboard.html",
        jobs_count=jobs_count,
        users_count=users_count,
        applications_count=applications_count,
        latest_jobs=latest_jobs,
    )


@app.route("/admin/jobs/add", methods=["GET", "POST"])
@admin_required
def add_job():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        company = request.form.get("company", "").strip()
        location = request.form.get("location", "").strip()
        salary = request.form.get("salary", "").strip()
        experience = request.form.get("experience", "").strip()
        job_type = request.form.get("job_type", "").strip()
        skills = request.form.get("skills", "").strip()
        description = request.form.get("description", "").strip()

        if not all([title, company, location, salary, experience, job_type, skills, description]):
            flash("All job fields are required.", "error")
        else:
            db = get_db()
            db.execute(
                "INSERT INTO jobs (title, company, location, salary, experience, job_type, skills, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (title, company, location, salary, experience, job_type, skills, description),
            )
            db.commit()
            flash("Job added successfully.", "success")
            return redirect(url_for("manage_jobs"))

    return render_template("add_job.html")


@app.route("/admin/jobs")
@admin_required
def manage_jobs():
    db = get_db()
    q = request.args.get("q", "").strip()
    job_type = request.args.get("job_type", "").strip()

    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if q:
        query += " AND (title LIKE ? OR company LIKE ? OR location LIKE ? OR skills LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term, term])
    if job_type:
        query += " AND job_type = ?"
        params.append(job_type)
    query += " ORDER BY id DESC"
    jobs = db.execute(query, params).fetchall()
    return render_template("manage_jobs.html", jobs=jobs, q=q, job_type=job_type)


@app.route("/admin/jobs/edit/<int:job_id>", methods=["GET", "POST"])
@admin_required
def edit_job(job_id):
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        company = request.form.get("company", "").strip()
        location = request.form.get("location", "").strip()
        salary = request.form.get("salary", "").strip()
        experience = request.form.get("experience", "").strip()
        job_type = request.form.get("job_type", "").strip()
        skills = request.form.get("skills", "").strip()
        description = request.form.get("description", "").strip()

        if not all([title, company, location, salary, experience, job_type, skills, description]):
            flash("All fields are required.", "error")
        else:
            db.execute(
                "UPDATE jobs SET title = ?, company = ?, location = ?, salary = ?, experience = ?, job_type = ?, skills = ?, description = ? WHERE id = ?",
                (title, company, location, salary, experience, job_type, skills, description, job_id),
            )
            db.commit()
            flash("Job updated successfully.", "success")
            return redirect(url_for("manage_jobs"))

    return render_template("edit_job.html", job=job)


@app.route("/admin/jobs/delete/<int:job_id>", methods=["POST"])
@admin_required
def delete_job(job_id):
    db = get_db()
    db.execute("DELETE FROM applications WHERE job_id = ?", (job_id,))
    db.execute("DELETE FROM saved_jobs WHERE job_id = ?", (job_id,))
    db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    db.commit()
    flash("Job deleted successfully.", "success")
    return redirect(url_for("manage_jobs"))


@app.route("/admin/users")
@admin_required
def manage_users():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    return render_template("manage_users.html", users=users)


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    db = get_db()
    db.execute("DELETE FROM applications WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM saved_jobs WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    flash("User deleted successfully.", "success")
    return redirect(url_for("manage_users"))


@app.route("/admin/applications")
@admin_required
def manage_applications():
    db = get_db()
    applications = db.execute(
        """
        SELECT a.id, a.status, a.applied_date, u.fullname, u.email, j.title, j.company
        FROM applications a
        JOIN users u ON a.user_id = u.id
        JOIN jobs j ON a.job_id = j.id
        ORDER BY a.id DESC
        """
    ).fetchall()
    return render_template("manage_applications.html", applications=applications)


@app.route("/admin/applications/<int:application_id>/status", methods=["POST"])
@admin_required
def update_application_status(application_id):
    status = request.form.get("status", "Pending")
    db = get_db()
    db.execute("UPDATE applications SET status = ? WHERE id = ?", (status, application_id))
    db.commit()
    flash("Application status updated.", "success")
    return redirect(url_for("manage_applications"))


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
