"""
parametri.py — Riferimento centralizzato dei parametri di gioco di FutureSoccer.

Questo file raccoglie, in un unico posto, tutte le costanti che governano il
bilanciamento del gioco. È pensato come DOCUMENTAZIONE/ESEMPIO: i valori qui
riportati rispecchiano quelli effettivamente usati nel codice (app/routes,
app/utils, app/models) al momento della stesura.

NOTA: alcune costanti sono anche configurabili da variabile d'ambiente
(vedi .env.example). Dove esiste un override env, è indicato accanto al valore.
Modificare questo file da solo NON cambia il comportamento del gioco: serve come
riferimento di tuning. Per cambiare davvero un valore, modificarlo nel modulo
indicato come "fonte".
"""

# ─────────────────────────────────────────────────────────────────────────────
# OROLOGIO DI GIOCO            (fonte: app/utils/gameclock.py, .env.example)
# ─────────────────────────────────────────────────────────────────────────────
GAME_CLOCK_RATIO = 3600          # secondi reali per ogni giorno di gioco in modalità default
                                 # (env GAME_CLOCK_RATIO; 3600 = 1 ora reale = 1 giorno)
GAME_START = "31 agosto 2099"    # data di inizio del mondo di gioco

# Modalità tempo selezionabili dal superadmin (salvate in GameConfig.time_mode):
#   'default' → GAME_CLOCK_RATIO (1 ora reale = 1 giorno)
#   'week'    → 1 giorno reale ≈ 1 settimana di gioco
#   'month'   → 1 giorno reale = 1 mese di gioco
TIME_MODE_WEEK_DAY_SECONDS = 12_000   # week mode: 3h20m per giorno (7 giorni + pausa = 24h reali)
TIME_MODE_MONTH_DAY_SECONDS = 2_880   # month mode: 48 min per giorno (30 giorni = 24h reali)
WEEK_REAL_SECONDS = 86_400            # in week mode una settimana occupa 24h reali allineate all'ora del server
# Check superadmin:
FREEZE_AUG15 = False                  # blocca il gioco al 15 agosto finché attivo, poi riparte da lì
FAST_AUGUST_DAY_SECONDS = 3_600       # mese veloce: dal 3 agosto, per 24 giorni, 1 ora reale per giorno
FAST_AUGUST_START = "3 agosto"        # (non interviene se il giorno dura già meno di un'ora)
FAST_AUGUST_DAYS = 24

# Giorni della settimana di gioco (0=Lun ... 6=Dom)
TRAINING_WEEKDAYS = (1, 2, 3, 4) # Mar (regolare), Mer (recupero Mar), Gio (regolare), Ven (recupero Gio)
SPONSOR_WEEKDAY = 4              # Venerdì: offerte sponsor
MATCH_WEEKDAYS = (2, 6)          # Mercoledì e Domenica: match day (fonte: match.py / scheduler.py)
WELLNESS_PURCHASE_WEEKDAYS = (2, 3, 4, 5, 6)  # Mer–Dom: acquisto sessioni benessere

# ─────────────────────────────────────────────────────────────────────────────
# PARTITE                      (fonte: app/utils/match_engine.py, .env.example)
# ─────────────────────────────────────────────────────────────────────────────
MATCH_TURN_SECONDS = 30          # durata reale di un turno (env MATCH_TURN_SECONDS)
MATCH_REGULAR_TURNS = 6          # turni di gioco regolamentari (+ 1 supplementare in caso di parità)
GOAL_COEFF = 1.0                 # coefficiente formula gol (env GOAL_COEFF)
                                 # modello a soglia: gol se GOAL_COEFF*Attacco*rand(0-2)/(Difesa+Porta) >= 1
INJURY_BASE = 0.010              # probabilità base infortunio per turno (env INJURY_BASE)
INJURY_MALUS_MIN = -12.0         # malus freschezza minimo per infortunio
INJURY_MALUS_MAX = -5.0          # malus freschezza massimo per infortunio (la freschezza può andare in negativo)
FRESHNESS_LOSS_PER_TURN = -0.3   # calo freschezza dei titolari per turno
FRESHNESS_MATCH_THRESHOLD = 2.0  # sotto questa soglia il giocatore è escluso/sostituito
GROUND_INJURY_REDUCTION_PER_STAR = 0.001  # Manto Erboso: -0,1 punti percentuali di prob. infortunio per stella
STREAMING_REVENUE_PER_STAR = 100_000      # ricavo streaming per stella, a ogni partita in casa

