# Home Server — Documento de continuidad

> Estado migrado desde la wiki de conocimiento `D:\Desarrollo\llm-wiki` (2026-11-24). Ese repositorio queda como **fuente de consulta** (dominio `wiki/self-hosting/` + `wiki/self-hosting/decision-home-server.md`, cerrada). Este documento es el punto de partida operativo acá.
> **Ubicación actual (2026-11-25)**: sesión cerrada tras instalar stack de medios completo y cableado. Pendientes inmediatos: verificación end-to-end de la primera descarga (Matrix Generation en curso), Bazarr idiomas, Sonarr login, Tailscale.

## Pendientes priorizados (al cierre 2026-11-25)

1. **Verificar primera descarga end-to-end**: Matrix Generation estaba en cola de qBittorrent — confirmar import en Radarr y aparición en Jellyfin/TV.
2. **Bazarr**: configurar idiomas (Español Latino) para subtítulos automáticos.
3. **Sonarr**: primer acceso pide auth (mismo user/pass que Radarr: `javier` + la suya; Allowed Hosts `192.168.1.200,localhost`).
4. **Tailscale** (aprobado): acceso NAS desde afuera; requiere cuenta GitHub/Google/Microsoft del usuario para el tailnet.
5. **Router del usuario**: DNS → 192.168.1.200 (filtrado LAN completo) + verificar pool DHCP no pisa .200.
6. **Lidarr** (música, candidato) y **Readarr+Kavita** (libros, opcional) — decidir en próxima sesión.
7. **Escuela / 2º server**: Pi-hole con DHCP rango desde .150 como redundancia del ISP; usar §4 como receta.
8. **Apps solicitadas pendientes de detalles**: herdr, gentle-ai, pi-agent, freellmAPI, opencode (definir origen/repo, rol servicio-vs-CLI, API keys).
9. **Consumo eléctrico medido** ✅ (~6.3 W) — re-medir si cambia hardware.
10. **Consumo de disco**: revisar cuando biblioteca >200 GB (compresión H.265 por lotes).

## 1. Hardware y red (especificación del usuario)

| Componente | Valor |
|---|---|
| Equipo | Dell Latitude E7470 (laptop dedicada) |
| RAM | 16 GB |
| Almacenamiento | SSD **~446 GB reales** (la spec original decía 240 GB); raíz LVM 437 GB, 411 GB libres |
| IP | **192.168.1.200/24 fija por netplan** (MAC 18:db:f2:5a:00:4d, gateway 192.168.1.1). La .30 original DHCP quedó obsoleta |
| Wi-Fi | **Desactivado permanentemente** (eliminado del netplan; solo Ethernet) |
| ISP | **CGNAT** — sin port forwarding; todo lo externo por túnel (Tailscale / Cloudflare Tunnel) |
| Tapa / pantalla física | Cierre de tapa: **sin acción** (`HandleLidSwitch=ignore`, `/etc/systemd/logind.conf.d/99-lid.conf`). Pantalla: se apaga a los **5 min** (`consoleblank=300` en GRUB, activo desde 2026-11-25) |

## 2. Arquitectura decidida (contra la spec)

