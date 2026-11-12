"""Génère un rapport de tendances à partir des briefings quotidiens Horizon.

Chaîne de 3 agents (prompts dans veille-bi/agents/) :
  1. analyste      -> regroupe les signaux en tendances
  2. redacteur     -> rédige le rapport selon le modèle
  3. verificateur  -> contrôle les faits face aux sources

Usage :
  python veille-bi/scripts/rapport_tendances.py generer --posts-dir pages/_posts --jours 7
  python veille-bi/scripts/rapport_tendances.py publier veille-bi/rapports/2026-11-16-hebdo.md --out-dir out/_posts

Variables d'environnement :
  ANTHROPIC_API_KEY  (obligatoire pour "generer", sauf --dry-run)
  VEILLE_MODEL       (optionnel ; sinon le modèle de data/config.github.json)
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BI = ROOT / "veille-bi"
POST_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-summary-(\w+)\.md$")
MAX_CHARS_PAR_JOUR = 14000


def lire(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def nettoyer_briefing(texte: str) -> str:
    """Retire le front matter, les blocs HTML de références et les ancres pour économiser des tokens."""
    texte = re.sub(r"^---\n.*?\n---\n", "", texte, count=1, flags=re.S)
    texte = re.sub(r"<details>.*?</details>", "", texte, flags=re.S)
    texte = re.sub(r"<a id=\"[^\"]*\"></a>", "", texte)
    texte = html.unescape(html.unescape(texte.replace("\\#", "#")))
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    return texte.strip()[:MAX_CHARS_PAR_JOUR]


def collecter(posts_dir: Path, jours: int, langue: str, fin: date) -> list[tuple[str, str]]:
    debut = fin - timedelta(days=jours - 1)
    briefings = []
    for p in sorted(posts_dir.glob("*.md")):
        m = POST_RE.match(p.name)
        if not m or m.group(2) != langue:
            continue
        d = date.fromisoformat(m.group(1))
        if debut <= d <= fin:
            briefings.append((m.group(1), nettoyer_briefing(lire(p))))
    return briefings


def modele_par_defaut() -> str:
    env = os.environ.get("VEILLE_MODEL")
    if env:
        return env
    for nom in ("config.json", "config.github.json"):
        cfg = ROOT / "data" / nom
        if cfg.exists():
            return json.loads(lire(cfg))["ai"]["model"]
    sys.exit("Aucun modèle trouvé : définissez VEILLE_MODEL.")


def appeler(client, modele: str, systeme: str, contenu: str) -> str:
    rep = client.messages.create(
        model=modele,
        max_tokens=8000,
        system=systeme,
        messages=[{"role": "user", "content": contenu}],
    )
    return "".join(b.text for b in rep.content if getattr(b, "type", "") == "text").strip()


def generer(args) -> None:
    fin = date.fromisoformat(args.fin) if args.fin else datetime.now(timezone.utc).date()
    briefings = collecter(Path(args.posts_dir), args.jours, args.langue, fin)
    if not briefings:
        sys.exit(f"Aucun briefing '{args.langue}' trouvé sur les {args.jours} derniers jours dans {args.posts_dir}.")

    debut = briefings[0][0]
    periode = f"du {debut} au {briefings[-1][0]}" if len(briefings) > 1 else f"le {debut}"
    corpus = "\n\n".join(f"=== BRIEFING DU {d} ===\n{t}" for d, t in briefings)
    modele_rapport = lire(BI / "templates" / "rapport-hebdo.md")
    print(f"{len(briefings)} briefing(s) collecté(s) ({periode}), {len(corpus)} caractères.")

    sortie = Path(args.sortie or BI / "rapports" / f"{fin.isoformat()}-{args.jours}j.md")
    sortie.parent.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        sortie.with_suffix(".corpus.txt").write_text(corpus, encoding="utf-8")
        print(f"[dry-run] Corpus écrit dans {sortie.with_suffix('.corpus.txt')}")
        return

    import anthropic

    client = anthropic.Anthropic()
    modele = args.modele or modele_par_defaut()
    print(f"Modèle : {modele}")

    print("1/3 Analyste…")
    analyse = appeler(client, modele, lire(BI / "agents" / "analyste.md"),
                      f"Période : {periode}\n\n{corpus}")

    print("2/3 Rédacteur…")
    rapport = appeler(client, modele, lire(BI / "agents" / "redacteur.md"),
                      f"Période : {periode}\nNombre de briefings : {len(briefings)}\n\n"
                      f"# MODÈLE DE RAPPORT\n{modele_rapport}\n\n# ANALYSE\n{analyse}")

    print("3/3 Vérificateur…")
    final = appeler(client, modele, lire(BI / "agents" / "verificateur.md"),
                    f"# BRIEFINGS SOURCES\n{corpus}\n\n# RAPPORT À VÉRIFIER\n{rapport}")

    entete = f"<!-- brouillon généré le {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · {periode} · {modele} -->\n"
    sortie.write_text(entete + final + "\n", encoding="utf-8")
    (sortie.with_suffix(".analyse.md")).write_text(analyse + "\n", encoding="utf-8")
    print(f"Brouillon écrit : {sortie}")


def publier(args) -> None:
    src = Path(args.brouillon)
    texte = re.sub(r"^<!--.*?-->\n", "", lire(src), flags=re.S)
    titre = next((l[2:].strip() for l in texte.splitlines() if l.startswith("# ")), "Rapport de tendances")
    texte = "\n".join(l for l in texte.splitlines() if not l.startswith("# ")).strip()
    jour = src.name[:10]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{jour}-rapport-tendances-fr.md"
    titre_yaml = titre.replace('"', "'")
    dest.write_text(
        f"---\nlayout: default\ntitle: \"{titre_yaml}\"\ndate: {jour}\nlang: fr\n"
        f"categories: rapport\n---\n\n{texte}\n",
        encoding="utf-8",
    )
    print(f"Publié : {dest}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generer", help="Générer un brouillon de rapport")
    g.add_argument("--posts-dir", default="docs/_posts")
    g.add_argument("--jours", type=int, default=7, help="7 = hebdo, 30 = mensuel")
    g.add_argument("--langue", default="fr")
    g.add_argument("--fin", help="Date de fin AAAA-MM-JJ (défaut : aujourd'hui)")
    g.add_argument("--modele")
    g.add_argument("--sortie")
    g.add_argument("--dry-run", action="store_true", help="Collecter sans appeler l'API")
    g.set_defaults(func=generer)

    p = sub.add_parser("publier", help="Transformer un brouillon validé en article GitHub Pages")
    p.add_argument("brouillon")
    p.add_argument("--out-dir", default="docs/_posts")
    p.set_defaults(func=publier)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
