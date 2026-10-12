import os, re, uuid
from functools import wraps

import boto3
import pymysql
from dotenv import load_dotenv
from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, url_for)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", 100)) * 1024 * 1024

BUCKET = os.environ["S3_BUCKET"]
# On EC2 the IAM role supplies credentials automatically - no keys in code.
s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-south-1"))

BLOCKED_EXT = {"exe", "bat", "cmd", "sh", "msi", "dll", "scr", "com", "js", "php"}
RESUME_EXT = {"pdf", "doc", "docx"}


def db():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        charset="utf8mb4",
    )


def clean_segment(name):
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return name or "file"


def clean_path(path):
    parts = [clean_segment(p) for p in path.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    return "/".join(parts)


def ext(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def store(cur, member_id, fs, category):
    """Upload one FileStorage to S3 and record it in MySQL."""
    raw = fs.filename or ""
    if not raw or ext(raw) in BLOCKED_EXT:
        return False
    rel = clean_path(raw)                       # keeps folder structure for folder uploads
    base = rel.rsplit("/", 1)[-1]
    if category == "resume" and ext(base) not in RESUME_EXT:
        return False
    sub = rel if category == "folder" else f"{uuid.uuid4().hex[:8]}_{base}"
    key = f"members/{member_id}/{category}/{sub}"
    s3.upload_fileobj(fs.stream, BUCKET, key,
                      ExtraArgs={"ContentType": fs.mimetype or "application/octet-stream",
                                 "ServerSideEncryption": "AES256"})
    size = fs.stream.tell()
    cur.execute(
        "INSERT INTO uploads (member_id, category, s3_key, original_name, relative_path, content_type, size_bytes)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (member_id, category, key, base, rel if category == "folder" else None, fs.mimetype, size),
    )
    return True


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        auth = request.authorization
        if not auth or auth.username != os.environ.get("ADMIN_USER") or auth.password != os.environ.get("ADMIN_PASS"):
            return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Admin"'})
        return f(*a, **kw)
    return wrapper


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("index.html")

    f = request.form
    name, email = f.get("full_name", "").strip(), f.get("email", "").strip().lower()
    if not name or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        flash("Please enter a valid name and email.")
        return render_template("index.html", form=f), 400

    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM members WHERE email=%s", (email,))
            if cur.fetchone():
                flash("This email is already registered.")
                return render_template("index.html", form=f), 409
            cur.execute(
                "INSERT INTO members (full_name,email,phone,city,country,job_title,company,aws_level,"
                "certifications,skills,linkedin_url,bio) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (name, email, f.get("phone"), f.get("city"), f.get("country"), f.get("job_title"),
                 f.get("company"), f.get("aws_level") or "Beginner", f.get("certifications"),
                 f.get("skills"), f.get("linkedin_url"), f.get("bio")),
            )
            mid = cur.lastrowid
            count = 0
            resume = request.files.get("resume")
            if resume and store(cur, mid, resume, "resume"):
                count += 1
            for fs in request.files.getlist("files"):
                count += store(cur, mid, fs, "file")
            for fs in request.files.getlist("folder"):
                count += store(cur, mid, fs, "folder")
    finally:
        conn.close()
    return render_template("thanks.html", name=name, count=count)


@app.route("/admin")
@admin_required
def admin():
    conn = db()
    with conn.cursor() as cur:
        cur.execute("SELECT m.*, (SELECT COUNT(*) FROM uploads u WHERE u.member_id=m.id) AS n_files "
                    "FROM members m ORDER BY m.created_at DESC")
        members = cur.fetchall()
    conn.close()
    return render_template("admin.html", members=members)


@app.route("/admin/member/<int:mid>")
@admin_required
def member(mid):
    conn = db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM members WHERE id=%s", (mid,))
        m = cur.fetchone()
        if not m:
            abort(404)
        cur.execute("SELECT * FROM uploads WHERE member_id=%s ORDER BY category, relative_path, original_name", (mid,))
        files = cur.fetchall()
    conn.close()
    return render_template("member.html", m=m, files=files)


@app.route("/admin/download/<int:upload_id>")
@admin_required
def download(upload_id):
    conn = db()
    with conn.cursor() as cur:
        cur.execute("SELECT s3_key, original_name FROM uploads WHERE id=%s", (upload_id,))
        u = cur.fetchone()
    conn.close()
    if not u:
        abort(404)
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": u["s3_key"],
                "ResponseContentDisposition": f'attachment; filename="{u["original_name"]}"'},
        ExpiresIn=300,
    )
    return redirect(url)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
