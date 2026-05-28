# ⚽ FutureSoccer

> **Il primo gioco di management calcistico ambientato nel 2099.**
> Tecnologia cyberpunk, stadi del futuro, giocatori potenziati e competizione globale in tempo reale.

---

## 🚀 Panoramica del Prodotto

**FutureSoccer** è un gioco di simulazione e management calcistico web-based, ambientato in un universo futuristico dove il calcio si è evoluto oltre i limiti umani. I giocatori assumono il ruolo di direttore sportivo, costruendo squadre di atleti umani, donne e cyborg, gestendo budget milionari, strutture d'avanguardia e affrontando avversari reali in sfide settimanali in tempo reale.

Il gioco gira su un **orologio accelerato** (per impostazione predefinita **1 ora reale = 1 giorno di gioco**, configurabile via `GAME_CLOCK_RATIO`), creando un mondo persistente in continua evoluzione che spinge i manager a tornare ogni giorno per non perdere opportunità di mercato, sessioni di allenamento e partite decisive. Il mondo parte dal **31 agosto 2099**.

---

## 🎮 Funzionalità di Gioco

### 👥 Gestione della Squadra

- **Creazione team personalizzata**: nome, città, stadio, colori esclusivi
- **Rosa fino a 12 giocatori**, con tre tipologie: Uomo, Donna, Cyber
- **Statistiche complete**: vittorie, pareggi, sconfitte, gol fatti/subiti, budget
- **Classifica generale** in tempo reale con sistema a punti (3V / 1P / 0S)

### 🧬 Sistema Giocatori

Ogni atleta è generato proceduralmente con attributi unici:

| Attributo | Descrizione |
|-----------|-------------|
| **Porta** | Capacità da portiere |
| **Difesa** | Efficacia difensiva |
| **Attacco** | Potere offensivo |
| **Resistenza** | Durata fisica e recupero |

- Le abilità individuali partono nel range **0.5–4.5** (rosa iniziale e offerte di mercato base); con lo **Scouting Avanzato** si arriva fino a **6.5** e con lo **Scouting Gold** fino a circa **7.0**. Tutte le skill possono crescere con l'allenamento fino al tetto massimo di **10.0**
- **Freschezza** (scala 0–10): influenza la partecipazione alle partite; i giocatori esausti (freschezza sotto 2) sono esclusi automaticamente
- **Infortuni**: penalizzano pesantemente la freschezza (da −5 a −12), potendola portare in negativo; vengono gestiti in tempo reale durante le partite e recuperati con le sessioni Benessere
- **Tre tipologie** di giocatore (uomo, donna, cyber): ognuna con un range di carisma nascosto diverso (uomo 1–8, donna 4–12, cyber 1–5) che incide sull'influenza social della squadra
- **Recupero automatico**: +0.3 di freschezza per ogni giorno di riposo (tetto 10)

### ⚽ Sistema Partite

**Il cuore dell'esperienza competitiva.**

- **6 turni di gioco** + eventuale turno di supplementare in caso di parità
- **30 secondi reali per turno**: adrenalina pura con decisioni rapide
- **Formazione tattica**: 1 portiere + fino a 3 difensori + fino a 3 attaccanti + riserve
- **Modificatori di ingaggio**: dal −20% al +10% sui gol per personalizzare l'approccio (gli ingaggi aggressivi aumentano anche il rischio infortuni, quelli bassi riducono il calo di freschezza)
- **Sostituzioni in tempo reale** con effetto dal turno successivo
- **Cambio di ruolo live**: sposta giocatori tra le posizioni durante la partita (nel rispetto dei limiti di formazione)
- **Log eventi turno per turno**: gol, infortuni, esclusioni per stanchezza
- **Snapshot della formazione**: le statistiche al momento del calcio d'inizio sono fissate, eliminando exploit last-minute

**Modalità di gioco:**
- **Amichevoli vs AI** (`Squadra del Bar` o squadre bot del campionato): si giocano nei match day (**mercoledì e domenica**), una sola al giorno
- **Sfide PvP**: invia la sfida nei giorni non-partita (lun–mar–gio–ven–sab); la partita parte automaticamente al prossimo match day (**mercoledì o domenica**)
- **Autostart delle sfide** dopo 60 secondi reali dall'inizio del match day (con risoluzione automatica di backup lato server)

### 🏋️ Allenamento Giocatori

**Sistema di sviluppo a più livelli**, con progressione controllata e fattore RNG:

| Livello | Costo | Esito |
|---------|-------|-------|
| Standard | Gratuito | 20% di successo → +0.1 abilità |
| P50k | €50.000/atleta | 50% di successo → +0.1 abilità |
| P200k | €200.000/atleta | Successo garantito → +0.1 (30% di probabilità di +0.2) |
| Bulk (Mar/Gio) | €500.000 flat | Probabilità tipo P50k (50%) per tutti |

- **Giorni di allenamento**: martedì e giovedì (con giorni di recupero mercoledì e venerdì); il sabato con struttura dedicata
- **Penalità freschezza**: ogni sessione costa −0.1 di freschezza
- **Centro di Allenamento**: offre sessioni P200k gratuite il sabato (slot = stelle della struttura)
- Le abilità non possono superare il tetto massimo di **10.0**

