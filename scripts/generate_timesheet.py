import csv
from datetime import datetime, timedelta
import os

os.makedirs("output", exist_ok=True)
vandaag = datetime.now().date()
maandag = vandaag - timedelta(days=vandaag.weekday()) # Maandag van deze week

rows = []
if os.path.exists("data/uren.csv"):
    with open("data/uren.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r_datum = datetime.strptime(r["datum"], "%Y-%m-%d").date()
            if maandag <= r_datum <= vandaag:
                rows.append(r)

# Samenvatting maken
totaal_uren = sum(float(r["netto_uren"]) for r in rows)
thuis_uren = sum(float(r["netto_uren"]) for r in rows if r["locatie"] == "Thuis")
kantoor_uren = sum(float(r["netto_uren"]) for r in rows if r["locatie"] != "Thuis")

md = f"# Timesheet Week ({maandag} t/m {vandaag})\n\n"
md += f"- **Totaal gewerkt:** {totaal_uren:.2f} uur\n"
md += f"- **Thuiswerk:** {thuis_uren:.2f} uur | **Kantoor/Klant:** {kantoor_uren:.2f} uur\n\n"
md += "| Datum | Locatie | Tijden | Pauze | Netto Uur | Omschrijving |\n"
md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
for r in rows:
    md += f"| {r['datum']} | {r['locatie']} | {r['start']}-{r['eind']} | {r['pauze_min']}m | {r['netto_uren']} | {r['omschrijving']} |\n"

with open("output/timesheet_week.md", "w", encoding="utf-8") as f:
    f.write(md)

# Toon in GitHub Actions Summary interface
if "GITHUB_STEP_SUMMARY" in os.environ:
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write(md)