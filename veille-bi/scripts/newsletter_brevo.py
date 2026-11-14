"""Envoie un rapport de tendances en newsletter via Brevo (ex-Sendinblue).

Usage :
  python veille-bi/scripts/newsletter_brevo.py RAPPORT.md --test      # envoi test à BREVO_TEST_EMAIL
  python veille-bi/scripts/newsletter_brevo.py RAPPORT.md --envoyer   # envoi à toute la liste
  python veille-bi/scripts/newsletter_brevo.py RAPPORT.md --dry-run   # écrit seulement le HTML

Variables d'environnement :
  BREVO_API_KEY       clé API Brevo (secret GitHub)
  BREVO_LIST_ID       numéro de la liste de contacts Brevo
  BREVO_SENDER_EMAIL  adresse d'expéditeur validée dans Brevo
  BREVO_SENDER_NAME   nom d'expéditeur (défaut : "Veille-Tech")
  BREVO_TEST_EMAIL    adresse(s) de test, séparées par des virgules
  SITE_URL            défaut : https://yannk59.github.io/Horizon
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path

import httpx
import markdown

API = "https://api.brevo.com/v3"

GABARIT = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{titre}</title></head>
<body style="margin:0;padding:0;background:#f4f4f5;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="max-width:640px;background:#ffffff;border-radius:8px;font-family:Georgia,'Times New Roman',serif;color:#1f2933;">
<tr><td style="padding:28px 32px 8px;border-bottom:3px solid #1f6feb;">
  <div style="font-family:Arial,sans-serif;font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#1f6feb;">Veille-Tech · startups &amp; tech</div>
  <h1 style="font-size:24px;line-height:1.3;margin:8px 0 12px;">{titre}</h1>
</td></tr>
<tr><td class="contenu" style="padding:16px 32px 8px;font-size:16px;line-height:1.6;">
{contenu}
</td></tr>
<tr><td style="padding:8px 32px 24px;">
  <a href="{lien}" style="display:inline-block;background:#1f6feb;color:#ffffff;text-decoration:none;font-family:Arial,sans-serif;font-size:14px;padding:10px 18px;border-radius:6px;">Lire en ligne</a>
</td></tr>
<tr><td style="padding:16px 32px 28px;border-top:1px solid #e4e7eb;font-family:Arial,sans-serif;font-size:12px;color:#7b8794;">
  Vous recevez cet email car vous êtes inscrit(e) à la newsletter Veille-Tech.<br>
  <a href="{{{{ unsubscribe }}}}" style="color:#7b8794;">Se désabonner</a>
</td></tr>
</table></td></tr></table></body></html>"""

STYLES = {
    "<h2>": '<h2 style="font-size:20px;margin:28px 0 8px;color:#102a43;">',
    "<h3>": '<h3 style="font-size:17px;margin:20px 0 6px;color:#102a43;">',
    "<blockquote>": '<blockquote style="margin:0 0 16px;padding:8px 14px;border-left:3px solid #d9e2ec;color:#52606d;">',
    "<table>": '<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:14px;margin:8px 0 16px;">',
    "<th>": '<th style="text-align:left;border-bottom:2px solid #d9e2ec;padding:6px;">',
    "<td>": '<td style="border-bottom:1px solid #e4e7eb;padding:6px;vertical-align:top;">',
    "<a href": '<a style="color:#1f6feb;" href',
    "<code>": '<code style="font-family:Arial,sans-serif;font-size:12px;background:#eef2ff;padding:1px 6px;border-radius:4px;">',
}


def preparer(chemin: Path, site_url: str) -> tuple[str, str]:
    texte = chemin.read_text(encoding="utf-8")
    texte = re.sub(r"^<!--.*?-->\s*", "", texte, flags=re.S)
    if texte.startswith("---\n"):  # front matter d'un article publié
        texte = re.sub(r"^---\n.*?\n---\n", "", texte, count=1, flags=re.S)
    titre = next((l[2:].strip() for l in texte.splitlines() if l.startswith("# ")), "Rapport de tendances")
    corps = "\n".join(l for l in texte.splitlines() if not l.startswith("# "))
    corps = re.sub(r"\n_Vérification :.*$", "", corps.strip())  # mention interne, pas pour les lecteurs
    # Python-Markdown exige une ligne vide avant une liste (ex. "**Preuves** :" suivi de puces)
    corps = re.sub(r"(?m)^(?![ \t]*(?:[-*+]|\d+\.) )(\S.*)\n(?=[ \t]*(?:[-*+]|\d+\.) )", r"\1\n\n", corps)
    contenu = markdown.markdown(corps, extensions=["tables", "sane_lists"])
    for brut, style in STYLES.items():
        contenu = contenu.replace(brut, style)
    jour = chemin.name[:10]
    a, m, j = jour.split("-")
    lien = f"{site_url}/{a}/{m}/{j}/rapport-tendances-fr.html"
    return titre, GABARIT.format(titre=html.escape(titre), contenu=contenu, lien=lien)


def api(client: httpx.Client, methode: str, chemin: str, **kw) -> dict:
    r = client.request(methode, f"{API}{chemin}", **kw)
    if r.status_code >= 400:
        sys.exit(f"Erreur Brevo {r.status_code} sur {chemin} : {r.text}")
    return r.json() if r.content else {}


def env(nom: str, defaut: str | None = None) -> str:
    v = os.environ.get(nom) or defaut
    if not v:
        sys.exit(f"Variable manquante : {nom}")
    return v


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rapport")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--test", action="store_true")
    g.add_argument("--envoyer", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    chemin = Path(args.rapport)
    titre, corps_html = preparer(chemin, os.environ.get("SITE_URL") or "https://yannk59.github.io/Horizon")

    if args.dry_run:
        sortie = chemin.with_suffix(".newsletter.html")
        sortie.write_text(corps_html, encoding="utf-8")
        print(f"HTML écrit : {sortie}")
        return

    entetes = {"api-key": env("BREVO_API_KEY"), "accept": "application/json"}
    campagne = {
        "name": f"{'[TEST] ' if args.test else ''}{titre}",
        "subject": titre,
        "previewText": "Les tendances startups & tech de la période, chiffres et sources à l'appui.",
        "sender": {"name": env("BREVO_SENDER_NAME", "Veille-Tech"), "email": env("BREVO_SENDER_EMAIL")},
        "htmlContent": corps_html,
    }
    if not args.test:  # un test n'exige pas de contacts dans la liste (Brevo refuse une liste vide)
        campagne["recipients"] = {"listIds": [int(env("BREVO_LIST_ID"))]}
    with httpx.Client(headers=entetes, timeout=60) as client:
        cid = api(client, "POST", "/emailCampaigns", json=campagne)["id"]
        print(f"Campagne Brevo créée : #{cid}")
        if args.test:
            dest = [e.strip() for e in env("BREVO_TEST_EMAIL").split(",") if e.strip()]
            api(client, "POST", f"/emailCampaigns/{cid}/sendTest", json={"emailTo": dest})
            print(f"Email de test envoyé à : {', '.join(dest)}")
        else:
            api(client, "POST", f"/emailCampaigns/{cid}/sendNow")
            print("Newsletter envoyée à la liste.")


if __name__ == "__main__":
    main()
