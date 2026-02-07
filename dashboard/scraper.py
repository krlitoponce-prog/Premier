import re
import requests
from bs4 import BeautifulSoup
from django.db import transaction

from .models import Lesionado
from .utils import obtener_datos_completos_premier

URL_LESIONADOS = "https://www.futbolfantasy.com/premier-league/lesionados"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Nombres de equipos que podemos encontrar en la web (pueden variar)
EQUIPOS_PREMIER = list(obtener_datos_completos_premier().keys())
# Variantes que la web puede usar (ej: "Bournemouth" -> "AFC Bournemouth")
EQUIPO_ALIAS = {
    "bournemouth": "AFC Bournemouth",
    "brighton": "Brighton & Hove Albion",
    "west ham": "West Ham United",
    "man city": "Manchester City",
    "manchester city": "Manchester City",
    "man united": "Manchester United",
    "manchester united": "Manchester United",
    "newcastle": "Newcastle United",
    "tottenham": "Tottenham Hotspur",
    "spurs": "Tottenham Hotspur",
    "wolves": "Wolverhampton Wanderers",
    "wolverhampton": "Wolverhampton Wanderers",
}


def _normalizar_equipo(texto):
    """Devuelve el nombre oficial del equipo si el texto coincide (o alias)."""
    if not texto:
        return None
    t = texto.strip()
    for nombre in EQUIPOS_PREMIER:
        if t.lower() == nombre.lower():
            return nombre
    return EQUIPO_ALIAS.get(t.lower())


def _equipo_desde_texto(texto):
    """Si el texto empieza por un nombre de equipo (o lo contiene al inicio), devuelve ese equipo."""
    if not texto:
        return None
    # Primera línea o primeros 60 caracteres (por si el bloque tiene "Arsenal\n0%\nJugador...")
    inicio = texto.strip()[:60].split("\n")[0].strip()
    eq = _normalizar_equipo(inicio)
    if eq:
        return eq
    for nombre in EQUIPOS_PREMIER:
        if texto.strip().lower().startswith(nombre.lower()):
            return nombre
    for alias, nombre in EQUIPO_ALIAS.items():
        if texto.strip().lower().startswith(alias):
            return nombre
    return None


def _encontrar_equipo_en_ancestros(elemento):
    """Sube por los padres; la web usa div.row.block-new con el nombre del equipo como primer texto."""
    current = elemento
    for _ in range(25):
        if current is None:
            break
        direct = (current.get_text() or "").strip()
        # Bloque tipo "Arsenal\n0%\nJugador..." -> el inicio es el equipo
        eq = _equipo_desde_texto(direct)
        if eq:
            return eq
        # Cabeceras h2/h3/h4 con solo el nombre del equipo
        for tag in current.find_all(["h2", "h3", "h4"], limit=3):
            txt = (tag.get_text() or "").strip()
            if len(txt) < 50 and _normalizar_equipo(txt):
                return _normalizar_equipo(txt)
        # Hermanos anteriores
        sib = current.find_previous_sibling() if hasattr(current, "find_previous_sibling") else None
        while sib:
            txt = (sib.get_text() or "").strip()
            if sib.name in ("h2", "h3", "h4") and len(txt) < 50 and _normalizar_equipo(txt):
                return _normalizar_equipo(txt)
            if _equipo_desde_texto(txt):
                return _equipo_desde_texto(txt)
            sib = sib.find_previous_sibling() if hasattr(sib, "find_previous_sibling") else None
        current = getattr(current, "parent", None)
    return None


