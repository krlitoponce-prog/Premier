import math

# 20 equipos Premier League (temporada 2025/26) con estadísticas base (goles avg, corners, tarjetas)
_EQUIPOS_PREMIER_STATS = {
    "AFC Bournemouth": {"g": 1.4, "c": 5, "t": 2.8},
    "Arsenal": {"g": 2.1, "c": 6, "t": 2.5},
    "Aston Villa": {"g": 1.8, "c": 5, "t": 2.2},
    "Brentford": {"g": 1.5, "c": 5, "t": 2.4},
    "Brighton & Hove Albion": {"g": 1.7, "c": 6, "t": 2.1},
    "Burnley": {"g": 1.3, "c": 5, "t": 2.6},
    "Chelsea": {"g": 1.9, "c": 6, "t": 2.3},
    "Crystal Palace": {"g": 1.3, "c": 5, "t": 2.5},
    "Everton": {"g": 1.2, "c": 5, "t": 2.6},
    "Fulham": {"g": 1.5, "c": 5, "t": 2.2},
    "Leeds United": {"g": 1.5, "c": 5, "t": 2.4},
    "Liverpool": {"g": 2.3, "c": 7, "t": 2.0},
    "Manchester City": {"g": 2.4, "c": 7, "t": 1.8},
    "Manchester United": {"g": 1.7, "c": 6, "t": 2.4},
    "Newcastle United": {"g": 1.8, "c": 6, "t": 2.2},
    "Nottingham Forest": {"g": 1.3, "c": 5, "t": 2.7},
    "Sunderland": {"g": 1.4, "c": 5, "t": 2.5},
    "Tottenham Hotspur": {"g": 2.0, "c": 6, "t": 2.1},
    "West Ham United": {"g": 1.5, "c": 5, "t": 2.4},
    "Wolverhampton Wanderers": {"g": 1.4, "c": 5, "t": 2.3},
}

# Árbitros Premier: tarjetas por partido (promedio). Incluye Samuel Barrott y otros actuales.
_ARBITROS_PREMIER = [
    {"nombre": "Michael Oliver", "tarjetas_promedio": 4.2, "nota": "Estilo controlador"},
    {"nombre": "Anthony Taylor", "tarjetas_promedio": 3.8, "nota": "Medio"},
    {"nombre": "Paul Tierney", "tarjetas_promedio": 3.5, "nota": "Menos tarjetas"},
    {"nombre": "Stuart Attwell", "tarjetas_promedio": 4.5, "nota": "Tarjetero"},
    {"nombre": "Simon Hooper", "tarjetas_promedio": 3.2, "nota": "Permisivo"},
    {"nombre": "Chris Kavanagh", "tarjetas_promedio": 4.0, "nota": "Medio"},
    {"nombre": "Darren England", "tarjetas_promedio": 3.9, "nota": "Medio"},
    {"nombre": "Andy Madley", "tarjetas_promedio": 4.6, "nota": "Tarjetero"},
    {"nombre": "Robert Jones", "tarjetas_promedio": 3.4, "nota": "Menos tarjetas"},
    {"nombre": "David Coote", "tarjetas_promedio": 4.1, "nota": "Estilo controlador"},
    {"nombre": "Samuel Barrott", "tarjetas_promedio": 3.6, "nota": "Medio"},
    {"nombre": "Jarred Gillett", "tarjetas_promedio": 3.7, "nota": "Medio"},
    {"nombre": "Thomas Bramall", "tarjetas_promedio": 3.5, "nota": "Medio"},
]

# Asignación oficial árbitro por partido. Añadir aquí cuando tengas la fuente (ej. Premier League).
# Clave: (local, visitante) exactamente como en el selector de equipos.
_ARBITRO_POR_PARTIDO = {
    ("Arsenal", "Sunderland"): "Samuel Barrott",
    ("Sunderland", "Arsenal"): "Samuel Barrott",
    ("Brighton & Hove Albion", "Crystal Palace"): "Thomas Bramall",
    ("Crystal Palace", "Brighton & Hove Albion"): "Thomas Bramall",
}

# Plantilla típica por equipo para calcular % de bajas (jugadores que cuentan)
_JUGADORES_POR_EQUIPO = 25

