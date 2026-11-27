# NEXORA Studio — HTTP API contract

Base: same origin. JSON in/out. All times are **epoch seconds (float, UTC)** — the UI formats them in `Asia/Bangkok`.
Auth: cookie `nx_sid` (HttpOnly). Every non-GET request must send header `X-CSRF-Token: <csrf>` (csrf comes from
`GET /api/auth/session`). Errors: HTTP 4xx/5xx with body `{"error": "human message", "code": "machine_code"}`.
`401` => show login. `403` with code `read_only` => viewer role tried to write. `429` => rate limited (`Retry-After` header).
Roles: `admin` (everything) and `viewer` (GET only).

Enums
- platform: `youtube | facebook | tiktok`
- category: `Anime | Donghua | Cartoon | 3D Animation | International Movies`
- stages (in order): `research, script, voice, srt, assets, timeline, render, qc, publish, notify`
- job.status: `queued | running | done | failed | cancelled`
- project.status: `draft | queued | running | paused | failed | completed | ready_to_publish | published | cancelled`
- file.kind: `source | script | script_txt | audio_mp3 | audio_wav | srt_en | srt_my | scenes | video | metadata | qc | credits`
- format: `landscape_16_9 | vertical_9_16 | square_1_1 | portrait_4_5`
- resolution: `720p | 1080p | 1440p | 2160p`

## Auth
- `GET /api/auth/session` → `{configured:bool, authenticated:bool, role:"admin"|"viewer"|null, csrf:string|null}`
  (`configured:false` = server has no NEXORA_ADMIN_PASSWORD set; show a setup notice)
- `POST /api/auth/login` `{password}` → `{role, csrf}` (sets cookie)
- `POST /api/auth/logout` → `{ok:true}`

## Dashboard / system
- `GET /api/dashboard` →
```
{ now:float, tz:"Asia/Bangkok",
  backend:{ok:true, version:str, uptime_s:float, studio_workers:bool, db_schema:int},
  telegram:{configured:bool, connected:bool, bot_username:str|null, webhook_url:str|null, pending_updates:int|null, error:str|null, chat_configured:bool},
  providers:[{id:"openai"|"gemini", configured:bool, model:str, primary:bool, last_ok:float|null, last_error:str|null, last_error_at:float|null, calls:int, failures:int}],
  automation:{state:"stopped"|"running"|"paused", schedule:"HH:MM", next_run:float|null, last_run_date:str|null, today:{date:str, picks:[{platform, title, category, project_id}]}},
  jobs:{queued:int, running:int, failed:int, done:int, cancelled:int},
  recent_projects:[Project], recent_videos:[{project_id, title, platform, file_id, size, duration, created}],
  recent_errors:[{ts, job_id, project_id, stage, platform, msg}],
  running_jobs:[Job & {project_title:str}],
  alerts:[{level:"warn"|"error"|"info", code:str, msg:str}],
  resources:{ disk_free_gb:float, disk_total_gb:float, data_dir_gb:float, mem_free_mb:int|null, cpu_count:int, ffmpeg:bool, gpu:bool } }
```
- `GET /api/system` → `{ffmpeg:{ok,version}, ffprobe:bool, cpu_count, mem_total_mb, mem_free_mb, disk:{free_gb,total_gb}, gpu:{available:bool, note:str},
   persistence:{persistent:bool, data_dir:str, note:str}, executor:{can_render_local:bool, reasons:[str]}, resolutions:[{id, supported:bool, reason:str|null}],
   env:[{name, present:bool, purpose:str, required_for:str}], timezone:"Asia/Bangkok", python:str, version:str}` (env values are NEVER returned)

## Research
- `GET /api/research/search?q=TITLE&category=` → `{results:[{title, original_title, year, country, category, genres:[str], kind, catalog, url, source_urls:[str], excluded:bool, exclusion_reason:str|null}]}`
- `POST /api/research/verify` `{title, year?, category?, platform}` → `{verified:bool, status:"verified"|"insufficient_sources"|"not_found"|"excluded", title, original_title, year, country, category, genres, wiki_url, plot_chars:int, sources:[{name,url}], views_30d:int, checks:[{name, ok:bool, detail:str}], source_id:str}`
  (`source_id` is a server cache key you can pass to POST /api/projects as `source_id`)
- `GET /api/research/trends?category=` → `{category, items:[{title, year, country, popularity, catalog, url, used_before:bool}], fetched_at}`
- `GET /api/research/today` → `{date, picks:[{platform, title, category, year, sources:[str], project_id|null}], distinct:bool}`

