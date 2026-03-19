"""Volunteer routes — v2"""
from flask import render_template, request, redirect, url_for, flash, session, make_response, Response
from volunteer import volunteer_bp
from db import get_db
from auth.routes import login_required
import io


# ── GUARDS ──────────────────────────────────────────────────────────────────

def vol_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'volunteer':
            flash('Volunteer access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ── HELPERS ──────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── DASHBOARD ────────────────────────────────────────────────────────────────

@volunteer_bp.route('/dashboard')
@login_required
@vol_required
def dashboard():
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    vol  = db.execute('SELECT * FROM volunteers WHERE user_id=?', (session['user_id'],)).fetchone()

    applications = []
    upcoming     = []
    certificates = []

    if vol:
        applications = db.execute('''
            SELECT app.id, app.status, app.role_applied, app.created_at,
                   act.title AS act_title, act.start_date AS act_date,
                   act.location AS act_location, u.name AS org_name
            FROM applications app
            JOIN activities act ON app.activity_id = act.id
            JOIN organizations org ON act.org_id = org.id
            JOIN users u ON org.user_id = u.id
            WHERE app.volunteer_id = ?
            ORDER BY app.created_at DESC
        ''', (vol['id'],)).fetchall()

        upcoming = db.execute('''
            SELECT a.id, a.role, act.title AS act_title,
                   act.start_date AS act_date, act.location AS act_location,
                   act.id AS act_id
            FROM assignments a
            JOIN activities act ON a.activity_id = act.id
            WHERE a.volunteer_id = ?
            ORDER BY act.start_date ASC
        ''', (vol['id'],)).fetchall()

        certificates = db.execute('''
            SELECT c.*, act.title AS act_title, act.start_date AS act_date,
                   u.name AS org_name, c.issued_at
            FROM certificates c
            JOIN activities act ON c.activity_id = act.id
            JOIN organizations org ON act.org_id = org.id
            JOIN users u ON org.user_id = u.id
            WHERE c.volunteer_id = ?
            ORDER BY c.issued_at DESC
        ''', (vol['id'],)).fetchall()

    stats = {
        'applied':      db.execute(
            'SELECT COUNT(*) FROM applications WHERE volunteer_id=?',
            (vol['id'],)).fetchone()[0] if vol else 0,
        'approved':     db.execute(
            "SELECT COUNT(*) FROM applications WHERE volunteer_id=? AND status='approved'",
            (vol['id'],)).fetchone()[0] if vol else 0,
        'tasks':        db.execute(
            'SELECT COUNT(*) FROM assignments WHERE volunteer_id=?',
            (vol['id'],)).fetchone()[0] if vol else 0,
        'certificates': len(certificates),
    }

    return render_template(
        'volunteer/dashboard.html',
        current_user=user, volunteer=vol,
        applications=applications, upcoming=upcoming,
        certificates=certificates, stats=stats,
    )


# ── ACTIVITIES ───────────────────────────────────────────────────────────────

@volunteer_bp.route('/activities')
@login_required
@vol_required
def activities():
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    vol  = db.execute('SELECT * FROM volunteers WHERE user_id=?', (session['user_id'],)).fetchone()

    acts = db.execute('''
        SELECT act.*, u.name AS org_name,
               (SELECT COUNT(*) FROM assignments WHERE activity_id = act.id) AS assigned_count,
               (SELECT COALESCE(SUM(total), 0) FROM activity_roles WHERE activity_id = act.id) AS total_slots,
               (SELECT COUNT(*) FROM activity_days WHERE activity_id = act.id) AS day_count
        FROM activities act
        JOIN organizations org ON act.org_id = org.id
        JOIN users u ON org.user_id = u.id
        WHERE act.status = 'open'
        ORDER BY act.created_at DESC
    ''').fetchall()

    applied_ids = []
    if vol:
        applied_ids = [r[0] for r in db.execute(
            'SELECT activity_id FROM applications WHERE volunteer_id=?', (vol['id'],)
        ).fetchall()]

    roles_map = {}
    for act in acts:
        roles_map[act['id']] = db.execute(
            'SELECT * FROM activity_roles WHERE activity_id=?', (act['id'],)
        ).fetchall()

    return render_template(
        'volunteer/activities.html',
        current_user=user, activities=acts,
        applied_ids=applied_ids, roles_map=roles_map,
    )


# ── APPLY ────────────────────────────────────────────────────────────────────

@volunteer_bp.route('/apply/<int:activity_id>', methods=['POST'])
@login_required
@vol_required
def apply(activity_id):
    db  = get_db()
    vol = db.execute('SELECT * FROM volunteers WHERE user_id=?', (session['user_id'],)).fetchone()

    if not vol:
        flash('Volunteer profile not found.', 'danger')
        return redirect(url_for('volunteer.activities'))

    if db.execute(
        'SELECT id FROM applications WHERE volunteer_id=? AND activity_id=?',
        (vol['id'], activity_id)
    ).fetchone():
        flash('You have already applied for this activity.', 'warning')
        return redirect(url_for('volunteer.activities'))

    role       = request.form.get('role', 'General Volunteer')
    motivation = request.form.get('motivation', '')
    db.execute(
        'INSERT INTO applications (volunteer_id, activity_id, role_applied, motivation) VALUES (?,?,?,?)',
        (vol['id'], activity_id, role, motivation),
    )
    db.commit()
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('volunteer.dashboard'))


