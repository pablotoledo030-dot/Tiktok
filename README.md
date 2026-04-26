# 📼 TikTok → Transcripciones automáticas

Cada vez que le des ❤️ "Me gusta" a un video en TikTok, este repositorio lo
**descarga, lo transcribe con Whisper y guarda el texto en `transcripts/`**
automáticamente. Todo corre en GitHub Actions (gratis), tú no instalas nada.

```
TikTok ❤️ Me gusta
        │
        ▼  cron horario
   GitHub Actions
        │
        ├─► descarga el video
        ├─► transcribe con Whisper
        └─► commitea transcripts/<id>/transcript.txt al repo
              (+ opcional: sube .mp4 a Google Drive)
```

---

## 🚀 Setup mínimo (5 minutos, todo desde el navegador)

### Paso 1 — Pon públicos tus "Me gusta" en TikTok

En la app de TikTok (móvil):

```
Tu perfil → ☰ (arriba derecha) → Configuración y privacidad
   → Privacidad → "Videos a los que les diste me gusta"
   → Todos
```

### Paso 2 — Activa los workflows del repo

1. Abre el repo en GitHub: `https://github.com/pablotoledo030-dot/Tiktok`
2. Pestaña **Actions** → si te pide habilitarlos, dale **"I understand my workflows, go ahead and enable them"**.

### Paso 3 — Lanza el primer run a mano

1. Pestaña **Actions** → en la izquierda **"Sync TikTok favorites"** → botón **"Run workflow"** (arriba a la derecha) → branch `main` → **Run workflow**.
2. Espera 2-5 min. Si todo va bien:
   - Verás un nuevo commit con tus transcripciones en la pestaña **Code**.
   - Las encuentras en la carpeta **`transcripts/<id_video>/transcript.txt`**.

¡Y ya está! El cron se ejecuta solo cada hora a partir de aquí.

---

## 🛟 Si el primer run falla (probablemente "HTTP 403" o "secUid")

TikTok bloquea peticiones anónimas en algunas regiones. La solución: añadir
una cookie de sesión como secret. Dura ~30-60 días.

### Cómo obtener tu `cookies.txt` (5 min)

1. En tu navegador, instala la extensión **"Get cookies.txt LOCALLY"**:
   - Chrome: <https://chromewebstore.google.com/detail/cclelndahbckbenkjhflpdbgdldlbecc>
   - Firefox: busca "cookies.txt" en el store de Firefox.
2. Entra a `tiktok.com` y haz login en tu cuenta normal.
3. Click en la extensión → **Export** → guarda `tiktok.com_cookies.txt`.
4. Abre el archivo con un editor de texto y copia **todo el contenido**.

### Añadirlo como secret en GitHub

1. Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
2. Name: `TIKTOK_COOKIES` — Value: (pega el contenido completo).
3. **Add secret**.
4. Vuelve a **Actions → Sync TikTok favorites → Run workflow**.

---

## 💬 Cómo consultar después con Claude

Cuando tengas varias transcripciones en `transcripts/`:

### Opción A — Claude Projects (recomendado)

1. En `claude.ai` → **Projects** → **New project** → "TikTok Insights".
2. **Add files** → arrastra todos los `transcript.txt` de `transcripts/`.
   - Truco: descárgate el repo en zip desde GitHub (botón **Code → Download ZIP**) y arrastra los `.txt`.
3. Pregunta: *"resúmeme los videos sobre Claude Code"* / *"qué herramientas mencionaron en los últimos 7 días"*.

### Opción B — NotebookLM (gratis, sin tokens)

`https://notebooklm.google.com` → **New notebook** → Add source → sube los `.txt`. Chateas con Gemini sobre todas tus transcripciones.

### Opción C — Buscar en GitHub directamente

Las transcripciones están en el repo. Usa la barra de búsqueda de GitHub
o Ctrl+F dentro de cada `transcript.txt`.

---

## 🎬 (Opcional) Guardar también los `.mp4` en Google Drive

Por defecto el repo guarda solo las transcripciones (texto). Si quieres
también el video original en Drive, sigue estos pasos. Si no, ignóralos.

### 1) Generar el archivo de configuración de rclone (sin instalar nada)

Usaremos **Google Cloud Shell**, una terminal Linux gratis dentro del navegador:

1. Entra a `https://shell.cloud.google.com` con tu cuenta de Google.
2. En la terminal del navegador, ejecuta:

   ```bash
   curl -fsSL https://rclone.org/install.sh | sudo bash
   rclone config
   ```

