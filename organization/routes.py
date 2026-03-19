"""Organization routes — v2"""
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from organization import organization_bp
from db import get_db
from auth.routes import login_required
import random, json

def org_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'organization':
            flash('Organization access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def get_org(db, user_id):
    return db.execute('SELECT * FROM organizations WHERE user_id = ?', (user_id,)).fetchone()

def generate_activity_days(db, activity_id, start_date, end_date):
    """Auto-generate activity_days rows between start and end date."""
    from datetime import date, timedelta
    db.execute('DELETE FROM activity_days WHERE activity_id = ?', (activity_id,))
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date) if end_date else s
    except Exception:
        return
    current = s
    day_num = 1
    while current <= e:
        db.execute(
            'INSERT INTO activity_days (activity_id, day_date, label) VALUES (?,?,?)',
            (activity_id, current.isoformat(), f'Day {day_num}')
        )
        current += timedelta(days=1)
        day_num += 1
    db.commit()

def smart_assign(db, activity_id):
    """
    Skill-based assignment:
    - For each role with skill_tags: prefer volunteers whose skills match.
    - For general roles (no skill_tags): randomly assign from remaining approved volunteers.
    Returns list of (volunteer_id, role_name) tuples assigned.
    """
    roles = db.execute(
        'SELECT * FROM activity_roles WHERE activity_id = ?', (activity_id,)
    ).fetchall()

    approved_apps = db.execute('''
        SELECT app.volunteer_id, app.role_applied, v.skills, u.name
        FROM applications app
        JOIN volunteers v ON app.volunteer_id = v.id
        JOIN users u ON v.user_id = u.id
        WHERE app.activity_id = ? AND app.status = 'approved'
    ''', (activity_id,)).fetchall()

    # Remove already assigned
    already = set(
        r[0] for r in db.execute(
            'SELECT volunteer_id FROM assignments WHERE activity_id=?', (activity_id,)
        ).fetchall()
    )
    pool = [a for a in approved_apps if a['volunteer_id'] not in already]

    assigned = []
    used_vol_ids = set()

    for role in roles:
        needed  = role['total'] - role['filled']
        if needed <= 0:
            continue
        skill_tags = [s.strip().lower() for s in (role['skill_tags'] or '').split(',') if s.strip()]

        if skill_tags:
            # Score volunteers by how many required skills they have
            scored = []
            for vol in pool:
                if vol['volunteer_id'] in used_vol_ids:
                    continue
                vol_skills = [s.strip().lower() for s in (vol['skills'] or '').split(',') if s.strip()]
                score = sum(1 for sk in skill_tags if any(sk in vs or vs in sk for vs in vol_skills))
                scored.append((score, vol))
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates = [v for _, v in scored if _[0] >= 0]
        else:
            # General role — random shuffle
            candidates = [v for v in pool if v['volunteer_id'] not in used_vol_ids]
            random.shuffle(candidates)

        for vol in candidates[:needed]:
            if vol['volunteer_id'] not in used_vol_ids:
                db.execute(
                    'INSERT OR IGNORE INTO assignments (volunteer_id, activity_id, role) VALUES (?,?,?)',
                    (vol['volunteer_id'], activity_id, role['name'])
                )
                db.execute(
                    'UPDATE activity_roles SET filled = filled + 1 WHERE activity_id=? AND name=?',
                    (activity_id, role['name'])
                )
                used_vol_ids.add(vol['volunteer_id'])
                assigned.append({'vol_id': vol['volunteer_id'], 'name': vol['name'], 'role': role['name']})

    db.commit()
    return assigned


