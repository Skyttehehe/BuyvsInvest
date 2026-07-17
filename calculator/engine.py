"""Beregningsmotor: Køb af bolig vs. leje + investering (danske regler, 2026-satser).

Alle satser er standardværdier og kan overstyres fra frontenden, så
fejl i antagelserne kan findes og rettes (bug reports).

Metode: Der simuleres måned for måned over horisonten. Hver måned
sammenlignes ejerens kontante udgift med lejerens husleje, og den der
betaler mindst investerer differencen (først på ASK op til loftet,
derefter i frie midler). Formuen opgøres ved hvert årsskifte.
"""

DEFAULTS = {
    # Opsparing og bolig
    "savings": 200_000.0,          # kr. til rådighed (udbetaling + omkostninger)
    "auto_savings": 1,             # 1 = opsparing sættes automatisk til 5% udbetaling + alle købsomkostninger
    "price": 3_000_000.0,          # boligens pris
    "growth_pct": 2.5,             # årlig prisstigning på bolig, %
    "horizon_years": 30,           # sammenligningshorisont

    # Realkreditlån (op til 80% af købesummen)
    "rk_rate_pct": 4.0,            # rente p.a., 30-årigt fastforrentet
    "rk_years": 30,
    "bidrag_pct": 0.68,            # bidragssats p.a. af restgæld

    # Banklån (80-95% af købesummen)
    "bank_rate_pct": 6.5,
    "bank_years": 20,

    # Engangsomkostninger ved køb
    "purchase_fees": 25_000.0,     # rådgiver, bank, lånesagsgebyr mv.
    "tinglysning_skode_fixed": 1_850.0,
    "tinglysning_skode_pct": 0.6,      # % af købesum
    "tinglysning_pant_fixed": 1_825.0,
    "tinglysning_pant_pct": 1.45,      # % af pantebrev (pr. lån)

    # Løbende ejerudgifter og boligskatter
    "ejd_skat_low_pct": 0.51,      # ejendomsværdiskat under progressionsgrænsen
    "ejd_skat_high_pct": 1.4,      # over grænsen
    "ejd_skat_threshold": 9_400_000.0,
    "ejd_valuation_factor": 80.0,  # beskatningsgrundlag = % af boligværdi (forsigtighedsprincip)
    "grundskyld_promille": 7.4,    # grundskyldspromille (kommuneafhængig)
    "land_share_pct": 20.0,        # grundværdi som % af boligværdi
    "maintenance_pct": 1.0,        # vedligehold + ejerudgifter, % af boligværdi p.a.

    # Rentefradrag
    "fradrag_low_pct": 33.08,      # skatteværdi af renteudgifter op til grænsen
    "fradrag_high_pct": 25.08,     # over grænsen
    "fradrag_threshold": 50_000.0, # pr. person (100.000 for par)

    # Salg ved horisontens udløb
    "include_selling_costs": 1,    # 1 = medregn salgsomkostninger
    "selling_cost_pct": 2.5,       # mægler mv., % af salgspris (gevinst er skattefri, parcelhusreglen)

    # Leje
    "rent_monthly": 12_000.0,
    "rent_inflation_pct": 2.0,
    "deposit_months": 3,           # depositum, bindes uden afkast og returneres nominelt

    # Investering
    "return_pct": 7.0,             # forventet årligt afkast før skat
    "compound_monthly": 1,         # 1 = rentes rente månedligt (r/12 pr. md.), 0 = årligt ækvivalent ((1+r)^(1/12))
    "ask_limit": 174_200.0,        # loft for indskud på aktiesparekonto (2026)
    "ask_tax_pct": 17.0,           # lagerbeskatning på ASK
    "aktie_low_pct": 27.0,         # aktieindkomst under progressionsgrænsen
    "aktie_high_pct": 42.0,        # over grænsen
    "aktie_threshold": 83_100.0,   # progressionsgrænse for aktieindkomst (2026, enlig)
}

