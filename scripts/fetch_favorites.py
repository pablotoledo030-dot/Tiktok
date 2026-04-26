"""Lista los videos que el usuario ha guardado en TikTok.

Soporta dos fuentes:
- "likes"     -> los del botón ❤️ "Me gusta"  (deben estar PÚBLICOS)
- "favorites" -> los del botón 🔖 "Favoritos" (privados, requieren cookies)

Variables de entorno:
    TIKTOK_USERNAME   Username sin @ (ej: pablotoledo02)
    TIKTOK_SOURCE     "likes" (default) | "favorites"
    TIKTOK_COOKIES    Contenido del cookies.txt (Netscape) — siempre mejor,
                      indispensable para favorites privados.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Iterator
from urllib.parse import urlencode

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

PROFILE_URL = "https://www.tiktok.com/@{username}"

# La API de TikTok web reutiliza un mismo endpoint para likes y favorites
# y los distingue con un parámetro:
#   type=1  -> "Liked" (❤️ Me gusta) [comportamiento histórico]
# La colección de marcadores 🔖 ("Favoritos") usa un endpoint distinto.
LIKES_API = "https://www.tiktok.com/api/favorite/item_list/"
FAVORITES_API = "https://www.tiktok.com/api/user/collect/item_list/"


def load_cookiejar(cookies_text: str) -> MozillaCookieJar:
    jar = MozillaCookieJar()
    tmp = Path("/tmp/tt_cookies.txt")
    tmp.write_text(cookies_text)
    jar.load(str(tmp), ignore_discard=True, ignore_expires=True)
    return jar


def extract_sec_uid(html: str) -> str | None:
    m = re.search(r'"secUid":"([^"]+)"', html)
    return m.group(1) if m else None


def diagnose_html(html: str) -> str:
    """Devuelve una pista de por qué falla el HTML de perfil."""
    low = html.lower()
    if len(html) < 500:
        return f"respuesta sospechosamente corta ({len(html)} bytes)"
    if "captcha" in low or "verify" in low and "human" in low:
        return "TikTok devolvió un challenge/captcha (típico desde IP datacenter)"
    if "blocked" in low or "access denied" in low:
        return "TikTok ha bloqueado la IP del runner"
    if "couldn't find this account" in low or "no se encontró" in low:
        return "username no existe o perfil eliminado"
    if "<title>tiktok</title>" in low and "secuid" not in low:
        return "TikTok devolvió la página genérica (sin datos del perfil) — anti-bot"
    return "razón desconocida; revisa el snippet de HTML que sigue"


def fetch_sec_uid(session: requests.Session, username: str) -> str:
    url = PROFILE_URL.format(username=username)
    r = session.get(url, timeout=30)
    print(f"[fetch] perfil GET {url} -> HTTP {r.status_code} ({len(r.text)} bytes)",
          file=sys.stderr)
    r.raise_for_status()
    sec_uid = extract_sec_uid(r.text)
    if not sec_uid:
        diag = diagnose_html(r.text)
        snippet = r.text[:400].replace("\n", " ")
        raise RuntimeError(
            "No se encontró secUid en el HTML del perfil.\n"
            f"  Diagnóstico: {diag}\n"
            f"  Primeros 400 chars: {snippet!r}\n"
            "  Soluciones:\n"
            "    1. Asegúrate de que la pestaña 'Me gusta' está PÚBLICA en TikTok.\n"
            "    2. Añade el secret TIKTOK_COOKIES con tus cookies del navegador.\n"
            "    3. Si ya tienes cookies, regenéralas (caducan cada 30-60 días)."
        )
    return sec_uid


def iter_items(
    session: requests.Session, api_url: str, sec_uid: str
) -> Iterator[dict]:
    cursor = "0"
    while True:
        params = {
            "aid": "1988",
            "app_language": "en",
            "app_name": "tiktok_web",
            "channel": "tiktok_web",
            "device_platform": "web_pc",
            "count": "30",
            "cursor": cursor,
            "secUid": sec_uid,
        }
        r = session.get(f"{api_url}?{urlencode(params)}", timeout=30)
        print(f"[fetch] api GET cursor={cursor} -> HTTP {r.status_code} "
              f"({len(r.text)} bytes)", file=sys.stderr)
        if r.status_code != 200:
            print(f"[fetch] cuerpo: {r.text[:300]}", file=sys.stderr)
            r.raise_for_status()
        try:
            data = r.json()
        except json.JSONDecodeError:
            print(f"[fetch] respuesta no-JSON (probable challenge anti-bot):"
                  f" {r.text[:300]}", file=sys.stderr)
            return

        items = data.get("itemList") or []
        if not items and cursor == "0":
            status_code = data.get("statusCode") or data.get("status_code")
            status_msg = data.get("statusMsg") or data.get("status_msg") or ""
            print(f"[fetch] itemList vacío en primera página. "
                  f"statusCode={status_code} statusMsg={status_msg!r}. "
                  "Causas típicas: pestaña 'Me gusta' no es pública, "
                  "cookies caducadas, o IP del runner bloqueada por TikTok.",
                  file=sys.stderr)
        for it in items:
            yield it

        if not data.get("hasMore"):
            return
        cursor = str(data.get("cursor") or "0")
        if cursor == "0":
            return
        time.sleep(0.5)


def main() -> int:
    username = os.environ.get("TIKTOK_USERNAME", "pablotoledo02").lstrip("@")
    source = os.environ.get("TIKTOK_SOURCE", "likes").lower()
    cookies = os.environ.get("TIKTOK_COOKIES", "")

    if not username:
        print("Falta TIKTOK_USERNAME", file=sys.stderr)
        return 2
    if source not in {"likes", "favorites"}:
        print("TIKTOK_SOURCE debe ser 'likes' o 'favorites'", file=sys.stderr)
        return 2

    api_url = LIKES_API if source == "likes" else FAVORITES_API

    session = requests.Session()
    if cookies:
        session.cookies = load_cookiejar(cookies)
    session.headers.update(
        {"User-Agent": UA, "Referer": PROFILE_URL.format(username=username)}
    )

    sec_uid = fetch_sec_uid(session, username)
    print(f"[fetch] source={source} secUid={sec_uid}", file=sys.stderr)

    out = []
    for it in iter_items(session, api_url, sec_uid):
        vid = it.get("id")
        author = (it.get("author") or {}).get("uniqueId", "")
        if not vid or not author:
            continue
        out.append(
            {
                "id": vid,
                "url": f"https://www.tiktok.com/@{author}/video/{vid}",
                "author": author,
                "desc": it.get("desc", ""),
                "create_time": it.get("createTime"),
                "duration": (it.get("video") or {}).get("duration"),
            }
        )

    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
