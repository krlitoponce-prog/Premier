"""
Cliente para la API Sportmonks (Football API 3.0).
Documentación: https://docs.sportmonks.com/football/endpoints-and-entities/endpoints
ID Finder (ligas, temporadas, equipos): https://my.sportmonks.com/resources/id-finder

Variables de entorno:
  SPORTMONKS_API_TOKEN  - Tu API key (obligatoria).
  SPORTMONKS_SEASON_ID  - ID de la temporada Premier League (ej. 2025/26). Opcional; si no está, algunas funciones requieren pasar season_id.
"""
import os
from datetime import date

import requests

BASE_URL = "https://api.sportmonks.com/v3/football"
# Premier League: IDs en Sportmonks (verificar en https://my.sportmonks.com/resources/id-finder)
PREMIER_LEAGUE_ID = 8  # England Premier League
# Temporada 2025/26: obtener season_id desde ID Finder y definir SPORTMONKS_SEASON_ID en env
PREMIER_SEASON_ID_DEFAULT = 23937


def _token():
    return os.environ.get("SPORTMONKS_API_TOKEN", "").strip()


def _season_id():
    sid = os.environ.get("SPORTMONKS_SEASON_ID", "").strip()
    if sid.isdigit():
        return int(sid)
    return PREMIER_SEASON_ID_DEFAULT


def _get(path, params=None, timeout=15):
    """GET a la API con api_token en query."""
    token = _token()
    if not token:
        return None, "SPORTMONKS_API_TOKEN no configurada"
    url = BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    params = dict(params or {})
    params["api_token"] = token
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        return None, str(e)


# ------ Fixtures ------


def get_fixtures_by_date(fixture_date, league_ids=None):
    """
    Partidos por fecha. Formato fecha: YYYY-MM-DD.
    league_ids: opcional, lista de IDs de liga (ej. [8] para Premier) para filtrar.
    """
    if isinstance(fixture_date, date):
        fixture_date = fixture_date.strftime("%Y-%m-%d")
    path = f"fixtures/date/{fixture_date}"
    params = {}
    if league_ids:
        params["filters"] = f"fixtureLeagues:{','.join(map(str, league_ids))}"
    data, err = _get(path, params)
    if err:
        return None, err
    return (data.get("data") or [], data.get("pagination")), None


def get_fixture_by_id(fixture_id, include=None):
    """Un partido por ID. include: ej. 'participants;state;sidelined'."""
    path = f"fixtures/{fixture_id}"
    params = {}
    if include:
        params["include"] = include
    data, err = _get(path, params)
    if err:
        return None, err
    return data.get("data"), None


# ------ Predictions ------


def get_probabilities_by_fixture_id(fixture_id):
    """
    Probabilidades de resultado (marcadores) para un partido.
    Útil para predicciones: devuelve % para 0-0, 1-0, 1-1, etc.
    """
    path = f"predictions/probabilities/fixtures/{fixture_id}"
    data, err = _get(path)
    if err:
        return None, err
    items = data.get("data") or []
    if not items:
        return None, "Sin datos de predicción para este partido"
    return items[0], None


# ------ Teams ------


def get_teams_by_season(season_id=None):
    """Equipos de una temporada. Por defecto usa SPORTMONKS_SEASON_ID o Premier actual."""
    sid = season_id or _season_id()
    path = f"teams/seasons/{sid}"
    data, err = _get(path)
    if err:
        return None, err
    return data.get("data") or [], None


def get_team_by_id(team_id, include=None):
    """Un equipo por ID. include: ej. 'sidelined' para lesionados/sancionados."""
    path = f"teams/{team_id}"
    params = {}
    if include:
        params["include"] = include
    data, err = _get(path, params)
    if err:
        return None, err
    return data.get("data"), None


# ------ Standings ------


def get_standings_by_season(season_id=None):
    """Clasificación de la temporada."""
    sid = season_id or _season_id()
    path = f"standings/seasons/{sid}"
    data, err = _get(path)
    if err:
        return None, err
    return data.get("data") or [], None


# ------ Referees ------


def get_referees_by_season(season_id=None):
    """Árbitros que han pitado en la temporada."""
    sid = season_id or _season_id()
    path = f"referees/seasons/{sid}"
    data, err = _get(path)
    if err:
        return None, err
    return data.get("data") or [], None


