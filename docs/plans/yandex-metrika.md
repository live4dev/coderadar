# Plan: Add Yandex Metrika Integration

## Approach
Convert `index.html` to a Jinja2 template so the backend injects the Yandex Metrika counter ID at serve time. The snippet is only rendered when `YANDEX_METRIKA_ID` is set — no extra API calls, no JS config fetching.

## Files to Modify

1. **`requirements.txt`** — Add `jinja2` as an explicit dependency
2. **`app/core/config.py`** — Add `yandex_metrika_id: str = ""`
3. **`.env.example`** — Add `YANDEX_METRIKA_ID=` entry
4. **`app/main.py`** — Switch `/ui` routes from `FileResponse` to `Jinja2Templates.TemplateResponse`
5. **`app/static/index.html`** — Add conditional Yandex Metrika snippet before `</body>`
