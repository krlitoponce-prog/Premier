# Desplegar con GitHub (Railway o Render)

Sí se puede: subes el proyecto a GitHub y un servicio lo despliega desde el repositorio. Así tienes una URL pública (y luego puedes poner tu dominio).

---

## Qué hace falta

- Cuenta en **GitHub**.
- Cuenta en **Railway** o **Render** (ambos tienen plan gratis y se conectan a GitHub).

El proyecto ya tiene lo necesario: `gunicorn`, `whitenoise`, y `ALLOWED_HOSTS` con `.railway.app` y `.onrender.com`.

---

## Paso 1: Subir el proyecto a GitHub

1. Crea un repositorio nuevo en https://github.com/new (por ejemplo `premier-pro` o `dashboard-premier`). No añadas README ni .gitignore si ya tienes código local.

2. En la carpeta del proyecto (donde está `manage.py`), si aún no usas Git:

```powershell
cd E:\Dashboard
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

(Sustituye `TU_USUARIO` y `TU_REPO` por tu usuario de GitHub y el nombre del repo.)

3. Si no tienes `.gitignore`, créalo para no subir cosas innecesarias:

```
venv/
__pycache__/
*.pyc
db.sqlite3
.env
*.log
.DS_Store
```

Luego `git add .`, `git commit`, `git push` otra vez.

---

## Paso 2A: Desplegar con Railway

1. Entra en **https://railway.app** e inicia sesión (puedes usar “Login with GitHub”).

2. **New Project** → **Deploy from GitHub repo** → elige tu repositorio.

3. Railway suele detectar Django. Si te pide configurar:
   - **Build command:** (vacío o `pip install -r requirements.txt`)
   - **Start command:** `gunicorn core.wsgi --bind 0.0.0.0:$PORT`
   - O en Variables, a veces usan `PORT` automático; si no, añade variable `PORT` = `8000`.

4. En **Settings** del servicio → **Networking** → **Generate Domain**. Te dará una URL tipo `tu-proyecto.railway.app`.

5. En la pestaña **Variables** (opcional pero recomendado en producción):
   - `DEBUG` = `False`
   - `SECRET_KEY` = una clave larga y aleatoria (genera una nueva, no la de desarrollo).

6. Cada vez que hagas `git push` a `main`, Railway volverá a desplegar solo.

---

## Paso 2B: Desplegar con Render

1. Entra en **https://render.com** e inicia sesión (con GitHub).

2. **New** → **Web Service** → conecta tu repositorio de GitHub y elige el repo.

3. Configuración típica:
   - **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - **Start Command:** `gunicorn core.wsgi:application --bind 0.0.0.0:$PORT`
   - **Plan:** Free.

4. En **Environment** añade (recomendado para producción):
   - `DEBUG` = `False`
   - `SECRET_KEY` = una clave secreta nueva.

5. **Create Web Service**. Te dará una URL tipo `tu-servicio.onrender.com`.

Nota: en plan gratis, el servicio se “duerme” tras unos minutos sin visitas; la primera visita puede tardar un poco en responder.

---

## Dominio propio después

Tanto Railway como Render permiten añadir **tu dominio** (ej. `premier.tudominio.com`):

- En Railway: Settings del servicio → **Networking** → **Custom Domain**.
- En Render: Settings del Web Service → **Custom Domains**.

Luego en el DNS de tu dominio creas un CNAME que apunte a la URL que te den (ej. `tu-proyecto.railway.app`). Y en Django, en `ALLOWED_HOSTS` (en `core/settings.py`), añades tu dominio, por ejemplo: `"premier.tudominio.com"`.

---

## Resumen

| Paso | Acción |
|------|--------|
| 1 | Subir código a GitHub (`git init`, `git add`, `git commit`, `git push`) |
| 2 | Railway o Render → conectar el repo de GitHub |
| 3 | Configurar build/start (gunicorn) y variables (DEBUG, SECRET_KEY) |
| 4 | Obtener la URL (.railway.app o .onrender.com) |
| 5 | (Opcional) Añadir dominio propio en Railway/Render y en `ALLOWED_HOSTS` |

Así sí puedes usar GitHub para tener el código y que el sitio esté en línea (y con dominio si quieres).
