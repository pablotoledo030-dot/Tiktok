# TikTok → Drive (descarga + transcripción automática)

Pipeline gratis para que **cada video al que des ❤️ Me gusta en TikTok** se descargue,
se transcriba con Whisper y se guarde en tu Google Drive, listo para consultar
después con Claude / NotebookLM / búsqueda.

```
TikTok ❤️ Me gusta  ─►  GitHub Actions (cron 1h)
                         │
                         ├─ yt-dlp descarga .mp4
                         ├─ faster-whisper genera .txt + .json
                         └─ rclone sube a Google Drive/TikTok-Favoritos/AAAA-MM/
```

Costo: **0 €/mes** para volúmenes hasta ~150 videos al mes.

---

## 1. Pre-requisitos

- Cuenta de **GitHub** (este repo).
- Cuenta de **Google Drive** personal.
- Tu **username de TikTok** (sin `@`). Ej: `pablotoledo02`.
- Tener la pestaña **"Me gustó"** pública en TikTok:
  `Configuración → Privacidad → Videos que te han gustado → Todos`.
  *(Si la dejas privada, también funciona pero necesitas cookies — ver §5.)*

---

## 2. Setup local de rclone (una vez)

En tu PC:

```bash
# Instala rclone (https://rclone.org/install/)
rclone config
#   n) New remote
#   name> drive
#   storage> drive
#   client_id / secret> (déjalos vacíos para usar el default)
#   scope> 1   (drive completo)
#   service_account_file> (vacío)
#   Edit advanced config? n
#   Use auto config? y    -> abrirá tu navegador, autoriza
#   Configure as a Shared Drive? n
```

Verifica:

```bash
rclone lsd drive:
```

Codifica la config para subirla como secret:

```bash
base64 -w0 ~/.config/rclone/rclone.conf
```

Copia ese string.

---

## 3. Configurar el repo en GitHub

### Secrets (`Settings → Secrets and variables → Actions → Secrets`)

| Secret | Valor |
|---|---|
| `RCLONE_CONF_BASE64` | El string base64 del paso anterior |
| `TIKTOK_COOKIES` | *(opcional)* Tu `cookies.txt` Netscape — solo si quieres usar Favoritos privados |

### Variables (`Settings → Secrets and variables → Actions → Variables`)

| Variable | Valor sugerido |
|---|---|
| `TIKTOK_USERNAME` | `pablotoledo02` |
| `TIKTOK_SOURCE` | `likes` *(o `favorites` si haces el plan B)* |
| `WHISPER_MODEL` | `base` *(rápido, calidad razonable; sube a `small`/`medium` si no es suficiente)* |
| `WHISPER_LANGUAGE` | `es` |
| `RCLONE_REMOTE` | `drive` |
| `RCLONE_BASE_DIR` | `TikTok-Favoritos` |

---

## 4. Activación

1. Haz push de este repo a tu cuenta de GitHub.
2. Ve a `Actions` → habilita los workflows.
3. Lanza manualmente la primera vez: `Actions → Sync TikTok favorites → Run workflow`.
4. Si todo va bien, verás en tu Drive `TikTok-Favoritos/2026-04/<video_id>/` con `.mp4`, `.txt`, `.json`, `metadata.json`.
5. A partir de ahí, el cron se ejecuta cada hora.

---

## 5. Plan B — Si tu pestaña "Me gustó" es privada (o usas el botón 🔖 Favoritos)

Las dos opciones requieren cookies:

1. Inicia sesión en TikTok web en tu navegador.
2. Instala la extensión **"Get cookies.txt LOCALLY"** (Chrome/Firefox).
3. En la página de TikTok, exporta cookies → guarda como `cookies.txt`.
4. Copia el contenido completo y pégalo en el secret `TIKTOK_COOKIES`.
5. (Si vas con Favoritos en vez de Me gusta) cambia la variable `TIKTOK_SOURCE` a `favorites`.

La cookie `sessionid` dura ~30-60 días. Cuando el workflow falle con 401/403, repite el paso.

---

## 6. Compartir desde Android (atajo manual opcional)

Para los videos que veas fuera del cron y quieras procesar al instante:

1. Instala **HTTP Shortcuts** en Android (gratis, Play Store).
2. Crea un atajo nuevo:
   - **Method**: POST
   - **URL**: `https://api.github.com/repos/<tu-usuario>/tiktok/dispatches`
   - **Headers**:
     - `Accept: application/vnd.github+json`
     - `Authorization: Bearer <PAT>`  *(token con scope `repo`)*
   - **Body** (JSON):
     ```json
     {"event_type":"tiktok-share","client_payload":{"url":"{variable:url}"}}
     ```
3. Define una variable `url` que se rellena desde el "Compartir" del sistema.
4. En TikTok → Compartir → HTTP Shortcuts → el video se procesa en GitHub Actions.

---

## 7. Cómo consultar las transcripciones después

### Opción A — Claude Projects (recomendado)

1. En `claude.ai` → crea un Project nuevo "TikTok Insights".
2. Súbele todos los `.txt` de la carpeta de Drive (puedes hacer un zip).
3. Pregunta lo que quieras: *"resúmeme los videos sobre Claude Code que vi en marzo"*.

### Opción B — Google NotebookLM (gratis, sin coste de tokens)

1. Entra a `notebooklm.google.com`.
2. Crea un cuaderno → Add source → Google Drive → selecciona tu carpeta `TikTok-Favoritos`.
3. NotebookLM indexa todos los `.txt` y puedes chatear con Gemini sobre ellos.

### Opción C — grep / búsqueda local

Sincroniza la carpeta a tu PC con `rclone sync drive:TikTok-Favoritos ./local` y usa
cualquier herramienta de búsqueda (`ripgrep`, Obsidian, Recoll…).

---

## 8. Estructura del repo

```
.
├── .github/workflows/sync.yml   # cron horario + dispatch manual
├── scripts/
│   ├── fetch_favorites.py       # lista videos likes/favoritos
│   ├── transcribe.py            # faster-whisper -> .txt + .json
│   └── sync.py                  # orquestador
├── data/
│   └── index.json               # IDs ya procesados (commit-ado)
├── requirements.txt
├── rclone.conf.example
└── README.md
```

---

## 9. Tuning

- **Whisper más rápido**: `WHISPER_MODEL=tiny` (peor calidad pero ~3x más rápido).
- **Whisper más preciso**: `WHISPER_MODEL=medium` (más lento, mejor en jergas).
- **Idioma autodetect**: deja vacío `WHISPER_LANGUAGE`.
- **Cron más frecuente**: edita `.github/workflows/sync.yml`. Cuidado con el límite de 2000 min/mes.

---

## 10. Troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| `No se encontró secUid` | Username mal o anti-bot de TikTok | Verifica `TIKTOK_USERNAME`. Añade `TIKTOK_COOKIES`. |
| `HTTP 401/403` al fetch | Cookie expirada / privacidad | Re-exporta `cookies.txt` o haz pública la pestaña. |
| `yt-dlp` falla | Video privado o región bloqueada | Añade `TIKTOK_COOKIES`. |
| `rclone listremotes` vacío | Base64 mal pegado | Re-genera `RCLONE_CONF_BASE64`. |
| Cron no se ejecuta | Repo sin actividad >60 días | Hacé un push o usa `workflow_dispatch`. |

---

## Licencia

Uso personal. Respeta los Términos de Servicio de TikTok — solo descarga
contenido para uso propio.