# ── PROFILE ──────────────────────────────────────────────────────────────────

@volunteer_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@vol_required
def profile():
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    vol  = db.execute('SELECT * FROM volunteers WHERE user_id=?', (session['user_id'],)).fetchone()

    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        bio     = request.form.get('bio', '')
        skills  = request.form.get('skills', '')
        phone   = request.form.get('phone', '')
        college = request.form.get('college', '')
        year    = request.form.get('year', '')

        db.execute('UPDATE users SET name=? WHERE id=?', (name, session['user_id']))
        if vol:
            db.execute(
                'UPDATE volunteers SET bio=?, skills=?, phone=?, college=?, year=? WHERE user_id=?',
                (bio, skills, phone, college, year, session['user_id']),
            )
        else:
            db.execute(
                'INSERT INTO volunteers (user_id, bio, skills, phone, college, year) VALUES (?,?,?,?,?,?)',
                (session['user_id'], bio, skills, phone, college, year),
            )
        db.commit()
        session['user_name'] = name
        flash('Profile updated!', 'success')
        return redirect(url_for('volunteer.profile'))

    stats = {
        'total_applied':   db.execute(
            'SELECT COUNT(*) FROM applications WHERE volunteer_id=?',
            (vol['id'],)).fetchone()[0] if vol else 0,
        'total_completed': db.execute(
            'SELECT COUNT(*) FROM certificates WHERE volunteer_id=?',
            (vol['id'],)).fetchone()[0] if vol else 0,
        'certificates':    db.execute(
            'SELECT COUNT(*) FROM certificates WHERE volunteer_id=?',
            (vol['id'],)).fetchone()[0] if vol else 0,
    }

    return render_template(
        'volunteer/profile.html',
        current_user=user, volunteer=vol, stats=stats,
    )


# ── CHANGE PASSWORD ──────────────────────────────────────────────────────────

@volunteer_bp.route('/change-password', methods=['POST'])
@login_required
@vol_required
def change_password():
    from werkzeug.security import generate_password_hash, check_password_hash
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()

    old  = request.form.get('old_password', '')
    new  = request.form.get('new_password', '')
    conf = request.form.get('confirm_password', '')

    if not check_password_hash(user['password'], old):
        flash('Current password is incorrect.', 'danger')
    elif new != conf:
        flash('Passwords do not match.', 'danger')
    elif len(new) < 8:
        flash('Password must be at least 8 characters.', 'danger')
    else:
        db.execute(
            'UPDATE users SET password=? WHERE id=?',
            (generate_password_hash(new), session['user_id']),
        )
        db.commit()
        flash('Password changed!', 'success')

    return redirect(url_for('volunteer.profile'))


# ── PHOTO UPLOAD ─────────────────────────────────────────────────────────────

