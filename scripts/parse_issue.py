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
if start_extra and eind_extra:
    t_start_ex = datetime.strptime(start_extra, fmt)
    t_eind_ex = datetime.strptime(eind_extra, fmt)
    bruto_ex = (t_eind_ex - t_start_ex).total_seconds() / 60
    netto_extra = (bruto_ex - pauze_extra) / 60

totale_netto_uren = round(netto_dag + netto_extra, 2)

csv_path = "data/uren.csv"
os.makedirs("data", exist_ok=True)
file_exists = os.path.isfile(csv_path)

header = [
    "datum", "locatie", "start", "eind", "pauze_min",
    "start_extra", "eind_extra", "pauze_extra_min",
    "netto_uren", "omschrijving"
]

row = [
    datum, locatie, start, eind, pauze,
    start_extra, eind_extra, (pauze_extra if start_extra else ""),
    totale_netto_uren, omschrijving
]

with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(header)
    writer.writerow(row)