SIMPLIFICATIONS = [
    "Afkast tilskrives som udgangspunkt med rentes rente pr. måned (afkast/12 hver måned), så det "
    "effektive årlige afkast er lidt højere end den angivne sats. Sæt 'Månedlig rentetilskrivning' "
    "til 0 for at bruge den angivne sats som effektivt årligt afkast i stedet.",
    "Frie midler beskattes her årligt efter lagerprincippet (27%/42% af årets gevinst). "
    "I virkeligheden er frie midler realisationsbeskattede, så den reelle skat udskydes og er lidt lavere.",
    "Tab på ASK og frie midler fremføres og modregnes i senere gevinster.",
    "Bidragssatsen holdes konstant, selvom den reelt falder når belåningsgraden falder.",
    "Ejendomsvurderingen antages at følge boligens markedsværdi (beskatningsgrundlag = faktor x værdi).",
    "Grundværdien antages at være en fast procentdel af boligens værdi.",
    "Rentefradragets skatteværdi beregnes på årets samlede renteudgifter inkl. bidrag.",
    "Skattesatser, grænser og ASK-loft holdes konstante over hele horisonten (ingen regulering).",
    "Gevinst ved salg af egen bolig er skattefri (parcelhusreglen).",
    "Depositum ved leje forrentes ikke og returneres nominelt.",
    "Der ses bort fra flytteomkostninger, boligsikring og inflation i vedligehold ud over boligens værdistigning.",
]


def annuity_payment(principal, annual_rate, years):
    """Fast månedlig ydelse på et annuitetslån."""
    if principal <= 0:
        return 0.0
    r = annual_rate / 12.0
    n = int(years * 12)
    if r == 0:
        return principal / n
    return principal * r / (1.0 - (1.0 + r) ** -n)


class Portfolio:
    """Investeringsportefølje: ASK fyldes først (op til loftet), resten i frie midler.

    Beskattes ved hvert årsskifte: ASK 17% lager, frie midler 27%/42% af
    årets gevinst (lager-tilnærmelse). Tab fremføres.
    """

    def __init__(self, p):
        self.ask_limit = p["ask_limit"]
        self.ask_tax = p["ask_tax_pct"] / 100.0
        self.aktie_low = p["aktie_low_pct"] / 100.0
        self.aktie_high = p["aktie_high_pct"] / 100.0
        self.aktie_threshold = p["aktie_threshold"]
        if p["compound_monthly"]:
            self.monthly_factor = 1.0 + p["return_pct"] / 100.0 / 12.0
        else:
            self.monthly_factor = (1.0 + p["return_pct"] / 100.0) ** (1.0 / 12.0)
        self.ask = 0.0
        self.frie = 0.0
        self.ask_carry_loss = 0.0
        self.frie_carry_loss = 0.0
        self._reset_year()

    def _reset_year(self):
        self.ask_year_start = self.ask
        self.frie_year_start = self.frie
        self.ask_contrib = 0.0
        self.frie_contrib = 0.0

    def contribute(self, amount):
        if amount <= 0:
            return
        room = max(self.ask_limit - self.ask, 0.0)
        to_ask = min(amount, room)
        self.ask += to_ask
        self.ask_contrib += to_ask
        self.frie += amount - to_ask
        self.frie_contrib += amount - to_ask

    def grow_month(self):
        self.ask *= self.monthly_factor
        self.frie *= self.monthly_factor

    def year_end_tax(self):
        """Beregn og betal årets skat. Returnerer (ask_skat, frie_skat)."""
        ask_gain = self.ask - self.ask_year_start - self.ask_contrib
        ask_gain -= self.ask_carry_loss
        if ask_gain >= 0:
            self.ask_carry_loss = 0.0
            ask_tax = ask_gain * self.ask_tax
        else:
            self.ask_carry_loss = -ask_gain
            ask_tax = 0.0
        self.ask -= ask_tax

        frie_gain = self.frie - self.frie_year_start - self.frie_contrib
        frie_gain -= self.frie_carry_loss
        if frie_gain >= 0:
            self.frie_carry_loss = 0.0
            low_part = min(frie_gain, self.aktie_threshold)
            high_part = max(frie_gain - self.aktie_threshold, 0.0)
            frie_tax = low_part * self.aktie_low + high_part * self.aktie_high
        else:
            self.frie_carry_loss = -frie_gain
            frie_tax = 0.0
        self.frie -= frie_tax

        self._reset_year()
        return ask_tax, frie_tax

    @property
    def total(self):
        return self.ask + self.frie


