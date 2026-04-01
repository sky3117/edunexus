import os, random, string
from datetime import datetime, timedelta
from functools import wraps
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, session, flash)
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-prod')
app.permanent_session_lifetime = timedelta(hours=24)

# ─── MAIL CONFIG ─────────────────────────────────────────────
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=os.getenv('MAIL_USERNAME')
)
mail = Mail(app)

# ─── DATABASE ────────────────────────────────────────────────
def get_db():
    try:
        return mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'edunexus'),
            ssl_disabled=False,
            connection_timeout=30
        )
    except Error as e:
        print(f"DB Error: {e}")
        return None

def init_db():
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            ssl_disabled=False,
            connection_timeout=30
        )
        cur = conn.cursor()
        db = os.getenv('DB_NAME', 'edunexus')
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}`")
        cur.execute(f"USE `{db}`")

        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role ENUM('admin','teacher','viewer') DEFAULT 'admin',
            is_verified TINYINT(1) DEFAULT 0,
            otp VARCHAR(6),
            otp_expires DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            roll_no VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100),
            phone VARCHAR(15),
            class VARCHAR(20),
            section VARCHAR(5),
            dob DATE,
            address TEXT,
            user_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS marks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT,
            subject VARCHAR(50),
            exam_type VARCHAR(30),
            marks_obtained FLOAT,
            total_marks FLOAT,
            exam_date DATE,
            user_id INT,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT,
            att_date DATE,
            status ENUM('Present','Absent','Late') DEFAULT 'Present',
            user_id INT,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE KEY uq_att (student_id, att_date)
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS fees (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT,
            fee_type VARCHAR(50),
            amount DECIMAL(10,2),
            paid_amount DECIMAL(10,2) DEFAULT 0,
            due_date DATE,
            paid_date DATE,
            status ENUM('Pending','Partial','Paid') DEFAULT 'Pending',
            user_id INT,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")

        conn.commit(); cur.close(); conn.close()
        print("✅ Database initialized!")
    except Error as e:
        print(f"Init DB Error: {e}")

# ─── AUTH HELPERS ────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(email, name, otp, purpose='verify'):
    try:
        subject = "EduNexus — Your OTP Code" if purpose=='verify' else "EduNexus — Password Reset OTP"
        body = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;background:#0d1117;color:#e6edf3;border-radius:12px;overflow:hidden">
          <div style="background:linear-gradient(135deg,#7c6dfa,#39d0d8);padding:28px;text-align:center">
            <h1 style="margin:0;font-size:24px;color:white">🎓 EduNexus</h1>
            <p style="margin:6px 0 0;color:rgba(255,255,255,.8);font-size:14px">Student Management System</p>
          </div>
          <div style="padding:32px">
            <p style="font-size:16px;margin:0 0 8px">Hello, <strong>{name}</strong>!</p>
            <p style="color:#8b949e;font-size:14px;margin:0 0 28px">
              {'Use the OTP below to verify your email address.' if purpose=='verify' else 'Use the OTP below to reset your password.'}
            </p>
            <div style="background:#161b22;border:2px dashed #7c6dfa;border-radius:12px;padding:24px;text-align:center;margin-bottom:24px">
              <div style="font-size:40px;font-weight:900;letter-spacing:12px;color:#7c6dfa">{otp}</div>
              <p style="color:#8b949e;font-size:12px;margin:8px 0 0">Valid for <strong style="color:#e6edf3">10 minutes</strong></p>
            </div>
            <p style="color:#484f58;font-size:12px;margin:0">If you didn't request this, please ignore this email.</p>
          </div>
          <div style="background:#161b22;padding:16px;text-align:center">
            <p style="color:#484f58;font-size:11px;margin:0">© 2024 EduNexus • Secure School Management</p>
          </div>
        </div>
        """
        msg = Message(subject=subject, recipients=[email], html=body)
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Mail error: {e}")
        return False

# ─── AUTH ROUTES ─────────────────────────────────────────────
@app.route('/')
def landing():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        data = request.json
        email = data.get('email','').strip().lower()
        password = data.get('password','')
        conn = get_db()
        if not conn: return jsonify({'error':'Database error'}), 500
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close(); conn.close()
        if not user: return jsonify({'error':'Email not registered'}), 401
        if not user['is_verified']: return jsonify({'error':'Please verify your email first','need_verify':True,'email':email}), 401
        if not check_password_hash(user['password'], password): return jsonify({'error':'Wrong password'}), 401
        session.permanent = True
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user['email']
        return jsonify({'success':True})
    return render_template('auth.html', page='login')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        data = request.json
        name  = data.get('name','').strip()
        email = data.get('email','').strip().lower()
        pwd   = data.get('password','')

        if not name or not email or not pwd:
            return jsonify({'error':'All fields required'}), 400

        if len(pwd) < 6:
            return jsonify({'error':'Password must be 6+ characters'}), 400

        conn = get_db()
        if not conn:
            return jsonify({'error':'Database error'}), 500

        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error':'Email already registered'}), 400

        otp = generate_otp()
        otp_exp = datetime.now() + timedelta(minutes=10)
        hashed = generate_password_hash(pwd)

        try:
            cur.execute(
                "INSERT INTO users (name,email,password,otp,otp_expires) VALUES (%s,%s,%s,%s,%s)",
                (name, email, hashed, otp, otp_exp)
            )
            conn.commit()
        except Error as e:
            cur.close()
            conn.close()
            return jsonify({'error': str(e)}), 400

        cur.close()
        conn.close()

        # 🔥 EMAIL DISABLED (IMPORTANT FIX)
        print("OTP is:", otp)

        # sent = send_otp_email(email, name, otp, 'verify')
        # if not sent:
        #     return jsonify({'error':'Failed to send OTP. Check email config.'}), 500

        return jsonify({'success': True, 'email': email})

    return render_template('auth.html', page='register')

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data  = request.json
    email = data.get('email','').strip().lower()
    otp   = data.get('otp','').strip()
    conn  = get_db()
    if not conn: return jsonify({'error':'Database error'}), 500
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    if not user:
        cur.close(); conn.close()
        return jsonify({'error':'User not found'}), 404
    if user['is_verified']:
        cur.close(); conn.close()
        return jsonify({'success':True, 'already':True})
    if user['otp'] != otp:
        cur.close(); conn.close()
        return jsonify({'error':'Invalid OTP'}), 400
    if datetime.now() > user['otp_expires']:
        cur.close(); conn.close()
        return jsonify({'error':'OTP expired. Please register again'}), 400
    cur.execute("UPDATE users SET is_verified=1, otp=NULL, otp_expires=NULL WHERE email=%s", (email,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({'success':True})

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    data  = request.json
    email = data.get('email','').strip().lower()
    conn  = get_db()
    if not conn: return jsonify({'error':'Database error'}), 500
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE email=%s AND is_verified=0", (email,))
    user = cur.fetchone()
    if not user:
        cur.close(); conn.close()
        return jsonify({'error':'User not found or already verified'}), 404
    otp = generate_otp()
    otp_exp = datetime.now() + timedelta(minutes=10)
    cur.execute("UPDATE users SET otp=%s, otp_expires=%s WHERE email=%s", (otp, otp_exp, email))
    conn.commit(); cur.close(); conn.close()
    send_otp_email(email, user['name'], otp, 'verify')
    return jsonify({'success':True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

# ─── DASHBOARD ───────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html',
        user_name=session.get('user_name'),
        user_email=session.get('user_email'))

# ─── API: STATS ──────────────────────────────────────────────
@app.route('/api/stats')
@login_required
def stats():
    uid = session['user_id']
    conn = get_db()
    if not conn: return jsonify({'error':'DB failed'}), 500
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) as c FROM students WHERE user_id=%s", (uid,))
    total = cur.fetchone()['c']
    today = datetime.today().date().isoformat()
    cur.execute("SELECT COUNT(*) as c FROM attendance WHERE user_id=%s AND att_date=%s AND status='Present'", (uid,today))
    present = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM fees WHERE user_id=%s AND status!='Paid'", (uid,))
    pending = cur.fetchone()['c']
    cur.execute("SELECT AVG(marks_obtained/total_marks*100) as a FROM marks WHERE user_id=%s AND total_marks>0", (uid,))
    avg_row = cur.fetchone()
    avg = round(avg_row['a'] or 0, 1)
    cur.execute("SELECT class, COUNT(*) as cnt FROM students WHERE user_id=%s GROUP BY class ORDER BY class", (uid,))
    classes = cur.fetchall()
    cur.execute("""SELECT s.name, ROUND(AVG(m.marks_obtained/m.total_marks*100),1) as avg
        FROM students s JOIN marks m ON s.id=m.student_id
        WHERE m.user_id=%s AND m.total_marks>0 GROUP BY s.id ORDER BY avg DESC LIMIT 5""", (uid,))
    top = cur.fetchall()
    cur.close(); conn.close()
    return jsonify({'total':total,'present':present,'pending':pending,'avg':avg,'classes':classes,'top':top})

# ─── API: STUDENTS ───────────────────────────────────────────
@app.route('/api/students', methods=['GET'])
@login_required
def get_students():
    uid = session['user_id']
    conn = get_db(); cur = conn.cursor(dictionary=True)
    s = request.args.get('search',''); c = request.args.get('class','')
    q = "SELECT * FROM students WHERE user_id=%s"; p = [uid]
    if s:
        q += " AND (name LIKE %s OR roll_no LIKE %s OR email LIKE %s)"
        p += [f'%{s}%']*3
    if c: q += " AND class=%s"; p.append(c)
    q += " ORDER BY created_at DESC"
    cur.execute(q, p)
    rows = cur.fetchall()
    for r in rows:
        r['dob'] = str(r['dob']) if r.get('dob') else ''
        r['created_at'] = str(r['created_at']) if r.get('created_at') else ''
    cur.close(); conn.close(); return jsonify(rows)

@app.route('/api/students', methods=['POST'])
@login_required
def add_student():
    uid = session['user_id']
    d = request.json; conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO students (roll_no,name,email,phone,class,section,dob,address,user_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (d['roll_no'],d['name'],d.get('email',''),d.get('phone',''),d.get('class',''),d.get('section',''),d.get('dob') or None,d.get('address',''),uid))
        conn.commit(); return jsonify({'success':True,'id':cur.lastrowid})
    except Error as e: return jsonify({'error':str(e)}), 400
    finally: cur.close(); conn.close()

@app.route('/api/students/<int:sid>', methods=['GET'])
@login_required
def get_student(sid):
    uid = session['user_id']
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM students WHERE id=%s AND user_id=%s", (sid,uid))
    s = cur.fetchone()
    if s:
        s['dob'] = str(s['dob']) if s.get('dob') else ''
        s['created_at'] = str(s['created_at']) if s.get('created_at') else ''
    cur.close(); conn.close(); return jsonify(s)

@app.route('/api/students/<int:sid>', methods=['PUT'])
@login_required
def update_student(sid):
    uid = session['user_id']
    d = request.json; conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("UPDATE students SET roll_no=%s,name=%s,email=%s,phone=%s,class=%s,section=%s,dob=%s,address=%s WHERE id=%s AND user_id=%s",
            (d['roll_no'],d['name'],d.get('email',''),d.get('phone',''),d.get('class',''),d.get('section',''),d.get('dob') or None,d.get('address',''),sid,uid))
        conn.commit(); return jsonify({'success':True})
    except Error as e: return jsonify({'error':str(e)}), 400
    finally: cur.close(); conn.close()

@app.route('/api/students/<int:sid>', methods=['DELETE'])
@login_required
def delete_student(sid):
    uid = session['user_id']
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE id=%s AND user_id=%s", (sid,uid))
    conn.commit(); cur.close(); conn.close(); return jsonify({'success':True})

# ─── API: MARKS ──────────────────────────────────────────────
def get_grade(o,t):
    if not t: return 'N/A'
    p = o/t*100
    return 'A+' if p>=90 else 'A' if p>=80 else 'B+' if p>=70 else 'B' if p>=60 else 'C' if p>=50 else 'D' if p>=40 else 'F'

@app.route('/api/marks', methods=['GET'])
@login_required
def get_marks():
    uid = session['user_id']
    conn = get_db(); cur = conn.cursor(dictionary=True)
    sid = request.args.get('student_id','')
    if sid:
        cur.execute("SELECT m.*,s.name,s.roll_no FROM marks m JOIN students s ON m.student_id=s.id WHERE m.user_id=%s AND m.student_id=%s ORDER BY m.exam_date DESC", (uid,sid))
    else:
        cur.execute("SELECT m.*,s.name,s.roll_no FROM marks m JOIN students s ON m.student_id=s.id WHERE m.user_id=%s ORDER BY m.exam_date DESC LIMIT 200", (uid,))
    rows = cur.fetchall()
    for r in rows:
        r['exam_date'] = str(r['exam_date']) if r.get('exam_date') else ''
        r['grade'] = get_grade(r['marks_obtained'], r['total_marks'])
        r['pct'] = round(r['marks_obtained']/r['total_marks']*100,1) if r['total_marks'] else 0
    cur.close(); conn.close(); return jsonify(rows)

@app.route('/api/marks', methods=['POST'])
@login_required
def add_marks():
    uid = session['user_id']
    d = request.json; conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO marks (student_id,subject,exam_type,marks_obtained,total_marks,exam_date,user_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (d['student_id'],d['subject'],d['exam_type'],d['marks_obtained'],d['total_marks'],d.get('exam_date') or None,uid))
        conn.commit(); return jsonify({'success':True})
    except Error as e: return jsonify({'error':str(e)}), 400
    finally: cur.close(); conn.close()

@app.route('/api/marks/<int:mid>', methods=['DELETE'])
@login_required
def delete_mark(mid):
    uid = session['user_id']
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM marks WHERE id=%s AND user_id=%s", (mid,uid))
    conn.commit(); cur.close(); conn.close(); return jsonify({'success':True})

# ─── API: ATTENDANCE ─────────────────────────────────────────
@app.route('/api/attendance', methods=['GET'])
@login_required
def get_attendance():
    uid = session['user_id']
    conn = get_db(); cur = conn.cursor(dictionary=True)
    att_date = request.args.get('date', datetime.today().date().isoformat())
    cur.execute("""SELECT s.id,s.name,s.roll_no,s.class,s.section,
        COALESCE(a.status,'Not Marked') as status FROM students s
        LEFT JOIN attendance a ON s.id=a.student_id AND a.att_date=%s AND a.user_id=%s
        WHERE s.user_id=%s ORDER BY s.class,s.roll_no""", (att_date,uid,uid))
    rows = cur.fetchall()
    cur.close(); conn.close(); return jsonify(rows)

@app.route('/api/attendance', methods=['POST'])
@login_required
def mark_attendance():
    uid = session['user_id']
    d = request.json; conn = get_db(); cur = conn.cursor()
    try:
        for rec in d['records']:
            cur.execute("INSERT INTO attendance (student_id,att_date,status,user_id) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE status=%s,user_id=%s",
                (rec['student_id'],d['date'],rec['status'],uid,rec['status'],uid))
        conn.commit(); return jsonify({'success':True})
    except Error as e: return jsonify({'error':str(e)}), 400
    finally: cur.close(); conn.close()

@app.route('/api/attendance/summary')
@login_required
def att_summary():
    uid = session['user_id']
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("""SELECT s.id,s.name,s.roll_no,s.class,
        COUNT(a.id) as total, SUM(a.status='Present') as present,
        SUM(a.status='Absent') as absent, SUM(a.status='Late') as late,
        ROUND(SUM(a.status='Present')/NULLIF(COUNT(a.id),0)*100,1) as pct
        FROM students s LEFT JOIN attendance a ON s.id=a.student_id AND a.user_id=%s
        WHERE s.user_id=%s GROUP BY s.id ORDER BY pct DESC""", (uid,uid))
    rows = cur.fetchall(); cur.close(); conn.close(); return jsonify(rows)

# ─── API: FEES ───────────────────────────────────────────────
@app.route('/api/fees', methods=['GET'])
@login_required
def get_fees():
    uid = session['user_id']
    conn = get_db(); cur = conn.cursor(dictionary=True)
    st = request.args.get('status','')
    q = "SELECT f.*,s.name,s.roll_no FROM fees f JOIN students s ON f.student_id=s.id WHERE f.user_id=%s"; p = [uid]
    if st: q += " AND f.status=%s"; p.append(st)
    q += " ORDER BY f.due_date DESC"
    cur.execute(q,p); rows = cur.fetchall()
    for r in rows:
        r['due_date']  = str(r['due_date'])  if r.get('due_date')  else ''
        r['paid_date'] = str(r['paid_date']) if r.get('paid_date') else ''
        r['balance']   = float(r['amount']) - float(r['paid_amount'])
    cur.close(); conn.close(); return jsonify(rows)

@app.route('/api/fees', methods=['POST'])
@login_required
def add_fee():
    uid = session['user_id']
    d = request.json; conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO fees (student_id,fee_type,amount,paid_amount,due_date,paid_date,status,user_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (d['student_id'],d['fee_type'],d['amount'],d.get('paid_amount',0),d.get('due_date') or None,d.get('paid_date') or None,d.get('status','Pending'),uid))
        conn.commit(); return jsonify({'success':True})
    except Error as e: return jsonify({'error':str(e)}), 400
    finally: cur.close(); conn.close()

@app.route('/api/fees/<int:fid>', methods=['PUT'])
@login_required
def update_fee(fid):
    uid = session['user_id']
    d = request.json; conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE fees SET paid_amount=%s,paid_date=%s,status=%s WHERE id=%s AND user_id=%s",
        (d['paid_amount'],d.get('paid_date') or None,d['status'],fid,uid))
    conn.commit(); cur.close(); conn.close(); return jsonify({'success':True})

@app.route('/api/fees/<int:fid>', methods=['DELETE'])
@login_required
def delete_fee(fid):
    uid = session['user_id']
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM fees WHERE id=%s AND user_id=%s", (fid,uid))
    conn.commit(); cur.close(); conn.close(); return jsonify({'success':True})

# ─── EXPORT EXCEL ─────────────────────────────────────
@app.route("/export")
@login_required
def export():
    uid = session['user_id']
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM students WHERE user_id=%s", (uid,))
    data = cur.fetchall()

    cur.close()
    conn.close()

    if not data:
        return "No data found ❌"

    import pandas as pd
    df = pd.DataFrame(data)

    file_path = "students.xlsx"
    df.to_excel(file_path, index=False)

    from flask import send_file
    return send_file(file_path, as_attachment=True)

# ─── RUN ─────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