# Profundidad de plantilla: equipos con buenos recambios sufren menos la penalización por bajas.
# Valor 0 = penalización completa; 0.5 = solo se aplica el 50% de la penalización; 0.6 = 40% de la penalización.
# Así equipos "grandes" no bajan tanto aunque tengan lesionados/sancionados.
_PROFUNDIDAD_EQUIPO = {
    "Manchester City": 0.60,
    "Liverpool": 0.55,
    "Chelsea": 0.55,
    "Arsenal": 0.50,
    "Tottenham Hotspur": 0.50,
    "Manchester United": 0.45,
    "Newcastle United": 0.45,
    "Aston Villa": 0.40,
    "Brighton & Hove Albion": 0.35,
    "West Ham United": 0.25,
    "Fulham": 0.20,
    "Wolverhampton Wanderers": 0.20,
    "Brentford": 0.15,
    "Crystal Palace": 0.15,
    "Everton": 0.10,
    "Leeds United": 0.10,
    "Nottingham Forest": 0.10,
    "AFC Bournemouth": 0.05,
    "Burnley": 0.05,
    "Sunderland": 0.05,
}
# Mínimo de goles esperados por equipo (evita 0-0 artificial por muchas bajas)
_GOLES_MINIMOS_POR_EQUIPO = 0.55
# Penalización máxima por equipo (por muchas bajas no restamos más de esto)
_PENALIZACION_MAXIMA_GOLES = 1.2

# Tipo de cancha por equipo: altura (ventaja local, visitante rinde algo menos) vs llano.
# metros: altitud aprox. del estadio (m s.n.m.) para referencia.
# En Inglaterra los más altos suelen ser Burnley, Leeds, Wolves, Newcastle; el resto llano o bajo.
_ESTADIO_POR_EQUIPO = {
    "AFC Bournemouth": {"tipo": "llano", "metros": 5, "nota": "Costa"},
    "Arsenal": {"tipo": "llano", "metros": 40, "nota": ""},
    "Aston Villa": {"tipo": "llano", "metros": 120, "nota": "Villa Park, Birmingham"},
    "Brentford": {"tipo": "llano", "metros": 8, "nota": ""},
    "Brighton & Hove Albion": {"tipo": "llano", "metros": 5, "nota": "Costa"},
    "Burnley": {"tipo": "altura", "metros": 130, "nota": "Turf Moor, uno de los más altos"},
    "Chelsea": {"tipo": "llano", "metros": 15, "nota": ""},
    "Crystal Palace": {"tipo": "llano", "metros": 65, "nota": ""},
    "Everton": {"tipo": "llano", "metros": 25, "nota": "Liverpool"},
    "Fulham": {"tipo": "llano", "metros": 10, "nota": ""},
    "Leeds United": {"tipo": "altura", "metros": 70, "nota": "Elland Road"},
    "Liverpool": {"tipo": "llano", "metros": 20, "nota": ""},
    "Manchester City": {"tipo": "llano", "metros": 45, "nota": ""},
    "Manchester United": {"tipo": "llano", "metros": 45, "nota": ""},
    "Newcastle United": {"tipo": "altura", "metros": 80, "nota": "St James' Park"},
    "Nottingham Forest": {"tipo": "llano", "metros": 60, "nota": ""},
    "Sunderland": {"tipo": "llano", "metros": 30, "nota": ""},
    "Tottenham Hotspur": {"tipo": "llano", "metros": 35, "nota": ""},
    "West Ham United": {"tipo": "llano", "metros": 5, "nota": ""},
    "Wolverhampton Wanderers": {"tipo": "altura", "metros": 120, "nota": "Molineux"},
}
# Cuando el local juega en altura, el visitante suele rendir algo menos (factor sobre g_a)
_FACTOR_VISITANTE_EN_ALTURA = 0.94


def obtener_datos_completos_premier():
    """Devuelve un diccionario equipo -> {g, c, t} para usar en pronósticos."""
    return _EQUIPOS_PREMIER_STATS.copy()


def obtener_estadios_premier():
    """Devuelve equipo -> {tipo, metros, nota} para tipo de cancha (altura/llano)."""
    return _ESTADIO_POR_EQUIPO.copy()


def get_arbitros_fallback():
    """Lista estática de árbitros por si falla la carga externa. Para uso en vistas."""
    return list(_ARBITROS_PREMIER)


def obtener_lista_arbitros_premier():
    """Lista de árbitros para el selector: desde livefutbol.com o fallback a lista estática. Nunca devuelve lista vacía."""
    try:
        from .scraper_livefutbol import obtener_arbitros_livefutbol
        lista = obtener_arbitros_livefutbol()
        if lista:
            return lista
    except Exception:
        pass
    return get_arbitros_fallback()


