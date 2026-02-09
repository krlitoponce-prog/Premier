"""
Scraper de lesionados y sancionados desde apuestas-deportivas.es (Premier League).
Fuente: https://www.apuestas-deportivas.es/premier-league-inglaterra-jugadores-lesionados-y-sancionados/
"""
import re
import requests
from bs4 import BeautifulSoup
from django.db import transaction

from .models import Lesionado, Sancionado

URL = "https://www.apuestas-deportivas.es/premier-league-inglaterra-jugadores-lesionados-y-sancionados/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.apuestas-deportivas.es/",
}

# Nombre en la web -> nombre en nuestra app
EQUIPO_APUESTAS_A_OFICIAL = {
    "arsenal": "Arsenal",
    "aston villa": "Aston Villa",
    "bournemouth": "AFC Bournemouth",
    "brentford": "Brentford",
    "brighton": "Brighton & Hove Albion",
    "burnley": "Burnley",
    "chelsea": "Chelsea",
    "crystal palace": "Crystal Palace",
    "everton": "Everton",
    "fulham": "Fulham",
    "leeds": "Leeds United",
    "liverpool": "Liverpool",
    "manchester city": "Manchester City",
    "man city": "Manchester City",
    "manchester united": "Manchester United",
    "man united": "Manchester United",
    "newcastle united": "Newcastle United",
    "newcastle": "Newcastle United",
    "nottingham forest": "Nottingham Forest",
    "sunderland": "Sunderland",
    "tottenham": "Tottenham Hotspur",
    "tottenham hotspur": "Tottenham Hotspur",
    "west ham": "West Ham United",
    "west ham united": "West Ham United",
    "wolves": "Wolverhampton Wanderers",
    "wolverhampton wanderers": "Wolverhampton Wanderers",
    "wolverhampton": "Wolverhampton Wanderers",
}


def _normalizar_equipo(texto):
    if not texto:
        return None
    # Quitar números, entidades HTML y caracteres raros
    t = re.sub(r"^#+\s*", "", texto)
    t = re.sub(r"\s+", " ", t).strip().lower()
    t = t.replace("\u8211", "").replace("\u2013", "").strip()  # guiones unicode
    if not t:
        return None
    # Coincidencia exacta
    if t in EQUIPO_APUESTAS_A_OFICIAL:
        return EQUIPO_APUESTAS_A_OFICIAL[t]
    # Coincidencia parcial: si el título contiene el nombre del equipo
    for key, oficial in EQUIPO_APUESTAS_A_OFICIAL.items():
        if key in t or t in key:
            return oficial
    return None


def _extraer_texto(el):
    if hasattr(el, "get_text"):
        return (el.get_text() or "").strip()
    return str(el).strip()


def _procesar_tabla_equipo(tag, equipo, lesionados, sancionados):
    """Procesa todas las tablas que pertenecen a este h2 (hasta el siguiente h2)."""
    last_sancionado_player = None
    count_lesionados_equipo = 0

    for table in tag.find_all_next("table"):
        if table.find_previous("h2") != tag:
            break
        for tr in table.find_all("tr"):
            celdas = tr.find_all(["td", "th"])
            if len(celdas) < 2:
                continue
            c0 = _extraer_texto(celdas[0])
            c1 = _extraer_texto(celdas[1]).lower()
            c2 = _extraer_texto(celdas[2]) if len(celdas) > 2 else ""
            c3 = _extraer_texto(celdas[3]) if len(celdas) > 3 else ""

            # Cabecera de tabla de suspensiones
            if c0.lower() == "jugador" and ("suspensión" in c1 or "suspension" in c1):
                continue
            # Fila de suspensión: col1 = "Suspensión" o un partido (ej. "Sunderland-Liverpool")
            if "suspensión" in c1 or "suspension" in c1 or (c1 and "-" in c1 and len(c1) < 60):
                nombre = (c0 or last_sancionado_player or "Jugador")[:100]
                if c0:
                    last_sancionado_player = c0
                motivo = (c1 + " " + c2).strip()[:150] if (c1 or c2) else "Suspensión"
                if nombre and nombre.lower() != "jugador":
                    sancionados.append({"nombre": nombre, "equipo": equipo, "motivo": motivo})
            else:
                # Lesión: Jugador | Lesión | Fecha | Rendimiento
                if not c0 or c0.lower() in ("jugador", "lesión", "lesion"):
                    continue
                count_lesionados_equipo += 1
                estrellas = 3 if count_lesionados_equipo == 1 else (2 if count_lesionados_equipo <= 3 else 1)
                lesionados.append({
                    "nombre": c0[:100],
                    "equipo": equipo,
                    "tipo_lesion": _extraer_texto(celdas[1])[:120],
                    "retorno_esperado": c3[:120],
                    "estrellas": estrellas,
                })


