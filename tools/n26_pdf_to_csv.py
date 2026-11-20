#!/usr/bin/env python3
"""Turn N26 monthly statement PDFs (Kontoauszug) into one CSV the Budget app can import.

    python3 tools/n26_pdf_to_csv.py ~/Downloads/Enero.pdf ~/Downloads/Febrero.pdf ... -o ~/Downloads/n26.csv

Needs `pdftotext` (brew install poppler). Only the main account section is read: the
"Space Kontoauszug" pages repeat the moves to and from Spaces and would count them twice.
The output uses the same columns as N26's own CSV export.
"""
import argparse, csv, re, subprocess, sys
from pathlib import Path

MAIN = re.compile(r"^(?P<name>.+?)\s{2,}(?P<date>\d{2}\.\d{2}\.\d{4})\s+(?P<amt>[+-][\d.]+,\d{2})€\s*$")
FOOTER = re.compile(r"(Erstellt am|^\s*IBAN: DE\d+ • BIC: NTSB|^\s*\d+ / \d+\s*$|Nr\. \d\d/\d{4}\s*$)")


def parse(pdf: Path):
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    rows, cur, section = [], None, "main"
    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if s.startswith("Space Kontoauszug") or s.startswith("Spaces Zusammenfassung"):
            section = "space"; cur = None; continue
        if s.startswith("Kontoauszug Nr."):
            section = "main"; cur = None; continue
        if "Erstellt am" in s:  # page footer (name, address, IBAN) starts: close the open movement
            cur = None; continue
        if section != "main":
            continue
        m = MAIN.match(s)
        if m:
            d, mo, y = m["date"].split(".")
            cur = {"Booking Date": f"{y}-{mo}-{d}", "Value Date": "", "Partner Name": m["name"].strip(), "Partner Iban": "",
                   "Type": "", "Category": "", "Payment Reference": "", "Account Name": "Main Account",
                   "Amount (EUR)": m["amt"].replace(".", "").replace(",", ".").lstrip("+"), "Original Amount": "", "Original Currency": "", "Exchange Rate": ""}
            rows.append(cur); continue
        if cur is None or not s or FOOTER.search(line):
            if not s: cur = cur if cur and not cur["Type"] else None
            continue
        if s.startswith("Wertstellung"):
            d, mo, y = s.split()[-1].split(".")
            cur["Value Date"] = f"{y}-{mo}-{d}"
        elif not cur["Type"]:
            kind, _, cat = s.partition(" • ")
            cur["Type"], cur["Category"] = kind.strip(), cat.strip()
        elif s.startswith("IBAN:"):
            cur["Partner Iban"] = s.split()[1]
        elif s.startswith("Ursprungsbetrag"):
            mm = re.match(r"Ursprungsbetrag ([\d.]+) (\w+) \| Wechselkurs ([\d.]+)", s)
            if mm: cur["Original Amount"], cur["Original Currency"], cur["Exchange Rate"] = mm.groups()
        else:
            cur["Payment Reference"] = (cur["Payment Reference"] + " " + s).strip()
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdfs", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path, help="CSV file to write (default: stdout)")
    a = ap.parse_args()
    rows = []
    for p in a.pdfs:
        got = parse(p)
        print(f"{p.name}: {len(got)} movimientos", file=sys.stderr)
        rows += got
    rows.sort(key=lambda r: r["Booking Date"])
    out = open(a.out, "w", newline="", encoding="utf-8") if a.out else sys.stdout
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys()) if rows else ["Booking Date"])
    w.writeheader(); w.writerows(rows)
    if a.out:
        out.close(); print(f"→ {a.out} ({len(rows)} movimientos)", file=sys.stderr)


if __name__ == "__main__":
    main()
