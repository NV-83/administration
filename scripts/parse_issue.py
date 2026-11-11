import os
import re
from datetime import datetime
import csv

body = os.environ.get("ISSUE_BODY", "")

def extract(label):
    match = re.search(rf"### {re.escape(label)}\s*\n\s*(.*?)(?=\n###|\Z)", body, re.DOTALL)
    if not match:
        return ""
    val = match.group(1).strip()
    return "" if val.lower() in ["_no response_", "none"] else val

datum = extract("Datum")
locatie = extract("Locatie")
start = extract("Startuur")
eind = extract("Einduur")
pauze_raw = extract("Pauze (in minuten)")
pauze = int(pauze_raw) if pauze_raw.isdigit() else 0

start_extra = extract("Startuur extra (optioneel)")
eind_extra = extract("Einduur extra (optioneel)")
pauze_extra_raw = extract("Pauze extra (minuten, optioneel)")
pauze_extra = int(pauze_extra_raw) if (pauze_extra_raw and pauze_extra_raw.isdigit()) else 0

omschrijving = extract("Omschrijving werkzaamheden").replace("\n", " ").strip()
if not omschrijving:
    omschrijving = "-"

fmt = "%H:%M"

# 1. Reguliere shift berekenen
t_start = datetime.strptime(start, fmt)
t_eind = datetime.strptime(eind, fmt)
bruto_dag = (t_eind - t_start).total_seconds() / 60
netto_dag = (bruto_dag - pauze) / 60

# 2. Extra shift berekenen (indien ingevuld)
netto_extra = 0.0
start_display = start
eind_display = eind
totale_pauze = pauze

if start_extra and eind_extra:
    t_start_ex = datetime.strptime(start_extra, fmt)
    t_eind_ex = datetime.strptime(eind_extra, fmt)
    bruto_ex = (t_eind_ex - t_start_ex).total_seconds() / 60
    netto_extra = (bruto_ex - pauze_extra) / 60

    start_display = f"{start} + {start_extra}"
    eind_display = f"{eind} + {eind_extra}"
    totale_pauze += pauze_extra

totale_netto_uren = round(netto_dag + netto_extra, 2)

csv_path = "data/uren.csv"
os.makedirs("data", exist_ok=True)
file_exists = os.path.isfile(csv_path)

with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(["datum", "locatie", "start", "eind", "pauze_min", "netto_uren", "omschrijving"])
    writer.writerow([datum, locatie, start_display, eind_display, totale_pauze, totale_netto_uren, omschrijving])