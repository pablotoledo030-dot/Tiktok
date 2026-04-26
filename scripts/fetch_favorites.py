"""Lista los videos que el usuario ha guardado en TikTok.

Soporta dos fuentes:
- "likes"     -> los del botón ❤️ "Me gusta"  (deben estar PÚBLICOS)
- "favorites" -> los del botón 🔖 "Favoritos" (privados, requieren cookies)

Variables de entorno:
    TIKTOK_USERNAME   Username sin @ (ej: pablotoledo02)
    TIKTOK_SOURCE     "likes" (default) | "favorites"
    TIKTOK_COOKIES    Contenido del cookies.txt (Netscape) — siempre mejor,
                      indispensable para favorites privados.
    TIKTOK_SEC_UID    (opcional) si está definido se usa directamente y se
                      omite el scraping del HTML del perfil. Útil cuando
                      TikTok responde con anti-bot a las IPs de CI.
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
# type=1 -> "Liked" (❤️ Me gusta) [comportamiento histórico]
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
    # Probar varios patrones que TikTok ha usado en distintas variantes del HTML
    patterns = [
        r'"secUid":"([^"]+)"',
        r'\\"secUid\\":\\"([^\\"]+)\\"',
        r'"sec_uid":"([^"]+)"',
        r'secUid=([A-Za-z0-9_\-]+)',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def fetch_sec_uid(session: requests.Session, username: str) -> str:
    # 1) Intentar HTML del perfil (clásico)
    url = PROFILE_URL.format(username=username)
    r = session.get(url, timeout=30)
    print(
        f"[fetch] GET {url} -> HTTP {r.status_code}, len={len(r.text)}",
        file=sys.stderr,
    )
    if r.status_code == 200:
        sec_uid = extract_sec_uid(r.text)
        if sec_uid:
            return sec_uid
        # Pista de debug: primeros 300 chars y si parece anti-bot
        snippet = r.text[:300].replace("\n", " ")
        print(f"[fetch] HTML sin secUid. Inicio: {snippet}", file=sys.stderr)

    # 2) Fallback: endpoint público de detalle de usuario
    detail = (
        "https://www.tiktok.com/api/user/detail/"
        f"?aid=1988&uniqueId={username}"
    )
    try:
        r2 = session.get(detail, timeout=30)
        print(
            f"[fetch] GET user/detail -> HTTP {r2.status_code}, len={len(r2.text)}",
            file=sys.stderr,
        )
        if r2.status_code == 200:
            try:
                j = r2.json()
                sec = (
                    (j.get("userInfo") or {}).get("user") or {}
                ).get("secUid")
                if sec:
                    return sec
            except json.JSONDecodeError:
                print(
                    f"[fetch] user/detail no-JSON: {r2.text[:200]}",
                    file=sys.stderr,
                )
    except requests.RequestException as exc:
        print(f"[fetch] user/detail error: {exc}", file=sys.stderr)

    raise RuntimeError(
        "No se encontró secUid. TikTok probablemente está sirviendo "
        "anti-bot a esta IP. Define TIKTOK_SEC_UID como variable de "
        "entorno (es público, no es secreto) para saltar este paso."
    )


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
        if r.status_code != 200:
            print(f"[fetch] HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            r.raise_for_status()
        try:
            data = r.json()
        except json.JSONDecodeError:
            print(f"[fetch] respuesta no-JSON: {r.text[:200]}", file=sys.stderr)
            return

        items = data.get("itemList") or []
        print(
            f"[fetch] cursor={cursor} items={len(items)} hasMore={data.get('hasMore')}",
            file=sys.stderr,
        )
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
    sec_uid_env = os.environ.get("TIKTOK_SEC_UID", "").strip()

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
        {
            "User-Agent": UA,
            "Referer": PROFILE_URL.format(username=username),
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    if sec_uid_env:
        sec_uid = sec_uid_env
        print(f"[fetch] usando TIKTOK_SEC_UID del entorno", file=sys.stderr)
    else:
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

    print(f"[fetch] total recolectado: {len(out)}", file=sys.stderr)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