@volunteer_bp.route('/profile/photo/upload', methods=['POST'])
@login_required
@vol_required
def upload_photo():
    db  = get_db()
    vol = db.execute('SELECT * FROM volunteers WHERE user_id=?', (session['user_id'],)).fetchone()

    if not vol:
        flash('Volunteer profile not found.', 'danger')
        return redirect(url_for('volunteer.dashboard'))

    file = request.files.get('photo')
    if not file or file.filename == '':
        flash('No file selected.', 'warning')
        return redirect(url_for('volunteer.dashboard'))

    if not allowed_file(file.filename):
        flash('Invalid file type. Use JPG, PNG, or WEBP.', 'danger')
        return redirect(url_for('volunteer.dashboard'))

    data = file.read()
    if len(data) > 2 * 1024 * 1024:
        flash('File too large. Max 2 MB.', 'danger')
        return redirect(url_for('volunteer.dashboard'))

    db.execute(
        'UPDATE volunteers SET photo=?, photo_mime=? WHERE user_id=?',
        (data, file.content_type, session['user_id']),
    )
    db.commit()
    flash('Profile photo updated!', 'success')
    return redirect(url_for('volunteer.dashboard'))


# ── PHOTO REMOVE ─────────────────────────────────────────────────────────────

@volunteer_bp.route('/profile/photo/remove', methods=['POST'])
@login_required
@vol_required
def remove_photo():
    db = get_db()
    db.execute(
        'UPDATE volunteers SET photo=NULL, photo_mime=NULL WHERE user_id=?',
        (session['user_id'],),
    )
    db.commit()
    flash('Profile photo removed.', 'info')
    return redirect(url_for('volunteer.dashboard'))


# ── PHOTO SERVE ──────────────────────────────────────────────────────────────

@volunteer_bp.route('/profile/photo')
@login_required
@vol_required
def profile_photo():
    db  = get_db()
    vol = db.execute(
        'SELECT photo, photo_mime FROM volunteers WHERE user_id=?',
        (session['user_id'],),
    ).fetchone()

    if not vol or not vol['photo']:
        return redirect(url_for('static', filename='default_avatar.png'))

    return Response(vol['photo'], mimetype=vol['photo_mime'] or 'image/jpeg')


# ── CERTIFICATE DOWNLOAD ─────────────────────────────────────────────────────