def _fila_es_lesion_o_sancion(celdas):
    """Comprueba si la fila parece de lesionados/sancionados (no cabecera ni otra tabla)."""
    if len(celdas) < 2:
        return False
    c0 = _extraer_texto(celdas[0]).lower()
    c1 = _extraer_texto(celdas[1]).lower()
    if c0 in ("jugador", "lesión", "lesion", "#") and not c1:
        return False
    if "suspensión" in c1 or "suspension" in c1 or ("-" in c1 and len(c1) < 60):
        return True
    if any(x in c1 for x in ("lesión", "lesion", "malestar", "golpe", "rodilla", "tobillo", "muscular", "duda", "desconocido")):
        return True
    return False


def _parsear_desde_texto(html_text, lesionados, sancionados):
    """Último recurso: en HTML crudo, buscar h2/h3 con nombre de equipo y la siguiente tabla."""
    # Posiciones de cada <h2> o <h3> con su equipo normalizado
    titulos = []
    for m in re.finditer(r"<h[234][^>]*>([^<]+)</h[234]>", html_text, re.I):
        titulo_limpio = re.sub(r"\s+", " ", m.group(1).strip())
        equipo = _normalizar_equipo(titulo_limpio)
        if equipo:
            titulos.append((m.start(), m.end(), equipo))
    if not titulos:
        return
    # Para cada título, tomar la porción de HTML hasta el siguiente título (o fin) y extraer tablas
    for i, (t_start, t_end, equipo) in enumerate(titulos):
        fin_bloque = titulos[i + 1][0] if i + 1 < len(titulos) else len(html_text)
        bloque = html_text[t_end:fin_bloque]
        # Tablas simples (sin anidar): <table ...> ... </table>
        pos = 0
        while True:
            table_start = bloque.find("<table", pos)
            if table_start == -1:
                break
            table_end = bloque.find("</table>", table_start)
            if table_end == -1:
                break
            table_end += len("</table>")
            fragmento = bloque[table_start:table_end]
            sub = BeautifulSoup(fragmento, "html.parser")
            table = sub.find("table")
            if not table:
                pos = table_end
                continue
            last_sancionado_player = None
            count_lesionados_equipo = 0
            for tr in table.find_all("tr"):
                celdas = tr.find_all(["td", "th"])
                if len(celdas) < 2:
                    continue
                c0 = _extraer_texto(celdas[0])
                c1 = _extraer_texto(celdas[1]).lower()
                c2 = _extraer_texto(celdas[2]) if len(celdas) > 2 else ""
                c3 = _extraer_texto(celdas[3]) if len(celdas) > 3 else ""
                if c0.lower() == "jugador" and ("suspensión" in c1 or "suspension" in c1):
                    continue
                if "suspensión" in c1 or "suspension" in c1 or (c1 and "-" in c1 and len(c1) < 60):
                    nombre = (c0 or last_sancionado_player or "Jugador")[:100]
                    if c0:
                        last_sancionado_player = c0
                    motivo = (c1 + " " + c2).strip()[:150] if (c1 or c2) else "Suspensión"
                    if nombre and nombre.lower() != "jugador":
                        sancionados.append({"nombre": nombre, "equipo": equipo, "motivo": motivo})
                else:
                    if not c0 or c0.lower() in ("jugador", "lesión", "lesion"):
                        continue
                    count_lesionados_equipo += 1
                    estrellas = 3 if count_lesionados_equipo == 1 else (2 if count_lesionados_equipo <= 3 else 1)
                    lesionados.append({
                        "nombre": c0[:100],
                        "equipo": equipo,
                        "tipo_lesion": _extraer_texto(celdas[1])[:120],
                        "retorno_esperado": c3[:120],
                        "estrellas": estrellas,
                    })
            pos = table_end


