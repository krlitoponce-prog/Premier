"""
Verifica si podemos obtener el calendario 2025/26 por API (FixtureDownload).
Ejecutar: python manage.py verify_calendar_api

Si la API responde bien, verás cantidad de partidos y una muestra.
Si falla, conviene seguir con scrape.
"""
import json
import requests
from django.core.management.base import BaseCommand


# URLs a probar (FixtureDownload - temporada 2025/26)
URLS_TO_TRY = [
    "https://fixturedownload.com/feed/json/epl-2025",
    "https://fixturedownload.com/view/json/epl-2025",
]


class Command(BaseCommand):
    help = "Verifica si la API de calendario (FixtureDownload 2025/26) responde correctamente."

    def handle(self, *args, **options):
        self.stdout.write("Verificando API de calendario Premier 2025/26...\n")

        for url in URLS_TO_TRY:
            self.stdout.write(f"Probando: {url}")
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                self.stdout.write(f"  Status: {r.status_code}")

                if r.status_code != 200:
                    self.stdout.write(self.style.WARNING(f"  No OK (código {r.status_code}). Siguiente URL.\n"))
                    continue

                data = r.json()
                # FixtureDownload suele devolver lista de partidos o objeto con "Match" etc.
                if isinstance(data, list):
                    partidos = data
                elif isinstance(data, dict):
                    partidos = data.get("Match", data.get("Matches", data.get("Fixtures", [])))
                    if not partidos and data:
                        partidos = list(data.values())[0] if data else []
                    if not isinstance(partidos, list):
                        partidos = [data] if data else []
                else:
                    partidos = []

                n = len(partidos)
                self.stdout.write(self.style.SUCCESS(f"  OK. Partidos obtenidos: {n}"))

                if n > 0:
                    self.stdout.write("  Muestra (primer partido):")
                    self.stdout.write(json.dumps(partidos[0], indent=2, default=str))
                    self.stdout.write("\n  Conclusión: la API agarra bien. Se puede usar para 'partido entre semana'.")
                else:
                    self.stdout.write(self.style.WARNING("  La respuesta está vacía o tiene otro formato. Revisar estructura."))

                return
            except requests.exceptions.Timeout:
                self.stdout.write(self.style.WARNING("  Timeout. La URL no respondió a tiempo.\n"))
            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.WARNING(f"  Error de red: {e}\n"))
            except json.JSONDecodeError as e:
                self.stdout.write(self.style.WARNING(f"  No es JSON válido: {e}\n"))

        self.stdout.write(self.style.ERROR("Ninguna URL respondió bien. Conviene seguir con scrape del calendario."))