# ------ Schedules (próximos partidos por temporada) ------


def get_schedules_by_season(season_id=None, page=1, per_page=50):
    """Calendario de partidos de la temporada (útil para listar partidos Premier)."""
    sid = season_id or _season_id()
    path = f"schedules/seasons/{sid}"
    data, err = _get(path, params={"page": page, "per_page": per_page})
    if err:
        return None, err
    return data.get("data") or [], data.get("pagination"), None


# ------ Head2Head (enfrentamientos históricos) ------


def get_head2head(team_id_1, team_id_2, per_page=10):
    """
    Partidos históricos entre dos equipos (por ID).
    include: participants;scores;state para tener marcador y estado.
    """
    path = f"fixtures/head-to-head/{team_id_1}/{team_id_2}"
    params = {"per_page": min(per_page, 25), "include": "participants;scores;state"}
    data, err = _get(path, params)
    if err:
        return None, err
    fixtures = data.get("data") or []
    return fixtures, None


def _normalize_team_name(name):
    if not name:
        return ""
    return (name or "").strip().lower().replace("&", "and")


def _team_name_matches(our_name, api_name):
    """True si nuestro nombre del selector coincide con el nombre de la API."""
    if not our_name or not api_name:
        return False
    o, a = _normalize_team_name(our_name), _normalize_team_name(api_name)
    return o in a or a in o or o.replace(" ", "") == a.replace(" ", "")


def get_head2head_by_names(home_name, away_name, limit=8):
    """
    Últimos enfrentamientos entre local y visitante (por nombre de equipo).
    Devuelve (lista de dict con name, score_home, score_away, date), None) o (None, error).
    """
    teams, err = get_teams_by_season()
    if err or not teams:
        return None, err or "No se pudieron cargar equipos"
    team_id_by_name = {}
    for t in teams:
        nom = (t.get("name") or "").strip()
        if nom:
            team_id_by_name[nom] = t.get("id")
    # Buscar IDs: nuestro "Arsenal" puede coincidir con "Arsenal" de la API
    id_home = None
    id_away = None
    for api_name, tid in team_id_by_name.items():
        if _team_name_matches(home_name, api_name):
            id_home = tid
        if _team_name_matches(away_name, api_name):
            id_away = tid
    if not id_home or not id_away:
        return None, "No se encontraron ambos equipos en la temporada"
    fixtures, err = get_head2head(id_home, id_away, per_page=limit)
    if err or not fixtures:
        return [], None  # Sin historial, no es error
    result = []
    for f in fixtures:
        name = (f.get("name") or "").strip()
        state_id = f.get("state_id")
        # state_id 5 = finalizado (según docs)
        if state_id != 5:
            continue
        # Incluye: scores puede estar en f o en data anidado
        scores = f.get("scores") or []
        if isinstance(scores, dict) and "data" in scores:
            scores = scores.get("data") or []
        score_home = score_away = None
        for s in scores:
            if not isinstance(s, dict):
                continue
            participant_id = s.get("participant_id")
            score = s.get("score", {}).get("goals") if isinstance(s.get("score"), dict) else s.get("goals")
            if score is None:
                score = s.get("score")
            if participant_id == f.get("participants", [{}])[0].get("id") if f.get("participants") else None:
                score_home = score
            else:
                score_away = score
        # Alternativa: por type (total, home, away)
        if score_home is None and scores:
            for s in scores:
                if s.get("description") == "CURRENT" or s.get("type") == "total":
                    try:
                        score_home = int(s.get("score", {}).get("home") or s.get("home", 0))
                        score_away = int(s.get("score", {}).get("away") or s.get("away", 0))
                    except (TypeError, ValueError):
                        pass
                    break
        result_info = (f.get("result_info") or "").strip()
        if score_home is not None and score_away is not None:
            result.append({
                "name": name,
                "score_str": f"{score_home}-{score_away}",
                "score_home": score_home,
                "score_away": score_away,
                "starting_at": f.get("starting_at"),
            })
        elif result_info:
            result.append({"name": name, "score_str": result_info[:60], "starting_at": f.get("starting_at")})
        else:
            result.append({"name": name, "score_str": "—", "starting_at": f.get("starting_at")})
    return result[:limit], None


# ------ Helpers para integrar con tu app ------