def _procesar_tabla_equipo_fallback(soup, lesionados, sancionados):
    """Fallback: recorrer tablas y asociar con el h2/h3/h4 anterior; solo tablas que parecen de lesionados."""
    for table in soup.find_all("table"):
        # Comprobar que la tabla tiene al menos una fila de datos
        rows = table.find_all("tr")
        if not any(len(tr.find_all(["td", "th"])) >= 2 and _fila_es_lesion_o_sancion(tr.find_all(["td", "th"])) for tr in rows):
            continue
        prev = table.find_previous(["h2", "h3", "h4"])
        if not prev:
            continue
        titulo = _extraer_texto(prev)
        equipo = _normalizar_equipo(titulo)
        if not equipo:
            continue
        last_sancionado_player = None
        count_lesionados_equipo = 0
        for tr in table.find_all("tr"):
            celdas = tr.find_all(["td", "th"])
            if len(celdas) < 2:
                continue
            c0 = _extraer_texto(celdas[0])
            c1 = _extraer_texto(celdas[1]).lower()
            c2 = _extraer_texto(celdas[2]) if len(celdas) > 2 else ""
            c3 = _extraer_texto(celdas[3]) if len(celdas) > 3 else ""
            if c0.lower() == "jugador" and ("suspensión" in c1 or "suspension" in c1):
                continue
            if "suspensión" in c1 or "suspension" in c1 or (c1 and "-" in c1 and len(c1) < 60):
                nombre = (c0 or last_sancionado_player or "Jugador")[:100]
                if c0:
                    last_sancionado_player = c0
                motivo = (c1 + " " + c2).strip()[:150] if (c1 or c2) else "Suspensión"
                if nombre and nombre.lower() != "jugador":
                    sancionados.append({"nombre": nombre, "equipo": equipo, "motivo": motivo})
            else:
                if not c0 or c0.lower() in ("jugador", "lesión", "lesion"):
                    continue
                count_lesionados_equipo += 1
                estrellas = 3 if count_lesionados_equipo == 1 else (2 if count_lesionados_equipo <= 3 else 1)
                lesionados.append({
                    "nombre": c0[:100],
                    "equipo": equipo,
                    "tipo_lesion": _extraer_texto(celdas[1])[:120],
                    "retorno_esperado": c3[:120],
                    "estrellas": estrellas,
                })


def ejecutar_scraper_apuestas_lesionados_sancionados():
    """
    Scrape lesionados y sancionados desde apuestas-deportivas.es en una sola pasada.
    Busca secciones por equipo (h2/h3/h4) y tablas siguientes; filas Suspensión -> Sancionado, resto -> Lesionado.
    """
    try:
        response = requests.get(URL, headers=HEADERS, timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        lesionados = []
        sancionados = []

        # Buscar contenido principal (WordPress: article, main, #content) para no coger tablas del sidebar
        root = soup.find("article") or soup.find("main") or soup.find(id=re.compile(r"content|main", re.I)) or soup
        for tag in root.find_all(["h2", "h3", "h4"]):
            titulo = _extraer_texto(tag)
            equipo = _normalizar_equipo(titulo)
            if not equipo:
                continue
            _procesar_tabla_equipo(tag, equipo, lesionados, sancionados)

        # Si no se encontró nada, intentar fallback: tablas con título anterior
        if not lesionados and not sancionados:
            _procesar_tabla_equipo_fallback(root, lesionados, sancionados)

        # Último recurso: parsear el HTML como texto (por si las tablas son divs o estructura rara)
        if not lesionados and not sancionados:
            _parsear_desde_texto(response.text, lesionados, sancionados)

        with transaction.atomic():
            Lesionado.objects.all().delete()
            for item in lesionados:
                Lesionado.objects.create(
                    nombre=item["nombre"],
                    equipo=item["equipo"],
                    posicion="NA",
                    estrellas=item.get("estrellas", 1),
                    tipo_lesion=item.get("tipo_lesion", ""),
                    retorno_esperado=item.get("retorno_esperado", ""),
                )
            Sancionado.objects.all().delete()
            for item in sancionados:
                Sancionado.objects.create(
                    nombre=item["nombre"],
                    equipo=item["equipo"],
                    motivo=item.get("motivo", "Suspensión"),
                    jornada="",
                )
        return True, len(lesionados), len(sancionados)
    except Exception as e:
        print(f"Error scraper apuestas-deportivas: {e}")
        return False, 0, 0
