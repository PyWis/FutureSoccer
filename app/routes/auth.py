from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from app import db, limiter
from app.models.user import User
from app.utils.brevo import send_verification_email, send_welcome_email, send_password_reset_email

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit('10 per hour', methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('game.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        error = None
        if not username or len(username) < 3:
            error = 'Il nome utente deve avere almeno 3 caratteri.'
        elif not email or '@' not in email:
            error = 'Inserisci un indirizzo email valido.'
        elif len(password) < 8:
            error = 'La password deve avere almeno 8 caratteri.'
        elif password != confirm:
            error = 'Le password non coincidono.'
        elif User.query.filter_by(username=username).first():
            error = 'Nome utente già in uso.'

        if error:
            flash(error, 'danger')
            return render_template('auth/register.html')

        # Don't reveal whether an email is already registered (enumeration).
        # Silently behave as success; the real owner already has an account.
        if User.query.filter_by(email=email).first():
            flash('Registrazione completata! Controlla la tua email per attivare l\'account.', 'success')
            return redirect(url_for('auth.login'))

        user = User(username=username, email=email)
        user.set_password(password)
        token = user.generate_verification_token()
        db.session.add(user)
        db.session.commit()

        base_url = request.host_url.rstrip('/')
        send_verification_email(email, username, token, base_url)

        flash('Registrazione completata! Controlla la tua email per attivare l\'account.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/verify/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash('Link di verifica non valido o già utilizzato.', 'danger')
        return redirect(url_for('auth.login'))
    if user.verification_token_expires and datetime.utcnow() > user.verification_token_expires:
        flash('Link di verifica scaduto. Richiedi un nuovo link di registrazione.', 'danger')
        return redirect(url_for('auth.login'))

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.session.commit()

    send_welcome_email(user.email, user.username)
    flash('Email verificata! Puoi ora accedere al gioco.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per 15 minutes', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('game.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Email o password non corretti.', 'danger')
            return render_template('auth/login.html')

        if not user.is_verified:
            flash('Verifica la tua email prima di accedere.', 'warning')
            return render_template('auth/login.html')

        login_user(user, remember=remember)
        user.last_login = datetime.utcnow()
        db.session.commit()

        next_page = request.args.get('next')
        if user.is_superadmin:
            return redirect(next_page or url_for('admin.dashboard'))
        # First-time player without a team → go directly to team creation
        if not next_page and not user.team:
            return redirect(url_for('game.create_team'))
        return redirect(next_page or url_for('game.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout effettuato.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit('5 per hour', methods=['POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.generate_reset_token()
            db.session.commit()
            base_url = request.host_url.rstrip('/')
            send_password_reset_email(email, user.username, token, base_url)
        flash('Se l\'email è registrata, riceverai le istruzioni per il reset.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or (user.reset_token_expires and datetime.utcnow() > user.reset_token_expires):
        flash('Link di reset non valido o scaduto.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if len(password) < 8:
            flash('La password deve avere almeno 8 caratteri.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        if password != confirm:
            flash('Le password non coincidono.', 'danger')
            return render_template('auth/reset_password.html', token=token)
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        flash('Password aggiornata! Ora puoi accedere.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)
