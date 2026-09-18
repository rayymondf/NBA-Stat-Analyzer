# Backend-specific guidance

- Use Python 3.12 and the locked `uv` environment defined by `pyproject.toml` and `uv.lock`.
- Keep routers thin. Put computation in `services`, NBA transport/cache behavior in `nba`, and offline data/ML workflows in `pipeline`.
- Unit tests must not call NBA.com, Google Gemini, object storage, or any other live service.
- Preserve game/date groups across ML folds. Fit preprocessors and calibrators only on their assigned training or validation data.
- Treat Pydantic/FastAPI models and `openapi.json` as public contracts. Regenerate the contract after route changes.
- Use atomic writes for manifests and model artifacts. Verify checksums before loading remotely obtained joblib files.
