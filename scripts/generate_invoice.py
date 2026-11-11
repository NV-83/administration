#!/usr/bin/env python3
import csv
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

CSV_INPUT_PATH = "data/uren.csv"
BASE_FACTURATIE_DIR = "data/facturatie"
TIME_FORMAT = "%H:%M"


def parse_environment() -> Tuple[str, float, float, str, str]:
    """Leest en valideert de omgevingsvariabelen."""
    klant = os.environ.get("KLANT_NAAM", "waso").strip().lower()
    tarief = float(os.environ.get("UURTARIEF", "85.0"))
    btw_pct = float(os.environ.get("BTW_TARIEF", "21"))
    target_month = os.environ.get("TARGET_MONTH", "").strip()
    manual_factuur_nr = os.environ.get("MANUAL_FACTUUR_NR", "").strip()
    return klant, tarief, btw_pct, target_month, manual_factuur_nr


def determine_target_month(target_month_override: str) -> str:
    """Bepaalt de doelmaand (JJJJ-MM). Standaard de voorgaande kalendermaand."""
    if target_month_override:
        return target_month_override

    vandaag = datetime.now().date()
    eerste_van_nu = vandaag.replace(day=1)
    jaar = eerste_van_nu.year if eerste_van_nu.month > 1 else eerste_van_nu.year - 1
    maand = eerste_van_nu.month - 1 if eerste_van_nu.month > 1 else 12
    return f"{jaar}-{maand:02d}"


def get_next_invoice_number(klant: str, manual_nr: str = "") -> str:
    """
    Bepaalt het volgende factuurnummer.
    Scant data/facturatie/<klant>/** naar bestaande factuur_<nr> bestanden
    en telt op met +1. Start op '01' indien geen historiek aanwezig is.
    """
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
    """Laadt en filtert de rijen voor de gewenste maand uit de centrale CSV."""
    if not os.path.exists(csv_path):
        return []

    records = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("datum") and row["datum"].startswith(month_prefix):
                records.append(row)
    return records


def calculate_shift_minutes(start_str: str, eind_str: str, pauze_str: str) -> int:
    """Berekent netto minuten tussen twee tijdstippen minus pauze."""
    try:
        t1 = datetime.strptime(start_str, TIME_FORMAT)
        t2 = datetime.strptime(eind_str, TIME_FORMAT)
        pauze = int(pauze_str) if pauze_str and pauze_str.isdigit() else 0
        return max(0, int((t2 - t1).total_seconds() / 60) - pauze)
    except Exception:
        return 0


def calculate_financials(
    records: List[Dict[str, str]], tarief: float, btw_pct: float
) -> Dict[str, float]:
    """Berekent urentotalen, opsplitsing thuis/kantoor en financiële bedragen."""
    thuis_minuten = 0
    kantoor_minuten = 0

    for r in records:
        # Shift 1
        s1_min = calculate_shift_minutes(r.get("start", ""), r.get("eind", ""), r.get("pauze_min", "0"))
        if r.get("locatie") == "Thuis":
            thuis_minuten += s1_min
        else:
            kantoor_minuten += s1_min

        # Shift 2 (extra)
        if r.get("start_extra") and r.get("eind_extra"):
            s2_min = calculate_shift_minutes(
                r.get("start_extra", ""), r.get("eind_extra", ""), r.get("pauze_extra_min", "0")
            )
            loc2 = r.get("locatie_extra") or "Thuis"
            if loc2 == "Thuis":
                thuis_minuten += s2_min
            else:
                kantoor_minuten += s2_min

    totale_minuten = thuis_minuten + kantoor_minuten
    totaal_uren = round(totale_minuten / 60.0, 2)
    thuis_uren = round(thuis_minuten / 60.0, 2)
    kantoor_uren = round(kantoor_minuten / 60.0, 2)

    subtotaal = round(totaal_uren * tarief, 2)
    btw_bedrag = round(subtotaal * (btw_pct / 100.0), 2)
    totaal_incl = round(subtotaal + btw_bedrag, 2)

    return {
        "totale_minuten": totale_minuten,
        "totale_duur_str": f"{totale_minuten // 60:02d}:{totale_minuten % 60:02d}",
        "totaal_uren": totaal_uren,
        "thuis_uren": thuis_uren,
        "kantoor_uren": kantoor_uren,
        "subtotaal": subtotaal,
        "btw_bedrag": btw_bedrag,
        "totaal_incl": totaal_incl,
    }


