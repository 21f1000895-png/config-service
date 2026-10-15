import os
from typing import List, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yaml
from pydantic import BaseModel, Field

app = FastAPI()

# Enable CORS for browser checking
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Type coercion helper
def coerce_value(key: str, value: str):
    if key in ("port", "workers"):
        try:
            return int(value)
        except ValueError:
            return value
    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes", "on")
    return value

@app.get("/effective-config")
async def get_effective_config(set: Optional[List[str]] = Query(None)):
    # 1. Defaults
    config = {
        "port": 8000,
        "workers": 1,
        "debug": False,
        "log_level": "info",
        "api_key": "default-secret-000"
    }

    # 2. config.development.yaml (assuming APP_ENV=development or fallback)
    env_name = os.getenv("APP_ENV", "development")
    yaml_filename = f"config.{env_name}.yaml"
    if os.path.exists(yaml_filename):
        try:
            with open(yaml_filename, "r") as f:
                yaml_data = yaml.safe_load(f) or {}
                for k, v in yaml_data.items():
                    config[k] = coerce_value(k, v)
        except Exception:
            pass

    # 3. .env file (or environment variables typically loaded via dotenv)
    # Mapping specific aliases like NUM_WORKERS -> workers and APP_LOG_LEVEL -> log_level if present
    env_num_workers = os.getenv("NUM_WORKERS")
    if env_num_workers is not None:
        config["workers"] = coerce_value("workers", env_num_workers)
    
    env_app_log = os.getenv("APP_LOG_LEVEL")
    if env_app_log is not None:
        config["log_level"] = coerce_value("log_level", env_app_log)

    # 4. OS env vars (APP_* prefix)
    # Mapping APP_DEBUG -> debug, APP_API_KEY -> api_key, etc.
    for k, v in os.environ.items():
        if k.startswith("APP_"):
            config_key = k[4:].lower()
            if config_key in config:
                config[config_key] = coerce_value(config_key, v)

    # 5. CLI overrides via ?set=key=value query parameters (highest precedence)
    if set:
        for item in set:
            if "=" in item:
                k, v = item.split("=", 1)
                if k in config:
                    config[k] = coerce_value(k, v)

    # Ensure types are correct
    config["port"] = coerce_value("port", config["port"])
    config["workers"] = coerce_value("workers", config["workers"])
    config["debug"] = coerce_value("debug", config["debug"])

    # 6. Secret masking
    response_config = config.copy()
    response_config["api_key"] = "****"

    return response_config