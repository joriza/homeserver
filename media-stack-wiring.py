#!/usr/bin/env python3
"""Cableado del media stack: qBittorrent en Radarr/Sonarr + Prowlarr->apps + perfil 720p."""
import json
import subprocess
import urllib.error
import urllib.request

BASE = {
    "radarr": "http://localhost:7878/api/v3",
    "sonarr": "http://localhost:8989/api/v3",
    "prowlarr": "http://localhost:9696/api/v1",
}
KEY = {}
for app in BASE:
    out = subprocess.run(
        ["docker", "exec", app, "sed", "-n", r"s/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p", "/config/config.xml"],
        capture_output=True, text=True,
    ).stdout.strip()
    KEY[app] = out
    print(f"apikey {app}: len={len(out)}")


def call(app, method, path, body=None):
    """Llamada API con reporte de error en el propio retorno."""
    req = urllib.request.Request(  # noqa: S310 - localhost fijo, esquema http intencional
        f"{BASE[app]}{path}?apikey={KEY[app]}",
        json.dumps(body).encode() if body is not None else None,
        {"Content-Type": "application/json"},
        method=method,
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))  # noqa: S310
    except urllib.error.HTTPError as err:
        raw = err.read().decode(errors="replace")[:300]
        return {"__http": err.code, "raw": raw}


def ensure_list(app, path):
    """GET que devuelve lista; dict => error reportado."""
    data = call(app, "GET", path)
    return data if isinstance(data, list) else None


# 1. Download client qBittorrent en Radarr y Sonarr
for app, cat in (("radarr", "radarr"), ("sonarr", "sonarr")):
    existing = ensure_list(app, "/downloadclient")
    if existing is None:
        print(app, "ERROR list:", call(app, "GET", "/downloadclient"))
        continue
    if any(d.get("implementation") == "QBittorrent" for d in existing):
        print(app, "qbittorrent ya configurado")
        continue
    fields = [
        {"name": "host", "value": "192.168.1.200"},
        {"name": "port", "value": 8081},
        {"name": "useSsl", "value": False},
        {"name": "username", "value": "admin"},
        {"name": "password", "value": "admin2"},
        {"name": "movieCategory" if app == "radarr" else "tvCategory", "value": cat},
    ]
    body = {
        "enable": True, "protocol": "torrent", "priority": 1,
        "implementation": "QBittorrent", "configContract": "QBittorrentSettings",
        "name": "qbittorrent", "tags": [], "fields": fields,
    }
    r = call(app, "POST", "/downloadclient", body)
    ok = isinstance(r, dict) and "id" in r
    print(app, "downloadclient ->", f"OK id={r.get('id')}" if ok else r)

# 2. Perfil de calidad: "Any" con 720p priorizado
for app in ("radarr", "sonarr"):
    profiles = ensure_list(app, "/qualityprofile")
    if profiles is None:
        print(app, "ERROR profiles:", call(app, "GET", "/qualityprofile"))
        continue
    any_prof = next((p for p in profiles if p["name"].lower() == "any"), None)
    if not any_prof:
        print(app, "no hay perfil Any:", [p["name"] for p in profiles])
        continue
    if app == "radarr":
        qs = any_prof["items"]
        def qname(q):
            return q.get("name") or q.get("quality", {}).get("name", "")
        pref = [q for q in qs if "720p" in qname(q)]
        rest = [q for q in qs if "720p" not in qname(q)]
        any_prof["items"] = pref + rest
        web720 = next((q for q in pref if qname(q) == "WEB 720p"), None)
        any_prof["cutoff"] = web720["id"] if web720 and "id" in web720 else pref[0].get("quality", {}).get("id", any_prof["cutoff"])
    else:
        def is720(item):
            blob = json.dumps(item.get("qualities", [item.get("quality", {})]))
            return "720p" in blob
        groups720 = [it for it in any_prof.get("items", []) if is720(it)]
        rest = [it for it in any_prof.get("items", []) if not is720(it)]
        any_prof["items"] = groups720 + rest
        for it in groups720:
            quals = it.get("qualities") or [it.get("quality", {})]
            if quals:
                any_prof["cutoff"] = quals[0].get("id")
                break
    r = call(app, "PUT", f"/qualityprofile/{any_prof['id']}", any_prof)
    ok = isinstance(r, dict) and r.get("id")
    print(app, "perfil Any actualizado ->", "OK" if ok else r)

# 3. Prowlarr -> Radarr/Sonarr (sincronización de indexadores)
TV_CATS = [5000, 5010, 5020, 5030, 5040, 5045, 5070]
MOVIE_CATS = [2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060]
for app, port, cats in (("radarr", 7878, MOVIE_CATS), ("sonarr", 8989, TV_CATS)):
    apps = ensure_list("prowlarr", "/applications")
    if apps is None:
        print("prowlarr ERROR apps:", call("prowlarr", "GET", "/applications"))
        break
    if any(a.get("implementationName", "").lower() == app for a in apps):
        print("prowlarr ->", app, "ya configurada")
        continue
    fields = [
        {"name": "prowlarrUrl", "value": "http://192.168.1.200:9696"},
        {"name": "prowlarrApiKey", "value": KEY["prowlarr"]},
        {"name": "baseUrl", "value": f"http://192.168.1.200:{port}"},
        {"name": "apiKey", "value": KEY[app]},
        {"name": "syncCategories", "value": cats},
    ]
    if app == "sonarr":
        fields.append({"name": "seriesType", "value": "standard"})
    fields.append({"name": "qualityProfile", "value": 1})
    body = {
        "enabled": True, "syncLevel": "fullSync", "tags": [],
        "implementation": "Radarr" if app == "radarr" else "Sonarr",
        "configContract": "RadarrSettings" if app == "radarr" else "SonarrSettings",
        "implementationName": app.capitalize(), "name": app.capitalize(), "fields": fields,
    }
    r = call("prowlarr", "POST", "/applications", body)
    ok = isinstance(r, dict) and "id" in r
    print("prowlarr ->", app, f"OK id={r.get('id')}" if ok else r)

# 4. Test de aplicaciones desde Prowlarr
apps = ensure_list("prowlarr", "/applications")
if apps is not None:
    for a in apps:
        r = call("prowlarr", "POST", "/applications/test", a)
        print("TEST", a.get("name"), "->", json.dumps(r)[:120])
print("WIRING-DONE")