# ── DASHBOARD ────────────────────────────────────────────────────────────────
@organization_bp.route('/dashboard')
@login_required
@org_required
def dashboard():
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    org  = get_org(db, session['user_id'])
    if not org:
        flash('Organization profile not found.', 'danger')
        return redirect(url_for('auth.logout'))

    activities = db.execute('''
        SELECT act.*,
          (SELECT COUNT(*) FROM assignments WHERE activity_id=act.id) AS assigned_count,
          (SELECT COALESCE(SUM(total),0) FROM activity_roles WHERE activity_id=act.id) AS total_slots,
          (SELECT COUNT(*) FROM activity_days WHERE activity_id=act.id) AS day_count
        FROM activities act WHERE act.org_id=?
        ORDER BY act.created_at DESC LIMIT 10
    ''', (org['id'],)).fetchall()

    pending_apps = db.execute('''
        SELECT app.id, app.role_applied, app.status, app.created_at,
               u.name AS vol_name, u.email AS vol_email,
               act.title AS act_title
        FROM applications app
        JOIN volunteers v ON app.volunteer_id=v.id
        JOIN users u ON v.user_id=u.id
        JOIN activities act ON app.activity_id=act.id
        WHERE act.org_id=? AND app.status='pending'
        ORDER BY app.created_at DESC LIMIT 20
    ''', (org['id'],)).fetchall()

    stats = {
        'total_activities':    db.execute('SELECT COUNT(*) FROM activities WHERE org_id=?', (org['id'],)).fetchone()[0],
        'pending_applications': len(pending_apps),
        'assigned_volunteers':  db.execute('SELECT COUNT(*) FROM assignments a JOIN activities act ON a.activity_id=act.id WHERE act.org_id=?', (org['id'],)).fetchone()[0],
        'attendance_today':     0,
    }
    return render_template('organization/dashboard.html',
        current_user=user, organization=org,
        activities=activities, pending_applications=pending_apps, stats=stats)


# ── CREATE ACTIVITY ──────────────────────────────────────────────────────────
@organization_bp.route('/create-activity', methods=['GET','POST'])
@login_required
@org_required
def create_activity():
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    org  = get_org(db, session['user_id'])

    if request.method == 'POST':
        title       = request.form.get('title','').strip()
        desc        = request.form.get('description','')
        start_date  = request.form.get('start_date') or None
        end_date    = request.form.get('end_date') or None
        time_val    = request.form.get('time') or None
        location    = request.form.get('location','')
        deadline    = request.form.get('deadline') or None
        requirements= request.form.get('requirements','')
        status      = request.form.get('status','open')
        auto_assign = 1 if request.form.get('auto_assign') else 0

        if not title:
            flash('Activity title is required.', 'danger')
            return render_template('organization/create_activity.html', current_user=user)

        db.execute('''
            INSERT INTO activities (org_id,title,description,start_date,end_date,time,location,deadline,requirements,status,auto_assign)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ''', (org['id'],title,desc,start_date,end_date,time_val,location,deadline,requirements,status,auto_assign))
        db.commit()
        activity_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Generate day rows
        if start_date:
            generate_activity_days(db, activity_id, start_date, end_date or start_date)

        # Roles
        role_names  = request.form.getlist('role_name[]')
        role_counts = request.form.getlist('role_count[]')
        role_skills = request.form.getlist('role_skills[]')
        for i,(name,count) in enumerate(zip(role_names,role_counts)):
            name = name.strip()
            if name:
                try: c = max(1,int(count))
                except: c = 1
                skills = role_skills[i] if i < len(role_skills) else ''
                db.execute('INSERT INTO activity_roles (activity_id,name,total,skill_tags) VALUES (?,?,?,?)',
                           (activity_id,name,c,skills))
        db.commit()
        flash(f'Activity "{title}" created!', 'success')
        return redirect(url_for('organization.activity_detail', activity_id=activity_id))

    return render_template('organization/create_activity.html', current_user=user, activity=None)


