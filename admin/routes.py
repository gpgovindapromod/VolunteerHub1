"""Admin routes"""
from flask import render_template, request, redirect, url_for, flash, session
from admin import admin_bp
from db import get_db


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == 'admin' and password == 'admin123':
            session['is_admin'] = True
            flash('Admin access granted.', 'success')
            return redirect(url_for('admin.dashboard'))
        flash('Invalid admin credentials.', 'danger')
    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash('Logged out of admin panel.', 'info')
    return redirect(url_for('index'))


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    db = get_db()
    users = db.execute(
        "SELECT * FROM users WHERE role != 'admin' ORDER BY created_at DESC"
    ).fetchall()
    activities = db.execute('''
        SELECT act.*,
          (SELECT COUNT(*) FROM assignments WHERE activity_id=act.id) as assigned_count,
          (SELECT SUM(total) FROM activity_roles WHERE activity_id=act.id) as total_slots,
          u.name as org_name
        FROM activities act
        JOIN organizations org ON act.org_id = org.id
        JOIN users u ON org.user_id = u.id
        ORDER BY act.created_at DESC
    ''').fetchall()
    stats = {
        'total_volunteers':    db.execute("SELECT COUNT(*) FROM users WHERE role='volunteer'").fetchone()[0],
        'total_organizations': db.execute("SELECT COUNT(*) FROM users WHERE role='organization'").fetchone()[0],
        'total_activities':    db.execute('SELECT COUNT(*) FROM activities').fetchone()[0],
        'total_applications':  db.execute('SELECT COUNT(*) FROM applications').fetchone()[0],
    }
    return render_template('admin/dashboard.html', users=users, activities=activities, stats=stats)


@admin_bp.route('/user/toggle/<int:user_id>')
@admin_required
def toggle_user(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if user:
        new_status = 0 if user['is_active'] else 1
        db.execute('UPDATE users SET is_active=? WHERE id=?', (new_status, user_id))
        db.commit()
        flash('User status updated.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/user/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    db = get_db()
    db.execute('DELETE FROM users WHERE id=?', (user_id,))
    db.commit()
    flash('User deleted.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/activity/delete/<int:activity_id>')
@admin_required
def delete_activity(activity_id):
    db = get_db()
    db.execute('DELETE FROM activities WHERE id=?', (activity_id,))
    db.commit()
    flash('Activity deleted.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/users')
@admin_required
def users():
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/activities')
@admin_required
def activities():
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/organizations')
@admin_required
def organizations():
    return redirect(url_for('admin.dashboard'))
