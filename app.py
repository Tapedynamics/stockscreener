#!/usr/bin/env python3
"""
Flask Web App per Stock Screener
"""

from flask import Flask, render_template, jsonify
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

# URL del tuo screener Finviz
FINVIZ_URL = "https://finviz.com/screener.ashx?v=141&f=cap_midover,fa_eps5years_pos,fa_estltgrowth_pos,fa_netmargin_high,fa_opermargin_o20,fa_pe_u30,fa_roe_pos,geo_usa,sh_avgvol_o100,sh_curvol_o100,ta_sma200_pa&ft=4&o=-perf4w"


def get_finviz_stocks(url):
    """
    Scarica e parsifica la pagina Finviz per estrarre i ticker
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        tickers = []
        seen = set()

        # Trova tutti i link ai ticker
        all_links = soup.find_all('a', href=lambda x: x and 'quote.ashx?t=' in x)

        for link in all_links:
            href = link.get('href', '')

            # Estrai il ticker dal parametro t= nell'URL
            if '?t=' in href or '&t=' in href:
                match = re.search(r'[?&]t=([A-Z.-]+)', href)

                if match:
                    ticker = match.group(1)

                    if ticker not in seen:
                        tickers.append(ticker)
                        seen.add(ticker)

        return tickers

    except Exception as e:
        print(f"Errore: {e}")
        return []


def organize_basket(tickers):
    """
    Organizza i ticker in categorie
    """
    basket = {
        'take_profit': tickers[0:3],
        'hold': tickers[3:13],
        'buffer': tickers[13:15],
        'total_found': len(tickers)
    }

    return basket


@app.route('/')
def index():
    """Pagina principale"""
    return render_template('index.html')


@app.route('/api/screener', methods=['GET'])
def run_screener():
    """API endpoint per eseguire lo screener"""
    try:
        # Estrai i ticker
        tickers = get_finviz_stocks(FINVIZ_URL)

        if not tickers:
            return jsonify({
                'success': False,
                'error': 'Nessun ticker trovato'
            }), 500

        # Prendi i primi 15
        top_15 = tickers[:15]

        # Organizza in basket
        basket = organize_basket(top_15)

        return jsonify({
            'success': True,
            'data': basket
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("\n" + "="*50)
    print("Stock Screener Web App")
    print("="*50)
    print("\nServer in esecuzione su: http://localhost:5000")
    print("Premi CTRL+C per fermare il server\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