### 🏟️ Strutture dello Stadio

**Quattro categorie di impianti** da potenziare fino a 5 stelle:

| Struttura | Effetto |
|-----------|---------|
| **Centro di Allenamento** | Sessioni P200k gratuite il sabato (slot = stelle) |
| **Servizi Streaming** | +€100.000 per stella a ogni partita giocata in casa |
| **Spogliatoi** | Genera 1 sessione di fisioterapia a settimana per stella (riscuoti in Benessere) |
| **Manto Erboso** | Riduce il rischio infortuni (−0,1 punti percentuali per stella) |

**Costi di upgrade (soglie cumulative per raggiungere ogni livello):**

| Stelle | Investimento totale | Costo del singolo upgrade |
|--------|--------------------:|--------------------------:|
| 1★ | €1M | €1M |
| 2★ | €3M | €2M |
| 3★ | €5M | €2M |
| 4★ | €10M | €5M |
| 5★ | €25M | €15M |

- **Degradazione mensile**: fino a 2 impianti perdono 1 stella ciascuno, creando pressione costante a reinvestire
- Ogni upgrade è un investimento strategico a lungo termine nel vantaggio competitivo

### 💰 Economia e Mercato

**Budget iniziale: €50.000.000** — gestiscilo saggiamente.

#### Mercato Giocatori
- **Offerte settimanali**: acquisizione a €250.000/atleta
- **Scouting Avanzato** (€1M/settimana): accesso a giocatori di qualità superiore
- **Mercato Agenti Liberi**: metti i tuoi giocatori all'asta o acquista quelli degli avversari

#### Sistema Aste Agenti Liberi
- Prezzo base alla messa in vendita = abilità media × €1.000.000
- Finestra d'asta di 7 giorni dopo la prima offerta
- Prezzo con decadimento del 30% a settimana
- I venditori ricevono il **75%** del ricavato (entro 60 giorni di gioco dalla messa in vendita) o il **50%** oltre
- Al raggiungimento dei **90 giorni** il giocatore esce comunque dall'asta: se ci sono offerte valide vince la più alta, altrimenti viene svincolato

#### Sponsorizzazioni
- **1 sponsor principale** + fino a **2 sponsor secondari**
- Generazione automatica di offerte ogni venerdì, calibrate sulla qualità media della squadra
- Gli sponsor secondari pagano al 30% rispetto al principale
- Durata contrattuale configurabile: 4–10 settimane
- **Entrata passiva settimanale**: il vero motore economico del gioco
- **Sponsor Oscuro**: utilizzabile una sola volta ogni 200 settimane di gioco — paga subito ma con conseguenze casuali (anche multe)

### 📅 Calendario Settimanale di Gioco

| Giorno | Attività |
|--------|----------|
| **Lunedì** | Reset offerte mercato, apertura sfide PvP |
| **Martedì** | Sessione di allenamento disponibile |
| **Mercoledì** | Gestione squadra, aste agenti liberi, **match day** PvP |
| **Giovedì** | Seconda sessione di allenamento |
| **Venerdì** | Ricezione offerte sponsorizzazione |
| **Sabato** | Allenamento gratuito P200k (con struttura) |
| **Domenica** | **MATCH DAY** — amichevoli e sfide PvP |

### 👤 Sistema Utenti

- **Registrazione con verifica email** (integrazione Brevo)
- **Login sicuro** con "ricordami" e hashing bcrypt
- **Reset password** via email
- **Profilo utente** personalizzabile (username, avatar)
- **Tracking ultimo accesso**

### 🏆 Leghe Private e Campionato

- **Leghe private** a invito con calendario all'italiana, fee d'iscrizione e di permanenza, e un montepremi che viene distribuito **per intero a fine stagione** (2% al proprietario, 68% in parti uguali, 30% meritocratico) e poi azzerato
- **Campionato pubblico** a fasce con promozioni/retrocessioni mensili
- **Tornei** a eliminazione

---

## 📊 Dashboard Amministrativa

Pannello di controllo completo per operatori e business:

- **Gestione utenti**: crea, modifica, elimina account
- **Gestione squadre**: accesso diretto a tutti i team e giocatori
- **Controllo orologio di gioco**: avanza manualmente il tempo per eventi speciali
- **Classifica e statistiche globali**: panoramica in tempo reale dell'intera community

---

## 💎 Monetizzazione — Valuta Premium (Gold)

Il gioco include una **valuta premium (Gold)** con wallet sull'utente, registro transazioni dedicato (`GoldTransaction`) e negozio in-game (`/premium`). Le costanti sono in [`parametri.py`](parametri.py).

### Acquisto Gold (denaro reale)
> Predisposto con endpoint e provider astratto; **attivo solo configurando un provider di pagamento** (es. Stripe via `STRIPE_SECRET_KEY`). Finché non configurato, i pulsanti d'acquisto reale sono disattivati.