## Projects
Project: `{id, platform, date:"YYYY-MM-DD", title, category, year, country, status, stage:str|null, progress:0-100, origin:"auto"|"manual", config:ProjectConfig, error:str, created, updated, files:[File]}`
ProjectConfig: `{target_min:number, format, resolution, voice:str, voice_profile:str, srt_langs:["en","my"], burn_subs:"en"|"none", cta:str, publish_mode:"draft"|"auto", export_wav:bool, use_assets:bool}`
File: `{id, project_id, kind, name, size:int, duration:float|null, created, download_url:str}`
- `GET /api/projects?platform=&date=&status=&limit=` → `{projects:[Project], total:int}`
- `POST /api/projects` `{title, platform, category?, source_id?, config?:Partial<ProjectConfig>, autostart?:bool}` → `Project`
- `GET /api/projects/{id}` → `{project:Project, jobs:[Job], assets:[Asset], logs:[{ts,level,msg,job_id,stage}], source:{...}|null}`
- `DELETE /api/projects/{id}?confirm=1` → `{ok:true, deleted_files:int}` (400 without confirm=1)
- `POST /api/projects/{id}/run` `{from_stage?:stage, force?:bool}` → `{ok:true, job:Job}` (re-runs from a stage; invalidates downstream outputs)
- `POST /api/projects/{id}/cancel` → `{ok:true}`
- `GET /api/projects/{id}/script` → `{sections:[{title, kind, items:[{my, en}]}], provider:str|null, verified:bool, sources:[{name,url}], stats:{sentences, my_chars, est_minutes}, edited:bool}` (404 code `no_script` if none)
- `PUT /api/projects/{id}/script` `{sections}` → same shape (validates; marks edited; invalidates voice+later stages)
- `POST /api/projects/{id}/script/regenerate` `{}` → `{ok:true, job:Job}`
- `GET /api/projects/{id}/subtitles` → `{cues:[{i, start, end, my, en}], duration:float|null, audio_url:str|null, srt:{en:{ok,cues,issues:[str]}, my:{...}}}`
- `PUT /api/projects/{id}/subtitles` `{cues:[{start,end,my,en}]}` → same shape (validates ordering/overlap; rewrites SRT files)
- `POST /api/projects/{id}/subtitles/shift` `{seconds:number}` → same shape
- `GET /api/projects/{id}/files` → `{files:[File], total_size:int}`
- `GET /api/files/{id}/download` → file bytes (supports Range, attachment disposition; `?inline=1` for audio/video preview)
- `DELETE /api/files/{id}?confirm=1` → `{ok:true}`
- `GET /api/projects/{id}/timeline` → `{scenes:[{i, start, end, section, asset_id:int|null, asset_title:str|null, label:str}], total:float, has_scenes:bool}`
- `GET /api/projects/{id}/publish` → `{mode, status:"not_ready"|"draft_ready"|"uploaded"|"verified"|"failed"|"unavailable", url:str|null, detail:str, metadata:{title,description,tags,cta}|null}`

## Jobs
Job: `{id, project_id, platform, stage, status, attempts, max_attempts, progress:0-100, step:str, error:str, trigger:"auto"|"manual"|"retry"|"system", created, started, finished, not_before, executor:"local"}`
- `GET /api/jobs?status=&platform=&project_id=&limit=` → `{jobs:[Job & {project_title}], counts:{queued,running,failed,done,cancelled}}`
- `GET /api/jobs/{id}` → `{job:Job, logs:[{ts,level,msg}]}`
- `POST /api/jobs/{id}/retry` → `{ok:true, job:Job}`
- `POST /api/jobs/{id}/cancel` → `{ok:true}`
- `GET /api/queues` → `{queues:{youtube:{queued,running,failed,current:Job|null}, facebook:{...}, tiktok:{...}}, render_slot:{busy:bool, job_id:int|null}}`

## Platforms
- `GET /api/platforms` → `{platforms:{youtube:PlatformConfig, facebook:..., tiktok:...}, cta_defaults:{youtube_url, facebook_url}, rules:{youtube:{min:46,max:60}, facebook:{min:46,max:60}, tiktok:{min:4,max:7}}}`
  PlatformConfig: `{enabled:bool, target_min, format, resolution, voice, voice_profile, srt_langs, burn_subs, cta, publish_mode, export_wav, use_assets}`
- `PUT /api/platforms/{platform}` PlatformConfig partial → PlatformConfig (400 if target outside rules, or TikTok CTA lacks both channel URLs)
- `GET /api/platforms/status` → `{platforms:{youtube:{publish_ready:bool, method:"api"|"draft", missing:[env names], note}, ...}}`