# ── EDIT ACTIVITY ────────────────────────────────────────────────────────────
@organization_bp.route('/activity/<int:activity_id>/edit', methods=['GET','POST'])
@login_required
@org_required
def edit_activity(activity_id):
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    org  = get_org(db, session['user_id'])
    act  = db.execute('SELECT * FROM activities WHERE id=? AND org_id=?', (activity_id, org['id'])).fetchone()
    if not act:
        flash('Activity not found.', 'danger')
        return redirect(url_for('organization.dashboard'))

    roles = db.execute('SELECT * FROM activity_roles WHERE activity_id=?', (activity_id,)).fetchall()

    if request.method == 'POST':
        title       = request.form.get('title','').strip()
        desc        = request.form.get('description','')
        start_date  = request.form.get('start_date') or None
        end_date    = request.form.get('end_date') or None
        time_val    = request.form.get('time') or None
        location    = request.form.get('location','')
        deadline    = request.form.get('deadline') or None
        requirements= request.form.get('requirements','')
        status      = request.form.get('status', act['status'])
        auto_assign = 1 if request.form.get('auto_assign') else 0

        db.execute('''
            UPDATE activities SET title=?,description=?,start_date=?,end_date=?,time=?,
            location=?,deadline=?,requirements=?,status=?,auto_assign=? WHERE id=?
        ''', (title,desc,start_date,end_date,time_val,location,deadline,requirements,status,auto_assign,activity_id))

        # Regenerate days if dates changed
        if start_date:
            generate_activity_days(db, activity_id, start_date, end_date or start_date)

        # Rebuild roles
        db.execute('DELETE FROM activity_roles WHERE activity_id=?', (activity_id,))
        role_names  = request.form.getlist('role_name[]')
        role_counts = request.form.getlist('role_count[]')
        role_skills = request.form.getlist('role_skills[]')
        for i,(name,count) in enumerate(zip(role_names,role_counts)):
            name = name.strip()
            if name:
                try: c = max(1,int(count))
                except: c = 1
                skills = role_skills[i] if i < len(role_skills) else ''
                db.execute('INSERT INTO activity_roles (activity_id,name,total,skill_tags) VALUES (?,?,?,?)',
                           (activity_id,name,c,skills))
        db.commit()
        flash('Activity updated successfully!', 'success')
        return redirect(url_for('organization.activity_detail', activity_id=activity_id))

    return render_template('organization/create_activity.html',
        current_user=user, activity=act, roles=roles, edit=True)


# ── TOGGLE STATUS (reopen/close) ─────────────────────────────────────────────
@organization_bp.route('/activity/<int:activity_id>/toggle-status', methods=['POST'])
@login_required
@org_required
def toggle_status(activity_id):
    db  = get_db()
    org = get_org(db, session['user_id'])
    act = db.execute('SELECT * FROM activities WHERE id=? AND org_id=?', (activity_id, org['id'])).fetchone()
    if not act:
        flash('Activity not found.', 'danger')
        return redirect(url_for('organization.dashboard'))
    new_status = 'open' if act['status'] != 'open' else 'closed'
    db.execute('UPDATE activities SET status=? WHERE id=?', (new_status, activity_id))
    db.commit()
    flash(f'Activity {"reopened" if new_status=="open" else "closed"} successfully!', 'success')
    return redirect(url_for('organization.activity_detail', activity_id=activity_id))


