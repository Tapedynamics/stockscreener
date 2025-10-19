# Stock Screener - Finviz

Web application per analizzare e organizzare stocks da Finviz screener.

## Features

- Estrae i primi 15 stocks da un screener Finviz personalizzato
- Organizza automaticamente in 3 categorie:
  - **Top 3**: Take Profit (posizioni 1-3)
  - **10 Hold**: Basket principale (posizioni 4-13)
  - **2 Buffer**: Riserva (posizioni 14-15)
- Interfaccia web moderna e responsive
- Aggiornamento in tempo reale con un click

## Screener Configurato

Il screener utilizza i seguenti parametri Finviz:
- Mid/Large Cap USA stocks
- EPS growth positivo (5 anni)
- Net margin alto
- Operating margin > 20%
- P/E < 30
- ROE positivo
- Volume alto (avg > 100K, current > 100K)
- Sopra SMA 200
- Ordinato per performance 4 settimane (decrescente)

## Installazione Locale

### Prerequisiti
- Python 3.11+
- pip

### Setup

1. Clona il repository:
```bash
git clone https://github.com/Tapedynamics/stockscreener.git
cd stockscreener
```

2. Installa le dipendenze:
```bash
pip install -r requirements.txt
```

3. Avvia l'applicazione:
```bash
python app.py
```

4. Apri il browser su: http://localhost:5000

## Uso da Command Line

Puoi anche usare lo script Python direttamente:

```bash
python stock_screener.py
```

Questo stamperà i risultati nel terminale.

## Deploy su Render.com

### Metodo Automatico (Consigliato)

1. Vai su [Render.com](https://render.com) e crea un account
2. Click su "New +" → "Web Service"
3. Connetti il tuo repository GitHub: `https://github.com/Tapedynamics/stockscreener`
4. Render rileverà automaticamente `render.yaml` e configurerà tutto
5. Click su "Create Web Service"
6. Attendi il deploy (2-3 minuti)
7. L'app sarà disponibile su: `https://your-app-name.onrender.com`

### Metodo Manuale

1. Su Render.com, click "New +" → "Web Service"
2. Connetti GitHub e seleziona il repository
3. Configura:
   - **Name**: stock-screener
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. Click "Create Web Service"

## Struttura Progetto

```
stockscreener/
├── app.py                    # Flask web application
├── stock_screener.py         # Script CLI
├── templates/
│   └── index.html           # Interfaccia web
├── requirements.txt         # Dipendenze Python
├── render.yaml              # Configurazione Render
├── .gitignore              # File da ignorare
└── README.md               # Questa guida
```

## Tecnologie Utilizzate

- **Backend**: Flask (Python)
- **Web Scraping**: BeautifulSoup4, Requests
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Deployment**: Render.com, Gunicorn

## Personalizzazione

Per modificare lo screener Finviz:

1. Vai su [Finviz Screener](https://finviz.com/screener.ashx)
2. Configura i tuoi filtri
3. Copia l'URL risultante
4. Modifica `FINVIZ_URL` in `app.py` e `stock_screener.py`

## Limitazioni

- Richiede connessione internet per accedere a Finviz
- I dati dipendono dalla disponibilità di Finviz
- Rate limiting: evita troppe richieste consecutive

## License

MIT License

## Autore

Creato con Claude Code
