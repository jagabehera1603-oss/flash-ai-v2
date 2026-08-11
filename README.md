# Flash AI V2

AI shopping research app with a Django API and Streamlit UI.

## Components
- `frontend/app.py` — Streamlit interface
- `backend/` — Django REST API
- Tavily — web research
- OpenAI — evidence-based synthesis
- PostgreSQL or SQLite — research storage

## Streamlit deployment
1. Open Streamlit Community Cloud and choose **Create app**.
2. Repository: `jagabehera1603-oss/flash-ai-v2`
3. Branch: `main`
4. Main file: `frontend/app.py`
5. Add secrets:

```toml
DJANGO_API_URL = "https://YOUR-DJANGO-SERVICE.onrender.com/api"
```

## Django deployment
The included `render.yaml` can be used with Render. Set `TAVILY_API_KEY` and `OPENAI_API_KEY` in the service environment.

## Important
Do not commit API keys to GitHub. Put them in Streamlit Secrets / Render environment variables.