@volunteer_bp.route('/certificate/<int:cert_id>/download')
@login_required
@vol_required
def download_certificate(cert_id):
    db  = get_db()
    vol = db.execute('SELECT * FROM volunteers WHERE user_id=?', (session['user_id'],)).fetchone()

    if not vol:
        flash('Profile not found.', 'danger')
        return redirect(url_for('volunteer.dashboard'))

    cert = db.execute('''
        SELECT c.*, act.title AS act_title, act.start_date, act.end_date,
               act.location, u_org.name AS org_name,
               u_vol.name AS vol_name
        FROM certificates c
        JOIN activities act ON c.activity_id = act.id
        JOIN organizations org ON act.org_id = org.id
        JOIN users u_org ON org.user_id = u_org.id
        JOIN users u_vol ON c.volunteer_id = (
            SELECT id FROM volunteers WHERE user_id = u_vol.id LIMIT 1
        )
        WHERE c.id = ? AND c.volunteer_id = ?
    ''', (cert_id, vol['id'])).fetchone()

    if not cert:
        cert = db.execute('''
            SELECT c.*, act.title AS act_title, act.start_date, act.end_date,
                   u.name AS org_name
            FROM certificates c
            JOIN activities act ON c.activity_id = act.id
            JOIN organizations org ON act.org_id = org.id
            JOIN users u ON org.user_id = u.id
            WHERE c.id = ? AND c.volunteer_id = ?
        ''', (cert_id, vol['id'])).fetchone()

    if not cert:
        flash('Certificate not found.', 'danger')
        return redirect(url_for('volunteer.dashboard'))

    vol_name = db.execute(
        'SELECT name FROM users WHERE id=?', (session['user_id'],)
    ).fetchone()['name']

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Certificate — {cert['act_title']}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#07071a; display:flex; align-items:center; justify-content:center; min-height:100vh; font-family:'DM Sans',sans-serif; }}
  .cert {{
    width:900px; min-height:620px;
    background:linear-gradient(135deg,#10102a,#1a0a30);
    border:2px solid rgba(255,65,108,0.4); border-radius:24px; padding:60px 80px;
    text-align:center; position:relative; overflow:hidden;
    box-shadow:0 0 80px rgba(255,65,108,0.15);
  }}
  .cert::before {{
    content:''; position:absolute; top:0; left:20%; right:20%; height:3px;
    background:linear-gradient(90deg,transparent,#ff416c,#6a11cb,#00c6ff,transparent);
  }}
  .cert::after {{
    content:''; position:absolute; inset:0; border-radius:24px;
    background:
      radial-gradient(ellipse at 20% 20%, rgba(106,17,203,0.12) 0%, transparent 60%),
      radial-gradient(ellipse at 80% 80%, rgba(0,198,255,0.08) 0%, transparent 60%);
    pointer-events:none;
  }}
  .logo {{ font-family:'Syne',sans-serif; font-weight:800; font-size:18px; color:#f0f0ff; margin-bottom:30px; }}
  .logo span {{ background:linear-gradient(90deg,#ff416c,#00c6ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
  .cert-label {{ font-size:12px; font-weight:700; letter-spacing:0.15em; text-transform:uppercase; color:rgba(240,240,255,0.5); margin-bottom:16px; }}
  .cert-title {{ font-family:'Syne',sans-serif; font-weight:800; font-size:42px; color:#f0f0ff; margin-bottom:24px; letter-spacing:-1px; }}
  .cert-recipient {{ font-size:16px; color:rgba(240,240,255,0.6); margin-bottom:8px; }}
  .cert-name {{
    font-family:'Syne',sans-serif; font-weight:800; font-size:36px;
    background:linear-gradient(90deg,#ff416c,#6a11cb,#00c6ff);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:24px;
  }}
  .cert-for {{ font-size:15px; color:rgba(240,240,255,0.6); margin-bottom:6px; }}
  .cert-activity {{ font-family:'Syne',sans-serif; font-weight:700; font-size:22px; color:#f0f0ff; margin-bottom:30px; }}
  .cert-meta {{ display:flex; justify-content:center; gap:40px; margin-bottom:40px; }}
  .meta-item {{ text-align:center; }}
  .meta-label {{ font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:rgba(240,240,255,0.4); margin-bottom:4px; }}
  .meta-value {{ font-size:14px; font-weight:600; color:rgba(240,240,255,0.85); }}
  .cert-line {{ width:200px; height:1px; background:linear-gradient(90deg,transparent,rgba(255,65,108,0.5),transparent); margin:0 auto 12px; }}
  .cert-issued {{ font-size:12px; color:rgba(240,240,255,0.35); }}
  @media print {{
    body {{ background:#07071a !important; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
  }}
</style>
</head>
<body>
<div class="cert">
  <div class="logo">Volunteer<span>Hub</span></div>
  <div class="cert-label">Certificate of Participation</div>
  <div class="cert-title">This certifies that</div>
  <div class="cert-recipient">The following volunteer has successfully participated in</div>
  <div class="cert-name">{vol_name}</div>
  <div class="cert-for">has participated as a volunteer in</div>
  <div class="cert-activity">{cert['act_title']}</div>
  <div class="cert-meta">
    <div class="meta-item">
      <div class="meta-label">Organization</div>
      <div class="meta-value">{cert['org_name']}</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Date</div>
      <div class="meta-value">{cert['start_date'] or 'N/A'}</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Certificate ID</div>
      <div class="meta-value">VH-{cert_id:05d}</div>
    </div>
  </div>
  <div class="cert-line"></div>
  <div class="cert-issued">
    Issued on {cert['issued_at'].strftime('%Y-%m-%d') if cert['issued_at'] else 'N/A'} via VolunteerHub
  </div>
</div>
<script>window.onload = () => window.print();</script>
</body>
</html>"""

    response = make_response(html)
    response.headers['Content-Type'] = 'text/html'
    return response