| Req | Componente | Estado |
|---|---|---|
| Base | Ubuntu Server LTS + Docker Compose, **CasaOS** como panel (→ Portainer al crecer) | ✅ **LISTA Y VERIFICADA** |
| 3.1 DNS local | Pi-hole (LAN) — la fase externa ≤10 usuarios fue RETIRADA por decisión del usuario | ✅ instalado; filtrando el desktop; LAN total pendiente (router) |
| 3.2 Share LAN | Samba: `public` anónimo read-only + `write list = javier` (solo él puede cargar); `privado$` oculto solo javier | ✅ `\\192.168.1.200\public` + `\\192.168.1.200\privado$` |
| 3.2 Archivos remotos | Nextcloud (clientes móvil/escritorio) | pendiente |
| 3.3 Multimedia | Jellyfin | ✅ completo: `http://192.168.1.200:8096`, clientes activos (desktop, celular, Android TV — TV requirió conexión manual del server) |
| Media carga | Samba share `media`: `\\192.168.1.200\media` (peliculas/series/musica/fotos; lectura anónima, escritura solo javier) | ✅ |
| 3.4 Media automation | Radarr + Sonarr + Prowlarr + qBittorrent + Bazarr (stack en `/opt/media-stack/docker-compose.yml`) | ✅ contenedores corriendo y UIs activas — config de app (indexadores, perfiles de calidad, API keys entre apps) pendiente |
| 3.5 Apps web públicas | Contenedor por app + Nginx Proxy Manager o Traefik, expuesto por **Cloudflare Tunnel** | pendiente |
| Backups | Regla 3-2-1 obligatoria (RAID ≠ backup) | transversal |

## 3. Accesos y credenciales (server: javier@192.168.1.200)

| Servicio | Acceso |
|---|---|
| SSH | `ssh javier@192.168.1.200` — clave, **sudo NOPASSWD** (`/etc/sudoers.d/javier`) |
| CasaOS | `http://192.168.1.200` (cuenta creada por el usuario) |
| Pi-hole admin | `http://192.168.1.200:8080/admin` — sin usuario; password en `/root/pihole-web-password.txt` del server |
| Samba | `\\192.168.1.200\public` (anónimo RO + write javier) · `\\192.168.1.200\privado$` (oculto, javier) · `\\192.168.1.200\media` (biblioteca Jellyfin) |
| Media stack | Radarr `:7878` · Sonarr `:8989` · Prowlarr `:9696` · qBittorrent `:8081` · Bazarr `:6767` · FlareSolverr `:8191` (inútil en Prowlarr v3, ver abajo) |
| UFW | activo: 22, 53 (tcp+udp), 80, 443, 8080, 445 (perfil Samba) |

## 4. Procedimiento de despliegue (reproducible — guía para un 2º server)

Secuencia exacta ejecutada en este server; reutilizable tal cual en el próximo equipo:

1. **Ubuntu Server LTS** por USB, Ethernet, anotar IP.
2. **Acceso del agente sin claves**: copiar clave SSH pública del equipo de gestión a `~/.ssh/authorized_keys` del usuario admin; crear `/etc/sudoers.d/<usuario>` con `<usuario> ALL=(ALL) NOPASSWD:ALL` y `chmod 440`. (Se hace UNA vez, manualmente.)
3. **UFW** (no viene preinstalado en Ubuntu 26.04 mínima): `apt install ufw` → `ufw allow OpenSSH` → `ufw --force enable`. Abrir puertos solo cuando cada servicio lo necesite.
4. **IP fija por netplan** (no DHCP ni reserva del router): `addresses`, `routes: via gateway`, `nameservers` públicos (NUNCA apuntar el server a su propio Pi-hole: riesgo de bucle). `sudo netplan apply` con la conexión en riesgo controlado; reconectar por SSH a la IP nueva.
5. **LVM completo**: el instalador asigna solo ~100 GB; `lvextend -l +100%FREE /dev/<vg>/<lv> && resize2fs` para tomar todo el disco ANTES de cargar datos.
6. **Docker**: `apt install docker.io docker-compose-v2` → `systemctl enable --now docker` → hello-world → `usermod -aG docker <usuario>`.
7. **CasaOS**: `curl -fsSL https://get.casaos.io | sudo bash`. Abrir 80/443 en UFW.
8. **Wi-Fi off** (si el equipo tiene): bajar interfaz + eliminar bloque `wifis` del netplan. Evita rutas ambiguas con Docker.
9. **Apps de a una**, por compose en `/opt/<app>/docker-compose.yml`, cuidando puertos 80/8080/443.

### Pitfalls aprendidos (2026-11-25, server 1)

