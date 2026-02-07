# Ver el dashboard desde otra red (otra PC, móvil 4G, etc.)

Para acceder al Premier Pro desde otra red necesitas exponer tu servidor local a internet. La opción más sencilla es **ngrok**.

---

## Plan con ngrok (recomendado)

### 1. Crear cuenta y descargar ngrok

- Entra en **https://ngrok.com** y crea una cuenta gratis.
- Descarga ngrok para Windows: https://ngrok.com/download
- Descomprime el `.zip` y deja `ngrok.exe` en una carpeta (ej. `C:\ngrok` o en tu usuario).

### 2. Configurar tu token (solo una vez)

En la web de ngrok, en "Your Authtoken", copia el token. Luego en PowerShell:

```powershell
cd C:\ngrok
.\ngrok config add-authtoken TU_TOKEN_AQUI
```

(Sustituye `C:\ngrok` por la carpeta donde está `ngrok.exe` y `TU_TOKEN_AQUI` por tu token.)

### 3. Arrancar Django

En una terminal:

```powershell
cd E:\Dashboard
.\venv\Scripts\Activate.ps1
python manage.py runserver
```

(Django en el puerto 8000 por defecto.)

### 4. Arrancar el túnel ngrok

En **otra** terminal:

```powershell
cd C:\ngrok
.\ngrok http 8000
```

Verás algo como:

```
Forwarding   https://abc123xyz.ngrok-free.app -> http://localhost:8000
```

### 5. Entrar desde la otra PC

En la otra PC (cualquier red, incluso 4G):

- Abre el navegador.
- Pega la URL que ngrok te dio, por ejemplo: **https://abc123xyz.ngrok-free.app**
- En el plan gratis de ngrok puede salir una pantalla de “Visit Site”; haz clic en **Visit Site** y cargará tu dashboard.

---

## Resumen

| Paso | Dónde | Qué hacer |
|------|--------|-----------|
| 1 | ngrok.com | Cuenta + descargar ngrok |
| 2 | PowerShell | `ngrok config add-authtoken TU_TOKEN` |
| 3 | Terminal 1 | `python manage.py runserver` |
| 4 | Terminal 2 | `ngrok http 8000` |
| 5 | Otra PC | Abrir la URL que muestra ngrok |

---

## Límites del plan gratis ngrok

- La URL cambia cada vez que reinicias ngrok (salvo que tengas dominio fijo en plan de pago).
- Límite de tráfico mensual; para uso personal suele bastar.
- Mientras no cierres ngrok, la URL sigue funcionando desde cualquier red.

---

## Alternativa: Cloudflare Tunnel

Si prefieres no usar ngrok:

1. Instala **cloudflared**: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
2. Crea un túnel hacia `http://localhost:8000`.
3. Te dará una URL tipo `xxx.trycloudflare.com` para acceder desde otra red.

Django ya está configurado para aceptar peticiones que lleguen por ngrok (dominios `.ngrok-free.app`, `.ngrok.io`, etc.).

---

## Ponerlo en un dominio (tu propia URL)

Tienes varias opciones según si quieres una URL “de marca” (tu dominio) o solo una URL fija.

### Opción A: URL fija con ngrok (sin comprar dominio)

- En la cuenta de ngrok (dashboard.ngrok.com) → **Cloud Edge → Domains** → “Claim your free Domain”.
- Te dan una URL **fija** tipo `tunombre.ngrok-free.app` que no cambia al reiniciar ngrok.
- Al arrancar el túnel: `ngrok http --domain=tunombre.ngrok-free.app 8000`.
- No es “tu” dominio, pero es una URL estable y gratis.

### Opción B: Tu propio dominio con Cloudflare Tunnel (gratis)

Con esto puedes usar algo como **premier.tudominio.com** o **app.tudominio.com**.

1. **Tener un dominio**  
   Comprado donde sea (Namecheap, Google Domains, DonDominio, etc.).

2. **Añadir el dominio a Cloudflare**  
   - Entra en https://dash.cloudflare.com → Add site → introduce tu dominio.  
   - Cloudflare te dirá que cambies los *nameservers* en tu registrador al que te indique (o, si no quieres mover todo el dominio, más adelante puedes usar solo un CNAME; ver paso 4).

3. **Instalar cloudflared**  
   - Windows: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/  
   - O descarga directa: https://github.com/cloudflare/cloudflared/releases

4. **Crear un túnel con tu dominio**  
   - En Cloudflare: **Zero Trust** (o **Networks**) → **Tunnels** → Create a tunnel → nombre ej. `premier-pro`.  
   - Elige “Cloudflared” y sigue los pasos; te dará un comando para ejecutar en tu PC (incluye un token).  
   - En “Public Hostname” añades un hostname, por ejemplo:  
     - Subdominio: `premier` (o `app`)  
     - Dominio: `tudominio.com`  
     - Service: `http://localhost:8000`  
   - Si tu DNS está en Cloudflare, crea el CNAME automáticamente. Si no, en tu registrador creas un CNAME: `premier` → el valor que te indique Cloudflare (ej. `xxx.cfargotunnel.com`).

5. **En tu PC**  
   - Django corriendo: `python manage.py runserver`.  
   - En otra terminal: el comando que te dio Cloudflare para el túnel (suele ser `cloudflared tunnel run ...`).  
   - Cuando el túnel esté activo, **https://premier.tudominio.com** (o el subdominio que hayas elegido) abrirá tu dashboard.

6. **Decirle a Django que acepte ese dominio**  
   En `core/settings.py`, en `ALLOWED_HOSTS`, añade tu dominio, por ejemplo:

   ```python
   ALLOWED_HOSTS = [
       "localhost",
       "127.0.0.1",
       ".ngrok-free.app",
       ".ngrok.io",
       ".ngrok.app",
       "premier.tudominio.com",   # o "tudominio.com" si usas el apex
   ]
   ```

   (Sustituye `tudominio.com` por tu dominio real.)

### Opción C: Dominio en un servidor (producción 24/7)

Si quieres que esté siempre online sin tener tu PC encendida:

- Contratas un VPS o un hosting (Railway, PythonAnywhere, DigitalOcean, etc.).
- Despliegas ahí el proyecto Django y configuras el servidor (Gunicorn + Nginx, o lo que ofrezca el servicio).
- En el DNS de tu dominio apuntas el registro A o CNAME a la IP/hostname del servidor.
- En `ALLOWED_HOSTS` pones tu dominio.

---

## Resumen dominio

| Qué quieres              | Opción recomendada        | Resultado típico              |
|--------------------------|---------------------------|--------------------------------|
| URL fija, sin comprar dominio | ngrok dominio gratis      | `tunombre.ngrok-free.app`     |
| Tu dominio (ej. premier.midominio.com) | Cloudflare Tunnel        | `premier.tudominio.com`       |
| Siempre online, sin usar tu PC | VPS/hosting + despliegue  | `tudominio.com` en un servidor |