def export_csv(filepath: str, records: List[Dict[str, str]]) -> None:
    """Exporteert de gefilterde maanddata naar CSV."""
    fieldnames = [
        "datum", "locatie", "start", "eind", "pauze_min",
        "locatie_extra", "start_extra", "eind_extra", "pauze_extra_min",
        "duur", "netto_uren", "omschrijving"
    ]
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def export_json(filepath: str, metadata: dict, financials: dict, records: List[dict]) -> None:
    """Exporteert factuur- en prestatiemetadata naar JSON."""
    payload = {
        "metadata": metadata,
        "financieel": financials,
        "prestaties": records,
    }
    with open(filepath, mode="w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def export_html(filepath: str, metadata: dict, financials: dict, records: List[dict]) -> None:
    """Genereert de printklare A4 HTML factuurbijlage."""
    table_rows = []
    for r in records:
        p1 = r.get("pauze_min", "0")
        s1 = f"{r.get('start', '')} - {r.get('eind', '')}<br><small>({r.get('locatie', '')}, pauze: {p1}m)</small>"
        s2 = "-"
        if r.get("start_extra") and r.get("eind_extra"):
            loc2 = r.get("locatie_extra") or "Thuis"
            s2 = f"{r.get('start_extra')} - {r.get('eind_extra')}<br><small>({loc2})</small>"

        table_rows.append(f"""
        <tr>
          <td>{r.get('datum', '')}</td>
          <td>{s1}</td>
          <td>{s2}</td>
          <td style="font-weight:600;">{r.get('duur', '-')}</td>
          <td>{r.get('netto_uren', '0')}</td>
          <td>{r.get('omschrijving', '-')}</td>
        </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>Prestatiestaat {metadata['periode']} - {metadata['klant'].upper()}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 30px; color: #1e293b; }}
  .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #0f172a; padding-bottom: 15px; margin-bottom: 25px; }}
  .header h1 {{ margin: 0; font-size: 24px; color: #0f172a; }}
  .meta-box {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 25px; }}
  .meta-box h3 {{ margin-top: 0; margin-bottom: 10px; font-size: 16px; color: #334155; }}
  .meta-box p {{ margin: 4px 0; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }}
  th {{ background: #f1f5f9; color: #0f172a; }}
  .totals {{ margin-top: 25px; float: right; width: 320px; }}
  .totals table {{ border: none; font-size: 14px; }}
  .totals td {{ border: none; padding: 6px; }}
  .grand-total {{ font-weight: bold; font-size: 16px; border-top: 2px solid #0f172a !important; color: #0f172a; }}
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
      <h3>Urenoverzicht</h3>
      <p><strong>Totaal gewerkt:</strong> {financials['totale_duur_str']} ({financials['totaal_uren']:.2f} uur)</p>
      <p><strong>Kantoor / On-site:</strong> {financials['kantoor_uren']:.2f} uur</p>
      <p><strong>Thuiswerk:</strong> {financials['thuis_uren']:.2f} uur</p>
    </div>
    <div>
      <h3>Facturatieparameters</h3>
      <p><strong>Uurtarief:</strong> € {metadata['tarief']:,.2f}</p>
      <p><strong>Btw-tarief:</strong> {int(metadata['btw_pct'])}%</p>
      <p><strong>Status:</strong> Facturatieklaar</p>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Datum</th>
        <th>Shift 1</th>
        <th>Shift 2 (extra)</th>
        <th>Duur</th>
        <th>Uur</th>
        <th>Omschrijving</th>
      </tr>
    </thead>
    <tbody>
      {"".join(table_rows)}
    </tbody>
  </table>

  <div class="totals">
    <table>
      <tr>
        <td>Subtotaal (excl. btw):</td>
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
</body>
</html>
"""
    with open(filepath, mode="w", encoding="utf-8") as f:
        f.write(html_content)


def emit_github_outputs(metadata: dict, financials: dict, output_dir: str) -> None:
    """Communiceert de resultaten terug naar GitHub Actions Job Summary en GITHUB_OUTPUT."""
    summary_md = f"""# Factuurdossier Gegenereerd: {metadata['klant'].upper()} ({metadata['periode']})

- **Factuurnummer:** `factuur_{metadata['factuur_nr']}`
- **Locatie:** `{output_dir}/`
- **Totaal prestatie:** {financials['totale_duur_str']} ({financials['totaal_uren']:.2f} uur)
- **Subtotaal:** € {financials['subtotaal']:,.2f} | **Btw ({int(metadata['btw_pct'])}%):** € {financials['btw_bedrag']:,.2f} | **Totaal incl. btw:** € {financials['totaal_incl']:,.2f}

**Aangemaakte bestanden:**
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
    klant, tarief, btw_pct, target_month_env, manual_nr = parse_environment()
    month_prefix = determine_target_month(target_month_env)
    records = load_monthly_records(CSV_INPUT_PATH, month_prefix)

    # Fallback bij testen: als de berekende doelmaand leeg is, probeer huidige maand
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

    financials = calculate_financials(records, tarief, btw_pct)
    metadata = {
        "klant": klant,
        "periode": folder_periode,
        "factuur_nr": factuur_nr,
        "tarief": tarief,
        "btw_pct": btw_pct,
        "datum_gegenereerd": datetime.now().isoformat(),
    }

    base_path = os.path.join(output_dir, f"factuur_{factuur_nr}")
    export_csv(f"{base_path}.csv", records)
    export_json(f"{base_path}.json", metadata, financials, records)
    export_html(f"{base_path}.html", metadata, financials, records)

    emit_github_outputs(metadata, financials, output_dir)
    print(f"Factuur #{factuur_nr} succesvol aangemaakt in {output_dir}")


if __name__ == "__main__":
    main()