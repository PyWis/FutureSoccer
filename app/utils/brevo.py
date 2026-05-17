import os
import requests


BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL', 'noreply@futuresoccer.com')
SENDER_NAME = os.environ.get('BREVO_SENDER_NAME', 'FutureSoccer')
BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'


def _send(to_email: str, to_name: str, subject: str, html_content: str) -> bool:
    if not BREVO_API_KEY:
        print(f"[BREVO MOCK] To: {to_email} | Subject: {subject}")
        return True

    payload = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content,
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": BREVO_API_KEY,
    }
    try:
        resp = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=10)
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[BREVO ERROR] {e}")
        return False


def send_verification_email(user_email: str, username: str, token: str, base_url: str) -> bool:
    verify_url = f"{base_url}/auth/verify/{token}"
    html = f"""
    <div style="font-family:Arial,sans-serif;background:#0a0a1a;color:#e0e0e0;padding:40px;border-radius:12px;max-width:600px;margin:auto;">
      <div style="text-align:center;margin-bottom:30px;">
        <h1 style="color:#00f5ff;font-size:2rem;letter-spacing:3px;">⚽ FUTURE<span style="color:#7b2fff">SOCCER</span></h1>
        <p style="color:#aaa;font-size:0.9rem;">Anno 2099 — Il calcio del futuro</p>
      </div>
      <h2 style="color:#00f5ff;">Benvenuto, {username}!</h2>
      <p>Hai richiesto di unirti alla lega più avanzata del futuro. Conferma il tuo indirizzo email per attivare il tuo account.</p>
      <div style="text-align:center;margin:30px 0;">
        <a href="{verify_url}" style="background:linear-gradient(135deg,#00f5ff,#7b2fff);color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:1rem;letter-spacing:1px;">
          ATTIVA ACCOUNT
        </a>
      </div>
      <p style="color:#888;font-size:0.8rem;">Il link scade tra 24 ore. Se non hai richiesto la registrazione, ignora questa email.</p>
      <hr style="border-color:#333;margin:30px 0;">
      <p style="color:#555;font-size:0.75rem;text-align:center;">© 2099 FutureSoccer Corp. All rights reserved.</p>
    </div>
    """
    return _send(user_email, username, "🚀 Attiva il tuo account FutureSoccer", html)


def send_welcome_email(user_email: str, username: str) -> bool:
    html = f"""
    <div style="font-family:Arial,sans-serif;background:#0a0a1a;color:#e0e0e0;padding:40px;border-radius:12px;max-width:600px;margin:auto;">
      <div style="text-align:center;margin-bottom:30px;">
        <h1 style="color:#00f5ff;font-size:2rem;letter-spacing:3px;">⚽ FUTURE<span style="color:#7b2fff">SOCCER</span></h1>
      </div>
      <h2 style="color:#7b2fff;">Account attivato, {username}!</h2>
      <p>Il tuo accesso alla lega è confermato. Costruisci la tua squadra, potenzia i tuoi giocatori con tecnologie cybernetiche e domina il campo nel 2099.</p>
      <p style="color:#00f5ff;font-weight:bold;">Buona fortuna, Manager!</p>
      <hr style="border-color:#333;margin:30px 0;">
      <p style="color:#555;font-size:0.75rem;text-align:center;">© 2099 FutureSoccer Corp.</p>
    </div>
    """
    return _send(user_email, username, "✅ Benvenuto in FutureSoccer!", html)


def send_password_reset_email(user_email: str, username: str, token: str, base_url: str) -> bool:
    reset_url = f"{base_url}/auth/reset-password/{token}"
    html = f"""
    <div style="font-family:Arial,sans-serif;background:#0a0a1a;color:#e0e0e0;padding:40px;border-radius:12px;max-width:600px;margin:auto;">
      <div style="text-align:center;margin-bottom:30px;">
        <h1 style="color:#00f5ff;font-size:2rem;letter-spacing:3px;">⚽ FUTURE<span style="color:#7b2fff">SOCCER</span></h1>
      </div>
      <h2 style="color:#ff6b6b;">Reset Password</h2>
      <p>Hai richiesto il reset della password per l'account <strong>{username}</strong>.</p>
      <div style="text-align:center;margin:30px 0;">
        <a href="{reset_url}" style="background:linear-gradient(135deg,#ff6b6b,#7b2fff);color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:1rem;">
          RESET PASSWORD
        </a>
      </div>
      <p style="color:#888;font-size:0.8rem;">Il link scade tra 1 ora. Se non hai fatto questa richiesta, ignora questa email.</p>
      <hr style="border-color:#333;margin:30px 0;">
      <p style="color:#555;font-size:0.75rem;text-align:center;">© 2099 FutureSoccer Corp.</p>
    </div>
    """
    return _send(user_email, username, "🔐 Reset Password FutureSoccer", html)
