#!/usr/bin/env python3
import csv
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Tuple

CSV_INPUT_PATH = "data/uren.csv"
BASE_FACTURATIE_DIR = "data/facturatie"
TIME_FORMAT = "%H:%M"


def parse_environment() -> Tuple[str, float, float, str, str]:
    """Leest configuratie uit omgevingsvariabelen."""
    klant = os.environ.get("KLANT_NAAM", "waso").strip().lower()
    dagtarief = float(os.environ.get("DAG_TARIEF", "650.0"))
    btw_pct = float(os.environ.get("BTW_TARIEF", "21"))
    target_month = os.environ.get("TARGET_MONTH", "").strip()
    manual_factuur_nr = os.environ.get("MANUAL_FACTUUR_NR", "").strip()
    return klant, dagtarief, btw_pct, target_month, manual_factuur_nr


def determine_target_month(target_month_override: str) -> str:
    """Bepaalt de doelmaand (JJJJ-MM). Standaard de voorbije maand."""
    if target_month_override:
        return target_month_override

    vandaag = datetime.now().date()
    eerste_van_nu = vandaag.replace(day=1)
    jaar = eerste_van_nu.year if eerste_van_nu.month > 1 else eerste_van_nu.year - 1
    maand = eerste_van_nu.month - 1 if eerste_van_nu.month > 1 else 12
    return f"{jaar}-{maand:02d}"


def get_next_invoice_number(klant: str, manual_nr: str = "") -> str:
    """Scant data/facturatie/<klant>/ en telt door met +1 (bijv. 01, 02)."""
    if manual_nr:
        return f"{int(manual_nr):02d}" if manual_nr.isdigit() else manual_nr

    klant_dir = os.path.join(BASE_FACTURATIE_DIR, klant)
    if not os.path.exists(klant_dir):
        return "01"

    found_numbers = []
    pattern = re.compile(r"factuur_(\d+)\.(html|json|csv)$")

    for root, _, files in os.walk(klant_dir):
        for f in files:
            match = pattern.search(f)
            if match:
                found_numbers.append(int(match.group(1)))

    if not found_numbers:
        return "01"

    next_val = max(found_numbers) + 1
    return f"{next_val:02d}"


def load_monthly_records(csv_path: str, month_prefix: str) -> List[Dict[str, str]]:
    """Laadt de registraties voor de gevraagde maand uit de CSV."""
    if not os.path.exists(csv_path):
        return []

    records = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("datum") and row["datum"].startswith(month_prefix):
                records.append(row)
    return records


def calculate_days_and_financials(
    records: List[Dict[str, str]], dagtarief: float, btw_pct: float
) -> Tuple[List[Dict[str, str]], Dict[str, float]]:
    """
    Groepeert per unieke gewerkte kalenderdag en berekent de factuurtotalen
    op basis van het dagtarief.
    """
    days_dict: Dict[str, Dict] = {}

    for r in records:
        d = r.get("datum")
        if not d:
            continue
        if d not in days_dict:
            days_dict[d] = {
                "datum": d,
                "status": "Gewerkt",
                "uren": float(r.get("netto_uren", 0.0)),
                "dagtarief": dagtarief
            }
        else:
            days_dict[d]["uren"] += float(r.get("netto_uren", 0.0))

    # Sorteren op datum
    sorted_days = sorted(days_dict.values(), key=lambda x: x["datum"])
    aantal_dagen = len(sorted_days)

    totale_uren = sum(d["uren"] for d in sorted_days)
    gemiddelde_uren_dag = round(totale_uren / aantal_dagen, 2) if aantal_dagen > 0 else 0.0

    subtotaal = round(aantal_dagen * dagtarief, 2)
    btw_bedrag = round(subtotaal * (btw_pct / 100.0), 2)
    totaal_incl = round(subtotaal + btw_bedrag, 2)

    financials = {
        "aantal_dagen": aantal_dagen,
        "totale_uren": round(totale_uren, 2),
        "gemiddelde_uren_dag": gemiddelde_uren_dag,
        "subtotaal": subtotaal,
        "btw_bedrag": btw_bedrag,
        "totaal_incl": totaal_incl
    }

    return sorted_days, financials


