#!/usr/bin/env python3
"""
Decode Finviz URL parameters to understand screening criteria
"""

FINVIZ_URL = "https://finviz.com/screener.ashx?v=141&f=cap_midover,fa_eps5years_pos,fa_estltgrowth_pos,fa_netmargin_pos,fa_opermargin_pos,fa_pe_u30,fa_roe_pos,geo_usa,sh_avgvol_o100,sh_curvol_o100,ta_sma200_pa&ft=4&o=-perf4w"

# Parameter dictionary with descriptions
PARAM_DESCRIPTIONS = {
    # Market Cap
    'cap_midover': {
        'category': 'Market Capitalization',
        'criterion': 'Mid-cap and above',
        'value': '$2 billion+',
        'description': 'Filtra solo aziende con capitalizzazione >= $2B (esclude small-cap)'
    },

    # Fundamental Analysis - Growth
    'fa_eps5years_pos': {
        'category': 'Growth - EPS',
        'criterion': 'EPS growth past 5 years',
        'value': 'Positive (>0%)',
        'description': 'Utile per azione cresciuto negli ultimi 5 anni'
    },
    'fa_estltgrowth_pos': {
        'category': 'Growth - Estimates',
        'criterion': 'Long term growth estimate',
        'value': 'Positive (>0%)',
        'description': 'Stime analisti prevedono crescita futura positiva'
    },

    # Fundamental Analysis - Profitability
    'fa_netmargin_pos': {
        'category': 'Profitability',
        'criterion': 'Net profit margin',
        'value': 'Positive (>0%)',
        'description': 'Margine di profitto netto positivo (azienda in utile)'
    },
    'fa_opermargin_pos': {
        'category': 'Profitability',
        'criterion': 'Operating margin',
        'value': 'Positive (>0%)',
        'description': 'Margine operativo positivo (operazioni core profittevoli)'
    },
    'fa_roe_pos': {
        'category': 'Profitability',
        'criterion': 'Return on Equity (ROE)',
        'value': 'Positive (>0%)',
        'description': 'Ritorno sul capitale proprio positivo (efficienza nell\'uso del capitale)'
    },

    # Valuation
    'fa_pe_u30': {
        'category': 'Valuation',
        'criterion': 'Price/Earnings ratio',
        'value': 'Under 30',
        'description': 'P/E < 30 (esclude aziende sopravvalutate)'
    },

    # Geography
    'geo_usa': {
        'category': 'Geography',
        'criterion': 'Location',
        'value': 'USA only',
        'description': 'Solo aziende americane'
    },

    # Liquidity (Volume)
    'sh_avgvol_o100': {
        'category': 'Liquidity',
        'criterion': 'Average daily volume',
        'value': 'Over 100K shares',
        'description': 'Volume medio > 100K (liquidità sufficiente per trading)'
    },
    'sh_curvol_o100': {
        'category': 'Liquidity',
        'criterion': 'Current volume',
        'value': 'Over 100K shares',
        'description': 'Volume corrente > 100K (trading attivo oggi)'
    },

    # Technical Analysis
    'ta_sma200_pa': {
        'category': 'Technical Analysis',
        'criterion': 'Price vs SMA 200',
        'value': 'Above SMA 200',
        'description': 'Prezzo sopra media mobile 200 giorni (trend rialzista di lungo termine)'
    }
}

# Sorting parameter
SORTING = {
    'o=-perf4w': {
        'criterion': 'Sorting',
        'value': 'By 4-week performance (descending)',
        'description': 'Ordina per performance degli ultimi 30 giorni (i migliori prima)'
    }
}

print("\n" + "="*80)
print("DECODIFICA PARAMETRI FINVIZ SCREENER")
print("="*80)

print(f"\nURL: {FINVIZ_URL}\n")

# Group by category
from collections import defaultdict
categories = defaultdict(list)

for param, info in PARAM_DESCRIPTIONS.items():
    categories[info['category']].append((param, info))

# Display grouped
for category, params in categories.items():
    print(f"\n{'='*80}")
    print(f"  {category.upper()}")
    print(f"{'='*80}")

    for param, info in params:
        print(f"\n  [{param}]")
        print(f"  Criterio: {info['criterion']}")
        print(f"  Valore:   {info['value']}")
        print(f"  Cosa fa:  {info['description']}")

# Sorting
print(f"\n{'='*80}")
print(f"  ORDINAMENTO")
print(f"{'='*80}")
for param, info in SORTING.items():
    print(f"\n  [{param}]")
    print(f"  Criterio: {info['criterion']}")
    print(f"  Valore:   {info['value']}")
    print(f"  Cosa fa:  {info['description']}")

# Summary
print(f"\n{'='*80}")
print("RIEPILOGO CRITERI DI SELEZIONE")
print(f"{'='*80}")

print("\nIL LINK FINVIZ SELEZIONA AZIENDE CHE:")
print("  1. Hanno capitalizzazione >= $2B (mid/large cap)")
print("  2. Sono in CRESCITA (EPS 5y positivo + stime analisti positive)")
print("  3. Sono PROFITTEVOLI (margini netti e operativi positivi, ROE positivo)")
print("  4. Non sono SOPRAVVALUTATE (P/E < 30)")
print("  5. Sono LIQUIDE (volume > 100K)")
print("  6. Sono in TREND RIALZISTA (prezzo > SMA 200)")
print("  7. Sono AMERICANE")
print("  8. Ordina per MOMENTUM (top performers ultimi 30 giorni)")

print("\n" + "="*80)
print("FILOSOFIA DELLA STRATEGIA")
print("="*80)
print("""
Questa combinazione di filtri cerca aziende:
  - SOLIDE (large cap, profittevoli)
  - IN CRESCITA (EPS + stime positive)
  - CON MOMENTUM (trend + performance recente)
  - BEN VALUTATE (P/E ragionevole)
  - LIQUIDE (facilmente tradabili)

E' una strategia GROWTH + MOMENTUM su aziende di QUALITA'.
""")

print("="*80 + "\n")

# Count current matches
print("Verifica quante aziende soddisfano TUTTI questi criteri oggi...")
from stock_screener import get_finviz_stocks
import os
from dotenv import load_dotenv

load_dotenv()
FINVIZ_URL_ACTUAL = os.getenv(
    'FINVIZ_URL',
    "https://finviz.com/screener.ashx?v=141&f=cap_midover,fa_eps5years_pos,fa_estltgrowth_pos,fa_netmargin_pos,fa_opermargin_pos,fa_pe_u30,fa_roe_pos,geo_usa,sh_avgvol_o100,sh_curvol_o100,ta_sma200_pa&ft=4&o=-perf4w"
)

try:
    stocks = get_finviz_stocks(FINVIZ_URL_ACTUAL)
    print(f"\nTotale aziende che soddisfano TUTTI i criteri: {len(stocks)}")
    print(f"Top 15 con miglior momentum (4-week performance):")
    for i, ticker in enumerate(stocks[:15], 1):
        print(f"  {i:2d}. {ticker}")
except Exception as e:
    print(f"\nErrore: {e}")

print()
