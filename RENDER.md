# Desplegar en Render

Pasos para que la app **Premier Pro** (Django) corra en [Render](https://render.com).

---

## 1. Crear el Web Service en Render

1. Entra en [dashboard.render.com](https://dashboard.render.com).
2. **New** → **Web Service**.
3. Conecta tu repositorio (ej. `krlitoponce-prog/Premier`) y rama `main`.

---

## 2. Configuración del servicio

### Build Command

```bash
pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
```

### Start Command

```bash
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT
```

### Runtime

- **Environment:** Python 3.

---

## 3. Variables de entorno (Environment)

En el servicio → **Environment** → **Add Environment Variable**:

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `SECRET_KEY` | Recomendada en producción | Clave secreta de Django. **Tiene que ser exactamente `SECRET_KEY` en mayúsculas** (no `secret_key`). Si no está, Django usa la del código (menos seguro). |
| `DEBUG` | No | Pon `False` en producción para evitar errores visibles. Por defecto puede estar en True. |
| `SPORTMONKS_API_TOKEN` | Sí (para Sportmonks) | Tu API key de [MySportmonks](https://my.sportmonks.com/). Sin ella no se mostrarán probabilidades ni Head2Head. |
| `SPORTMONKS_SEASON_ID` | No | ID de la temporada Premier (ej. 2025/26). Lo ves en [ID Finder](https://my.sportmonks.com/resources/id-finder). Si no está, se usa un valor por defecto. |

Ejemplo para generar una `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Copia el resultado y pégalo en `SECRET_KEY` en Render.

---

## 4. Deploy

- **Auto-Deploy:** si está activado, cada `git push` a `main` desplegará solo.
- **Manual:** en **Manual Deploy** → **Deploy latest commit**.

Tras el build, la app quedará en una URL tipo:

`https://premier-league-XXXX.onrender.com`

---

## 5. Después del deploy

1. Abre la URL del servicio (la primera vez puede tardar ~50 s en responder en plan Free).
2. Ve a **Inicio** y usa **Actualizar lesionados** / **Actualizar sancionados** si quieres datos desde apuestas-deportivas (o Sportmonks cuando lo uses para eso).
3. Elige equipos y **Lanzar pronóstico**: verás tu pronóstico, Sportmonks (marcadores probables, goles totales, ambos anotan) y **Últimos enfrentamientos** (Head2Head).

---

## 6. Base de datos

Por defecto la app usa **SQLite** (`db.sqlite3`). En Render el disco es efímero, así que los datos (lesionados, sancionados, etc.) se pierden al redeploy. Puedes:

- Dejarlo así y volver a pulsar «Actualizar lesionados/sancionados» tras cada deploy, o
- Añadir una base **PostgreSQL** en Render y configurar `DATABASE_URL` (requiere `dj-database-url` y cambios en `settings.py`).

---

## Resumen rápido

| Paso | Acción |
|------|--------|
| Build | `pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput` |
| Start | `gunicorn core.wsgi:application --bind 0.0.0.0:$PORT` |
| Env | `SECRET_KEY`, `SPORTMONKS_API_TOKEN` (y opcional `SPORTMONKS_SEASON_ID`, `DEBUG=False`) |

Con esto la app queda lista para correr en Render.
