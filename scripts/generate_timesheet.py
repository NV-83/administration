import csv
from datetime import datetime, timedelta
import os

os.makedirs("output", exist_ok=True)
vandaag = datetime.now().date()
maandag = vandaag - timedelta(days=vandaag.weekday())

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

totaal_uren = sum(float(r["netto_uren"]) for r in rows)
thuis_uren = sum(float(r["netto_uren"]) for r in rows if r["locatie"] == "Thuis")
kantoor_uren = sum(float(r["netto_uren"]) for r in rows if r["locatie"] != "Thuis")

md = f"# Timesheet Week ({maandag} t/m {vandaag})\n\n"
md += f"- **Totaal gewerkt:** {totaal_uren:.2f} uur\n"
md += f"- **Thuiswerk:** {thuis_uren:.2f} uur | **Kantoor/Klant:** {kantoor_uren:.2f} uur\n\n"
md += "| Datum | Locatie | Shift 1 | Shift 2 (extra) | Netto Uur | Omschrijving |\n"
md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"

for r in rows:
    shift1 = f"{r['start']}-{r['eind']} (p: {r['pauze_min']}m)"
    shift2 = f"{r['start_extra']}-{r['eind_extra']}" if r.get("start_extra") else "-"
    if shift2 != "-" and r.get("pauze_extra_min") and int(r["pauze_extra_min"]) > 0:
        shift2 += f" (p: {r['pauze_extra_min']}m)"
    md += f"| {r['datum']} | {r['locatie']} | {shift1} | {shift2} | {r['netto_uren']} | {r['omschrijving']} |\n"

with open("output/timesheet_week.md", "w", encoding="utf-8") as f:
    f.write(md)

if "GITHUB_STEP_SUMMARY" in os.environ:
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write(md)