# ── ACTIVITY DETAIL ───────────────────────────────────────────────────────────
@organization_bp.route('/activity/<int:activity_id>')
@login_required
@org_required
def activity_detail(activity_id):
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    org  = get_org(db, session['user_id'])
    act  = db.execute('''
        SELECT act.*,
          (SELECT COUNT(*) FROM assignments WHERE activity_id=act.id) AS assigned_count,
          (SELECT COALESCE(SUM(total),0) FROM activity_roles WHERE activity_id=act.id) AS total_slots,
          (SELECT COUNT(*) FROM activity_days WHERE activity_id=act.id) AS day_count
        FROM activities act WHERE act.id=? AND act.org_id=?
    ''', (activity_id, org['id'])).fetchone()
    if not act:
        flash('Activity not found.', 'danger')
        return redirect(url_for('organization.dashboard'))

    roles       = db.execute('SELECT * FROM activity_roles WHERE activity_id=?', (activity_id,)).fetchall()
    days        = db.execute('SELECT * FROM activity_days WHERE activity_id=? ORDER BY day_date', (activity_id,)).fetchall()
    assignments = db.execute('''
        SELECT a.id, a.role, u.name AS vol_name, u.email AS vol_email,
               v.skills AS vol_skills, v.phone AS vol_phone
        FROM assignments a
        JOIN volunteers v ON a.volunteer_id=v.id
        JOIN users u ON v.user_id=u.id
        WHERE a.activity_id=?
        ORDER BY a.role, u.name
    ''', (activity_id,)).fetchall()

    applications = db.execute('''
        SELECT app.id, app.role_applied, app.status, app.created_at,
               u.name AS vol_name, v.skills AS vol_skills
        FROM applications app
        JOIN volunteers v ON app.volunteer_id=v.id
        JOIN users u ON v.user_id=u.id
        WHERE app.activity_id=?
        ORDER BY app.status, u.name
    ''', (activity_id,)).fetchall()

    # Check if all attendance is complete for all days
    all_complete = False
    if days and assignments:
        total_needed = len(days) * len(assignments)
        total_marked = db.execute('''
            SELECT COUNT(*) FROM attendance_log al
            JOIN assignments a ON al.assignment_id=a.id
            WHERE a.activity_id=?
        ''', (activity_id,)).fetchone()[0]
        all_complete = (total_marked >= total_needed)

    # Certificate stats
    cert_count = db.execute('SELECT COUNT(*) FROM certificates WHERE activity_id=?', (activity_id,)).fetchone()[0]

    return render_template('organization/activity_detail.html',
        current_user=user, activity=act, roles=roles, days=days,
        assignments=assignments, applications=applications,
        all_complete=all_complete, cert_count=cert_count)


# ── SMART AUTO-ASSIGN ─────────────────────────────────────────────────────────
@organization_bp.route('/activity/<int:activity_id>/auto-assign', methods=['POST'])
@login_required
@org_required
def auto_assign(activity_id):
    db  = get_db()
    org = get_org(db, session['user_id'])
    act = db.execute('SELECT * FROM activities WHERE id=? AND org_id=?', (activity_id, org['id'])).fetchone()
    if not act:
        flash('Activity not found.', 'danger')
        return redirect(url_for('organization.dashboard'))

    assigned = smart_assign(db, activity_id)
    if assigned:
        flash(f'Auto-assigned {len(assigned)} volunteers based on skills!', 'success')
    else:
        flash('No new volunteers to assign. Make sure applications are approved first.', 'warning')
    return redirect(url_for('organization.activity_detail', activity_id=activity_id))


# ── VOLUNTEERS LIST ───────────────────────────────────────────────────────────
@organization_bp.route('/volunteers')
@login_required
@org_required
def volunteers():
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    org  = get_org(db, session['user_id'])

    applications = db.execute('''
        SELECT app.id, app.role_applied, app.status, app.created_at,
               u.name AS vol_name, u.email AS vol_email, v.phone AS vol_phone,
               act.title AS act_title, act.id AS act_id
        FROM applications app
        JOIN volunteers v ON app.volunteer_id=v.id
        JOIN users u ON v.user_id=u.id
        JOIN activities act ON app.activity_id=act.id
        WHERE act.org_id=?
        ORDER BY app.created_at DESC
    ''', (org['id'],)).fetchall()

    return render_template('organization/volunteers.html',
        current_user=user, applications=applications)