def get_premier_fixture_id_for_teams(home_name, away_name, fixture_date=None):
    """
    Busca el fixture_id del partido local vs visitante en Premier.
    home_name / away_name: nombres como en tu selector (ej. "Arsenal", "Liverpool").
    fixture_date: opcional, date o "YYYY-MM-DD"; si no se pasa, se usa la fecha de hoy.
    Devuelve (fixture_id, None) o (None, error).
    """
    if fixture_date is None:
        fixture_date = date.today()
    if isinstance(fixture_date, date):
        fixture_date = fixture_date.strftime("%Y-%m-%d")
    premier_league_ids = [PREMIER_LEAGUE_ID]
    fixtures, err = get_fixtures_by_date(fixture_date, league_ids=premier_league_ids)
    if err:
        return None, err
    fixture_list = fixtures[0] if fixtures else []
    home_lower = (home_name or "").strip().lower()
    away_lower = (away_name or "").strip().lower()
    for f in fixture_list:
        name = (f.get("name") or "").strip()
        if not name or " vs " not in name:
            continue
        parts = name.split(" vs ", 1)
        if len(parts) != 2:
            continue
        local, visitante = parts[0].strip().lower(), parts[1].strip().lower()
        if (home_lower in local or local in home_lower) and (away_lower in visitante or visitante in away_lower):
            return f.get("id"), None
        if (away_lower in local or local in away_lower) and (home_lower in visitante or visitante in home_lower):
            return f.get("id"), None
    return None, "No se encontró partido para esa fecha y equipos"


def get_prediction_for_match(home_name, away_name, fixture_date=None):
    """
    Obtiene las probabilidades de marcador (Sportmonks) para local vs visitante.
    Devuelve dict con 'scores' (ej. {"1-0": 4.75, "1-1": 8.72, ...}) o None y mensaje de error.
    """
    fixture_id, err = get_premier_fixture_id_for_teams(home_name, away_name, fixture_date)
    if err or not fixture_id:
        return None, err or "Fixture no encontrado"
    prob, err = get_probabilities_by_fixture_id(fixture_id)
    if err or not prob:
        return None, err or "Sin probabilidades"
    predictions = prob.get("predictions") or {}
    scores = predictions.get("scores") or {}
    return {"fixture_id": fixture_id, "scores": scores, "raw": prob}, None


def procesar_probabilidades_sportmonks(scores_dict):
    """
    A partir del dict de marcadores de Sportmonks (ej. {"1-0": 4.75, "1-1": 8.72}),
    devuelve estructuras para la plantilla:
      - top_marcadores: lista de (marcador, prob) ordenada por prob desc, máx 5
      - total_goals: lista de (total_goles, prob_pct) para 0, 1, 2, 3, 4+
      - btts_partido_pct: probabilidad estimada ambos anotan (suma de marcadores con ambos > 0)
    Los valores en scores_dict pueden ser porcentajes (4.75 = 4.75%) o ya normalizados.
    """
    if not scores_dict or not isinstance(scores_dict, dict):
        return {"top_marcadores": [], "total_goals": [], "btts_partido_pct": None}
    # Filtrar solo marcadores tipo "1-0", "2-1", etc. (no "Other_1", "Other_2")
    valid = []
    for k, v in scores_dict.items():
        if not k or k.startswith("Other"):
            continue
        try:
            parts = k.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                valid.append((k, float(v)))
        except (ValueError, TypeError):
            continue
    if not valid:
        return {"top_marcadores": [], "total_goals": [], "btts_partido_pct": None}
    # Top 5 marcadores por probabilidad
    valid.sort(key=lambda x: -x[1])
    top_marcadores = valid[:5]
    # Total goles: agrupar por suma local+visitante
    total_goals_prob = {}
    btts_sum = 0.0
    for marcador, prob in valid:
        a, b = marcador.split("-", 1)
        total = int(a) + int(b)
        total_goals_prob[total] = total_goals_prob.get(total, 0) + prob
        if int(a) > 0 and int(b) > 0:
            btts_sum += prob
    total_goals = sorted([(t, round(p, 1)) for t, p in total_goals_prob.items()], key=lambda x: -x[1])
    btts_partido_pct = round(btts_sum, 1) if btts_sum else None
    return {
        "top_marcadores": top_marcadores,
        "total_goals": total_goals,
        "btts_partido_pct": btts_partido_pct,
    }
