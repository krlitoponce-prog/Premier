from django.shortcuts import render, redirect
from django.contrib import messages
from .utils import generar_pronostico_pro, obtener_datos_completos_premier, obtener_estadios_premier
from .scraper import ejecutar_scraper_premier
from .scraper_arbitros import ejecutar_scraper_arbitros_fichajes
from .scraper import ejecutar_scraper_sancionados
from .models import Lesionado, Sancionado


def home_dashboard(request):
    equipos = list(obtener_datos_completos_premier().keys())
    context = {'equipos': equipos}
    
    if request.method == 'POST':
        if 'update_bajas' in request.POST:
            ejecutar_scraper_premier()
            messages.success(request, "Lista de lesionados actualizada.")
            return redirect('home')
        if 'update_arbitros' in request.POST:
            num_partidos, num_arbitros = ejecutar_scraper_arbitros_fichajes(obtener_pagina_partido=True)
            if num_partidos:
                messages.success(
                    request,
                    f"Árbitros actualizados: {num_partidos} partidos revisados, {num_arbitros} con árbitro asignado. "
                    "Las tarjetas del pronóstico usarán estos datos cuando estén disponibles."
                )
            else:
                messages.warning(request, "No se pudieron cargar partidos desde la fuente. Reintenta más tarde.")
            return redirect('home')
        if 'update_sancionados' in request.POST:
            if ejecutar_scraper_sancionados():
                messages.success(request, "Lista de sancionados actualizada. El pronóstico tendrá en cuenta las bajas por sanción.")
            else:
                messages.warning(request, "No se pudieron cargar sancionados. Reintenta más tarde.")
            return redirect('home')
            
        home = request.POST.get('home_team')
        away = request.POST.get('away_team')
        if home and away:
            context.update(generar_pronostico_pro(home, away))
            context['home_sel'] = home
            context['away_sel'] = away
            
    return render(request, 'dashboard/inicio.html', context)


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