def upfront_costs(p):
    """Engangsomkostninger og lånefordeling ved køb.

    Lånestørrelsen afhænger af udbetalingen, som afhænger af
    tinglysningsafgifterne, som afhænger af lånestørrelsen - løses
    med få fixpunkt-iterationer.
    """
    price = p["price"]
    skode = p["tinglysning_skode_fixed"] + p["tinglysning_skode_pct"] / 100.0 * price
    if p["auto_savings"]:
        # Opsparing = minimum for at købe: 5% udbetaling + alle omkostninger
        # (lånefordelingen er kendt: 80% realkredit, 15% banklån)
        pant_rk_auto = p["tinglysning_pant_fixed"] + p["tinglysning_pant_pct"] / 100.0 * (0.80 * price)
        pant_bank_auto = p["tinglysning_pant_fixed"] + p["tinglysning_pant_pct"] / 100.0 * (0.15 * price)
        p["savings"] = 0.05 * price + skode + pant_rk_auto + pant_bank_auto + p["purchase_fees"]
    savings = p["savings"]
    rk_loan = bank_loan = 0.0
    pant_rk = pant_bank = 0.0
    for _ in range(5):
        pant_rk = (p["tinglysning_pant_fixed"] + p["tinglysning_pant_pct"] / 100.0 * rk_loan) if rk_loan > 0 else 0.0
        pant_bank = (p["tinglysning_pant_fixed"] + p["tinglysning_pant_pct"] / 100.0 * bank_loan) if bank_loan > 0 else 0.0
        total_costs = skode + pant_rk + pant_bank + p["purchase_fees"]
        down_payment = max(savings - total_costs, 0.0)
        total_loan = max(price - down_payment, 0.0)
        rk_loan = min(0.80 * price, total_loan)
        bank_loan = total_loan - rk_loan

    warnings = []
    if down_payment < 0.05 * price:
        def dk(v):
            return f"{v:,.0f}".replace(",", ".")
        warnings.append(
            f"Udbetalingen ({dk(down_payment)} kr.) er under lovkravet på 5% af købesummen "
            f"({dk(0.05 * price)} kr.). Banklånet er sat til at dække resten alligevel, "
            "men i praksis kan boligen ikke købes med denne opsparing."
        )

    return {
        "skode": skode,
        "pant_realkredit": pant_rk,
        "pant_bank": pant_bank,
        "fees": p["purchase_fees"],
        "total_costs": skode + pant_rk + pant_bank + p["purchase_fees"],
        "down_payment": down_payment,
        "rk_loan": rk_loan,
        "bank_loan": bank_loan,
    }, warnings


def property_taxes_yearly(p, house_value):
    """(ejendomsværdiskat, grundskyld) for et år ved given boligværdi."""
    base = house_value * p["ejd_valuation_factor"] / 100.0
    thr = p["ejd_skat_threshold"]
    ejd = (min(base, thr) * p["ejd_skat_low_pct"] / 100.0
           + max(base - thr, 0.0) * p["ejd_skat_high_pct"] / 100.0)
    land_base = house_value * p["land_share_pct"] / 100.0 * p["ejd_valuation_factor"] / 100.0
    grundskyld = land_base * p["grundskyld_promille"] / 1000.0
    return ejd, grundskyld


def fradrag_value(p, yearly_interest):
    """Skatteværdien af årets renteudgifter (rentefradrag)."""
    thr = p["fradrag_threshold"]
    low = min(yearly_interest, thr)
    high = max(yearly_interest - thr, 0.0)
    return low * p["fradrag_low_pct"] / 100.0 + high * p["fradrag_high_pct"] / 100.0