# Formazione: 1 portiere + fino a MAX_DEFENDERS difensori + fino a MAX_ATTACKERS attaccanti
MAX_DEFENDERS = 3
MAX_ATTACKERS = 3

# Modificatori di ingaggio applicati realmente (fonte: match_engine.py)
ENGAGEMENT_GOAL_MULT = {         # moltiplicatore gol
    'basso': 0.80, 'moderato': 0.80,        # -20% gol
    'normale': 1.00,
    'aggressivo': 1.10, 'super_aggressivo': 1.10,  # +10% gol
}
ENGAGEMENT_INJURY_ADD = {        # probabilità infortunio aggiuntiva per turno
    'aggressivo': 0.03, 'super_aggressivo': 0.03,
}
ENGAGEMENT_FRESH_MULT = {        # moltiplicatore del calo di freschezza
    'basso': 0.50, 'moderato': 0.50,        # -50% calo freschezza
}

# Autostart / risoluzione sfide PvP
MATCH_AUTOSTART_DELAY_SECONDS = 60     # avvio automatico lato richiesta (fonte: match.py)
MATCH_BACKUP_AUTOCALC_SECONDS = 120    # risoluzione automatica di backup (fonte: scheduler.py)

# ─────────────────────────────────────────────────────────────────────────────
# GIOCATORI E ABILITÀ          (fonte: app/utils/generators.py, app/models/team.py)
# ─────────────────────────────────────────────────────────────────────────────
SKILLS = ['porta', 'difesa', 'attacco', 'resistenza']
SKILL_GENERATION_MAX = 6.5       # tetto delle abilità alla generazione procedurale
SKILL_ABSOLUTE_MAX = 10.0        # tetto massimo raggiungibile con allenamento/ritiro/social
FRESHNESS_SCALE = (0, 10)        # scala nominale della freschezza
FRESHNESS_DAILY_RECOVERY = 0.3   # recupero freschezza per giorno di riposo (fonte: game.py)

# ─────────────────────────────────────────────────────────────────────────────
# ROSA E MERCATO               (fonte: app/routes/events.py, app/routes/game.py)
# ─────────────────────────────────────────────────────────────────────────────
MAX_ROSTER = 12                  # giocatori massimi in rosa
MARKET_OFFER_COST = 250_000      # costo acquisto offerta settimanale di mercato
SCOUTING_WEEKLY_COST = 1_000_000 # abbonamento settimanale Scouting Avanzato

# Aste agenti liberi
AUCTION_DECAY_PER_WEEK = 0.70    # prezzo *= 0.70 ogni settimana (decadimento -30%/settimana)
AUCTION_MIN_PRICE = 200_000      # prezzo minimo d'asta
AUCTION_BID_WINDOW_DAYS = 7      # finestra d'asta dopo la prima offerta
AUCTION_LISTING_EXPIRY_DAYS = 90 # scadenza massima del listing: alla scadenza si assegna alla miglior offerta o si svincola
SELLER_PCT_WITHIN_60 = 0.75      # quota al venditore se ceduto entro 60 giorni
SELLER_PCT_AFTER_60 = 0.50       # quota al venditore oltre i 60 giorni
SELL_BASE_PRICE_MULT = 1_000_000 # prezzo base messa in vendita = avg_skill * questo valore

# ─────────────────────────────────────────────────────────────────────────────
# ALLENAMENTO                  (fonte: app/routes/events.py)
# ─────────────────────────────────────────────────────────────────────────────
TRAINING_STANDARD_PROB = 0.20    # gratuito: 20% di successo, +0.1
TRAINING_P50K_COST = 50_000      # 50% di successo, +0.1
TRAINING_P50K_PROB = 0.50
TRAINING_P200K_COST = 200_000    # successo garantito (+0.1; 30% di probabilità di +0.2)
TRAINING_P200K_BIG_DELTA_PROB = 0.30
TRAINING_BULK_COST = 500_000     # bulk Mar/Gio: 500k flat, probabilità tipo P50k (50%) per tutti
TRAINING_FRESHNESS_COST = 0.1    # calo freschezza per sessione