# ── REVIEW APPLICATION ────────────────────────────────────────────────────────
@organization_bp.route('/review/<int:app_id>', methods=['POST'])
@login_required
@org_required
def review_application(app_id):
    db  = get_db()
    org = get_org(db, session['user_id'])
    app = db.execute('''
        SELECT app.*, act.org_id FROM applications app
        JOIN activities act ON app.activity_id=act.id WHERE app.id=?
    ''', (app_id,)).fetchone()

    if not app or app['org_id'] != org['id']:
        flash('Application not found.', 'danger')
        return redirect(url_for('organization.volunteers'))

    action = request.form.get('action')
    if action == 'approve':
        db.execute("UPDATE applications SET status='approved' WHERE id=?", (app_id,))
        db.execute('INSERT OR IGNORE INTO assignments (volunteer_id,activity_id,role) VALUES (?,?,?)',
                   (app['volunteer_id'], app['activity_id'], app['role_applied']))
        db.commit()
        flash('Volunteer approved and assigned!', 'success')
    elif action == 'reject':
        db.execute("UPDATE applications SET status='rejected' WHERE id=?", (app_id,))
        db.commit()
        flash('Application rejected.', 'info')

    return redirect(url_for('organization.volunteers'))


# ── ATTENDANCE (multi-day) ────────────────────────────────────────────────────
@organization_bp.route('/attendance')
@login_required
@org_required
def attendance():
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    org  = get_org(db, session['user_id'])

    activities = db.execute(
        'SELECT * FROM activities WHERE org_id=? ORDER BY start_date DESC', (org['id'],)
    ).fetchall()

    selected_activity = None
    assignments       = []
    days              = []
    # IMPORTANT: All keys in attendance_map are STRINGS to avoid int/str mismatch in Jinja2
    # Structure: { "assignment_id_str": { "YYYY-MM-DD": 0|1 } }
    attendance_map    = {}
    selected_day      = None
    days_status       = {}  # { "YYYY-MM-DD": "complete"|"partial"|"empty" }

    act_id  = request.args.get('activity')
    day_sel = request.args.get('day')

    if act_id:
        selected_activity = db.execute(
            'SELECT * FROM activities WHERE id=? AND org_id=?', (act_id, org['id'])
        ).fetchone()

        if selected_activity:
            days = db.execute(
                'SELECT * FROM activity_days WHERE activity_id=? ORDER BY day_date', (act_id,)
            ).fetchall()

            # Auto-create Day 1 if activity has no days yet
            if not days and selected_activity['start_date']:
                db.execute(
                    'INSERT OR IGNORE INTO activity_days (activity_id, day_date, label) VALUES (?,?,?)',
                    (act_id, selected_activity['start_date'], 'Day 1')
                )
                db.commit()
                days = db.execute(
                    'SELECT * FROM activity_days WHERE activity_id=? ORDER BY day_date', (act_id,)
                ).fetchall()

            assignments = db.execute("""
                SELECT a.id, a.role, u.name AS vol_name, u.email AS vol_email,
                       v.phone AS vol_phone, a.volunteer_id
                FROM assignments a
                JOIN volunteers v ON a.volunteer_id=v.id
                JOIN users u ON v.user_id=u.id
                WHERE a.activity_id=? ORDER BY a.role, u.name
            """, (act_id,)).fetchall()

            # Build attendance_map with ALL string keys
            logs = db.execute("""
                SELECT al.assignment_id, al.day_date, al.is_present
                FROM attendance_log al
                JOIN assignments a ON al.assignment_id=a.id
                WHERE a.activity_id=?
            """, (act_id,)).fetchall()
            for log in logs:
                a_key  = str(log['assignment_id'])
                d_key  = str(log['day_date'])
                attendance_map.setdefault(a_key, {})[d_key] = int(log['is_present'])

            # Calculate per-day status
            total_vols = len(assignments)
            for day in days:
                dd = str(day['day_date'])
                if total_vols == 0:
                    days_status[dd] = 'empty'
                    continue
                marked = db.execute("""
                    SELECT COUNT(*) FROM attendance_log al
                    JOIN assignments a ON al.assignment_id=a.id
                    WHERE a.activity_id=? AND al.day_date=?
                """, (act_id, dd)).fetchone()[0]
                if marked == 0:
                    days_status[dd] = 'empty'
                elif marked < total_vols:
                    days_status[dd] = 'partial'
                else:
                    days_status[dd] = 'complete'

            # Auto-select first incomplete day; fallback to first day
            if day_sel:
                selected_day = str(day_sel)
            else:
                selected_day = next(
                    (str(d['day_date']) for d in days
                     if days_status.get(str(d['day_date']), 'empty') != 'complete'),
                    str(days[0]['day_date']) if days else None
                )

    return render_template('organization/attendance.html',
        current_user=user, activities=activities,
        selected_activity=selected_activity, assignments=assignments,
        days=days, attendance_map=attendance_map,
        selected_day=selected_day, days_status=days_status)

