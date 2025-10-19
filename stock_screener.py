#!/usr/bin/env python3
"""
Stock Screener - Finviz Parser
Estrae i primi 15 stocks da un screener Finviz personalizzato
"""

import requests
from bs4 import BeautifulSoup
import sys
import logging
from typing import List, Dict, Optional
from constants import HTTP_REQUEST_TIMEOUT, HTTP_HEADERS

logger = logging.getLogger(__name__)


def get_finviz_stocks(url: str) -> List[str]:
    """
    Scarica e parsifica la pagina Finviz per estrarre i ticker

    Args:
        url: URL del screener Finviz

    Returns:
        list: Lista dei ticker symbols
    """
    try:
        # Richiesta HTTP con timeout
        response = requests.get(
            url,
            headers=HTTP_HEADERS,
            timeout=HTTP_REQUEST_TIMEOUT
        )
        response.raise_for_status()

        logger.info(f"Successfully fetched data from Finviz")

        # Parsing HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        tickers = []
        seen = set()  # Per evitare duplicati

        # Trova tutti i link ai ticker
        all_links = soup.find_all('a', href=lambda x: x and 'quote.ashx?t=' in x)

        for link in all_links:
            href = link.get('href', '')

            # Estrai il ticker dal parametro t= nell'URL
            if '?t=' in href or '&t=' in href:
                # Esempio: quote.ashx?t=ABEV&ty=c&p=d&b=1
                import re
                match = re.search(r'[?&]t=([A-Z.-]+)', href)

                if match:
                    ticker = match.group(1)

                    # Aggiungi solo se non l'abbiamo già visto
                    if ticker not in seen:
                        tickers.append(ticker)
                        seen.add(ticker)

        logger.info(f"Found {len(tickers)} tickers from Finviz")
        return tickers

    except requests.exceptions.Timeout:
        logger.error(f"Request timeout after {HTTP_REQUEST_TIMEOUT} seconds")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return []


def organize_basket(tickers: List[str]) -> Dict[str, any]:
    """
    Organizza i ticker in categorie

    Args:
        tickers: Lista di ticker symbols

    Returns:
        dict: Dizionario con le categorie
    """
    if len(tickers) < 15:
        logger.warning(f"Only {len(tickers)} tickers found (expected at least 15)")

    basket = {
        'take_profit': tickers[0:3],      # Top 3
        'hold': tickers[3:13],             # Posizioni 4-13 (10 stocks)
        'buffer': tickers[13:15],          # Posizioni 14-15 (2 stocks)
        'total_found': len(tickers)
    }

    return basket


def print_basket(basket):
    """
    Stampa il basket formattato
    """
    print("\n" + "="*50)
    print("STOCK SCREENER - BASKET")
    print("="*50 + "\n")

    print("TOP 3 (Take Profit):")
    print(", ".join(basket['take_profit']))

    print("\n10 HOLD (Basket):")
    print(", ".join(basket['hold']))

    print("\n2 BUFFER:")
    print(", ".join(basket['buffer']))

    print("\n" + "="*50)


def main():
    # URL del tuo screener Finviz
    FINVIZ_URL = "https://finviz.com/screener.ashx?v=141&f=cap_midover,fa_eps5years_pos,fa_estltgrowth_pos,fa_netmargin_pos,fa_opermargin_pos,fa_pe_u30,fa_roe_pos,geo_usa,sh_avgvol_o100,sh_curvol_o100,ta_sma200_pa&ft=4&o=-perf4w"

    print("Scaricamento dati da Finviz...")

    # Estrai i ticker
    tickers = get_finviz_stocks(FINVIZ_URL)

    if not tickers:
        print("Nessun ticker trovato. Controlla l'URL o la connessione.")
        sys.exit(1)

    print(f"Trovati {len(tickers)} ticker")

    # Prendi solo i primi 15
    top_15 = tickers[:15]

    # Organizza in basket
    basket = organize_basket(top_15)

    # Stampa risultato
    print_basket(basket)


if __name__ == "__main__":
    main()
