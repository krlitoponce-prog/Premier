from django.shortcuts import render, redirect
from django.contrib import messages
from .utils import (
    generar_pronostico_pro,
    obtener_datos_completos_premier,
    obtener_estadios_premier,
    obtener_lista_arbitros_premier,
    get_arbitros_fallback,
)
from .scraper_apuestas import ejecutar_scraper_apuestas_lesionados_sancionados
from .scraper_arbitros import ejecutar_scraper_arbitros_fichajes
from .scraper_livefutbol import obtener_arbitros_livefutbol, limpiar_cache_arbitros
from .sportmonks_client import (
    get_prediction_for_match,
    procesar_probabilidades_sportmonks,
    get_head2head_by_names,
)
from .models import Lesionado, Sancionado


def home_dashboard(request):
    equipos = list(obtener_datos_completos_premier().keys())
    try:
        arbitros = obtener_lista_arbitros_premier()
    except Exception:
        arbitros = get_arbitros_fallback()
    context = {"equipos": equipos, "arbitros": arbitros, "head2head": []}

    if request.method == "POST":
        if "update_bajas" in request.POST:
            ok, n_les, n_san = ejecutar_scraper_apuestas_lesionados_sancionados()
            if ok:
                messages.success(
                    request,
                    f"Lesionados y sancionados actualizados desde apuestas-deportivas.es: {n_les} lesionados, {n_san} sancionados.",
                )
            else:
                messages.warning(request, "No se pudieron cargar lesionados/sancionados. Reintenta más tarde.")
            return redirect("home")
        if "update_arbitros" in request.POST:
            # 1) Actualizar lista de árbitros (nombres + tarjetas/partido) desde livefutbol
            limpiar_cache_arbitros()
            lista_livefutbol = obtener_arbitros_livefutbol()
            # 2) Opcional: designaciones por partido desde fichajes
            num_partidos, num_designaciones = ejecutar_scraper_arbitros_fichajes(obtener_pagina_partido=True)
            if lista_livefutbol:
                msg = f"Lista de árbitros actualizada desde livefutbol.com: {len(lista_livefutbol)} árbitros (tarjetas/partido)."
                if num_partidos and num_designaciones:
                    msg += f" Designaciones por partido: {num_partidos} partidos, {num_designaciones} con árbitro."
                messages.success(request, msg)
            elif num_partidos and num_designaciones:
                messages.success(
                    request,
                    f"Designaciones por partido actualizadas: {num_designaciones} partidos con árbitro. "
                    "La lista del desplegable usa datos guardados.",
                )
            else:
                n_arb = len(arbitros)
                messages.info(
                    request,
                    f"No se pudo conectar con livefutbol ni con la fuente de partidos. "
                    f"El desplegable sigue con la lista actual ({n_arb} árbitros) para elegir y calcular tarjetas.",
                )
            return redirect("home")
        if "update_sancionados" in request.POST:
            ok, n_les, n_san = ejecutar_scraper_apuestas_lesionados_sancionados()
            if ok:
                messages.success(
                    request,
                    f"Lesionados y sancionados actualizados: {n_les} lesionados, {n_san} sancionados.",
                )
            else:
                messages.warning(request, "No se pudieron cargar sancionados. Reintenta más tarde.")
            return redirect("home")

        home = request.POST.get("home_team")
        away = request.POST.get("away_team")
        arbitro_manual = (request.POST.get("arbitro_manual") or "").strip() or None
        if home and away:
            context.update(generar_pronostico_pro(home, away, arbitro_manual=arbitro_manual))
            context["home_sel"] = home
            context["away_sel"] = away
            if arbitro_manual:
                context["arbitro_sel"] = arbitro_manual
            # Datos Sportmonks: marcadores probables, goles totales, ambos anotan
            fixture_date = context.get("fixture_date_iso")
            pred, err = get_prediction_for_match(home, away, fixture_date)
            if err or not pred:
                msg = err or "Sin datos"
                if "api_token=" in msg or "for url:" in msg.lower() or "403" in msg or "Forbidden" in msg:
                    msg = (
                        "Sportmonks: predicciones no disponibles (acceso denegado). "
                        "Comprueba en MySportmonks que el componente «Prediction Model» esté habilitado y la API key."
                    )
                context["sportmonks_error"] = msg
                context["sportmonks"] = {}
            else:
                context["sportmonks_error"] = None
                scores = (pred.get("scores") or {}) if isinstance(pred, dict) else {}
                context["sportmonks"] = {**procesar_probabilidades_sportmonks(scores)}
                if pred.get("fulltime_result") is not None:
                    context["sportmonks"]["fulltime_result"] = pred["fulltime_result"]
                if pred.get("over_under_25") is not None:
                    context["sportmonks"]["over_under_25"] = pred["over_under_25"]
            # Head2Head: últimos enfrentamientos (no bloquea si falla)
            head2head_list, _ = get_head2head_by_names(home, away, limit=8)
            context["head2head"] = head2head_list or []

    return render(request, "dashboard/inicio.html", context)


def estadisticas(request):
    """Vista de estadísticas base por equipo (goles, corners, tarjetas, tipo cancha)."""
    datos = obtener_datos_completos_premier()
    estadios = obtener_estadios_premier()
    equipos_stats = []
    for eq, d in sorted(datos.items()):
        e = estadios.get(eq, {"tipo": "llano", "metros": 0, "nota": ""})
        equipos_stats.append({
            "equipo": eq,
            "goles": d["g"], "corners": d["c"], "tarjetas": d["t"],
            "cancha_tipo": e.get("tipo", "llano"),
            "cancha_metros": e.get("metros", 0),
            "cancha_nota": e.get("nota", ""),
        })
    return render(request, "dashboard/estadisticas.html", {"equipos_stats": equipos_stats})


def lesionados(request):
    """Vista de lesionados por equipo."""
    bajas = Lesionado.objects.all().order_by("equipo", "nombre")
    por_equipo = {}
    for b in bajas:
        if b.equipo not in por_equipo:
            por_equipo[b.equipo] = []
        por_equipo[b.equipo].append(b)
    return render(request, "dashboard/lesionados.html", {"por_equipo": por_equipo, "total": bajas.count()})


def sancionados(request):
    """Vista de sancionados por equipo."""
    lista = Sancionado.objects.all().order_by("equipo", "nombre")
    por_equipo = {}
    for s in lista:
        if s.equipo not in por_equipo:
            por_equipo[s.equipo] = []
        por_equipo[s.equipo].append(s)
    return render(request, "dashboard/sancionados.html", {"por_equipo": por_equipo, "total": lista.count()})