- **systemd-resolved retiene :53** en Ubuntu → `/etc/systemd/resolved.conf.d/99-no-stub.conf` con `DNSStubListener=no` + restart, ANTES de Pi-hole.
- **Pi-hole v6 descarta clientes fuera de su subred Docker** → `FTLCONF_dns_listeningMode: "all"` en el compose (síntoma: queries llegan por tcpdump, cero respuesta).
- **Windows no respeta orden de DNS**: con DNS secundario público, el filtrado es parcial (~50%); para probar, DNS único.
- **WARP pisa el DNS** de Windows (127.0.2.2): mientras esté conectado, Pi-hole no filtra ese equipo. Ver decisión D-2026-11-25-C.
- **PowerShell no soporta heredoc** (`<<EOF`) en comandos SSH remotos → usar una línea con pipes o `ssh -t`.
- **Ubuntu 26.04 mínima no trae** `ufw`, `ping`, `tcpdump`, `nslookup` — instalar a demanda.
- El comando final `ping -c1 router && echo OK` marca FAIL solo porque falta el binario; verificar conectividad con `ip route` o curl.

## 5. Log de implementación (cronológico)

- **2026-11-24**: decisión migrada desde la wiki; plan de 7 pasos comunicado.
- **2026-11-25**: instalación de Ubuntu 26.04.1 hecha por el usuario (IP inicial .30 por DHCP).
- **2026-11-25**: sudo NOPASSWD para `javier` (acceso de agente sin claves).
- **2026-11-25**: UFW instalado/activo (solo 22); Docker + Compose v2 verificados; `javier` en grupo docker.
- **2026-11-25**: LVM extendido 98→437 GB; descubierto que el SSD real es ~446 GB.
- **2026-11-25**: CasaOS v0.4.15 instalado (puerto 80); UFW +80/443. Wi-Fi desactivado permanente (netplan).
- **2026-11-25**: Pi-hole instalado por compose en `/opt/pihole` (:53 DNS, :8080 admin); stub de resolved desactivado; UFW +53/8080.
- **2026-11-25**: verificación Pi-hole desde desktop falló → tcpdump reveló queries sin respuesta → fix `FTLCONF_dns_listeningMode: "all"`. Bloqueo confirmado (doubleclick.net → 0.0.0.0).
- **2026-11-25**: prueba Pi-hole solo en desktop Windows (DNS manual en adaptador; sin tocar el router). Detectado que WARP pisaba el DNS.
- **2026-11-25**: IP fija 192.168.1.200/24 por netplan (reemplaza DHCP .30). CasaOS y Pi-hole verificados en la nueva IP; desktop actualizado a DNS .200 y bloqueo re-verificado.
- **2026-11-25**: verificación end-to-end de Samba (desktop escribe public → celular de la LAN lee). Ajuste `write list = javier` en public. Share `media` creado (`/srv/media` con peliculas/series/musica/fotos) para la biblioteca.
- **2026-11-25**: Prowlarr v3.x **eliminó FlareSolverr** — 1337x/EZTV inutilizables (Cloudflare). Agregados por API y verificados: **YTS + The Pirate Bay + LimeTorrents** (búsqueda real: 245 resultados para "matrix"). Aprendizaje: agregar indexadores por API requiere GET `/indexer/schema`, setear `enabled/priority/tags/appProfileId=1` y POST del schema completo (los POST con cuerpo mínimo fallan con validaciones). Normalización de audio completada: **9/9 OK, 0 errores**, originales eliminados, biblioteca = 10 pelis `"- VOLUMEN"` (18 GB).
- **2026-11-25 (qBittorrent)**: password final `admin/admin2`. Saga: qBittorrent v5.3 guarda la clave como `Password_PBKDF2` (SIN prefijo) dentro de la sección `[WebUI]` del conf; PBKDF2-HMAC-SHA512, 100k iteraciones, salt 16B + key 64B, base64 (`@ByteArray(salt:key)`). Los `docker compose stop/start` desde el host NO reiniciaban el proceso (usar `docker restart <contenedor>`); qBittorrent banea IPs 1h tras 5 fallos de login (reiniciar contenedor limpia bans y rota la password temporal); API `setPreferences` con `webui_password` devolvía 200 sin aplicar — editar el conf directo es lo confiable. Verificar hash OFFLINE antes de escribir.
- **2026-11-26 (Bazarr completo)**: Bazarr quedó cableado y funcionando: conectado a Radarr (ip `radarr` por red compose, apikey seteada vía API settings con claves `settings-radarr-*`), perfil "Español Latino" (id 1) asignado a todas las películas, proveedores activos: opensubtitlescom (cuenta `joriza_` del usuario, migrada del .org viejo) + subtitulamostv + subdl. Primera descarga real: 4/4 películas con subtítulo es-MX (.srt) junto al video. El username del usuario en opensubtitles.com es `joriza_` (con guion bajo) y su contraseña vieja del .org de 2008 no servía: hubo que restablecerla en el sitio nuevo. La IP CGNAT del server a veces recibe 503 de la WAF de OpenSubtitles — si fallan descargas futuras, resetear throttling (POST /api/providers?action=reset) y reintentar.
- **2026-11-26 (audio latino)**: Custom Format "Audio Latino" (id 1) creado en Radarr: regex de título `(?i)(latino|lat\b|sub[ ._-]?spa|\b(es|esp|spa)[ ._-]?(audio|ac3|dts|lat)\b)` con exclusión de idiomas no deseados; asignado al perfil "Any" con score 300. Nota API: el POST de customformat exige `name` en cada specification; el qualityprofile usa la key `format` (no `id`) en formatItems. Radarr agrega el CF al perfil automáticamente con score 0 al crearlo. Reemplazos de torrents muertos: Cold Storage re-agarrada con WEBRip x265 de 403 semillas (agregada por link Prowlarr directo a qB con category=radarr, import OK); Oak Street y War Machine completadas en 1080p liviano. Matrix Generation sigue stalledDL (enjambre YTS no conecta); pendiente alternativa.
- **2026-11-26**: Política de tamaños aprobada por el usuario (máx 1080p, ~1-3 GB): en Radarr se deshabilitaron TODAS las calidades 2160p y Remux-1080p (en el perfil "Any", items PUT qualityprofile/1), y se aplicaron límites de tamaño por calidad (qualitydefinition, MB/min): 720p max 12, 1080p max 20 (≈4.8 GB por película de 2 h; default 100 era el que dejaba pasar Bluray de 12 GB). Nota de API: qualitydefinition/update bulk devuelve 400/409; hacer PUT individual por id funciona. Lecciones: el push de Radarr (/release/push) exige el objeto release COMPLETO (como el schema de Prowlarr) pero el envío a qBittorrent se puede perder; ruta confiable = descargar el link de Prowlarr y POST directo a qB /torrents/add con category=radarr. Conectividad P2P verificada OK (torrent Ubuntu 8.4 MB/s); los enjambres chicos (<15 semillas) tardan en conectar o están muertos. qBittorrent: límites subidos a max_active_downloads=10, max_active_torrents=12, uploads=5. Bazarr: perfil de idioma creado por sqlite directo (la API v1.6.2 no tiene POST de profiles): table_languages_profiles id=1 "Español Latino" (code3=spl), idioma habilitado en table_settings_languages; falta conectárselo a películas/series y probar descarga real.
- **2026-11-25**: Cableado completo del stack por API (`media-stack-wiring.py` en este repo): qBittorrent cliente de descargas en Radarr (categoría `radarr`) y Sonarr (`sonarr`); perfiles "Any" con 720p priorizado (cutoff WEB 720p); Prowlarr→Radarr/Sonarr conectados y tests OK (sincronización de indexadores automática). **Pendiente**: Bazarr (idiomas ES).

