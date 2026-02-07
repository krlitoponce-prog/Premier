"""
Calendario Premier League 2025/26 vía FixtureDownload API.
Usado para: fecha del partido, partido entre semana, y mejorar pronósticos.
"""
import requests
from datetime import datetime, timezone, timedelta

CALENDAR_URL = "https://fixturedownload.com/feed/json/epl-2025"
_CACHE = {"data": None, "at": None}
CACHE_MINUTES = 10

# Alias para emparejar nombres del dashboard con los de la API (canonical en minúsculas)
TEAM_ALIASES = {
    "afc bournemouth": "bournemouth",
    "bournemouth": "bournemouth",
    "man city": "manchester city",
    "man united": "manchester united",
    "man utd": "manchester united",
    "spurs": "tottenham",
    "tottenham hotspur": "tottenham",
    "tottenham": "tottenham",
    "west ham united": "west ham",
    "west ham": "west ham",
    "wolves": "wolverhampton",
    "wolverhampton wanderers": "wolverhampton",
    "wolverhampton": "wolverhampton",
    "newcastle": "newcastle united",
    "newcastle united": "newcastle united",
    "brighton": "brighton",
    "brighton & hove albion": "brighton",
    "nottingham forest": "nottingham forest",
    "crystal palace": "crystal palace",
    "aston villa": "aston villa",
    "leeds united": "leeds united",
    "burnley": "burnley",
    "sunderland": "sunderland",
}


def _normalize_team(name):
    """Devuelve nombre normalizado en minúsculas para comparar (alias aplicados)."""
    if not name:
        return ""
    s = name.strip().lower()
    canonical = TEAM_ALIASES.get(s, name.strip())
    return canonical.lower()


def _teams_match(api_home, api_away, our_home, our_away):
    """Comprueba si el partido de la API es el mismo que local vs visitante nuestro."""
    n_api_h = _normalize_team(api_home)
    n_api_a = _normalize_team(api_away)
    n_our_h = _normalize_team(our_home)
    n_our_a = _normalize_team(our_away)
    return (n_api_h == n_our_h and n_api_a == n_our_a) or (n_api_h == n_our_a and n_api_a == n_our_h)


def _fetch_calendar():
    """Obtiene el calendario de la API (con cache en memoria)."""
    now = datetime.now(timezone.utc)
    if _CACHE["data"] is not None and _CACHE["at"] is not None:
        if (now - _CACHE["at"]).total_seconds() < CACHE_MINUTES * 60:
            return _CACHE["data"]
    try:
        r = requests.get(CALENDAR_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        partidos = data if isinstance(data, list) else []
        _CACHE["data"] = partidos
        _CACHE["at"] = now
        return partidos
    except Exception:
        return _CACHE["data"] or []


def _parse_date_utc(s):
    """Convierte '2025-08-15 19:00:00Z' a datetime en UTC."""
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00").strip()
        return datetime.fromisoformat(s)
    except Exception:
        return None


def get_fixture_for_match(home_team, away_team):
    """
    Busca en el calendario el partido entre home_team y away_team.
    Devuelve el dict del partido (con DateUtc, HomeTeam, AwayTeam, Location, RoundNumber, etc.)
    o None si no se encuentra.
    Prioriza partidos futuros; si no hay, devuelve el último jugado.
    """
    partidos = _fetch_calendar()
    now = datetime.now(timezone.utc)
    candidatos = []
    for p in partidos:
        api_h = (p.get("HomeTeam") or "").strip()
        api_a = (p.get("AwayTeam") or "").strip()
        if not _teams_match(api_h, api_a, home_team, away_team):
            continue
        dt = _parse_date_utc(p.get("DateUtc"))
        if dt is None:
            continue
        candidatos.append((dt, p))
    if not candidatos:
        return None
    # Ordenar por fecha; preferir el próximo partido (fecha >= hoy)
    candidatos.sort(key=lambda x: x[0])
    for dt, p in candidatos:
        if dt >= now:
            return p
    # Si todos son pasados, devolver el más reciente
    return candidatos[-1][1]


def had_midweek_match(team_name, fixture_date_utc, all_matches=None):
    """
    Indica si el equipo jugó otro partido entre 2 y 6 días antes de fixture_date_utc.
    (Partido entre semana = posible cansancio.)
    all_matches: lista de partidos de la API; si None se usa el calendario completo.
    """
    if fixture_date_utc is None or not team_name:
        return False
    if all_matches is None:
        all_matches = _fetch_calendar()
    team_n = _normalize_team(team_name)
    start = fixture_date_utc - timedelta(days=6)
    end = fixture_date_utc - timedelta(days=2)
    for p in all_matches:
        dt = _parse_date_utc(p.get("DateUtc"))
        if dt is None:
            continue
        if not (start <= dt <= end):
            continue
        api_h = _normalize_team((p.get("HomeTeam") or "").strip())
        api_a = _normalize_team((p.get("AwayTeam") or "").strip())
        if api_h == team_n or api_a == team_n:
            return True
    return False


def format_fixture_date(date_utc):
    """Formatea la fecha del partido para mostrar (ej: 'Dom 8/02/2026 11:30')."""
    if date_utc is None:
        return None
    try:
        # pasar a hora local sería ideal; aquí mostramos UTC simplificado
        d = date_utc.date()
        t = date_utc.timetz()
        dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        dow = dias[d.weekday()]
        return f"{dow} {d.day:02d}/{d.month:02d}/{d.year} {t.hour:02d}:{t.minute:02d}"
    except Exception:
        return str(date_utc)