def simulate(p):
    """Kør hele simuleringen. Returnerer dict klar til JSON."""
    upfront, warnings = upfront_costs(p)

    months = int(p["horizon_years"]) * 12
    growth_m = (1.0 + p["growth_pct"] / 100.0) ** (1.0 / 12.0)

    # Køber
    rk_balance = upfront["rk_loan"]
    bank_balance = upfront["bank_loan"]
    rk_payment = annuity_payment(rk_balance, p["rk_rate_pct"] / 100.0, p["rk_years"])
    bank_payment = annuity_payment(bank_balance, p["bank_rate_pct"] / 100.0, p["bank_years"])
    house_value = p["price"]
    owner_portfolio = Portfolio(p)

    # Lejer
    deposit = p["deposit_months"] * p["rent_monthly"]
    renter_portfolio = Portfolio(p)
    renter_start_investment = max(p["savings"] - deposit, 0.0)
    renter_portfolio.contribute(renter_start_investment)
    if p["savings"] < deposit:
        warnings.append("Opsparingen kan ikke dække depositum ved leje.")
    rent = p["rent_monthly"]

    sell_pct = p["selling_cost_pct"] / 100.0 if p["include_selling_costs"] else 0.0

    def buy_net_worth():
        return (house_value * (1.0 - sell_pct) - rk_balance - bank_balance
                + owner_portfolio.total)

    def rent_net_worth():
        return renter_portfolio.total + deposit

    years = [{
        "year": 0,
        "buy_net_worth": buy_net_worth(),
        "rent_net_worth": rent_net_worth(),
        "house_value": house_value,
        "rk_balance": rk_balance,
        "bank_balance": bank_balance,
        "owner_portfolio": owner_portfolio.total,
        "renter_portfolio": renter_portfolio.total,
    }]

    totals = {
        "rk_interest": 0.0, "bank_interest": 0.0, "bidrag": 0.0,
        "ejd_skat": 0.0, "grundskyld": 0.0, "maintenance": 0.0,
        "fradrag": 0.0, "rent_paid": 0.0,
        "owner_ask_tax": 0.0, "owner_frie_tax": 0.0,
        "renter_ask_tax": 0.0, "renter_frie_tax": 0.0,
        "owner_invested": 0.0, "renter_invested": 0.0,
    }

    owner_invested_year = 0.0
    renter_invested_year = 0.0

    for month in range(1, months + 1):
        # --- Køberens måned ---
        rk_interest = rk_balance * p["rk_rate_pct"] / 100.0 / 12.0
        rk_pay = min(rk_payment, rk_balance + rk_interest)
        rk_balance = max(rk_balance + rk_interest - rk_pay, 0.0)

        bank_interest = bank_balance * p["bank_rate_pct"] / 100.0 / 12.0
        bank_pay = min(bank_payment, bank_balance + bank_interest)
        bank_balance = max(bank_balance + bank_interest - bank_pay, 0.0)

        bidrag = (rk_balance * p["bidrag_pct"] / 100.0) / 12.0

        ejd_y, grund_y = property_taxes_yearly(p, house_value)
        ejd_m, grund_m = ejd_y / 12.0, grund_y / 12.0
        maint_m = house_value * p["maintenance_pct"] / 100.0 / 12.0

        interest_m = rk_interest + bank_interest + bidrag
        fradrag_m = fradrag_value(p, interest_m * 12.0) / 12.0

        owner_cash = rk_pay + bank_pay + bidrag + ejd_m + grund_m + maint_m - fradrag_m

        # --- Lejerens måned ---
        renter_cash = rent

        # --- Den billigste part investerer differencen ---
        owner_portfolio.grow_month()
        renter_portfolio.grow_month()
        diff = owner_cash - renter_cash
        if diff > 0:
            renter_portfolio.contribute(diff)
            totals["renter_invested"] += diff
            renter_invested_year += diff
        elif diff < 0:
            owner_portfolio.contribute(-diff)
            totals["owner_invested"] += -diff
            owner_invested_year += -diff

        house_value *= growth_m

        totals["rk_interest"] += rk_interest
        totals["bank_interest"] += bank_interest
        totals["bidrag"] += bidrag
        totals["ejd_skat"] += ejd_m
        totals["grundskyld"] += grund_m
        totals["maintenance"] += maint_m
        totals["fradrag"] += fradrag_m
        totals["rent_paid"] += rent

        if month % 12 == 0:
            o_ask_tax, o_frie_tax = owner_portfolio.year_end_tax()
            r_ask_tax, r_frie_tax = renter_portfolio.year_end_tax()
            totals["owner_ask_tax"] += o_ask_tax
            totals["owner_frie_tax"] += o_frie_tax
            totals["renter_ask_tax"] += r_ask_tax
            totals["renter_frie_tax"] += r_frie_tax

            year = month // 12
            ejd_y_now, grund_y_now = property_taxes_yearly(p, house_value)
            years.append({
                "year": year,
                "buy_net_worth": buy_net_worth(),
                "rent_net_worth": rent_net_worth(),
                "house_value": house_value,
                "rk_balance": rk_balance,
                "bank_balance": bank_balance,
                "owner_portfolio": owner_portfolio.total,
                "renter_portfolio": renter_portfolio.total,
                "owner_monthly_cost": owner_cash,
                "rent_monthly": rent,
                "ejd_skat_year": ejd_y_now,
                "grundskyld_year": grund_y_now,
                "renter_ask": renter_portfolio.ask,
                "renter_frie": renter_portfolio.frie,
                "owner_ask": owner_portfolio.ask,
                "owner_frie": owner_portfolio.frie,
                "renter_ask_tax": r_ask_tax,
                "renter_frie_tax": r_frie_tax,
                "owner_ask_tax": o_ask_tax,
                "owner_frie_tax": o_frie_tax,
                "renter_invested_year": renter_invested_year,
                "owner_invested_year": owner_invested_year,
            })
            renter_invested_year = 0.0
            owner_invested_year = 0.0

            rent *= 1.0 + p["rent_inflation_pct"] / 100.0

    # Breakpoint: første år hvor køb overhaler leje+investering (eller omvendt)
    breakpoint_info = None
    start_buy_ahead = years[0]["buy_net_worth"] >= years[0]["rent_net_worth"]
    for i in range(1, len(years)):
        prev, cur = years[i - 1], years[i]
        prev_diff = prev["buy_net_worth"] - prev["rent_net_worth"]
        cur_diff = cur["buy_net_worth"] - cur["rent_net_worth"]
        if prev_diff * cur_diff < 0 or (prev_diff != 0 and cur_diff == 0):
            frac = abs(prev_diff) / (abs(prev_diff) + abs(cur_diff)) if (abs(prev_diff) + abs(cur_diff)) > 0 else 0.0
            breakpoint_info = {
                "year": prev["year"] + frac,
                "direction": "buy_overtakes" if cur_diff > 0 else "rent_overtakes",
            }
            break

    final = years[-1]
    return {
        "params": p,
        "warnings": warnings,
        "upfront": upfront,
        "years": years,
        "totals": totals,
        "breakpoint": breakpoint_info,
        "start_buy_ahead": start_buy_ahead,
        "summary": {
            "buy_final": final["buy_net_worth"],
            "rent_final": final["rent_net_worth"],
            "buy_total_taxes": totals["ejd_skat"] + totals["grundskyld"]
                               + totals["owner_ask_tax"] + totals["owner_frie_tax"],
            "rent_total_taxes": totals["renter_ask_tax"] + totals["renter_frie_tax"],
            "renter_start_investment": renter_start_investment,
            "deposit": deposit,
        },
        "simplifications": SIMPLIFICATIONS,
    }


def parse_params(query):
    """Byg parameter-dict fra querystring; ukendte/ugyldige felter falder tilbage til default."""
    p = dict(DEFAULTS)
    for key in DEFAULTS:
        raw = query.get(key)
        if raw is None or raw == "":
            continue
        try:
            p[key] = float(str(raw).replace(",", "."))
        except ValueError:
            pass
    p["horizon_years"] = int(max(1, min(p["horizon_years"], 60)))
    p["include_selling_costs"] = 1 if p["include_selling_costs"] else 0
    p["compound_monthly"] = 1 if p["compound_monthly"] else 0
    p["auto_savings"] = 1 if p["auto_savings"] else 0
    return p