## 6. Decisiones registradas

- **D-2026-11-24-A**: retirado el requisito de DNS externo ≤10 usuarios (3.1 fase 2).
- **D-2026-11-24-B**: Dokploy descartado como base — opción futura para despliegue por Git (anexo en la wiki).
- **D-2026-11-24-C**: implementación migrada a este proyecto; `llm-wiki` queda como fuente de consulta.
- **D-2026-11-25-A**: sudo NOPASSWD para el usuario admin en vez de pasar claves al agente (variante restrictiva con lista de binarios disponible si se pide).
- **D-2026-11-25-B**: no crear usuario aparte para el agente — `javier` ya es admin; menos superficie y trazabilidad simple.
- **D-2026-11-25-C**: convivencia WARP/Pi-hole en el desktop — **gana WARP cuando está conectado** (el usuario lo usa para no ser flagueado por IP). Adaptador con DNS Pi-hole fijo: sin WARP → filtra; con WARP → túnel sin filtrado local. Auto-inicio de WARP deshabilitable desde Administrador de tareas → Aplicaciones de inicio. El resto de la LAN filtra vía router cuando se cambie el DNS del router.
- **D-2026-11-25-D**: IP fija por netplan (.200) en vez de reserva DHCP del router — el usuario prefiere no tocar el router por ahora. Riesgo aceptado: verificar que .200 esté fuera del pool DHCP antes de confiar el rol a largo plazo.
- **D-2026-11-25-E**: prueba de Pi-hole acotada al desktop (DNS manual por equipo), filtrado LAN completo diferido.