@organization_bp.route('/attendance/save', methods=['POST'])
@login_required
@org_required
def save_attendance():
    db       = get_db()
    org      = get_org(db, session['user_id'])
    act_id   = (request.form.get('activity_id') or '').strip()
    day_date = (request.form.get('day_date') or '').strip()
    present  = set(request.form.getlist('present[]'))

    if not act_id or not day_date:
        flash('Missing activity or date. Please try again.', 'danger')
        return redirect(url_for('organization.attendance'))

    act = db.execute('SELECT id FROM activities WHERE id=? AND org_id=?', (act_id, org['id'])).fetchone()
    if not act:
        flash('Activity not found.', 'danger')
        return redirect(url_for('organization.attendance'))

    assignments = db.execute('SELECT id FROM assignments WHERE activity_id=?', (act_id,)).fetchall()
    if not assignments:
        flash('No volunteers assigned to this activity yet.', 'warning')
        return redirect(url_for('organization.attendance', activity=act_id, day=day_date))

    saved_count = 0
    for a in assignments:
        is_present = 1 if str(a['id']) in present else 0
        # Safe upsert — delete then insert (works on ALL SQLite versions)
        db.execute('DELETE FROM attendance_log WHERE assignment_id=? AND day_date=?',
                   (a['id'], day_date))
        db.execute('INSERT INTO attendance_log (assignment_id, day_date, is_present) VALUES (?,?,?)',
                   (a['id'], day_date, is_present))
        if is_present:
            saved_count += 1
    db.commit()
    present_count = saved_count
    total_count   = len(assignments)
    flash(f'Attendance saved for {day_date} — {present_count}/{total_count} present.', 'success')
    return redirect(url_for('organization.attendance', activity=act_id, day=day_date))


# ── ISSUE CERTIFICATES ────────────────────────────────────────────────────────
@organization_bp.route('/activity/<int:activity_id>/issue-certificates', methods=['POST'])
@login_required
@org_required
def issue_certificates(activity_id):
    db  = get_db()
    org = get_org(db, session['user_id'])
    act = db.execute('SELECT * FROM activities WHERE id=? AND org_id=?', (activity_id, org['id'])).fetchone()
    if not act:
        flash('Activity not found.', 'danger')
        return redirect(url_for('organization.dashboard'))

    assignments = db.execute('''
        SELECT a.volunteer_id FROM assignments a WHERE a.activity_id=?
    ''', (activity_id,)).fetchall()

    issued = 0
    for a in assignments:
        existing = db.execute(
            'SELECT id FROM certificates WHERE volunteer_id=? AND activity_id=?',
            (a['volunteer_id'], activity_id)
        ).fetchone()
        if not existing:
            db.execute(
                'INSERT INTO certificates (volunteer_id, activity_id, issued_by) VALUES (?,?,?)',
                (a['volunteer_id'], activity_id, session['user_id'])
            )
            issued += 1
    db.commit()
    flash(f'Certificates issued to {issued} volunteers!', 'success')
    return redirect(url_for('organization.activity_detail', activity_id=activity_id))


# ── SAVE ATTENDANCE (legacy single-day) ─ kept for compatibility
@organization_bp.route('/activity/<int:activity_id>')
@login_required
@org_required
def activity_detail_redirect(activity_id):
    return redirect(url_for('organization.activity_detail', activity_id=activity_id))


# Backward compat: old single-day attendance redirect