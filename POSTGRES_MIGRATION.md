# Migrazione a PostgreSQL su Render

## Problema
SQLite su Render si resetta ad ogni deploy. Per mantenere i dati persistenti serve PostgreSQL.

## Soluzione: PostgreSQL Gratuito su Render

### Step 1: Creare Database PostgreSQL su Render

1. Vai su https://dashboard.render.com
2. Click **"New +"** → **"PostgreSQL"**
3. Compila:
   - **Name**: `stockscreener-db`
   - **Database**: `stockscreener`
   - **User**: (generato automaticamente)
   - **Region**: Stesso del web service
   - **Plan**: **Free** (0$/mese, 90 giorni poi scade ma rinnovi gratis)
4. Click **"Create Database"**
5. Attendi 2-3 minuti per la creazione

### Step 2: Collegare Database al Web Service

1. Apri il tuo web service **stockscreener-2aeg**
2. Vai su **"Environment"**
3. Click **"Add Environment Variable"**
4. Aggiungi:
   - **Key**: `DATABASE_URL`
   - **Value**: Copia l'**Internal Database URL** dal database PostgreSQL creato
   - Format: `postgresql://user:password@host:5432/dbname`
5. Click **"Save Changes"**
6. Il servizio si riavvierà automaticamente

### Step 3: Deploy Codice Aggiornato

Il codice è già stato aggiornato per supportare PostgreSQL:
- ✅ `requirements.txt` include `psycopg2-binary`
- ⚠️ `database.py` deve essere riscritto (IN CORSO)

### Step 4: Verifica

Dopo il deploy:
1. Vai su https://stockscreener-2aeg.onrender.com
2. Esegui il primo ordine
3. Fai un nuovo deploy (push qualsiasi modifica)
4. Verifica che gli ordini siano ancora presenti ✅

## Vantaggi PostgreSQL

✅ **Persistenza**: Dati salvati permanentemente
✅ **Scalabilità**: Supporta più connessioni simultanee
✅ **Backup automatico**: Render fa backup giornalieri
✅ **Gratis**: Piano free 90 giorni (rinnovabile)

## Alternative (se non vuoi PostgreSQL)

### Opzione B: Render Disk (COSTA DENARO)
- Costo: $1/mese per 1GB
- Pros: Mantieni SQLite
- Cons: Pagamento mensile

### Opzione C: Database Esterno
- ElephantSQL, PlanetScale, Supabase
- Pros: Fuori da Render
- Cons: Più configurazione

## Prossimi Passi

🔧 Sto riscrivendo `database.py` per supportare PostgreSQL automaticamente.
Il codice rileverà `DATABASE_URL` e userà PostgreSQL, altrimenti SQLite locale.