## 7. Pendientes

**Del usuario (router)**: confirmar pool DHCP no pisa .200; DNS del router → 192.168.1.200 cuando quiera filtrado LAN completo.

**Del plan (en orden)**: ~~Samba~~ ✅ ~~Jellyfin~~ ✅ ~~Media stack server-side~~ ✅ → **config de apps del stack** (indexadores/calidad — requiere decisiones del usuario) → **Tailscale** (acceso NAS desde afuera, aprobado) → ~~Nextcloud~~ POSTERGADO → NPM/Traefik + Cloudflare Tunnel.

**Solicitadas por el usuario (2026-11-25, pendientes de definir detalles)**: herdr, gentle-ai, pi-agent, freellmAPI, opencode. Antes de instalar cada una: origen/descarga (¿repo propio del usuario o releases públicos?), puertos, si requieren API keys/secretos, y si corren como contenedor compose (preferido) o binario de sistema.

**Lagunas de conocimiento (requieren ingesta en la wiki)**:
1. Stack de torrents/series/subtítulos ES-LatAm (req 3.4).
2. ACL fina de Samba (share privado oculto seguro).
3. Laptop como servidor 24/7 (tapa cerrada, batería, consumo).
4. Cloudflare Tunnel vs. alternativas para apps públicas bajo CGNAT.

**Decisión aplazada**: CasaOS — mantener por ahora como interfaz de emergencia del usuario (panel de contenedores/recursos sin terminal). Evaluar desinstalación (`casaos-uninstall`, limpio y oficial) cuando el flujo agente+compose esté consolidado o si deja de usarse; el §4 funciona sin CasaOS y el próximo server puede no incluirlo.

### Tratamiento de media (fórmulas probadas / en evaluación)

**Diagnóstico previo (dentro del contenedor jellyfin, ffprobe/ffmpeg en `/usr/lib/jellyfin-ffmpeg/`):**
```bash
# FPS de cabecera vs real (detecta archivos que ahogan navegadores)
docker exec jellyfin /usr/lib/jellyfin-ffmpeg/ffprobe -v error -select_streams v:0 \
  -show_entries stream=r_frame_rate,avg_frame_rate -of csv=p=0 'ARCHIVO'
# Loudness real (objetivo streaming: I=-16 LUFS, TP=-1.5 dBTP)
docker exec jellyfin /usr/lib/jellyfin-ffmpeg/ffmpeg -hide_banner -t 300 -i 'ARCHIVO' \
  -map 0:a:0 -af loudnorm=I=-16:TP=-1.5:print_format=summary -f null - 2>&1 | grep -E 'Input'
```

