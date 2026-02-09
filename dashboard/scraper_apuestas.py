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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.apuestas-deportivas.es/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
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


# Cadenas que indican que la fila NO es un jugador (tablas de casas de apuestas, etc.)
_NO_ES_JUGADOR = frozenset([
    "1xbet", "bet365", "codere", "sportium", "william hill", "luckia", "versus",
    "gran madrid", "retabet", "bwin", "reseña", "unirse", "marathonbet", "kirolbet",
    "leovegas", "marca apuestas",
])


def _es_nombre_jugador(nombre):
    """Devuelve False si el nombre parece una casa de apuestas o no es un jugador."""
    if not nombre or len(nombre) < 3:
        return False
    n = nombre.lower().strip()
    if n in _NO_ES_JUGADOR:
        return False
    for no in _NO_ES_JUGADOR:
        if no in n or n in no:
            return False
    if n in ("jugador", "lesión", "lesion", "#", "sin especificar"):
        return False
    return True


def _celda_es_lesion_o_suspension(texto):
    """True si el texto de la columna parece tipo lesión o suspensión."""
    t = (texto or "").lower()
    if "suspensión" in t or "suspension" in t:
        return True
    palabras = (
        "lesión", "lesion", "malestar", "golpe", "rodilla", "tobillo", "muscular", "duda", "desconocido",
        "pie", "gemelo", "isquiotibial", "cruzado", "distensión", "espalda", "hombro", "cadera", "pierna",
        "conmoción", "cerebral", "cirugía", "roto", "rotura", "ligamento", "muslo",
    )
    if any(x in t for x in palabras):
        return True
    if "-" in t and len(t) < 60 and re.match(r"^[a-záéíóúñ\s\-]+$", t):
        return True  # partido tipo "Sunderland-Liverpool"
    return False


def _columnas_fila(celdas):
    """Devuelve (nombre, lesion, fecha, retorno). Si la primera celda está vacía (tabla con columna extra), desplaza índices."""
    if len(celdas) < 2:
        return None
    c0 = _extraer_texto(celdas[0])
    # Tabla con columna vacía al inicio: [vacío, Jugador, Lesión, Fecha, Rendimiento]
    if not c0 and len(celdas) >= 5:
        return (
            _extraer_texto(celdas[1]),
            _extraer_texto(celdas[2]),
            _extraer_texto(celdas[3]) if len(celdas) > 3 else "",
            _extraer_texto(celdas[4]) if len(celdas) > 4 else "",
        )
    return (
        c0,
        _extraer_texto(celdas[1]),
        _extraer_texto(celdas[2]) if len(celdas) > 2 else "",
        _extraer_texto(celdas[3]) if len(celdas) > 3 else "",
    )


def _procesar_tabla_equipo(tag, equipo, lesionados, sancionados):
    """Procesa todas las tablas que pertenecen a este h2 (hasta el siguiente h2)."""
    last_sancionado_player = None
    count_lesionados_equipo = 0

    for table in tag.find_all_next("table"):
        if table.find_previous(["h2", "h3", "h4"]) != tag:
            break
        for tr in table.find_all("tr"):
            celdas = tr.find_all(["td", "th"])
            col = _columnas_fila(celdas)
            if not col:
                continue
            c0, c1_raw, c2, c3 = col
            c1 = c1_raw.lower()

            # Cabecera de tabla de suspensiones
            if c0.lower() == "jugador" and ("suspensión" in c1 or "suspension" in c1):
                continue
            # Fila de suspensión: col1 = "Suspensión" o un partido (ej. "Sunderland-Liverpool")
            if "suspensión" in c1 or "suspension" in c1 or (c1 and "-" in c1 and len(c1) < 60):
                nombre = (c0 or last_sancionado_player or "Jugador")[:100]
                if c0:
                    last_sancionado_player = c0
                motivo = (c1 + " " + c2).strip()[:150] if (c1 or c2) else "Suspensión"
                if nombre and nombre.lower() != "jugador" and _es_nombre_jugador(nombre):
                    sancionados.append({"nombre": nombre, "equipo": equipo, "motivo": motivo})
            else:
                # Lesión: Jugador | Lesión | Fecha | Rendimiento
                if not c0 or c0.lower() in ("jugador", "lesión", "lesion") or not _es_nombre_jugador(c0):
                    continue
                if not _celda_es_lesion_o_suspension(c1_raw):
                    continue
                count_lesionados_equipo += 1
                estrellas = 3 if count_lesionados_equipo == 1 else (2 if count_lesionados_equipo <= 3 else 1)
                lesionados.append({
                    "nombre": c0[:100],
                    "equipo": equipo,
                    "tipo_lesion": c1_raw[:120],
                    "retorno_esperado": c3[:120],
                    "estrellas": estrellas,
                })