def _elegir_arbitro_para_partido(home, away):
    """Elige árbitro: 1) DB (scraper), 2) lista estática, 3) hash. Devuelve (arbitro_dict, es_oficial)."""
    from .models import DesignacionArbitro
    key_local, key_visitante = home.strip(), away.strip()
    designacion = (
        DesignacionArbitro.objects.filter(equipo_local=key_local, equipo_visitante=key_visitante).first()
        or DesignacionArbitro.objects.filter(equipo_local=key_visitante, equipo_visitante=key_local).first()
    )
    if designacion:
        nombre = designacion.arbitro_nombre
        for a in _ARBITROS_PREMIER:
            if a["nombre"] == nombre:
                return a, True
        return {"nombre": nombre, "tarjetas_promedio": 3.8, "nota": "Actualizado"}, True
    nombre_oficial = _ARBITRO_POR_PARTIDO.get((key_local, key_visitante)) or _ARBITRO_POR_PARTIDO.get((key_visitante, key_local))
    if nombre_oficial:
        for a in _ARBITROS_PREMIER:
            if a["nombre"] == nombre_oficial:
                return a, True
    idx = hash((home, away)) % len(_ARBITROS_PREMIER)
    return _ARBITROS_PREMIER[idx], False


def _buscar_arbitro_por_nombre(nombre):
    """Busca un árbitro por nombre en la lista de livefutbol o estática."""
    if not nombre:
        return None
    nombre = nombre.strip()
    lista = obtener_lista_arbitros_premier()
    for a in lista:
        if (a.get("nombre") or "").strip() == nombre:
            return a
    return {"nombre": nombre, "tarjetas_promedio": 3.8, "nota": "Selección manual"}


