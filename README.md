# ⚽ FutureSoccer

<div align="center">

> ### **Il primo gioco di management calcistico ambientato nel 2099.**
> Tecnologia cyberpunk · Stadi del futuro · Giocatori potenziati · Competizione globale in tempo reale

[![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-green?logo=flask)](https://flask.palletsprojects.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-orange)](https://sqlalchemy.org)
[![License](https://img.shields.io/badge/License-Proprietary-red)]()

</div>

---

## 🌟 Il Prodotto — Visione d'Insieme

**FutureSoccer** è una piattaforma web di simulazione e management calcistico ambientata in un universo futuristico: anno 2099. Il calcio si è evoluto oltre i limiti umani. Atleti potenziati da innesti cyberbenetici, stadi ipersmart e intelligenza artificiale competono fianco a fianco in un mondo persistente sempre in movimento.

Il giocatore assume il ruolo di **Direttore Sportivo**, gestendo un club dalla A alla Z: rosa, tattiche, economia, strutture, sponsor, social media e competizioni — tutto in un **ecosistema live** dove ogni ora reale equivale a un giorno di gioco.

> 💡 **Per investitori e partner**: FutureSoccer è una piattaforma SaaS gaming con modello freemium, valuta virtuale e leve di retention quotidiana. Il backend modulare Flask + PostgreSQL è pronto per scalare da server singolo a architettura cloud distribuita.

---

## 🎯 Proposta di Valore Unica

| Pilastro | Vantaggio Competitivo |
|----------|-----------------------|
| 🕹️ **Profondità gestionale** | Economia, tattiche, wellness, social media — tutto integrato |
| ⚡ **Real-time** | Partite in tempo reale con turni da 30 secondi, sostituzioni live |
| 🤖 **Tre tipologie di atleti** | Uomo, Donna, Cyber — con statistiche e carisma differenti |
| 💎 **Monetizzazione nativa** | Valuta Gold, pass stagionali, abbonamenti e micro-transazioni |
| 🏆 **Competizione a più livelli** | PvP, Campionato pubblico, Leghe private, Tornei a eliminazione |
| 📱 **Retention quotidiana** | Ciclo settimanale con eventi ogni giorno di gioco |
| 🌐 **Scalabile** | Da SQLite locale a PostgreSQL cloud senza riscrittura del codice |

---

## 🗺️ Indice

1. [Panoramica del Gioco](#-panoramica-del-gioco)
2. [Sistema Giocatori](#-sistema-giocatori)
3. [Partite e Tattica](#-partite-e-tattica)
4. [Allenamento e Sviluppo](#-allenamento-e-sviluppo)
5. [Economia e Mercato](#-economia-e-mercato)
6. [Strutture dello Stadio](#-strutture-dello-stadio)
7. [Sistema Wellness e Recupero](#-sistema-wellness-e-recupero)
8. [Sponsorizzazioni](#-sponsorizzazioni)
9. [Mercato Agenti Liberi (Aste)](#-mercato-agenti-liberi-aste)
10. [Sistema Finanziario e Prestiti](#-sistema-finanziario-e-prestiti)
11. [Investimenti (Cedole)](#-investimenti-cedole)
12. [Social Media e Influenza](#-social-media-e-influenza)
13. [Campionato Pubblico](#-campionato-pubblico)
14. [Leghe Private](#-leghe-private)
15. [Tornei e Coppe](#-tornei-e-coppe)
16. [Hall of Fame](#-hall-of-fame)
17. [Calendario Settimanale](#-calendario-settimanale)
18. [Sistema Utenti e Profilo](#-sistema-utenti-e-profilo)
19. [Valuta Premium — Gold](#-valuta-premium--gold)
20. [Dashboard Amministrativa](#-dashboard-amministrativa)
21. [Orologio di Gioco](#-orologio-di-gioco)
22. [Loop Economico e Retention](#-loop-economico-e-retention)
23. [Monetizzazione](#-monetizzazione)
24. [Stack Tecnologico](#-stack-tecnologico)
25. [Avvio Rapido](#-avvio-rapido)
26. [Roadmap](#-roadmap)
27. [Contatti & Business](#-contatti--business)

---

## 🎮 Panoramica del Gioco

FutureSoccer si svolge in un **mondo persistente accelerato**: l'orologio di gioco avanza indipendentemente dalla presenza online dei manager, ma ogni giorno porta nuove opportunità — offerte di mercato, sessioni di allenamento, sfide PvP, proposte di sponsor — creando una pressione sana che invita a tornare ogni giorno.

- **Data di inizio**: 31 agosto 2099
- **Velocità predefinita**: 1 ora reale = 1 giorno di gioco (configurabile)
- **Budget iniziale**: €50.000.000
- **Rosa massima**: 12 giocatori (espandibile a 15 con Gold)
- **Tre archetipi**: Uomo · Donna · Cyber — ciascuno con distribuzioni di attributi uniche

---

## 🧬 Sistema Giocatori

Ogni atleta è **generato proceduralmente** e possiede una combinazione unica di statistiche, carisma e tipo. La profondità del sistema giocatori è il cuore del gameplay strategico.

### Attributi Principali

| Attributo | Descrizione | Range |
|-----------|-------------|-------|
| **Porta** | Efficacia da portiere — blocca i gol avversari | 0.5 → 10.0 |
| **Difesa** | Capacità difensiva — riduce il tasso di gol subiti | 0.5 → 10.0 |
| **Attacco** | Potere offensivo — incrementa la probabilità di segnare | 0.5 → 10.0 |
| **Resistenza** | Durata fisica — riduce il rischio infortuni e il calo di freschezza | 0.5 → 10.0 |

- Le abilità vengono generate nel range **0.5–6.5** e crescono attraverso l'allenamento fino al **tetto massimo di 10.0**
- La **media abilità** (`avg_skill`) determina il valore di mercato e il prezzo base nelle aste

### Freschezza (Freshness)

La **freschezza** è la risorsa più critica nella gestione giornaliera: scala da 0 a 10 e influenza direttamente la disponibilità dei giocatori in partita.

- Giocatori con freschezza **sotto 2** vengono esclusi automaticamente dalla formazione
- Ogni sessione di allenamento costa **−0.1** di freschezza
- Il **recupero naturale** è **+0.3 per giorno di riposo** (tetto 10.0)
- Gli **infortuni in partita** penalizzano da **−5 a −12** di freschezza, potendo andare in negativo
- Le **sessioni Wellness** (Fisioterapia, Salute, Cyber) recuperano freschezza in modo accelerato
- Il **Boost Gold** aggiunge istantaneamente **+2** a tutti i giocatori della rosa

### Carisma (Attributo Nascosto)

Il carisma è un valore segreto che influenza il sistema social media:

| Tipo Atleta | Range Carisma |
|-------------|---------------|
| Uomo | 1 – 8 |
| Cyber | 1 – 5 |
| Donna | 4 – 12 |

Il carisma determina la probabilità di sbloccare canali social e il bonus mensile che questi generano.

### Tipologie di Atleti

| Tipo | Caratteristiche | Strategia |
|------|-----------------|-----------|
| **Uomo** | Abilità bilanciate, carisma medio | Versatile, adatto a qualsiasi ruolo |
| **Donna** | Carisma elevato, eccellente per social | Ottima per generare entrate sui social |
| **Cyber** | Potenziale offensivo/difensivo alto, carisma basso | Power player — scarso social, alto impatto in campo |

### Hall of Fame

I giocatori con carriere eccezionali possono essere inclusi nella **Hall of Fame** del gioco, ricevendo il tag speciale `is_hof`. Questi atleti leggendari sono visibili nella sezione dedicata e rappresentano un elemento aspirazionale per tutti i manager.

---

## ⚽ Partite e Tattica

### Il Cuore dell'Esperienza Competitiva

Le partite di FutureSoccer non sono simulazioni passive: ogni match è **un evento live di circa 4 minuti** con decisioni reali a ogni turno.

### Struttura di una Partita

```
TURNO 1 → TURNO 2 → TURNO 3 → TURNO 4 → TURNO 5 → TURNO 6 → [SUPPLEMENTARE]
  30s        30s        30s        30s        30s        30s        30s
```

- **6 turni regolamentari** da 30 secondi ciascuno
- **1 turno supplementare** se il punteggio è in parità a fine gara
- In ogni turno viene simulata l'azione con la formula gol e calcolato il rischio infortuni
- **Log eventi in tempo reale**: gol, infortuni, esclusioni per stanchezza turno per turno

### Formula Gol

```
GOAL se: GOAL_COEFF × Attacco(squadra) × rand(0–2) / (Difesa(avversario) + Porta(avversario)) ≥ 1
```

La formula bilancia potere offensivo, solidità difensiva e un fattore di casualità controllata.

### Formazione Tattica

- **1 Portiere** fisso
- **Fino a 3 Difensori** (posizione dedicata)
- **Fino a 3 Attaccanti** (posizione dedicata)
- **Riserve**: entrano in campo su sostituzione del manager o automaticamente in caso di infortuni

### Modificatori di Ingaggio

Il manager sceglie lo stile di gioco prima della partita, con impatti diretti su attacco, freschezza e rischio:

| Livello | Modificatore Gol | Calo Freschezza | Rischio Infortuni |
|---------|:----------------:|:---------------:|:-----------------:|
| **Basso** | −20% | −50% | Normale |
| **Moderato** | −20% | −50% | Normale |
| **Normale** | Neutro | Normale | Normale |
| **Aggressivo** | +10% | Normale | +3% |
| **Super Aggressivo** | +10% | Normale | +3% |

### Azioni Live Durante la Partita

- **Sostituzioni in tempo reale**: effettive dal turno successivo
- **Cambio di ruolo live**: sposta giocatori tra difesa e attacco (nel rispetto dei limiti di formazione)
- **Snapshot formazione**: le statistiche vengono "bloccate" al calcio d'inizio per eliminare exploit last-minute

### Modalità di Gioco

| Modalità | Descrizione | Disponibilità |
|----------|-------------|---------------|
| **Amichevoli vs AI** | Sfide contro la `Squadra del Bar` (AI) | Ogni giorno, illimitate |
| **PvP — Sfide Dirette** | Sfida un altro manager umano | Lunedì–Venerdì (match day: Mer e Dom) |
| **Campionato Pubblico** | Partite automatiche nella lega di appartenenza | Mercoledì e Domenica |
| **Lega Privata** | Calendario all'italiana con altri club della lega | Come da calendario lega |
| **Tornei** | Fase eliminatoria con bracket automatico | Luglio (Finals) e coppe stagionali |

- Le sfide PvP si avviano automaticamente dopo **60 secondi reali** dall'orario stabilito
- Se un manager non è online, il server risolve automaticamente la partita lato back-end

---

## 🏋️ Allenamento e Sviluppo

L'allenamento è il principale motore di crescita a lungo termine. Il sistema a più livelli permette di scegliere il rapporto rischio/ricompensa per ogni sessione.

### Livelli di Allenamento

| Livello | Costo | Probabilità di Successo | Guadagno |
|---------|------:|:-----------------------:|:--------:|
| **Standard** | Gratuito | 20% | +0.1 abilità |
| **P50k** | €50.000/atleta | 50% | +0.1 abilità |
| **P200k** | €200.000/atleta | 100% (garantito) | +0.1 (30% di prob.: +0.2) |
| **Bulk (Martedì/Giovedì)** | €500.000 flat | 50% per ogni giocatore | +0.1 per quelli che riescono |

- La sessione **Bulk** allena l'intera rosa in una volta sola — ideale per team numerosi
- Il **Centro di Allenamento** (struttura stadio) offre sessioni P200k gratuite ogni sabato: quanti slot quante stelle (fino a 5 al giorno a 5★)
- Ogni sessione costa **−0.1 di freschezza** al giocatore allenato
- Nessuna abilità può superare il **tetto massimo di 10.0**

### Giorni di Allenamento

| Giorno | Attività |
|--------|----------|
| **Martedì** | Prima sessione settimanale (Standard / P50k / P200k / Bulk) |
| **Giovedì** | Seconda sessione settimanale |
| **Sabato** | Sessioni P200k gratuite (solo con Centro di Allenamento ≥ 1★) |

---

## 💰 Economia e Mercato

La gestione economica è tanto importante quanto quella tattica. Con un budget iniziale di **€50.000.000**, ogni decisione ha un impatto a lungo termine.

### Mercato Giocatori

#### Offerte Settimanali
- Ogni lunedì arriva un'offerta settimanale: un nuovo atleta disponibile a **€250.000**
- L'atleta ha statistiche visibili e può essere acquisito direttamente se c'è spazio in rosa

#### Scouting Avanzato
- Attivando lo **scouting premium** (€1.000.000/settimana), si accede a giocatori di qualità superiore con abilità più elevate
- Lo **Scouting Gold** (1 Gold/mese di gioco) garantisce un atleta con media fino a **6.0** con distribuzione pesata verso valori alti

### Riepilogo Flussi Economici

```
ENTRATE                            USCITE
─────────────────────────────      ─────────────────────────────
✅ Sponsor principale              💸 Acquisizione giocatori
✅ Sponsor secondari (fino a 2)    💸 Allenamento (P50k / P200k / Bulk)
✅ Sponsor Oscuro (1x/200 sett.)   💸 Upgrade strutture
✅ Sponsor Gold (10 Gold)          💸 Sessioni Wellness
✅ Sponsor Stadio (5 Gold)         💸 Scouting avanzato
✅ Streaming casa (+€100k/★)       💸 Fee lega privata
✅ Vendita giocatori (aste)        💸 Interessi sui prestiti
✅ Montepremi campionato           💸 Penali Sponsor Oscuro
✅ Montepremi lega privata         💸 Fee iscrizione / permanenza lega
✅ Cedole / investimenti           💸 Acquisto Gold
```

---

## 🏟️ Strutture dello Stadio

Lo stadio è l'infrastruttura fisica della squadra. Quattro tipologie di impianti, ciascuna potenziabile fino a **5 stelle**, con impatti diretti sulla competitività e sui ricavi.

### Le Quattro Strutture

| Struttura | Effetto in Gioco | Beneficio Strategico |
|-----------|-----------------|----------------------|
| 🏋️ **Centro di Allenamento** | Slot di sessioni P200k gratuite ogni sabato (1 slot per stella) | Risparmio massimo €1M/settimana a 5★ |
| 📡 **Servizi Streaming** | +€100.000 per stella a ogni partita casalinga | Entrata passiva garantita: €500k/partita a 5★ |
| 🚿 **Spogliatoi** | Genera 1 sessione di Fisioterapia a settimana per stella | Recupero freschezza gratuito |
| 🌱 **Manto Erboso** | Riduce il rischio infortuni (−0.1 punti % per stella) | Protezione fino a −0.5% a 5★ |

### Tabella Costi di Upgrade

| Livello | Investimento Totale | Costo Upgrade Singolo |
|---------|--------------------:|---------------------:|
| ⭐ 1 stella | €1.000.000 | €1.000.000 |
| ⭐⭐ 2 stelle | €3.000.000 | €2.000.000 |
| ⭐⭐⭐ 3 stelle | €5.000.000 | €2.000.000 |
| ⭐⭐⭐⭐ 4 stelle | €10.000.000 | €5.000.000 |
| ⭐⭐⭐⭐⭐ 5 stelle | €25.000.000 | €15.000.000 |

### Degradazione Mensile

⚠️ Ogni mese, **fino a 2 impianti** perdono automaticamente **1 stella**: questo crea una pressione costante a reinvestire e mantiene vivo l'economia del gioco nel lungo periodo.

**Eccezione**: lo **Sponsor Stadio** (5 Gold) blocca completamente la degradazione di tutti gli impianti per **50 settimane di gioco**.

---

## 💊 Sistema Wellness e Recupero

Il sistema Wellness è il contromisura principale agli infortuni e alla stanchezza cronica. Tre tipologie di sessioni, ognuna con un pool limitato per team.

### Tipologie di Sessioni

| Tipo | Effetto | Pool Massimo |
|------|---------|:------------:|
| 🩺 **Fisioterapia** | Recupero freschezza fisica accelerato | 20 sessioni |
| ❤️ **Salute** | Recupero generale e prevenzione | 5 sessioni |
| 🤖 **Cyber** | Manutenzione componenti cyberbenetici | 5 sessioni |

### Come Funziona

- **Finestra di acquisto**: da mercoledì a domenica, **1 sessione acquistabile per settimana**
- Gli **Spogliatoi** (struttura stadio) rigenerano automaticamente sessioni di Fisioterapia gratuite ogni settimana (1 per stella)
- Le sessioni si accumolano nel pool del team e vengono utilizzate on-demand dal manager

---

## 🎯 Sponsorizzazioni

Le sponsorizzazioni sono il **motore economico primario** del gioco — la rendita passiva che permette a una squadra di sopravvivere e crescere.

### Tipologie di Sponsor

#### 🏷️ Sponsor Principale
- **1 slot** sempre disponibile
- Offerta generata automaticamente ogni venerdì, calibrata sulla qualità media della rosa
- Durata configurabile: **4–10 settimane**
- Paga ogni settimana di gioco

#### 🏷️🏷️ Sponsor Secondari
- Fino a **2 slot** base (espandibile a 3 con Gold)
- Pagano al **30%** rispetto allo sponsor principale
- Stessa generazione automatica del venerdì

#### 🌑 Sponsor Oscuro
- **1 utilizzo ogni 200 settimane di gioco** — rarissimo e ad alto rischio
- Paga immediatamente una cifra elevata
- Ma porta **conseguenze casuali** (anche pesanti, come multe e penalità)
- Ideale per uscire da situazioni di crisi finanziaria acuta

#### 🥇 Sponsor Gold (10 Gold)
- Attivato con valuta premium
- Paga **€4.000.000/settimana per 5 settimane** → totale €20M garantiti
- Se l'aiuto della Federazione è attivo, lo salda immediatamente
- Occupa lo slot principale e rimane bloccato per 10 settimane

#### 🏟️ Sponsor Stadio (5 Gold)
- Trasforma lo sponsor principale in uno speciale contratto stadio
- Dura **50 settimane di gioco**
- Blocca completamente la **degradazione degli impianti**: nessuna struttura perde stelle durante la durata del contratto

---

## 🔨 Mercato Agenti Liberi (Aste)

Il mercato delle aste è il luogo dove i manager comprano e vendono talenti tra loro, con un sistema di offerte competitivo e un meccanismo di decadimento del prezzo.

### Come Funziona un'Asta

1. **Il venditore** mette il giocatore in vendita — il prezzo base è `avg_skill × €1.000.000`
2. Il giocatore appare nel mercato come **Agente Libero**
3. **La finestra d'asta** si apre con la prima offerta e dura **7 giorni di gioco**
4. Il prezzo decade del **30% ogni settimana** se non arrivano offerte
5. Dopo **90 giorni**, l'asta si chiude automaticamente:
   - Se ci sono offerte valide → vince la più alta
   - Se nessuna offerta → il giocatore viene svincolato (free agent)

### Commissioni al Venditore

| Durata in Vendita | % del Ricavato al Venditore |
|:-----------------:|:---------------------------:|
| ≤ 60 giorni | **75%** |
| > 60 giorni | **50%** |

---

## 🏦 Sistema Finanziario e Prestiti

Quando il budget scende sotto zero, FutureSoccer offre un sistema di prestiti multi-livello con tassi e durate differenti.

### Tipologie di Prestito

| Tipo | Caratteristiche | Rischio |
|------|-----------------|:-------:|
| 🟢 **Verde** | Importo basso, interesse basso, rimborso rapido | Basso |
| 🟡 **Giallo** | Bilanciato | Medio |
| 🔴 **Rosso** | Importo alto, interesse più alto | Alto |
| ⚫ **Nero** | Massimo importo, rimborso lento, interesse elevato | Molto alto |
| 🏛️ **Federazione** | Emergenza — si attiva dopo 25 settimane consecutive in rosso | Critico |

- **Massimo 3 prestiti attivi** contemporaneamente per team
- **Prestito Federazione**: il sistema porta automaticamente il budget a €2.000.000 ma **dimezza temporaneamente le abilità di tutti i giocatori** — una punizione severa per la gestione finanziaria irresponsabile

### Registro Transazioni (Ledger)

Ogni movimento economico viene registrato nel **ledger di bilancio** con categoria, importo, segno (entrata/uscita) e riferimento al giorno di gioco. Il manager può consultare l'intera storia finanziaria nella sezione **Finanze**.

---

## 📈 Investimenti (Cedole)

Il sistema cedole permette ai manager con surplus di budget di **far fruttare la liquidità** investendo in strumenti finanziari virtuali.

- **Cedola Verde / Gialla / Rossa / Nera**: rischio e rendimento crescenti
- Ogni cedola ha una **scadenza** (maturità): al termine, il capitale torna con gli interessi
- Gli investimenti sono visibili nel bilancio e contabilizzati come **attivo finanziario**
- Strategia ideale per i team con budget in surplus che vogliono ottimizzare i flussi di cassa

---

## 📲 Social Media e Influenza

Un sistema di **influenza mediatica** unico nel panorama dei giochi di management. I giocatori con alto carisma possono diventare vere star dei social, portando bonus economici mensili al club.

### I Tre Canali Social

| Canale | Descrizione |
|--------|-------------|
| 📸 **InstOK** | Piattaforma di immagini — ideale per giocatrici donna con alto carisma |
| 🏆 **SportSocial** | Rete sportiva specializzata — per i campioni riconosciuti |
| 🎮 **FanSoccer** | Community dei tifosi — accessibile ma con audience più ampia |

### Meccaniche Social

- **Sblocco canale**: richiede un check di carisma (probabilità variabile) — non tutti possono entrare in ogni canale
- **Effetti attivi**: massimo **3 canali attivi contemporaneamente** sull'intera rosa
- **Costo settimanale**: ogni canale attivo costa **−0.5 di freschezza** al giocatore
- **Cooldown**: dopo la disattivazione, il canale non può essere riaperto per **90 giorni di gioco**
- **Lock permanente**: se un canale rimane inattivo per oltre **180 giorni**, si blocca definitivamente per quel giocatore
- **Bonus mensile**: gli effetti attivi generano entrate mensili basate su carisma e popolarità del canale

---

## 🏆 Campionato Pubblico

La competizione principale di FutureSoccer: una **piramide a 5 livelli** dove ogni club scala o scende in base ai risultati mensili.

### Struttura a Livelli

```
        🥇 ELITE
       🥈 GOLD
      🥉 SILVER
     🟫 BRONZE
    ⬛ IRON
```

| Livello | Descrizione |
|---------|-------------|
| **Elite** | La vetta — solo i migliori. Montepremi più alti |
| **Gold** | Seconda divisione — un passo dalla gloria |
| **Silver** | Divisione intermedia — teatro delle battaglie più accese |
| **Bronze** | Livello per chi sta costruendo la propria potenza |
| **Iron** | Il punto di partenza — da qui si sale |

### Promozioni e Retrocessioni

- **Ogni mese**: i **top 2** di ogni gruppo salgono di livello, i **bottom 2** scendono
- Le partite del campionato si giocano nei **match day** (mercoledì e domenica)
- I **team bot** (AI) riempiono i gruppi dove mancano manager umani, garantendo una competizione sempre attiva

---

## 🏟️ Leghe Private

Le Leghe Private sono la feature più esclusiva e social di FutureSoccer: **competizioni su invito** create dai manager stessi, con economia interna, calendario personalizzato e un sistema di montepremi a fine stagione.

### Caratteristiche

| Parametro | Valore |
|-----------|--------|
| **Costo creazione** | €100.000.000 + prestito federazione €105M (100 settimane @ €1.05M/sett.) |
| **Fee iscrizione** | €10.000.000 per team partecipante |
| **Fee settimanale permanenza** | €5.000.000/settimana (ogni team) |
| **Team minimi** | 4 |
| **Team massimi** | 24 |
| **Formato** | Doppio girone all'italiana (stile Serie A) |

### Distribuzione Montepremi (Fine Stagione)

Il montepremi si accumula durante tutta la stagione e viene distribuito interamente a fine stagione, poi azzera:

| Quota | % del Montepremi | Beneficiario |
|-------|:----------------:|--------------|
| **Owner** | 2% | Proprietario della lega |
| **Uguale** | 68% | Diviso in parti uguali tra tutti i team |
| **Meritocratica** | 30% | Bonus per le prime 4 posizioni |

**Moltiplicatori bonus meritocratici:**
- 🥇 1° posto: **×100**
- 🥈 2° posto: **×50**
- 🥉 3° posto: **×20**
- 4° posto: **×10**

---

## 🏅 Tornei e Coppe

### 🎊 Finals di Luglio (Torneo Principale)
- Si svolge ogni luglio di gioco
- Formato a eliminazione diretta con **bracket automatico**
- Aperto a tutti i team — la prova suprema dell'anno
- **Montepremi vincitore: €15.000.000**

### 🥈 Coppa Secondaria
- Torneo a eliminazione separato durante la stagione
- Offre un percorso competitivo alternativo al campionato principale

### 🏆 Super Cup
- Playoff tra i migliori team — un'élite tra le élite
- Accesso limitato e montepremi dedicato

---

## 🌟 Hall of Fame

La **Hall of Fame** è il pantheon dei grandi campioni di FutureSoccer. Gli atleti con carriere straordinarie vengono immortalati con il badge speciale `HOF` e sono visibili nella sezione dedicata del gioco.

- Rappresenta un **traguardo aspirazionale** per ogni manager
- Gli atleti HOF mantengono il loro record anche dopo il ritiro o la cessione
- La Hall of Fame è consultabile da tutti i manager come fonte di ispirazione

---

## 📅 Calendario Settimanale

Ogni giorno porta un'opportunità diversa. Il calendario settimanale è la spina dorsale dell'engagement quotidiano.

| Giorno di Gioco | Attività Disponibili |
|-----------------|---------------------|
| **Lunedì** | 🔄 Reset offerte mercato · 📩 Apertura sfide PvP |
| **Martedì** | 🏋️ Prima sessione di allenamento |
| **Mercoledì** | ⚽ **MATCH DAY** PvP · 🔨 Aste agenti liberi · 🏃 Gestione rosa |
| **Giovedì** | 🏋️ Seconda sessione di allenamento |
| **Venerdì** | 💼 Ricezione offerte sponsorizzazione |
| **Sabato** | 🆓 Allenamento P200k gratuito (con Centro di Allenamento) |
| **Domenica** | ⚽ **MATCH DAY** principale · 🤝 Amichevoli vs AI |

---

## 👤 Sistema Utenti e Profilo

### Registrazione e Autenticazione

- **Registrazione con verifica email** (integrazione Brevo API)
- **Login sicuro** con opzione "Ricordami" e hashing bcrypt
- **Reset password** via link email con token a scadenza
- **Tracking ultimo accesso** per analytics di engagement

### Profilo Personalizzabile

- **Username** modificabile
- **Avatar** personalizzato
- **Storico partite e statistiche**
- **Wallet Gold** visibile con saldo aggiornato
- **Creazione guidata del team** al primo accesso (nome, città, stadio, colori)

---

## 💎 Valuta Premium — Gold

Il **Gold** è la valuta premium di FutureSoccer. Tutte le transazioni premium sono registrate in un ledger dedicato (`GoldTransaction`) per piena trasparenza operativa e compliance.

### Come Acquistare Gold (con denaro reale)

> ⚙️ Il sistema di pagamento è predisposto con endpoint e provider astratto. **Attivo solo configurando un provider** (es. Stripe via `STRIPE_SECRET_KEY`).

| Pacchetto | Prezzo | Gold |
|-----------|-------:|-----:|
| Starter | €5 | 10 Gold |
| Pro | €20 | 50 Gold |
| **Abbonamento mensile** | **€5/mese** | **8 Gold** (primi 6 mesi) → **16 Gold**/mese |

### Pass Speciali

| Pass | Costo | Contenuto | Condizioni |
|------|------:|-----------|------------|
| **Pass Stagionale** | €3 | 10 Gold + €25M in-game | 1 volta a stagione (set–dic) |
| **Pass Natale** | Gratuito | 2 Gold | Automatico ogni 25 dic di gioco |
| **Pass Finanza** | 5 Gold | €250.000.000 in-game | On demand |

### Spese Gold — Abbonamenti Mensili (1 Gold/mese ciascuno)

| Servizio | Effetto | Max |
|----------|---------|:---:|
| **Scouting Gold** | 1 giocatore premium/mese (avg ≤ 6.0, distribuzione pesata) | 1 |
| **Slot Rosa Extra** | +1 slot oltre i 12 base | 3 |
| **Slot Sponsor Extra** | +1 sponsor secondario oltre i 2 base | 1 |

### Spese Gold — Acquisti Singoli

| Acquisto | Costo | Effetto |
|----------|------:|---------|
| **Sponsor Gold** | 10 Gold | €4M/sett. × 5 settimane; salda il debito federale se attivo |
| **Sponsor Stadio** | 5 Gold | 50 settimane, blocca degradazione strutture |
| **Boost Freschezza** | 1 Gold | +2 freschezza istantanea a tutta la rosa |
| **Pass Finanza** | 5 Gold | €250M in-game |

### Funzione Admin

- Il **superadmin** può regalare **10 Gold** a tutti gli utenti dalla dashboard — ideale per eventi speciali, lanci e campagne di engagement

---

## 🛡️ Dashboard Amministrativa

Pannello di controllo completo per gli operatori della piattaforma.

### Funzionalità Admin

| Sezione | Capacità |
|---------|----------|
| **Gestione Utenti** | Crea, modifica, elimina account · Visualizza storico login |
| **Gestione Squadre** | Accesso diretto a tutti i team: budget, statistiche, rosa completa |
| **Gestione Giocatori** | Modifica attributi, freschezza, tipo, age di qualsiasi atleta |
| **Orologio di Gioco** | Avanza manualmente il tempo (utile per testing ed eventi speciali) |
| **Classifica Globale** | Panoramica in tempo reale dell'intera community |
| **Gift Gold** | Dona 10 Gold a tutti gli utenti con un solo click |
| **Statistiche Globali** | Match giocati, utenti attivi, transazioni, top team |

---

## ⏰ Orologio di Gioco

FutureSoccer gira su un **orologio accelerato** completamente configurabile — il principale strumento di bilanciamento del ritmo di gioco.

| Parametro | Valore Predefinito | Note |
|-----------|------------------:|------|
| **GAME_CLOCK_RATIO** | 3600 secondi | 1 ora reale = 1 giorno di gioco |
| **Data di inizio** | 31 agosto 2099 | Immutabile |
| **Modalità Fast August** | Attiva | 3–26 agosto: accelerazione extra |
| **Modalità Week** | Opzionale | 1 giorno reale ≈ 1 settimana di gioco |
| **Modalità Month** | Opzionale | Per testing rapido |

L'admin può **avanzare manualmente il tempo** dalla dashboard — fondamentale per eventi speciali, stress test e campagne a tempo limitato.

---

## 🔄 Loop Economico e Retention

### Il Loop di Gioco

```
        ┌─────────────────────────────────────────┐
        │                                         │
        ▼                                         │
  BUDGET INIZIALE €50M                            │
        │                                         │
        ▼                                         │
  Acquisto Giocatori / Allenamento / Strutture    │
        │                                         │
        ▼                                         │
  Squadra più Forte → Più Vittorie                │
        │                                         │
        ▼                                         │
  Sponsor Migliori + Montepremi + Streaming  ─────┘
```

### Retention Drivers — Frequenza e Impatto

| Meccanica | Frequenza | Impatto Retention |
|-----------|:---------:|:-----------------:|
| Offerte di mercato | Settimanale (Lunedì) | 🔴 Alta |
| Allenamento giocatori | 2–3x/settimana | 🔴 Alta |
| Partite PvP | Mercoledì + Domenica | 🔴 Altissima |
| Offerte sponsor | Settimanale (Venerdì) | 🟠 Media-Alta |
| Aste agenti liberi | Continua (7gg finestre) | 🟠 Media |
| Gestione social media | Mensile | 🟡 Media |
| Degradazione strutture | Mensile | 🟡 Media |
| Tornei | Stagionale | 🔴 Alta (picco) |
| Montepremi lega | Fine stagione | 🔴 Altissima (picco) |

### Vantaggi per l'Operatore

- **Daily Active Users garantiti**: il ciclo settimanale crea un habit loop quotidiano
- **Monetization touchpoints multipli**: ogni area del gioco ha un'opzione premium
- **Churn prevention**: la degradazione delle strutture e i contratti sponsor attivi creano switching cost emotivi
- **Social hooks**: le leghe private generano reti di amici che si invitano a vicenda

---

## 💳 Monetizzazione

### Modello Freemium

FutureSoccer adotta un modello **freemium**: il gioco base è completamente gratuito e competitive; la valuta Gold offre vantaggi di comodità e accelerazione, non di pay-to-win puro.

### Stack Monetizzazione Attuale

```
┌─────────────────────────────────────────────────────────┐
│  TIER 1: One-time purchases                              │
│  • Pack 10 Gold (€5) · Pack 50 Gold (€20)               │
│  • Pass Stagionale (€3): 10 Gold + €25M                  │
│                                                          │
│  TIER 2: Subscription                                    │
│  • €5/mese → 8 Gold (poi 16): massimo LTV               │
│                                                          │
│  TIER 3: In-game Gold spending                           │
│  • Sponsor Gold · Sponsor Stadio · Scouting              │
│  • Slot Extra · Boost Freschezza · Pass Finanza          │
└─────────────────────────────────────────────────────────┘
```

### Roadmap Monetizzazione (da Implementare)

- [ ] **Integrazione Stripe**: Checkout + webhook server-side, abbonamenti ricorrenti
- [ ] **Training Premium**: sessioni dedicate con tassi di successo superiori
- [ ] **Cosmetici**: skin stadio, colori esclusivi, temi UI, badge profilo
- [ ] **Assicurazione Infortuni**: protezione premium contro infortuni gravi
- [ ] **Riduzione Cooldown**: Sponsor Oscuro, canali social, aste
- [ ] **Scout Mirato**: scegli la tipologia di giocatore da cercare
- [ ] **Branding Personalizzato**: nome e logo sponsor/lega brandizzati
- [ ] **Anticipo Montepremi**: accesso early al fondo lega
- [ ] **Notifiche Push Premium**: alert real-time su match, aste, sponsor

---

## 🛠️ Stack Tecnologico

| Layer | Tecnologia | Note |
|-------|-----------|------|
| **Backend** | Python 3 / Flask 3.0.3 | Modularizzato con Blueprint |
| **ORM** | SQLAlchemy 2.0 + Flask-Migrate (Alembic) | DB-agnostic, 15 migration versions |
| **Autenticazione** | Flask-Login + Flask-Bcrypt | Session management + hashing sicuro |
| **Email** | Brevo API (ex Sendinblue) | Verifica, reset password, notifiche |
| **Scheduling** | APScheduler 3.10.4 | Job periodici (giornalieri, settimanali, mensili) |
| **Frontend** | HTML5 + CSS3 + Jinja2 + Vanilla JS | No framework frontend — load leggero |
| **Font** | Orbitron (Google Fonts) | Estetica futuristica e riconoscibile |
| **Database** | SQLite (dev) → PostgreSQL (prod) | Zero riscrittura per migrazione |
| **Media** | Pillow | Gestione avatar e immagini |

### Scalabilità

- **Architettura modulare** a Blueprint Flask: ogni area di gioco è un modulo indipendente
- **ORM database-agnostic**: passaggio da SQLite a PostgreSQL con una sola variabile d'ambiente
- **Email transazionale** già integrata (Brevo)
- **Deployment-ready**: struttura testata per Heroku, Railway, Render, AWS, Hetzner
- **Scheduler**: configurabile per deployment multi-processo WSGI (gunicorn/uwsgi — un solo worker esegue lo scheduler)

### Parametri di Bilanciamento

Tutte le costanti di gioco sono documentate in un unico file di riferimento: [`parametri.py`](parametri.py)

- Orologio di gioco · Partite · Allenamento · Mercato
- Sponsor · Strutture · Leghe · Campionato · Tornei
- Social media · Gold · Prestiti · Cedole

---

## 🏁 Avvio Rapido

```bash
# 1. Clona il repository
git clone https://github.com/pywis/futuresoccer.git
cd futuresoccer

# 2. Crea ambiente virtuale
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Installa dipendenze
pip install -r requirements.txt

# 4. Configura variabili d'ambiente
cp .env.example .env
# Edita .env con le tue credenziali (database, email, secret key, etc.)

# 5. Inizializza e migra il database
flask db upgrade

# 6. Avvia il server
python run.py
```

🌐 Apri il browser su **`http://localhost:5000`** e inizia a costruire la tua squadra del futuro.

### Variabili d'Ambiente Principali

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `SECRET_KEY` | Chiave sessione Flask | — (obbligatoria) |
| `DATABASE_URL` | URL database | SQLite locale |
| `GAME_CLOCK_RATIO` | Secondi reali per 1 giorno di gioco | 3600 |
| `GOAL_COEFF` | Coefficiente formula gol | 1.0 |
| `MATCH_TURN_SECONDS` | Durata turno in secondi | 30 |
| `INJURY_BASE` | Probabilità base infortuni (%) | 1.0 |
| `BREVO_API_KEY` | Chiave API email | — |
| `ADMIN_USERNAME` | Username superadmin | — |
| `SCHEDULER_ENABLED` | Attiva scheduler | true |

---

## 🗺️ Roadmap

### ✅ Completato
- [x] Sistema di registrazione e autenticazione con verifica email
- [x] Gestione rosa con tre tipologie di atleti (Uomo, Donna, Cyber)
- [x] Sistema allenamento a più livelli con fattore RNG
- [x] Partite in tempo reale con 6 turni + supplementare
- [x] Sostituzioni live e cambio ruolo durante la partita
- [x] Modificatori di ingaggio (5 livelli: Basso → Super Aggressivo)
- [x] Sistema freschezza e recupero automatico
- [x] Quattro strutture stadio (fino a 5★) con degradazione mensile
- [x] Sponsorizzazioni (principale + secondari + Oscuro + Gold + Stadio)
- [x] Mercato agenti liberi con aste e decadimento prezzo
- [x] Sistema prestiti multi-livello (Verde / Giallo / Rosso / Nero / Federazione)
- [x] Cedole e investimenti con scadenza
- [x] Sistema social media (InstOK, SportSocial, FanSoccer) con carisma
- [x] Valuta premium Gold con wallet e registro transazioni
- [x] Campionato pubblico a 5 livelli (Elite → Iron) con promozioni/retrocessioni
- [x] Leghe private con calendario all'italiana e montepremi
- [x] Tornei a eliminazione (Finals luglio, Coppa, Super Cup)
- [x] Hall of Fame per i campioni leggendari
- [x] Dashboard amministrativa completa
- [x] Orologio di gioco configurabile e controllabile da admin
- [x] Sistema Wellness (Fisioterapia, Salute, Cyber) con pool limitato
- [x] Servizi Streaming (ricavi a partita in casa)
- [x] Spogliatoi (sessioni fisioterapia settimanali gratuite)
- [x] Amichevoli vs AI (Squadra del Bar) disponibili ogni giorno

### 🔜 In Sviluppo
- [ ] Integrazione Stripe (pagamenti reali + abbonamenti)
- [ ] Notifiche push (match, mercato, sponsor, aste)
- [ ] App mobile (PWA)
- [ ] Cosmetici premium (skin stadio, temi UI, badge)
- [ ] Sistema talenti (giovani con potenziale nascosto)
- [ ] Modalità allenatore avanzata con tattiche personalizzabili
- [ ] Torneo internazionale cross-server
- [ ] Assicurazione infortuni premium
- [ ] Scout mirato per tipologia e ruolo

---

## 📊 KPI e Metriche di Riferimento

Per investitori e operatori, FutureSoccer è progettato attorno a queste metriche chiave:

| KPI | Meccanica che lo guida |
|-----|----------------------|
| **DAU/MAU** | Ciclo settimanale con trigger giornalieri |
| **Session Length** | Partite live da ~4 minuti + gestione pre/post-match |
| **ARPU** | Gold: abbonamento €5/mese + acquisti una tantum |
| **LTV** | Sponsor attivi + lega privata = switching cost elevato |
| **Virality** | Leghe private = acquisizione organica per invito |
| **Churn Prevention** | Contratti sponsor e strutture da mantenere = abitudine |

---

## 📫 Contatti & Business

Per **partnership**, **licensing**, **investimenti**, **white-label** o **integrazioni enterprise**:

**Repository**: [github.com/pywis/futuresoccer](https://github.com/pywis/futuresoccer)

---

<div align="center">

*FutureSoccer — Il calcio come non l'hai mai vissuto.*

**Anno 2099. Il futuro è adesso.**

</div>
