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

fmt = "%H:%M"
thuis_minuten = 0
kantoor_minuten = 0

for r in rows:
    # Berekening Shift 1
    try:
        t1 = datetime.strptime(r["start"], fmt)
        t2 = datetime.strptime(r["eind"], fmt)
        p1 = int(r["pauze_min"]) if r.get("pauze_min") and r["pauze_min"].isdigit() else 0
        s1_min = max(0, int((t2 - t1).total_seconds() / 60) - p1)
    except Exception:
        s1_min = 0

    if r.get("locatie") == "Thuis":
        thuis_minuten += s1_min
    else:
        kantoor_minuten += s1_min

    # Berekening Shift 2 (extra)
    if r.get("start_extra") and r.get("eind_extra"):
        try:
            t1_ex = datetime.strptime(r["start_extra"], fmt)
            t2_ex = datetime.strptime(r["eind_extra"], fmt)
            p2 = int(r["pauze_extra_min"]) if r.get("pauze_extra_min") and r["pauze_extra_min"].isdigit() else 0
            s2_min = max(0, int((t2_ex - t1_ex).total_seconds() / 60) - p2)
        except Exception:
            s2_min = 0

        loc2 = r.get("locatie_extra") or "Thuis"
        if loc2 == "Thuis":
            thuis_minuten += s2_min
        else:
            kantoor_minuten += s2_min

thuis_uren = round(thuis_minuten / 60.0, 2)
kantoor_uren = round(kantoor_minuten / 60.0, 2)

totale_minuten = thuis_minuten + kantoor_minuten
totaal_uren = round(totale_minuten / 60.0, 2)
totaal_duur_str = f"{totale_minuten // 60:02d}:{totale_minuten % 60:02d}"

md = f"# Timesheet Week: {maandag.strftime('%d-%m-%Y')} t/m {vandaag.strftime('%d-%m-%Y')}\n\n"
md += f"- **Totaal gewerkt:** {totaal_duur_str} ({totaal_uren:.2f} uur)\n"
md += f"- **Kantoor / On-site:** {kantoor_uren:.2f} uur | **Thuiswerk:** {thuis_uren:.2f} uur\n\n"
md += "| Datum | Shift 1 | Shift 2 (extra) | Duur | Netto Uur | Omschrijving |\n"
md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"

for r in rows:
    pauze_1 = r.get("pauze_min", "0")
    shift1 = f"{r['start']}-{r['eind']} ({r['locatie']}, p: {pauze_1}m)"
    
    shift2 = "-"
    if r.get("start_extra") and r.get("eind_extra"):
        loc2 = r.get("locatie_extra") or "Thuis"
        shift2 = f"{r['start_extra']}-{r['eind_extra']} ({loc2})"
        p_extra = r.get("pauze_extra_min")
        if p_extra and p_extra.isdigit() and int(p_extra) > 0:
            shift2 += f" (p: {p_extra}m)"
            
    duur_val = r.get("duur", "-")
    netto_val = r.get("netto_uren", "0")
    omschr = r.get("omschrijving", "-")
    md += f"| {r['datum']} | {shift1} | {shift2} | **{duur_val}** | {netto_val} | {omschr} |\n"

with open("output/timesheet_week.md", "w", encoding="utf-8") as f:
    f.write(md)

if "GITHUB_STEP_SUMMARY" in os.environ:
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write(md)