"""Auth routes: login, register, logout"""
from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from auth import auth_bp
from db import get_db


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', '')
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE email = ? AND role = ? AND is_active = 1',
            (email, role)
        ).fetchone()
        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['user_name'] = user['name']
            flash(f'Welcome back, {user["name"]}!', 'success')
            if role == 'volunteer':
                return redirect(url_for('volunteer.dashboard'))
            elif role == 'organization':
                return redirect(url_for('organization.dashboard'))
        else:
            flash('Invalid credentials. Please check your email, password, and role.', 'danger')
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        role     = request.form.get('role', '')

        if not all([name, email, password, role]):
            flash('All required fields must be filled.', 'danger')
            return render_template('auth/register.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/register.html')

        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            flash('An account with this email already exists.', 'danger')
            return render_template('auth/register.html')

        hashed = generate_password_hash(password)
        db.execute(
            'INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)',
            (name, email, hashed, role)
        )
        db.commit()
        user_id = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()['id']

        if role == 'volunteer':
            phone = request.form.get('phone', '')
            db.execute('INSERT INTO volunteers (user_id, phone) VALUES (?, ?)', (user_id, phone))
        elif role == 'organization':
            org_type = request.form.get('org_type', '')
            description = request.form.get('description', '')
            db.execute(
                'INSERT INTO organizations (user_id, org_type, description) VALUES (?, ?, ?)',
                (user_id, org_type, description)
            )
        db.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
