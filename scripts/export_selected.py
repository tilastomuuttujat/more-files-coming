#!/usr/bin/env python3
"""
export_selected.py
------------------
Lukee `export_selection.yaml`-tiedoston ja exporttaa kaikki rivit,
joilla include: true, JSON-tiedostoiksi:

  - taulut  -> public/data/<name>.json
  - näkymät -> public/data/views/<name>.json

Käyttää PostgRESTiä rivien hakuun (sivutus 1000 / kutsu).
"""
from __future__ import annotations
import os, sys, json, urllib.request, urllib.error
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML puuttuu. Asenna: pip install pyyaml")

SB_URL = os.environ["TTT_SB_URL"].rstrip("/")
SB_KEY = os.environ["TTT_SB_SERVICE_KEY"]
PAGE = 1000

SELECTION_FILE = Path("export_selection.yaml")
DATA_DIR = Path("public/data")
VIEWS_DIR = Path("public/data/views")


def fetch_all(name: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        url = f"{SB_URL}/rest/v1/{name}?select=*&limit={PAGE}&offset={offset}"
        req = urllib.request.Request(
            url,
            headers={
                "apikey": SB_KEY,
                "Authorization": f"Bearer {SB_KEY}",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                batch = json.loads(r.read())
        except urllib.error.HTTPError as e:
            print(f"  ! {name}: HTTP {e.code} -> ohitetaan "
                  f"({e.read().decode(errors='ignore')[:200]})")
            return rows
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
    return rows


def export(name: str, outdir: Path) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    rows = fetch_all(name)
    out = outdir / f"{name}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
    return len(rows)


def main() -> None:
    if not SELECTION_FILE.exists():
        sys.exit(f"{SELECTION_FILE} puuttuu. Aja ensin 'Discover schema' -workflow.")
    doc = yaml.safe_load(SELECTION_FILE.read_text()) or {}

    tables = [t["name"] for t in (doc.get("tables") or []) if t.get("include")]
    views = [v["name"] for v in (doc.get("views") or []) if v.get("include")]

    if not tables and not views:
        sys.exit("Mitään ei ole valittu (include: true). Ei tehdä mitään.")

    print(f"Exportoidaan {len(tables)} taulua -> {DATA_DIR}/")
    for t in tables:
        n = export(t, DATA_DIR)
        print(f"  ✓ {t}: {n} riviä")

    print(f"Exportoidaan {len(views)} näkymää -> {VIEWS_DIR}/")
    for v in views:
        n = export(v, VIEWS_DIR)
        print(f"  ✓ {v}: {n} riviä")

    print("Valmis.")


if __name__ == "__main__":
    main()
