import csv
from datetime import datetime
import os

tarief = float(os.environ.get("UURTARIEF", "85.0"))
btw_pct = float(os.environ.get("BTW_TARIEF", "21"))

vandaag = datetime.now().date()
# Bepaal vorige maand
eerste_van_nu = vandaag.replace(day=1)
vorig_maand_eind = eerste_van_nu
target_jaar = vorig_maand_eind.year if vorig_maand_eind.month > 1 else vorig_maand_eind.year - 1
target_maand = vorig_maand_eind.month - 1 if vorig_maand_eind.month > 1 else 12

maand_prefix = f"{target_jaar}-{target_maand:02d}"

rows = []
if os.path.exists("data/uren.csv"):
    with open("data/uren.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r["datum"].startswith(maand_prefix):
                rows.append(r)

totaal_uren = sum(float(r["netto_uren"]) for r in rows)
thuis_dagen = len([r for r in rows if r["locatie"] == "Thuis"])
kantoor_dagen = len([r for r in rows if r["locatie"] != "Thuis"])

subtotaal = totaal_uren * tarief
btw = subtotaal * (btw_pct / 100.0)
totaal_incl = subtotaal + btw

factuur_md = f"""# FACTUUR-BIJLAGE: {maand_prefix}

- **Gefactureerde periode:** {maand_prefix}
- **Uurtarief:** €{tarief:.2f}
- **Dagen thuis gewerkt:** {thuis_dagen}
- **Dagen on-site gewerkt:** {kantoor_dagen}

---

### Overzicht
- **Totaal uren:** {totaal_uren:.2f} uur
- **Subtotaal excl. btw:** €{subtotaal:,.2f}
- **Btw ({int(btw_pct)}%):** €{btw:,.2f}
- **Totaal incl. btw:** €{totaal_incl:,.2f}

---

### Urenspecificatie
| Datum | Locatie | Uren | Omschrijving |
| :--- | :--- | :--- | :--- |
"""
for r in rows:
    factuur_md += f"| {r['datum']} | {r['locatie']} | {r['netto_uren']} | {r['omschrijving']} |\n"

os.makedirs("output", exist_ok=True)
with open(f"output/factuur_{maand_prefix}.md", "w", encoding="utf-8") as f:
    f.write(factuur_md)

if "GITHUB_STEP_SUMMARY" in os.environ:
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write(factuur_md)