**1. Audio bajo — sube volumen sin tocar el video (probado ✅ en Matrix; ~5 min/peli):**
```bash
# desde el server; contenedor temporal con disco rw (Jellyfin ve /srv/media read-only)
sudo docker run --rm -v /srv/media:/m:rw --entrypoint '' jellyfin/jellyfin:latest \
  /usr/lib/jellyfin-ffmpeg/ffmpeg -v error -i 'ORIGEN' \
  -map 0:v -c:v copy -map 0:a:0 -c:a aac -b:a 192k \
  -af 'loudnorm=I=-16:TP=-1.5:LRA=17:measured_I=<I>:measured_TP=<TP>:measured_LRA=<LRA>:measured_thresh=<TH>:linear=true' \
  -movflags +faststart 'SALIDA - VOLUMEN.mp4'
```
Caso real: Matrix venía a **-23.8 LUFS** (8 dB bajo estándar) → ganancia lineal +7.8 dB, video bit-a-bit idéntico.

**2. Compresión con py-video-converter (proyecto del usuario, EN EVALUACIÓN ⏳):**
- Herramienta: `d:\Desarrollo\py-video-converter-v2-tmp` (HEVC CRF 28, salida `<stem>_m.mp4` junto a la fuente; corre en Windows, apunta al share por SMB con letra de unidad: `net use M: \\192.168.1.200\media /user:javier <pw>`).
- Política del proyecto por defecto baja a **480p** (demasiado para TV); usar `--res max720 --crf 27` como compromiso (est. ~700MB–1GB por peli de 2GB).
- Tiempo: **2–4 h por película** (libx265 CPU de desktop).
- Reproducción HEVC: Android TV/celular por hardware OK; navegador desktop puede forzar transcodificación del server (Dell no está para eso).
- **Orden correcto del pipeline si se adopta**: 1º loudness (audio), 2º compresión `_m` — así el audio corregido viaja en el archivo final.
- Estado: pendiente de verificación visual de la primera peli (Moonfall) en Android TV.

**Regla de ingesta adoptada**: contenido nuevo → verificar FPS de cabecera (`r_frame_rate` vs `avg_frame_rate`); cabecera rota (ej. 360 fps) → corregir antes de catalogar. Carga solo por `\\192.168.1.200\media` (escritura javier); Jellyfin lee read-only.

## 8. Referencias en la wiki fuente

- `wiki/self-hosting/decision-home-server.md` — decisión cerrada + anexo CasaOS vs. Dokploy.
- `wiki/self-hosting/self-hosting.md` — hub del dominio (pilar 4: qué self-hostear y qué no).
- `wiki/self-hosting/casaos.md`, `docker-homelab.md`, `pi-hole.md` — conceptos nucleares.
- Resúmenes clave: `resumen-he-cancelado-servicios-streaming-servidor-domestico-gctech`, `resumen-he-clonado-google-fotos-dropbox-chatgpt-en-local-enreta-domotica`, `resumen-home-servers-en-2025-pocho-labs`, `resumen-WL617-servidor-casa-cancelado-pepotech`, `resumen-WL734-nube-en-casa-nas-scpc`, `resumen-15-docker-containers-home-lab-virtualizationhowto`.

## 9. Advertencias activas

- Laptop 24/7: consumo sin medir — medir antes de confiar el rol permanente.
  ✅ **Medido (2026-11-25)**: ~7 W sistema completo en reposo (CPU ~2.2 W; governor `powersave`/`intel_pstate`, pantalla apagada, Wi-Fi off). `powertop --auto-tune` aplicado y persistido como servicio `powertop-autotune.service` (multi-user) → ~6.3–6.5 W. Suspend+WOL **descartado** (fricción WOL, DNS crítico para la LAN, ahorro insignificante ~$3/año). Batería 100% sirve de UPS natural.
- `docker image prune` periódico (SSD 437 GB, 411 libres).
- Documentar todo lo que se toca (este documento es el registro).
