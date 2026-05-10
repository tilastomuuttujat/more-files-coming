#!/usr/bin/env python3
"""
discover_schema.py
------------------
Listaa kaikki public-skeeman taulut ja näkymät ulkoisesta Supabasesta
ja päivittää `export_selection.yaml`-tiedoston:

  - Uudet entryt lisätään include: false -arvolla
  - Olemassa olevien entryjen include-valinta SÄILYY ennallaan
  - Poistetut entryt poistetaan myös YAML:stä

YAML toimii "lomakkeena": editoit sitä GitHubin web-editorissa
(tai paikallisesti) ja vaihdat haluamasi rivit include: true.

Tarvittavat env-muuttujat:
  TTT_SB_URL           - https://<project>.supabase.co
  TTT_SB_SERVICE_KEY   - service_role key (vain GitHub Secretsissä)
"""
from __future__ import annotations
import os, sys, json, urllib.request, urllib.error
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:
    sys.exit("PyYAML puuttuu. Asenna: pip install pyyaml")

SB_URL = os.environ["TTT_SB_URL"].rstrip("/")
SB_KEY = os.environ["TTT_SB_SERVICE_KEY"]

SELECTION_FILE = Path("export_selection.yaml")

# Käytetään Supabasen RPC:tä SQL:ää varten? -> ei, vaan PostgREST:n
# information_schema-näkymä ei ole oletuksena käytettävissä.
# Käytetään sen sijaan pg_meta -tyyppistä reittiä RPC:llä jos löytyy,
# muuten yksinkertainen RPC `exec_sql` -fallback. Helpoin ja varmin
# tapa on luoda yksi pieni Postgres-funktio kerran (ks. README).

SQL = """
select table_name as name,
       case table_type when 'VIEW' then 'view' else 'table' end as kind
from information_schema.tables
where table_schema = 'public'
  and table_name not like 'pg_%'
order by kind, name;
"""

def fetch_objects() -> list[dict]:
    """Kutsuu RPC-funktiota public.list_public_objects()."""
    url = f"{SB_URL}/rest/v1/rpc/list_public_objects"
    req = urllib.request.Request(
        url,
        method="POST",
        data=b"{}",
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(
            f"RPC list_public_objects epäonnistui ({e.code}). "
            f"Luo funktio Supabasen SQL-editorissa (ks. README).\n"
            f"Vastaus: {e.read().decode(errors='ignore')}"
        )


def load_existing() -> dict[str, bool]:
    if not SELECTION_FILE.exists():
        return {}
    data = yaml.safe_load(SELECTION_FILE.read_text()) or {}
    out: dict[str, bool] = {}
    for section in ("tables", "views"):
        for item in (data.get(section) or []):
            out[f"{section}:{item['name']}"] = bool(item.get("include", False))
    return out


def main() -> None:
    objects = fetch_objects()
    existing = load_existing()

    tables, views = [], []
    for o in objects:
        name, kind = o["name"], o["kind"]
        section = "tables" if kind == "table" else "views"
        include = existing.get(f"{section}:{name}", False)
        (tables if kind == "table" else views).append(
            {"name": name, "include": include}
        )

    doc = {
        "_help": (
            "Vaihda 'include: true' niille tauluille/näkymille, jotka "
            "haluat exporttiin. Aja sen jälkeen 'Export selected to JSON' "
            "-workflow."
        ),
        "tables": tables,
        "views": views,
    }

    SELECTION_FILE.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, indent=2)
    )

    sel_t = sum(1 for t in tables if t["include"])
    sel_v = sum(1 for v in views if v["include"])
    print(f"Löytyi {len(tables)} taulua ja {len(views)} näkymää.")
    print(f"Valittuna: {sel_t} taulua, {sel_v} näkymää.")
    print(f"Päivitetty: {SELECTION_FILE}")


if __name__ == "__main__":
    main()
