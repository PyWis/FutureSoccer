"""Valuta premium (Gold): wallet, registro transazioni e listini.

Il Gold vive sull'utente (User.gold). Ogni movimentazione passa da grant()/spend()
così resta tracciata in GoldTransaction. spend() applica le verifiche server-side
(saldo sufficiente) e non committa: il chiamante è responsabile del commit.
"""
from app import db


# ── Listini acquisto con denaro reale (€) ──────────────────────────────────────
# Predisposti per un futuro provider di pagamento (es. Stripe). Senza provider
# configurato gli endpoint di acquisto reale restano disattivati.
GOLD_PACKS = {
    'pack_5':  {'price_eur': 5,  'gold': 10, 'label': '10 Gold'},
    'pack_20': {'price_eur': 20, 'gold': 50, 'label': '50 Gold'},
}
# Abbonamento mensile reale: 8 Gold per i primi 6 pagamenti, 16 Gold dai successivi
GOLD_SUB = {'price_eur': 5, 'gold_first6': 8, 'gold_after': 16, 'first_count': 6}

# ── Pass ────────────────────────────────────────────────────────────────────────
PASS_STAGIONALE = {'price_eur': 3, 'gold': 10, 'cash': 25_000_000}  # 1 volta/stagione, set-dic
PASS_NATALE_GOLD = 2          # gratuiti ogni 25 dicembre di gioco
PASS_FINANZA = {'cash': 250_000_000, 'gold': 5}   # spende denaro di gioco per Gold

# ── Spese Gold ricorrenti (ogni mese di gioco) ──────────────────────────────────
GOLD_SCOUTING_COST = 1        # 1 Gold/mese → 1 giocatore (media fino a 6.0)
GOLD_ROSTER_SLOT_COST = 1     # 1 Gold/mese per slot rosa extra
GOLD_ROSTER_SLOT_MAX = 3
GOLD_SPONSOR_SLOT_COST = 1    # 1 Gold/mese per slot sponsor secondario extra
GOLD_SPONSOR_SLOT_MAX = 1

# ── Spese Gold una tantum ───────────────────────────────────────────────────────
GOLD_SPONSOR_COST = 10        # Sponsor Gold
GOLD_SPONSOR_WEEKLY = 4_000_000
GOLD_SPONSOR_WEEKS = 5
GOLD_SPONSOR_WEEKS_FED = 10   # se attivo l'aiuto federazione: 10 settimane bloccato in main
GOLD_STADIUM_COST = 5         # Sponsor Stadio
GOLD_STADIUM_WEEKS = 50
GOLD_FRESHNESS_COST = 1       # Boost freschezza istantaneo (+2 a tutti)
GOLD_FRESHNESS_BOOST = 2.0


def grant(user, amount, reason=''):
    """Accredita Gold all'utente e registra la transazione. Non committa."""
    from app.models.game import GoldTransaction
    if amount <= 0:
        return
    user.gold = (user.gold or 0) + int(amount)
    db.session.add(GoldTransaction(user_id=user.id, amount=int(amount), reason=reason))


def spend(user, amount, reason=''):
    """Spende Gold se il saldo è sufficiente. Ritorna True/False. Non committa."""
    from app.models.game import GoldTransaction
    amount = int(amount)
    if (user.gold or 0) < amount:
        return False
    user.gold -= amount
    db.session.add(GoldTransaction(user_id=user.id, amount=-amount, reason=reason))
    return True


def balance(user):
    return user.gold or 0
