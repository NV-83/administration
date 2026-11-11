import os
import re
from datetime import datetime
import csv

body = os.environ.get("ISSUE_BODY", "")

def extract(label):
    match = re.search(rf"### {label}\s*\n\s*(.*?)(?=\n###|\Z)", body, re.DOTALL)
    return match.group(1).strip() if match else ""

datum = extract("Datum")
locatie = extract("Locatie")
start = extract("Startuur")
eind = extract("Einduur")
pauze = int(extract("Pauze (in minuten)") or 0)
omschrijving = extract("Omschrijving werkzaamheden").replace("\n", " ")

# Netto-uren berekenen
fmt = "%H:%M"
t_start = datetime.strptime(start, fmt)
t_eind = datetime.strptime(eind, fmt)
bruto_min = (t_eind - t_start).total_seconds() / 60
netto_uren = round((bruto_min - pauze) / 60, 2)

csv_path = "data/uren.csv"
os.makedirs("data", exist_ok=True)
file_exists = os.path.isfile(csv_path)

with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(["datum", "locatie", "start", "eind", "pauze_min", "netto_uren", "omschrijving"])
    writer.writerow([datum, locatie, start, eind, pauze, netto_uren, omschrijving])