"""
Scraper de árbitros: obtiene partidos de fichajes.com y opcionalmente el árbitro
de la página de cada partido (cuando la designación se publica 1-2 días antes).
Fuente: https://www.fichajes.com/futbol-tele/inglaterra/premier-league
"""
import re
import requests
from bs4 import BeautifulSoup
from django.db import transaction

from .models import DesignacionArbitro

URL_PREMIER = "https://www.fichajes.com/futbol-tele/inglaterra/premier-league"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Slug en URL fichajes -> nombre exacto en nuestro selector (todos los equipos Premier)
SLUG_A_EQUIPO = {
    "manchester-united": "Manchester United",
    "tottenham-hotspur": "Tottenham Hotspur",
    "tottenham": "Tottenham Hotspur",
    "bournemouth": "AFC Bournemouth",
    "aston-villa": "Aston Villa",
    "fulham": "Fulham",
    "everton": "Everton",
    "arsenal": "Arsenal",
    "sunderland": "Sunderland",
    "wolverhampton-wanderers": "Wolverhampton Wanderers",
    "wolverhampton": "Wolverhampton Wanderers",
    "chelsea": "Chelsea",
    "burnley": "Burnley",
    "west-ham-united": "West Ham United",
    "west-ham": "West Ham United",
    "newcastle-united": "Newcastle United",
    "newcastle": "Newcastle United",
    "brentford": "Brentford",
    "brighton-hove-albion": "Brighton & Hove Albion",
    "brighton": "Brighton & Hove Albion",
    "crystal-palace": "Crystal Palace",
    "liverpool": "Liverpool",
    "manchester-city": "Manchester City",
    "man-city": "Manchester City",
    "leeds-united": "Leeds United",
    "leeds": "Leeds United",
    "nottingham-forest": "Nottingham Forest",
}


def _slug_a_equipo(slug):
    s = (slug or "").strip().lower().replace("_", "-")
    return SLUG_A_EQUIPO.get(s) or slug


def _parsear_directo_url(href):
    """De una URL tipo /directo/123456-brighton-hove-albion-vs-crystal-palace devuelve (local, visitante)."""
    if not href or "vs" not in href:
        return None, None
    part = href.split("/")[-1]
    part = re.sub(r"^\d+-", "", part)
    if "-vs-" in part:
        a, b = part.split("-vs-", 1)
        return _slug_a_equipo(a.strip()), _slug_a_equipo(b.strip())
    return None, None


def _extraer_arbitro_de_pagina(html_text):
    """Busca en el HTML el nombre del árbitro (patrones: 'Árbitro:', 'Referee:', labels, etc.)."""
    if not html_text:
        return None
    soup = BeautifulSoup(html_text, "html.parser")
    # 1) Buscar en etiquetas que suelen llevar "Árbitro" / "Referee" (dt, label, span, div)
    for tag in soup.find_all(["dt", "label", "span", "div", "th", "td", "p"]):
        txt = (tag.get_text() or "").strip()
        if not txt or len(txt) > 60:
            continue
        if re.search(r"árbitro|referee", txt, re.I) and ":" in txt:
            # Ej: "Árbitro: Thomas Bramall" o "Referee: Michael Oliver"
            m = re.search(r"[:\s]\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\.]{2,50}?)(?:\s*\||\s*$|\s*<|$)", txt)
            if m:
                name = m.group(1).strip().rstrip(".,;:")
                if 4 < len(name) < 45 and not name.lower().startswith(("el ", "la ", "los ")):
                    return name
        # Si el texto es solo "Árbitro" o "Referee", el nombre puede estar en el siguiente hermano
        if re.match(r"^(Árbitro|Referee)\s*:?\s*$", txt, re.I):
            next_sib = tag.find_next_sibling()
            if next_sib:
                name = (next_sib.get_text() or "").strip()
                if 4 < len(name) < 45:
                    return name
    # 2) Buscar en el texto plano de la página
    text = soup.get_text(separator=" ", strip=True)
    for pattern in [
        r"[Aa]rbitro\s*[:\s]+\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\.]{2,45}?)(?:\s+[\d\.]|\s*$)",
        r"[Rr]eferee\s*[:\s]+\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\.]{2,45}?)(?:\s+[\d\.]|\s*$)",
        r"[Aa]rbitro\s+principal\s*[:\s]+\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\.]{2,45}?)(?:\s|$)",
    ]:
        m = re.search(pattern, text)
        if m:
            name = m.group(1).strip().rstrip(".,;:")
            if len(name) > 4 and not name.lower().startswith(("el ", "la ", "los ")):
                return name
    return None


def ejecutar_scraper_arbitros_fichajes(obtener_pagina_partido=True):
    """
    Scrape fichajes.com Premier League: lista de partidos y, si obtener_pagina_partido,
    entra en cada enlace de partido para intentar sacar el árbitro.
    Devuelve (num_partidos, num_arbitros_actualizados).
    """
    try:
        r = requests.get(URL_PREMIER, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return 0, 0
        soup = BeautifulSoup(r.content, "html.parser")
        partidos = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/directo/" in href and "vs" in href:
                text = (a.get_text() or "").strip()
                if not text or len(text) > 80:
                    continue
                local, visitante = _parsear_directo_url(href)
                if local and visitante:
                    partidos.append({"local": local, "visitante": visitante, "href": href})
        # Quitar duplicados por (local, visitante)
        vistos = set()
        unicos = []
        for p in partidos:
            k = (p["local"], p["visitante"])
            if k not in vistos:
                vistos.add(k)
                unicos.append(p)
        partidos = unicos
        actualizados = 0
        with transaction.atomic():
            for p in partidos:
                arbitro_nombre = None
                if obtener_pagina_partido and p.get("href"):
                    try:
                        url_partido = p["href"].strip()
                        if not url_partido.startswith("http"):
                            url_partido = ("https://www.fichajes.com" + url_partido) if url_partido.startswith("/") else "https://www.fichajes.com/" + url_partido
                        r2 = requests.get(url_partido, headers=HEADERS, timeout=10)
                        if r2.status_code == 200:
                            arbitro_nombre = _extraer_arbitro_de_pagina(r2.text)
                    except Exception:
                        pass
                if arbitro_nombre:
                    DesignacionArbitro.objects.update_or_create(
                        equipo_local=p["local"],
                        equipo_visitante=p["visitante"],
                        defaults={"arbitro_nombre": arbitro_nombre},
                    )
                    actualizados += 1
        return len(partidos), actualizados
    except Exception as e:
        print(f"Error scraper árbitros: {e}")
        return 0, 0