def ejecutar_scraper_premier():
    """
    Scrape lesionados desde futbolfantasy.com.
    Acepta dos estructuras: div.equipo-lista (antigua) o bloques con h2/h3 de equipo + enlaces /jugadores/.
    """
    try:
        response = requests.get(URL_LESIONADOS, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return False
        soup = BeautifulSoup(response.content, "html.parser")
        creados = []

        # 1) Estructura antigua: div.equipo-lista con h2 y div.nombre
        articulos = soup.find_all("div", class_="equipo-lista")
        if articulos:
            with transaction.atomic():
                Lesionado.objects.all().delete()
                for art in articulos:
                    h2 = art.find("h2")
                    if not h2:
                        continue
                    nombre_eq = _normalizar_equipo(h2.get_text()) or h2.get_text().strip()
                    jugadores = art.find_all("div", class_="nombre")
                    for i, j in enumerate(jugadores):
                        estrellas = 3 if i == 0 else (2 if i <= 2 else 1)
                        nombre_jug = (j.get_text() or "").strip()
                        if nombre_jug:
                            Lesionado.objects.create(
                                nombre=nombre_jug, equipo=nombre_eq, posicion="NA", estrellas=estrellas
                            )
                return True

        # 2) Estructura alternativa: buscar todos los enlaces a /jugadores/ y asignar equipo por ancestro
        def _extraer_tipo_y_retorno(elemento):
            """Del bloque del jugador (div.elemento.lesionado) extrae tipo de lesión y retorno esperado."""
            bloque = elemento
            for _ in range(5):
                if bloque is None:
                    break
                if "lesionado" in (getattr(bloque, "get", lambda x: None)("class") or []):
                    texto = (bloque.get_text() or "").replace("\n", " ").strip()
                    tipo = ""
                    retorno = ""
                    # Tipo: "Lesión de X", "Molestias en X", "Esguince", etc.
                    m = re.search(r"(Lesión\s+de\s+\w+|Lesión\s+en\s+[^\.]+|Molestias\s+[^\.]+|Esguince[^\.]*|Cirugía[^\.]*|Contusión[^\.]*|Enfermedad)", texto, re.I)
                    if m:
                        tipo = m.group(1).strip()[:100]
                    # Retorno: "Baja confirmada", "Duda", "Desde DD/MM", "jornada XX"
                    if "Baja confirmada" in texto or "baja confirmada" in texto:
                        retorno = "Baja confirmada"
                    elif "Duda" in texto or "duda" in texto:
                        retorno = "Duda"
                    if not retorno and re.search(r"Desde\s+\d{2}/\d{2}", texto):
                        m2 = re.search(r"(Desde\s+\d{2}/\d{2}\s*\(\d+\s*días\)?)", texto)
                        if m2:
                            retorno = m2.group(1).strip()[:80]
                    return tipo or "", retorno or ""
                bloque = getattr(bloque, "parent", None)
            return "", ""

        enlaces = soup.find_all("a", href=re.compile(r"/jugadores/"))
        for a in enlaces:
            nombre_jug = (a.get_text() or "").strip()
            if not nombre_jug or len(nombre_jug) > 60:
                continue
            equipo = _encontrar_equipo_en_ancestros(a)
            if equipo:
                tipo_lesion, retorno_esperado = _extraer_tipo_y_retorno(a)
                creados.append({
                    "nombre": nombre_jug, "equipo": equipo,
                    "tipo_lesion": tipo_lesion, "retorno_esperado": retorno_esperado,
                })

        if not creados:
            # 3) Último recurso: buscar por cabeceras h2/h3 con nombre de equipo y siguientes hermanos
            for tag in soup.find_all(["h2", "h3", "h4"]):
                nombre_eq = _normalizar_equipo(tag.get_text())
                if not nombre_eq:
                    continue
                # Recoger enlaces /jugadores/ en hermanos siguientes hasta la siguiente cabecera
                siguiente = tag.find_next_sibling()
                while siguiente and siguiente.name not in ("h2", "h3", "h4"):
                    for link in siguiente.find_all("a", href=re.compile(r"/jugadores/")):
                        nombre_jug = (link.get_text() or "").strip()
                        if nombre_jug and len(nombre_jug) < 60:
                            creados.append({"nombre": nombre_jug, "equipo": nombre_eq, "tipo_lesion": "", "retorno_esperado": ""})
                    siguiente = siguiente.find_next_sibling()

        if creados:
            # Quitar duplicados (mismo equipo + nombre)
            vistos = set()
            unicos = []
            for item in creados:
                k = (item["equipo"], item["nombre"])
                if k not in vistos:
                    vistos.add(k)
                    unicos.append(item)
            creados = unicos
            # Agrupar por equipo para asignar estrellas (primero 3⭐, dos siguientes 2⭐, resto 1⭐)
            from collections import OrderedDict
            por_equipo = OrderedDict()
            for item in creados:
                eq = item["equipo"]
                if eq not in por_equipo:
                    por_equipo[eq] = []
                por_equipo[eq].append({"nombre": item["nombre"], "tipo_lesion": item.get("tipo_lesion", ""), "retorno_esperado": item.get("retorno_esperado", "")})
            with transaction.atomic():
                Lesionado.objects.all().delete()
                for equipo, lista in por_equipo.items():
                    for i, item in enumerate(lista):
                        estrellas = 3 if i == 0 else (2 if i <= 2 else 1)
                        nom = item if isinstance(item, str) else item.get("nombre", "")
                        tipo = item.get("tipo_lesion", "") if isinstance(item, dict) else ""
                        ret = item.get("retorno_esperado", "") if isinstance(item, dict) else ""
                        Lesionado.objects.create(
                            nombre=nom, equipo=equipo, posicion="NA", estrellas=estrellas,
                            tipo_lesion=tipo, retorno_esperado=ret,
                        )
            return True

        # Si no encontramos nada, no borrar los datos existentes
        return False
    except Exception as e:
        print(f"Error scraper lesionados: {e}")
        return False


URL_SANCIONADOS = "https://www.futbolfantasy.com/premier-league/sancionados"


def ejecutar_scraper_sancionados():
    """
    Scrape sancionados desde futbolfantasy.com/premier-league/sancionados.
    Misma lógica de equipo por ancestro que lesionados.
    """
    from .models import Sancionado
    try:
        response = requests.get(URL_SANCIONADOS, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return False
        soup = BeautifulSoup(response.content, "html.parser")
        creados = []
        enlaces = soup.find_all("a", href=re.compile(r"/jugadores/"))
        for a in enlaces:
            nombre_jug = (a.get_text() or "").strip()
            if not nombre_jug or len(nombre_jug) > 60:
                continue
            equipo = _encontrar_equipo_en_ancestros(a)
            if equipo:
                motivo = ""
                bloque = a
                for _ in range(6):
                    if bloque is None:
                        break
                    cls = getattr(bloque, "get", lambda x: None)("class") or []
                    if "sancionado" in " ".join(cls).lower() or "elemento" in " ".join(cls).lower():
                        texto = (bloque.get_text() or "").replace("\n", " ").strip()
                        if "tarjeta" in texto.lower() or "expul" in texto.lower() or "amarilla" in texto.lower():
                            motivo = texto[:120].strip()
                        break
                    bloque = getattr(bloque, "parent", None)
                creados.append({"nombre": nombre_jug, "equipo": equipo, "motivo": motivo})
        if not creados:
            return False
        vistos = set()
        unicos = []
        for item in creados:
            k = (item["equipo"], item["nombre"])
            if k not in vistos:
                vistos.add(k)
                unicos.append(item)
        with transaction.atomic():
            Sancionado.objects.all().delete()
            for item in unicos:
                Sancionado.objects.create(
                    nombre=item["nombre"], equipo=item["equipo"],
                    motivo=item.get("motivo", ""), jornada="",
                )
        return True
    except Exception as e:
        print(f"Error scraper sancionados: {e}")
        return False