# ─────────────────────────────────────────────────────────────────────────────
# STRUTTURE STADIO             (fonte: app/routes/game.py)
# ─────────────────────────────────────────────────────────────────────────────
# Soglie CUMULATIVE per raggiungere ogni livello di stelle (indice = stelle).
# Il costo del singolo upgrade = FACILITY_PRICES[n+1] - FACILITY_PRICES[n].
FACILITY_PRICES = [0, 1_000_000, 3_000_000, 5_000_000, 10_000_000, 25_000_000]
#   1★ tot. 1M  (upgrade 1M) | 2★ tot. 3M (upgrade 2M) | 3★ tot. 5M (upgrade 2M)
#   4★ tot. 10M (upgrade 5M) | 5★ tot. 25M (upgrade 15M)
FACILITY_MAX_STARS = 5
FACILITY_TYPES = ['training', 'stream', 'locker', 'ground']
# Effetti:
#   training → sessioni P200k gratuite il Sabato (slot = stelle)
#   stream   → +100k per stella a ogni partita in casa
#   locker   → 1 sessione fisioterapia/settimana per stella (riscuoti in Benessere)
#   ground   → -0,1 punti percentuali di prob. infortunio per stella

# ─────────────────────────────────────────────────────────────────────────────
# SPONSOR                      (fonte: app/routes/events.py)
# ─────────────────────────────────────────────────────────────────────────────
MAX_SECONDARY_SPONSORS = 2       # 1 principale + fino a 2 secondari
SECONDARY_SPONSOR_RATE = 0.30    # i secondari pagano il 30% del principale
SPONSOR_DURATION_WEEKS = (4, 10) # durata contrattuale configurabile
DARK_SPONSOR_COOLDOWN_WEEKS = 200          # Sponsor Oscuro: 1 uso ogni 200 settimane di gioco
DARK_SPONSOR_PAYOUT_MULT = 10_000_000      # payout = top7_avg_skill * questo valore (con conseguenze casuali)

# ─────────────────────────────────────────────────────────────────────────────
# PRESTITI / FEDERAZIONE       (fonte: app/routes/events.py)
# ─────────────────────────────────────────────────────────────────────────────
MAX_LOANS = 3
FEDERATION_TARGET = 2_000_000              # budget portato a questa soglia dal prestito d'emergenza
FEDERATION_STREAK_LIMIT = 25               # settimane consecutive in rosso prima dell'intervento federale
                                           # (dona ~50M ma dimezza tutte le abilità)

# ─────────────────────────────────────────────────────────────────────────────
# SOCIAL                       (fonte: app/utils/social.py)
# ─────────────────────────────────────────────────────────────────────────────
SOCIAL_CHANNELS = ['instok', 'sportsocial', 'fantasoccer']
CHANNEL_FRESHNESS_COST = 0.5     # calo freschezza per canale aperto, ogni settimana (Lunedì)
MAX_ACTIVE_SOCIAL_EFFECTS = 3
EFFECT_RELOCK_DAYS = 180         # un effetto spento da >=180 giorni non è riattivabile
CHANNEL_REOPEN_COOLDOWN_DAYS = 90
CARISMA_RANGE = {                # carisma nascosto per tipo (min, max)
    'uomo': (1, 8), 'cyber': (1, 5), 'donna': (4, 12),
}

# ─────────────────────────────────────────────────────────────────────────────
# LEGHE PRIVATE                (fonte: app/utils/league_engine.py)
# ─────────────────────────────────────────────────────────────────────────────
LEAGUE_CREATION_COST = 100_000_000
LEAGUE_LOAN_TOTAL_DUE = 105_000_000
LEAGUE_LOAN_WEEKLY_PAYMENT = 1_050_000
LEAGUE_LOAN_WEEKS = 100
LEAGUE_ENTRY_FEE = 10_000_000
LEAGUE_PERMANENCE_FEE = 5_000_000
LEAGUE_MIN_TEAMS = 4
LEAGUE_MAX_CAPACITY = 24
# Ripartizione del montepremi: erogato PER INTERO una sola volta a fine stagione,
# poi il budget della lega viene azzerato.
LEAGUE_OWNER_SHARE = 0.02        # 2% al proprietario
LEAGUE_EQUAL_SHARE = 0.68        # 68% in parti uguali
LEAGUE_MERIT_SHARE = 0.30        # 30% meritocratico
LEAGUE_POSITION_BONUSES = {1: 100, 2: 50, 3: 20, 4: 10}

# ─────────────────────────────────────────────────────────────────────────────
# CAMPIONATO PUBBLICO          (fonte: app/utils/championship_engine.py)
# ─────────────────────────────────────────────────────────────────────────────
CHAMPIONSHIP_BOT_ROSTER_SIZE = 7 # i bot del campionato schierano una rosa da 7

# ─────────────────────────────────────────────────────────────────────────────
# ECONOMIA GENERALE
# ─────────────────────────────────────────────────────────────────────────────
STARTING_BUDGET = 50_000_000     # budget iniziale di ogni squadra
POINTS_WIN = 3
POINTS_DRAW = 1
POINTS_LOSS = 0
