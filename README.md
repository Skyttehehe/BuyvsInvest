# Bolig vs. Investering

Beregner hvornår det bedst kan betale sig at købe bolig frem for at leje og
investere opsparingen — med danske skatteregler og lånestruktur (2026-satser).

## Start

```bash
pnpm app:start
```

Åbn derefter http://127.0.0.1:8000. Første kørsel opretter et virtuelt
Python-miljø (`.venv`) og installerer Django. Kræver Python 3 og pnpm.

## Modellen

Der simuleres måned for måned over horisonten. Hver måned sammenlignes
ejerens kontante udgift med lejerens husleje, og **den der betaler mindst
investerer differencen** — så sammenligningen er fair. Formuen opgøres ved
hvert årsskifte, og breakpointet er der hvor kurverne krydser.

**Køb:**
- Realkreditlån op til 80% af købesummen (annuitet, rente + bidragssats)
- Banklån for resten op til 95% (advarsel hvis udbetalingen er under 5%)
- Engangsomkostninger: tinglysning af skøde (1.850 kr. + 0,6%), tinglysning
  af pant pr. lån (1.825 kr. + 1,45%), rådgiver-/bankgebyrer
- Løbende: ejendomsværdiskat (0,51% / 1,4% over 9,4 mio. af 80% af værdien),
  grundskyld, vedligehold, minus rentefradrag (33,08% / 25,08% over 50.000 kr.)
- Ved horisont: salgsomkostninger kan medregnes; gevinsten er skattefri
  (parcelhusreglen)

**Leje + investering:**
- Opsparing minus depositum investeres fra dag ét
- Aktiesparekonto (ASK) fyldes først: 17% lagerbeskatning, loft 174.200 kr.
- Resten i frie midler: 27% / 42% over progressionsgrænsen (83.100 kr.)
- Tab fremføres og modregnes

Alle satser og grænser kan justeres i venstre side af appen, og alle
delbeløb vises i tabellerne, så antagelser kan efterprøves. Modellens
bevidste forenklinger er listet nederst på siden.

## Struktur

- `calculator/engine.py` — hele beregningsmotoren (ren Python, ingen database)
- `calculator/views.py` — side + JSON-API (`/api/calculate`)
- `calculator/templates/calculator/index.html` — frontend (Chart.js)
# BuyvsInvest