## Voice studio
- `GET /api/voice/presets` → `{presets:[{id, label, gender:"female"|"male", engine:"edge-tts", voice:"my-MM-NilarNeural", note}], offline_fallback:{available:bool, note}, gpu:{configured:bool, clone_supported:bool, note:str}}`
- `POST /api/voice/preview` `{text(<=300 chars), voice}` → `{ok, engine:"edge-tts"|"gtts"|"offline-espeak", quality:"standard"|"basic"|"low", duration:float, audio_url:str, note:str}`
- `GET /api/voice/profiles` → `{profiles:[{name, size, ext, created, duration:float|null, owner, used_for_synthesis:bool}], clone:{mode:"reference_conditioned_synthesis"|"unavailable", note:str}}`
- `POST /api/voice/profiles` multipart (`name`, `consent:"yes"`, `file`) → `{ok, profile}` (file validated: ogg/mp3/wav/m4a/flac, <=25 MB, magic bytes + ffprobe)
- `DELETE /api/voice/profiles/{name}?confirm=1` → `{ok:true}`
- `GET /api/voice/profile-audio/{name}` → audio bytes (preview of the uploaded sample)
- `GET /api/voice/settings` / `PUT /api/voice/settings` `{default_voice, default_profile, rate, pitch}` → same

## Assets (legal sources)
Asset: `{id, project_id, origin:"commons"|"openverse"|"upload", title, page_url, file_url, local_path:str, license, license_url, attribution, attribution_required:bool, verified:bool, note, width, height, created}`
- `GET /api/assets/search?q=&source=commons|openverse|all` → `{results:[Asset-like + {allowed:bool, reject_reason:str|null, thumb_url}]}`
- `POST /api/projects/{id}/assets` `{file_url, origin, title, page_url, license, license_url, attribution}` → Asset (server re-verifies license against allow-list and downloads; 422 `license_rejected`)
- `POST /api/projects/{id}/assets/upload` multipart (`file`, `license`:"own-work"|"cc0"|"cc-by"|"cc-by-sa"|"public-domain", `attribution`, `declaration:"yes"`) → Asset
- `DELETE /api/assets/{id}?confirm=1` → `{ok:true}`
- `GET /api/assets/{id}/image` → image bytes
- `GET /api/assets/policy` → `{allowed_licenses:[str], rules:[str]}`

## Automation
- `GET /api/automation` → `{state, schedule:"HH:MM", tz, next_run, last_run_date, publish_mode, platforms:{youtube:bool,...}, retry:{max_attempts:int, backoff_s:int}, storage:{min_free_gb:number}, today:{date, picks:[...], projects:[Project]}, workers:{running:bool, threads:int}, history:[{date, status:"completed"|"partial"|"failed"|"running", projects:[{platform,title,status,project_id}]}]}`
- `POST /api/automation/start|pause|resume|stop` → same as GET
- `PUT /api/automation/settings` `{schedule?, platforms?, publish_mode?, retry?, storage?}` → same
- `POST /api/automation/run-now` `{}` → `{ok:true, job:Job, already_ran_today:bool}` (idempotent: a second call the same day returns the existing job)
- `GET /api/automation/logs?limit=` → `{logs:[{ts, level, msg}]}`

## Telegram
- `GET /api/telegram` → `{configured, connected, bot_username, webhook_url, pending_updates, error, chat_configured, commands:[{cmd, desc}], web_actions:[{id,label,desc}]}`
- `POST /api/telegram/test` `{text?}` → `{ok:true, sent:true}` (sends a real message to the configured chat; 409 `not_configured` otherwise)
- `POST /api/telegram/action` `{action:"daily_report"|"status"}` → `{ok:true}`

## AI providers
- `GET /api/ai` → `{primary:"openai"|"gemini", fallback:bool, providers:[{id, configured, model, models_suggested:[str], last_ok, last_error, calls, failures}]}`
- `PUT /api/ai` `{primary?, fallback?, models?:{openai?:str, gemini?:str}}` → same
- `POST /api/ai/test` `{provider}` → `{ok:bool, latency_ms:int, error:str|null}` (one tiny real API call; 409 if not configured)

## Settings / storage / analytics
- `GET /api/settings` → `{audit:[{ts,actor,action,detail}], env:[...same as system.env], limits:{max_upload_mb:25}, version}`
- `GET /api/storage` → `{persistent:bool, note, data_dir_gb, free_gb, projects:[{id,title,platform,date,size}], temp_gb}`
- `POST /api/storage/cleanup` `{}` → `{ok:true, freed_mb:number, removed:int}` (temp/work dirs only; never deletes user project files)
- `GET /api/analytics?days=30` → `{days:[{date, completed, failed}], by_platform:{youtube:{completed,failed,avg_minutes}, ...}, by_category:{"Anime":n,...}, durations:{avg_render_s, avg_total_s}, failure_reasons:[{reason,count}], totals:{projects,videos,minutes_produced,storage_mb}}`

## Static frontend
Served at `/studio/` (SPA, hash routing `#/dashboard`, `#/recap-studio`, ...). `GET /` redirects to `/studio/`.