def generar_pronostico_pro(home, away, arbitro_manual=None):
    if not home or not away:
        return {}

    from .models import Lesionado, Sancionado

    db = obtener_datos_completos_premier()
    stats_h = db.get(home, {"g": 1.5, "c": 5, "t": 2})
    stats_a = db.get(away, {"g": 1.5, "c": 5, "t": 2})

    bajas_h = Lesionado.objects.filter(equipo__icontains=home.split()[0])
    bajas_a = Lesionado.objects.filter(equipo__icontains=away.split()[0])
    sanciones_h = Sancionado.objects.filter(equipo__iexact=home)
    sanciones_a = Sancionado.objects.filter(equipo__iexact=away)

    n_h, n_a = bajas_h.count(), bajas_a.count()
    pct_bajas_h = round((n_h / _JUGADORES_POR_EQUIPO) * 100) if n_h else 0
    pct_bajas_a = round((n_a / _JUGADORES_POR_EQUIPO) * 100) if n_a else 0

    # Peso por estrella (lesionados): 3⭐ resta más al equipo que 1⭐
    peso_bajas_h = sum(0.35 if b.estrellas == 3 else (0.25 if b.estrellas == 2 else 0.15) for b in bajas_h)
    peso_bajas_a = sum(0.35 if b.estrellas == 3 else (0.25 if b.estrellas == 2 else 0.15) for b in bajas_a)
    # Sancionados: cada uno resta ~0.2 goles
    peso_sanciones_h = sanciones_h.count() * 0.2
    peso_sanciones_a = sanciones_a.count() * 0.2

    # Penalización total en bruto (con tope para no castigar en exceso)
    penal_raw_h = min(peso_bajas_h + peso_sanciones_h, _PENALIZACION_MAXIMA_GOLES)
    penal_raw_a = min(peso_bajas_a + peso_sanciones_a, _PENALIZACION_MAXIMA_GOLES)
    # Equipos con profundidad (buenos recambios) sufren menos: se aplica (1 - profundidad) de la penalización
    factor_h = 1 - _PROFUNDIDAD_EQUIPO.get(home, 0)
    factor_a = 1 - _PROFUNDIDAD_EQUIPO.get(away, 0)
    penal_efectiva_h = penal_raw_h * factor_h
    penal_efectiva_a = penal_raw_a * factor_a

    g_h = stats_h['g'] - penal_efectiva_h
    g_a = stats_a['g'] - penal_efectiva_a
    # Suelo mínimo: ningún equipo baja de este valor por muchas bajas (refleja recambios y calidad)
    g_h = max(_GOLES_MINIMOS_POR_EQUIPO, g_h)
    g_a = max(_GOLES_MINIMOS_POR_EQUIPO, g_a)

    # Árbitro: si el usuario eligió uno manualmente, usarlo; si no, elegir automático
    if arbitro_manual:
        arbitro = _buscar_arbitro_por_nombre(arbitro_manual)
        arbitro_oficial = True  # usuario lo eligió
    else:
        arbitro, arbitro_oficial = _elegir_arbitro_para_partido(home, away)
    tarjetas_base = stats_h['t'] + stats_a['t']
    factor_arbitro = arbitro["tarjetas_promedio"] / 4.0
    tarjetas_ajustadas = round(tarjetas_base * factor_arbitro, 1)

    # Calendario API 2025/26: fecha del partido y partido entre semana
    from .calendar_api import (
        get_fixture_for_match,
        had_midweek_match,
        format_fixture_date,
        _parse_date_utc,
        _fetch_calendar,
    )
    fixture = get_fixture_for_match(home, away)
    fecha_partido = None
    partido_entre_semana_local = False
    partido_entre_semana_visitante = False
    if fixture:
        fecha_partido = format_fixture_date(_parse_date_utc(fixture.get("DateUtc")))
        dt = _parse_date_utc(fixture.get("DateUtc"))
        all_matches = _fetch_calendar()
        partido_entre_semana_local = had_midweek_match(home, dt, all_matches)
        partido_entre_semana_visitante = had_midweek_match(away, dt, all_matches)
        # Pequeña penalización en goles si jugaron entre semana (cansancio)
        if partido_entre_semana_local:
            g_h = max(0, g_h - 0.2)
        if partido_entre_semana_visitante:
            g_a = max(0, g_a - 0.2)

    # Cancha local: si es de altura, el visitante rinde algo menos
    estadio_local = _ESTADIO_POR_EQUIPO.get(home, {"tipo": "llano", "metros": 0, "nota": ""})
    if estadio_local.get("tipo") == "altura":
        g_a = max(_GOLES_MINIMOS_POR_EQUIPO, g_a * _FACTOR_VISITANTE_EN_ALTURA)

    # Porcentaje de goles en primer tiempo (media Premier ~42 %)
    total_goles_esperados = g_h + g_a
    pct_primer_tiempo = 42
    goles_primer_tiempo_esperados = round(total_goles_esperados * (pct_primer_tiempo / 100), 1)

    # Probabilidad que ambos anoten (modelo Poisson: P(>=1) = 1 - exp(-lambda))
    p_local_anota = 1 - math.exp(-max(0, g_h))
    p_visitante_anota = 1 - math.exp(-max(0, g_a))
    prob_ambos_anotan = round((p_local_anota * p_visitante_anota) * 100)

    # Texto cancha local para la ficha del pronóstico
    cancha_tipo = estadio_local.get("tipo", "llano")
    cancha_metros = estadio_local.get("metros", 0)
    cancha_nota = estadio_local.get("nota", "").strip()
    if cancha_tipo == "altura":
        cancha_local_texto = f"Altura ({cancha_metros} m)" + (f" — {cancha_nota}" if cancha_nota else "")
    else:
        cancha_local_texto = "Llano" + (f" ({cancha_metros} m)" if cancha_metros else "") + (f" — {cancha_nota}" if cancha_nota else "")

    return {
        'marcador': f"{max(0, round(g_h))} - {max(0, round(g_a))}",
        'bajas_h': [(b.nombre, b.get_posicion_display(), b.estrellas) for b in bajas_h],
        'bajas_a': [(b.nombre, b.get_posicion_display(), b.estrellas) for b in bajas_a],
        'sancionados_h': [s.nombre for s in sanciones_h],
        'sancionados_a': [s.nombre for s in sanciones_a],
        'pct_bajas_h': pct_bajas_h,
        'pct_bajas_a': pct_bajas_a,
        'cancha_local_tipo': cancha_tipo,
        'cancha_local_texto': cancha_local_texto,
        'corners': stats_h['c'] + stats_a['c'],
        'tarjetas': tarjetas_ajustadas,
        'arbitro_nombre': arbitro["nombre"],
        'arbitro_tarjetas_promedio': arbitro["tarjetas_promedio"],
        'arbitro_nota': arbitro["nota"],
        'arbitro_oficial': arbitro_oficial,
        'fecha_partido': fecha_partido,
        'partido_entre_semana_local': partido_entre_semana_local,
        'partido_entre_semana_visitante': partido_entre_semana_visitante,
        'pct_goles_primer_tiempo': pct_primer_tiempo,
        'goles_primer_tiempo_esperados': goles_primer_tiempo_esperados,
        'prob_ambos_anotan': prob_ambos_anotan,
    }
