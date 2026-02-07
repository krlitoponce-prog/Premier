from django.db import models


class Lesionado(models.Model):
    POSICIONES = [
        ('DEL', 'Delantero'),
        ('MED', 'Mediocampista'),
        ('DEF', 'Defensa'),
        ('POR', 'Portero'),
        ('NA', 'Sin especificar'),
    ]
    
    nombre = models.CharField(max_length=100)
    equipo = models.CharField(max_length=100)
    posicion = models.CharField(max_length=3, choices=POSICIONES, default='NA')
    estrellas = models.IntegerField(default=1)  # 1, 2 o 3 estrellas
    tipo_lesion = models.CharField(max_length=120, blank=True)   # ej. "Lesión de tobillo"
    retorno_esperado = models.CharField(max_length=120, blank=True)  # ej. "Duda", "Baja confirmada"
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_posicion_display()}) - {self.estrellas}⭐"


class Sancionado(models.Model):
    """Jugador sancionado (expulsión, acumulación de tarjetas, etc.) que baja el rendimiento del equipo."""
    nombre = models.CharField(max_length=100)
    equipo = models.CharField(max_length=100)
    motivo = models.CharField(max_length=150, blank=True)  # ej. "5.ª amarilla", "Expulsión"
    jornada = models.CharField(max_length=20, blank=True)  # ej. "Jornada 25"
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["equipo", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.equipo}) - {self.motivo or 'Sancionado'}"


class DesignacionArbitro(models.Model):
    """Árbitro asignado a un partido (actualizable con botón desde fichajes u otra fuente)."""
    equipo_local = models.CharField(max_length=120)
    equipo_visitante = models.CharField(max_length=120)
    arbitro_nombre = models.CharField(max_length=100)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["equipo_local", "equipo_visitante"]]
        ordering = ["-fecha_actualizacion"]

    def __str__(self):
        return f"{self.equipo_local} vs {self.equipo_visitante} → {self.arbitro_nombre}"