def export_csv(filepath: str, billed_days: List[Dict[str, str]]) -> None:
    """Exporteert het dagoverzicht naar CSV voor eventuele controle in Excel."""
    fieldnames = ["datum", "status", "dagtarief", "uren_geregistreerd"]
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in billed_days:
            writer.writerow({
                "datum": d["datum"],
                "status": d["status"],
                "dagtarief": f"{d['dagtarief']:.2f}",
                "uren_geregistreerd": f"{d['uren']:.2f}"
            })


def export_json(filepath: str, metadata: dict, financials: dict, billed_days: List[dict]) -> None:
    """Exporteert factuur- en prestatiemetadata naar JSON."""
    payload = {
        "metadata": metadata,
        "financieel": financials,
        "gefactureerde_dagen": billed_days
    }
    with open(filepath, mode="w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def export_html(filepath: str, metadata: dict, financials: dict, billed_days: List[dict]) -> None:
    """Genereert de cleane A4 factuurspecificatie."""
    table_rows = []
    for d in billed_days:
        # Formatteer naar dag-maand (bijv. 09-11)
        dt = datetime.strptime(d["datum"], "%Y-%m-%d")
        datum_kort = dt.strftime("%d-%m")
        datum_volledig = dt.strftime("%d-%m-%Y")

        table_rows.append(f"""
        <tr>
          <td style="font-weight: 500;">{datum_volledig} ({datum_kort})</td>
          <td><span class="badge">{d['status']}</span></td>
          <td style="text-align: right;">€ {d['dagtarief']:,.2f}</td>
        </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>Prestatiestaat {metadata['periode']} - {metadata['klant'].upper()}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 35px; color: #0f172a; }}
  .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #0f172a; padding-bottom: 15px; margin-bottom: 25px; }}
  .header h1 {{ margin: 0; font-size: 24px; color: #0f172a; }}
  .meta-box {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 25px; }}
  .meta-box h3 {{ margin-top: 0; margin-bottom: 10px; font-size: 15px; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; }}
  .meta-box p {{ margin: 5px 0; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 10px 14px; text-align: left; }}
  th {{ background: #f1f5f9; color: #0f172a; font-weight: 600; }}
  .badge {{ background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 4px; font-weight: 500; font-size: 13px; }}
  .totals {{ margin-top: 25px; float: right; width: 340px; }}
  .totals table {{ border: none; font-size: 14px; }}
  .totals td {{ border: none; padding: 6px; }}
  .grand-total {{ font-weight: bold; font-size: 16px; border-top: 2px solid #0f172a !important; color: #0f172a; }}
  .info-note {{ margin-top: 50px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 10px; }}
  @media print {{ body {{ margin: 10mm; }} }}
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Prestatiestaat & Factuurbijlage</h1>
      <p style="margin: 5px 0 0 0; color: #64748b;">Klant: {metadata['klant'].upper()} | Periode: {metadata['periode']} | Factuur #{metadata['factuur_nr']}</p>
    </div>
    <div style="text-align: right;">
      <h2 style="margin: 0; font-size: 20px; color: #0f172a;">NV-83</h2>
      <p style="margin: 4px 0 0 0; font-size: 13px; color: #64748b;">Consultancy & Platform Engineering</p>
    </div>
  </div>

  <div class="meta-box">
    <div>
      <h3>Prestatieoverzicht</h3>
      <p><strong>Aantal gefactureerde dagen:</strong> {financials['aantal_dagen']} dagen</p>
      <p><strong>Vast dagtarief:</strong> € {metadata['dagtarief']:,.2f}</p>
    </div>
    <div>
      <h3>Facturatiegegevens</h3>
      <p><strong>Btw-tarief:</strong> {int(metadata['btw_pct'])}%</p>
      <p><strong>Referentie:</strong> {metadata['periode']}-{metadata['factuur_nr']}</p>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Datum</th>
        <th>Status</th>
        <th style="text-align: right;">Bedrag</th>
      </tr>
    </thead>
    <tbody>
      {"".join(table_rows)}
    </tbody>
  </table>

  <div class="totals">
    <table>
      <tr>
        <td>Subtotaal ({financials['aantal_dagen']} dagen excl. btw):</td>
        <td style="text-align: right;">€ {financials['subtotaal']:,.2f}</td>
      </tr>
      <tr>
        <td>Btw ({int(metadata['btw_pct'])}%):</td>
        <td style="text-align: right;">€ {financials['btw_bedrag']:,.2f}</td>
      </tr>
      <tr class="grand-total">
        <td>Totaal incl. btw:</td>
        <td style="text-align: right;">€ {financials['totaal_incl']:,.2f}</td>
      </tr>
    </table>
  </div>

  <div style="clear: both;"></div>

  <div class="info-note">
    <em>Interne urencontrole ter verantwoording: {financials['totale_uren']} uur geregistreerd over {financials['aantal_dagen']} werkdagen (gemiddeld {financials['gemiddelde_uren_dag']} uur/dag).</em>
  </div>
</body>
</html>
"""
    with open(filepath, mode="w", encoding="utf-8") as f:
        f.write(html_content)


def emit_github_outputs(metadata: dict, financials: dict, output_dir: str, billed_days: List[dict]) -> None:
    """Toont het resultaat in GitHub Actions Summary en zet outputs voor de workflow."""
    lines_summary = []
    for d in billed_days:
        dt = datetime.strptime(d["datum"], "%Y-%m-%d")
        lines_summary.append(f"- **{dt.strftime('%d-%m')}:** {d['status']} (€ {d['dagtarief']:,.2f})")

    summary_md = f"""# Factuurdossier Gegenereerd: {metadata['klant'].upper()} ({metadata['periode']})

- **Factuurnummer:** `factuur_{metadata['factuur_nr']}`
- **Locatie:** `{output_dir}/`
- **Dagen gewerkt:** {financials['aantal_dagen']} dagen (€ {metadata['dagtarief']:,.2f}/dag)
- **Subtotaal:** € {financials['subtotaal']:,.2f} | **Btw ({int(metadata['btw_pct'])}%):** € {financials['btw_bedrag']:,.2f} | **Totaal incl. btw:** € {financials['totaal_incl']:,.2f}

### Gewerkte Dagen:
{chr(10).join(lines_summary)}

> *Uren ter verantwoording: {financials['totale_uren']} uur geregistreerd (gemiddeld {financials['gemiddelde_uren_dag']} u/dag).*

**Bestanden in dossier:**
- `factuur_{metadata['factuur_nr']}.html`
- `factuur_{metadata['factuur_nr']}.json`
- `factuur_{metadata['factuur_nr']}.csv`
"""
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(summary_md)

    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"klant={metadata['klant']}\n")
            f.write(f"factuur_nr={metadata['factuur_nr']}\n")
            f.write(f"periode={metadata['periode']}\n")
            f.write(f"output_dir={output_dir}\n")


def main() -> None:
    klant, dagtarief, btw_pct, target_month_env, manual_nr = parse_environment()
    month_prefix = determine_target_month(target_month_env)
    records = load_monthly_records(CSV_INPUT_PATH, month_prefix)

    # Fallback bij testen indien doelmaand leeg is
    if not records and not target_month_env:
        current_month = datetime.now().strftime("%Y-%m")
        records = load_monthly_records(CSV_INPUT_PATH, current_month)
        if records:
            month_prefix = current_month

    factuur_nr = get_next_invoice_number(klant, manual_nr)
    jaar_str, maand_str = month_prefix.split("-")
    folder_periode = f"{maand_str}-{jaar_str}"

    output_dir = os.path.join(BASE_FACTURATIE_DIR, klant, folder_periode)
    os.makedirs(output_dir, exist_ok=True)

    billed_days, financials = calculate_days_and_financials(records, dagtarief, btw_pct)

    metadata = {
        "klant": klant,
        "periode": folder_periode,
        "factuur_nr": factuur_nr,
        "dagtarief": dagtarief,
        "btw_pct": btw_pct,
        "datum_gegenereerd": datetime.now().isoformat(),
    }

    base_path = os.path.join(output_dir, f"factuur_{factuur_nr}")
    export_csv(f"{base_path}.csv", billed_days)
    export_json(f"{base_path}.json", metadata, financials, billed_days)
    export_html(f"{base_path}.html", metadata, financials, billed_days)

    emit_github_outputs(metadata, financials, output_dir, billed_days)
    print(f"Factuur #{factuur_nr} succesvol gegenereerd: {financials['aantal_dagen']} dagen.")


if __name__ == "__main__":
    main()