- **5 €** → 10 Gold · **20 €** → 50 Gold
- **Abbonamento 5 €/mese** → 8 Gold (primi 6 pagamenti), 16 Gold dai successivi

### Pass
- **Pass Stagionale** (3 €): 10 Gold + €25M, una volta a stagione (set–dic) *(richiede pagamento reale)*
- **Pass Natale**: 2 Gold gratuiti ogni 25 dicembre di gioco *(automatico)*
- **Pass Finanza**: €250M di gioco → 5 Gold

### Spese Gold (implementate)
- **Scouting Gold** — 1 Gold/mese di gioco → un giocatore (media fino a 6.0, distribuzione pesata)
- **Slot rosa extra** — 1 Gold/mese per slot, max 3 (oltre i 12 base)
- **Slot sponsor secondario extra** — 1 Gold/mese, max 1 (oltre i 2 base)
- **Sponsor Gold** (10 Gold) — sponsor €4M/sett. per 5 settimane; se l'aiuto della Federazione è attivo, lo salda e resta bloccato in principale per 10 settimane
- **Sponsor Stadio** (5 Gold) — trasforma lo sponsor principale in Sponsor Stadio per 50 settimane: blocca la manutenzione (niente degradazione)
- **Boost freschezza** (1 Gold) — +2 freschezza istantanea a tutti i giocatori
- Il **superadmin** può regalare 10 Gold a tutti gli utenti dalla dashboard

### Roadmap monetizzazione (da implementare)
- **Integrazione pagamenti** reale (Stripe Checkout + webhook con verifica server-side)
- **Training Premium**, **cosmetici** (colori/skin/temi stadio), **assicurazione infortuni**
- Riduzione cooldown Sponsor Oscuro / canali social, anticipo o boost montepremi lega
- Pacchetti "scout mirato", branding personalizzato sponsor/lega

---

## 🔄 Modello di Business — Loop Economico

```
Budget → Acquisto Giocatori / Allenamento / Strutture
  ↑                                              ↓
Sponsor / Vendite Mercato  ←  Qualità Squadra Migliorata
```

### Retention Drivers

| Meccanica | Frequenza | Impatto |
|-----------|-----------|---------|
| Offerte mercato | Settimanale | Alta |
| Allenamento | 2–3x/settimana | Alta |
| Offerte sponsor | Settimanale | Media |
| Match PvP | Settimanale | Altissima |
| Degradazione strutture | Mensile | Media |
| Aste agenti liberi | Continua | Media |

---

## 🛠️ Stack Tecnologico

| Layer | Tecnologia |
|-------|------------|
| **Backend** | Python 3 / Flask 3.0 |
| **ORM** | SQLAlchemy 2.0 + Flask-Migrate |
| **Auth** | Flask-Login + Flask-Bcrypt |
| **Email** | Brevo API (ex Sendinblue) |
| **Frontend** | HTML5 / CSS3 / Jinja2 / Vanilla JS |
| **Database** | SQLite (scalabile a PostgreSQL) |
| **Font** | Orbitron — estetica futuristica |

### Parametri di gioco
Tutte le costanti di bilanciamento (orologio, partite, allenamento, mercato, sponsor, strutture, leghe, social) sono documentate in un unico riferimento: [`parametri.py`](parametri.py).

### Scalabilità
- Architettura modulare a blueprint Flask
- ORM database-agnostic (SQLite → PostgreSQL senza riscrittura)
- Sistema email transazionale già integrato (Brevo)
- Struttura pronta per deployment su cloud (Heroku, Railway, Render, AWS)

> ⚠️ In deployment WSGI multi-processo (gunicorn/uwsgi) lo scheduler di gioco va avviato esplicitamente in un solo worker (vedi `run.py` / `SCHEDULER_ENABLED`).

---

## 🏁 Avvio Rapido

```bash
# Clona il repository
git clone https://github.com/pywis/futuresoccer.git
cd futuresoccer

# Crea ambiente virtuale
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Installa dipendenze
pip install -r requirements.txt

# Configura variabili d'ambiente
cp .env.example .env
# Edita .env con le tue credenziali

# Inizializza il database
flask db upgrade

# Avvia il server
python run.py
```

Apri il browser su `http://localhost:5000` e inizia a costruire la tua squadra del futuro.

---

## 🗺️ Roadmap

- [x] Servizi Streaming (ricavi a partita in casa)
- [x] Spogliatoi (sessioni di fisioterapia settimanali)
- [ ] Lega stagionale con playoff
- [ ] Notifiche push (match, mercato, sponsor)
- [ ] App mobile (PWA)
- [ ] Torneo internazionale cross-server
- [ ] Modalità allenatore avanzata con tattiche personalizzabili
- [ ] Sistema di talenti (giocatori giovani con potenziale nascosto)

---

## 📫 Contatti & Business

Per partnership, licensing, investimenti o integrazioni enterprise:

**Repository**: [github.com/pywis/futuresoccer](https://github.com/pywis/futuresoccer)

---

*FutureSoccer — Il calcio come non l'hai mai vissuto. Anno 2099.*
