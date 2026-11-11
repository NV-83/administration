import csv
from datetime import datetime, timedelta
import os

os.makedirs("output", exist_ok=True)
vandaag = datetime.now().date()
maandag = vandaag - timedelta(days=vandaag.weekday()) # Maandag van de huidige week

rows = []
if os.path.exists("data/uren.csv"):
    with open("data/uren.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if not r.get("datum"):
                continue
            r_datum = datetime.strptime(r["datum"], "%Y-%m-%d").date()
            if maandag <= r_datum <= vandaag:
                rows.append(r)

# Totalen berekenen
totaal_uren = sum(float(r["netto_uren"]) for r in rows)
thuis_uren = sum(float(r["netto_uren"]) for r in rows if r["locatie"] == "Thuis")
kantoor_uren = sum(float(r["netto_uren"]) for r in rows if r["locatie"] != "Thuis")

# Totale tijd omzetten naar UU:MM
totale_minuten = sum(
    int(r["duur"].split(":")[0]) * 60 + int(r["duur"].split(":")[1])
    for r in rows if r.get("duur") and ":" in r["duur"]
)
totaal_duur_str = f"{totale_minuten // 60:02d}:{totale_minuten % 60:02d}"

md = f"# Timesheet Week: {maandag.strftime('%d-%m-%Y')} t/m {vandaag.strftime('%d-%m-%Y')}\n\n"
md += f"- **Totaal gewerkt:** {totaal_duur_str} ({totaal_uren:.2f} uur)\n"
md += f"- **Kantoor / On-site:** {kantoor_uren:.2f} uur | **Thuiswerk:** {thuis_uren:.2f} uur\n\n"
md += "| Datum | Locatie | Shift 1 | Shift 2 (extra) | Duur | Netto Uur | Omschrijving |\n"
md += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"

for r in rows:
    shift1 = f"{r['start']}-{r['eind']} (p: {r['pauze_min']}m)"
    shift2 = "-"
    if r.get("start_extra") and r.get("eind_extra"):
        shift2 = f"{r['start_extra']}-{r['eind_extra']}"
        p_extra = r.get("pauze_extra_min")
        if p_extra and p_extra.isdigit() and int(p_extra) > 0:
            shift2 += f" (p: {p_extra}m)"
            
    duur_val = r.get("duur", "-")
    md += f"| {r['datum']} | {r['locatie']} | {shift1} | {shift2} | **{duur_val}** | {r['netto_uren']} | {r['omschrijving']} |\n"

with open("output/timesheet_week.md", "w", encoding="utf-8") as f:
    f.write(md)

# Direct tonen in GitHub Actions UI
if "GITHUB_STEP