def _fila_es_lesion_o_sancion(celdas):
    """Comprueba si la fila parece de lesionados/sancionados (no cabecera ni otra tabla). Usa _columnas_fila por si la tabla tiene columna vacía."""
    col = _columnas_fila(celdas)
    if not col:
        return False
    c0, c1_raw, *_ = col
    c0, c1 = c0.lower(), (c1_raw or "").lower()
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
            # Comprobar que la tabla tiene al menos una fila válida (jugador + lesión/suspensión)
            tiene_valida = False
            for tr in table.find_all("tr"):
                celdas = tr.find_all(["td", "th"])
                col = _columnas_fila(celdas)
                if not col:
                    continue
                c0, c1, *_ = col
                if _es_nombre_jugador(c0) and _celda_es_lesion_o_suspension(c1):
                    tiene_valida = True
                    break
            if not tiene_valida:
                pos = table_end
                continue
            last_sancionado_player = None
            count_lesionados_equipo = 0
            for tr in table.find_all("tr"):
                celdas = tr.find_all(["td", "th"])
                col = _columnas_fila(celdas)
                if not col:
                    continue
                c0, c1_raw, c2, c3 = col
                c1 = c1_raw.lower()
                if c0.lower() == "jugador" and ("suspensión" in c1 or "suspension" in c1):
                    continue
                if "suspensión" in c1 or "suspension" in c1 or (c1 and "-" in c1 and len(c1) < 60):
                    nombre = (c0 or last_sancionado_player or "Jugador")[:100]
                    if c0:
                        last_sancionado_player = c0
                    motivo = (c1 + " " + c2).strip()[:150] if (c1 or c2) else "Suspensión"
                    if nombre and nombre.lower() != "jugador" and _es_nombre_jugador(nombre):
                        sancionados.append({"nombre": nombre, "equipo": equipo, "motivo": motivo})
                else:
                    if not c0 or c0.lower() in ("jugador", "lesión", "lesion") or not _es_nombre_jugador(c0):
                        continue
                    if not _celda_es_lesion_o_suspension(c1_raw):
                        continue
                    count_lesionados_equipo += 1
                    estrellas = 3 if count_lesionados_equipo == 1 else (2 if count_lesionados_equipo <= 3 else 1)
                    lesionados.append({
                        "nombre": c0[:100],
                        "equipo": equipo,
                        "tipo_lesion": c1_raw[:120],
                        "retorno_esperado": c3[:120],
                        "estrellas": estrellas,
                    })
            pos = table_end


def _procesar_tabla_equipo_fallback(soup, lesionados, sancionados):
    """Fallback: recorrer tablas y asociar con el h2/h3/h4 anterior; solo tablas que parecen de lesionados."""
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        # Exigir que haya al menos una fila que sea lesión/sanción (evitar tabla de casas de apuestas)
        if not any(len(tr.find_all(["td", "th"])) >= 2 and _fila_es_lesion_o_sancion(tr.find_all(["td", "th"])) for tr in rows):
            continue
        # Y que alguna fila tenga col1 tipo lesión/suspensión y nombre que parezca jugador
        tiene_fila_valida = False
        for tr in rows:
            celdas = tr.find_all(["td", "th"])
            col = _columnas_fila(celdas)
            if not col:
                continue
            c0, c1, *_ = col
            if _es_nombre_jugador(c0) and _celda_es_lesion_o_suspension(c1):
                tiene_fila_valida = True
                break
        if not tiene_fila_valida:
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
            col = _columnas_fila(celdas)
            if not col:
                continue
            c0, c1_raw, c2, c3 = col
            c1 = c1_raw.lower()
            if c0.lower() == "jugador" and ("suspensión" in c1 or "suspension" in c1):
                continue
            if "suspensión" in c1 or "suspension" in c1 or (c1 and "-" in c1 and len(c1) < 60):
                nombre = (c0 or last_sancionado_player or "Jugador")[:100]
                if c0:
                    last_sancionado_player = c0
                motivo = (c1 + " " + c2).strip()[:150] if (c1 or c2) else "Suspensión"
                if nombre and nombre.lower() != "jugador" and _es_nombre_jugador(nombre):
                    sancionados.append({"nombre": nombre, "equipo": equipo, "motivo": motivo})
            else:
                if not c0 or c0.lower() in ("jugador", "lesión", "lesion") or not _es_nombre_jugador(c0):
                    continue
                if not _celda_es_lesion_o_suspension(c1_raw):
                    continue
                count_lesionados_equipo += 1
                estrellas = 3 if count_lesionados_equipo == 1 else (2 if count_lesionados_equipo <= 3 else 1)
                lesionados.append({
                    "nombre": c0[:100],
                    "equipo": equipo,
                    "tipo_lesion": c1_raw[:120],
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
        # Usar UTF-8 con reemplazo para evitar fallos de codificación en entornos (ej. Render)
        if response.encoding is None or response.encoding.lower() in ("iso-8859-1", "latin-1"):
            response.encoding = "utf-8"
        html_str = response.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html_str, "html.parser")
        lesionados = []
        sancionados = []

        def _extraer_con_root(raiz):
            for tag in raiz.find_all(["h2", "h3", "h4"]):
                titulo = _extraer_texto(tag)
                equipo = _normalizar_equipo(titulo)
                if not equipo:
                    continue
                _procesar_tabla_equipo(tag, equipo, lesionados, sancionados)

        # Buscar contenido principal (WordPress: article, main, .entry-content) para no coger tablas del sidebar
        root = (
            soup.find("article")
            or soup.find("main")
            or soup.find(class_=re.compile(r"entry-content|post-content|content", re.I))
            or soup.find(id=re.compile(r"content|main", re.I))
            or soup
        )
        _extraer_con_root(root)

        # Si no se encontró nada, intentar con la página completa (por si el contenido no está en article/main)
        if not lesionados and not sancionados:
            _extraer_con_root(soup)

        # Fallback: tablas con título anterior
        if not lesionados and not sancionados:
            _procesar_tabla_equipo_fallback(root, lesionados, sancionados)
        if not lesionados and not sancionados:
            _procesar_tabla_equipo_fallback(soup, lesionados, sancionados)

        # Último recurso: parsear el HTML como texto (por si las tablas son divs o estructura rara)
        if not lesionados and not sancionados:
            _parsear_desde_texto(html_str, lesionados, sancionados)

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