3. Sigue este diálogo (responde lo indicado en negrita):
   - `n) New remote` → **n**
   - `name>` → **drive**
   - `Storage>` → **drive** (o el número que aparezca al lado)
   - `client_id>` → (vacío, Enter)
   - `client_secret>` → (vacío, Enter)
   - `scope>` → **1** (full access)
   - `service_account_file>` → (vacío, Enter)
   - `Edit advanced config?` → **n**
   - `Use auto config?` → **n** (¡importante! Cloud Shell no abre navegador)
   - Te dará un comando del estilo `rclone authorize "drive" "..."`. **Copia ese comando**.
4. Abre **otra pestaña** en tu PC con `rclone` instalado, o pega el mismo comando en una terminal local — pero como dijiste que no quieres instalar nada, hay un truco más simple: en la **misma** Cloud Shell:

   ```bash
   rclone authorize "drive"
   ```

   Te abrirá una URL → ábrela en otra pestaña → autoriza con tu Google → te dará un código → pégalo en Cloud Shell.
5. Vuelve a la primera ventana de `rclone config` y pega el `config_token` que te da la otra.
6. `Configure as a Shared Drive?` → **n**
7. `Yes this is OK` → **y**
8. `q) Quit config` → **q**

Verifica:

```bash
rclone lsd drive:
```

Debería listar tus carpetas de Drive.

### 2) Codificar y guardar como secret

En la misma Cloud Shell:

```bash
base64 -w0 ~/.config/rclone/rclone.conf
```

Copia todo lo que imprime.

En GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

- Name: `RCLONE_CONF_BASE64`
- Value: (pegar)

A partir del próximo run, los `.mp4` se subirán a `Drive/TikTok-Favoritos/AAAA-MM/<id>/`.

---

## 📱 (Opcional) Atajo de Android para procesar al instante

Para videos que veas fuera del cron y quieras procesar ya:

1. Instala **HTTP Shortcuts** (gratis en Play Store).
2. Crea un Personal Access Token de GitHub (`Settings → Developer settings → Tokens (classic)` con scope `repo`).
3. En HTTP Shortcuts crea un nuevo shortcut:
   - Method: **POST**
   - URL: `https://api.github.com/repos/pablotoledo030-dot/Tiktok/dispatches`
   - Headers: `Authorization: Bearer <PAT>` y `Accept: application/vnd.github+json`
   - Body (JSON):
     ```json
     {"event_type":"tiktok-share","client_payload":{"url":"{variable:url}"}}
     ```
4. Define la variable `url` como entrada desde el "Compartir" del sistema.
5. En TikTok → **Compartir** → **HTTP Shortcuts** → se procesa en GitHub.

---

## ⚙️ Variables y secrets soportados

Todo es opcional excepto que tu pestaña Likes sea pública (o que añadas `TIKTOK_COOKIES`).

| Tipo | Nombre | Default | Para qué |
|---|---|---|---|
| Variable | `TIKTOK_USERNAME` | `pablotoledo02` | Tu username sin @ |
| Variable | `TIKTOK_SOURCE` | `likes` | `likes` o `favorites` |
| Variable | `WHISPER_MODEL` | `base` | `tiny`/`base`/`small`/`medium` |
| Variable | `WHISPER_LANGUAGE` | `es` | Código ISO; vacío = autodetect |
| Variable | `RCLONE_BASE_DIR` | `TikTok-Favoritos` | Carpeta destino en Drive |
| Secret   | `TIKTOK_COOKIES` | — | Cookies si la API anónima falla |
| Secret   | `RCLONE_CONF_BASE64` | — | Config rclone para guardar mp4 en Drive |

---

## 📂 Estructura del repo

```
.
├── .github/workflows/sync.yml   # cron horario + run manual + dispatch Android
├── scripts/
│   ├── fetch_favorites.py       # lista los likes del usuario
│   ├── transcribe.py            # faster-whisper en CPU
│   └── sync.py                  # orquestador
├── data/
│   └── index.json               # IDs ya procesados
├── transcripts/                 # ⭐ AQUÍ tus transcripciones
│   └── <video_id>/
│       ├── transcript.txt
│       ├── transcript.json
│       └── metadata.json
├── requirements.txt
└── README.md
```

---

## 🧯 Troubleshooting rápido

| Mensaje en los logs de Actions | Qué hacer |
|---|---|
| `No se encontró secUid` o `HTTP 403` | Añade el secret `TIKTOK_COOKIES`. |
| `yt-dlp` falla en un video | Probablemente video privado o regional. El resto sigue procesándose. |
| Workflow no se ejecuta solo | Tras 60 días sin actividad GitHub deshabilita los crons. Haz un commit cualquiera o **Run workflow**. |
| Whisper muy lento | Usa `WHISPER_MODEL=tiny` (variable). |

Cualquier duda, abre un **Issue** en este repo.
