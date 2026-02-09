"""
Scraper de árbitros Premier League desde livefutbol.com (estadísticas por árbitro).
Fuente: https://www.livefutbol.com/competition/co91/inglaterra-premier-league/referees/
Devuelve lista con nombre y tarjetas por partido (Amarillo + Amarillo Rojo + Rojo) / Juegos.
"""
import requests
from bs4 import BeautifulSoup

URL_REFEREES = "https://www.livefutbol.com/competition/co91/inglaterra-premier-league/referees/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

# Cache en memoria para no hacer request en cada carga del formulario
_cache_arbitros = None


def _int_val(text, default=0):
    try:
        return int("".join(c for c in str(text).strip() if c.isdigit()) or default)
    except (ValueError, TypeError):
        return default


def obtener_arbitros_livefutbol():
    """
    Scrape la tabla de árbitros (no asistentes). Devuelve lista de dicts:
    [{"nombre": "Michael Oliver", "tarjetas_promedio": 2.85, "nota": "20 partidos"}, ...]
    """
    global _cache_arbitros
    try:
        r = requests.get(URL_REFEREES, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return _cache_arbitros or []
        soup = BeautifulSoup(r.content, "html.parser")
        # Buscar la sección "Árbitro" (no "Árbitros asistentes")
        arbitros = []
        for h2 in soup.find_all("h2"):
            if "árbitro" in (h2.get_text() or "").lower() and "asistentes" not in (h2.get_text() or "").lower():
                table = h2.find_next("table")
                if not table:
                    continue
                for tr in table.find_all("tr"):
                    cells = tr.find_all(["td", "th"])
                    if len(cells) < 6:
                        continue
                    # Nombre: enlace con /person/ (puede ser celda con texto o con imagen; si no hay texto, usar slug del URL)
                    nombre = None
                    idx_name = -1
                    for i, cell in enumerate(cells):
                        for a in cell.find_all("a", href=True):
                            href = a.get("href") or ""
                            if "/person/" not in href:
                                continue
                            txt = (a.get_text() or "").strip()
                            if txt:
                                nombre = txt
                            else:
                                parts = href.rstrip("/").split("/")
                                if parts:
                                    slug = parts[-1]
                                    nombre = slug.replace("-", " ").title() if slug else None
                            if nombre:
                                idx_name = i
                                break
                        if idx_name >= 0:
                            break
                    if not nombre or idx_name < 0:
                        continue
                    # Columnas: [#], (imagen?), Apellido, Nacionalidad, Juegos, Amarillo, Amarillo Rojo, Rojo
                    off = idx_name + 2  # país, luego juegos
                    if off + 4 > len(cells):
                        continue
                    juegos = _int_val(cells[off].get_text(), 1)
                    amarillo = _int_val(cells[off + 1].get_text(), 0)
                    amarillo_rojo = _int_val(cells[off + 2].get_text(), 0)
                    rojo = _int_val(cells[off + 3].get_text(), 0)
                    if juegos <= 0:
                        juegos = 1
                    total_tarjetas = amarillo + amarillo_rojo + rojo
                    tarjetas_promedio = round(total_tarjetas / juegos, 1) if juegos else 3.8
                    arbitros.append({
                        "nombre": nombre[:80],
                        "tarjetas_promedio": tarjetas_promedio,
                        "nota": f"{juegos} partidos (livefutbol)",
                    })
                break  # Solo primera tabla de árbitros
        _cache_arbitros = arbitros
        return arbitros
    except Exception as e:
        print(f"Error scraper livefutbol árbitros: {e}")
        return _cache_arbitros or []


def limpiar_cache_arbitros():
    global _cache_arbitros
    _cache_arbitros = None
