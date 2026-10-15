import os
from typing import List, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yaml
from dotenv import dotenv_values

app = FastAPI()

# Enable CORS for browser checking
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def coerce_value(key: str, value):
    """Coerce string values into required types."""
    if value is None:
        return value
    if key in ("port", "workers"):
        try:
            return int(value)
        except ValueError:
            return value
    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "on")
    return str(value)

@app.get("/effective-config")
async def get_effective_config(set: Optional[List[str]] = Query(None)):
    # Layer 1: Hardcoded Defaults
    config = {
        "port": 8000,
        "workers": 1,
        "debug": False,
        "log_level": "info",
        "api_key": "default-secret-000"
    }

    # Layer 2: config.development.yaml
    yaml_file = "config.development.yaml"
    if os.path.exists(yaml_file):
        try:
            with open(yaml_file, "r") as f:
                yaml_data = yaml.safe_load(f) or {}
                for k, v in yaml_data.items():
                    if k in config:
                        config[k] = coerce_value(k, v)
        except Exception:
            pass

    # Layer 3: .env file & Environment Variables fallback
    dotenv_data = {}
    if os.path.exists(".env"):
        dotenv_data = dotenv_values(".env")
    
    # Merge OS environment variables so Render config is also captured here
    for env_k, env_v in os.environ.items():
        if env_k not in dotenv_data:
            dotenv_data[env_k] = env_v

    # Alias: NUM_WORKERS -> workers
    if "NUM_WORKERS" in dotenv_data and dotenv_data["NUM_WORKERS"] is not None:
        config["workers"] = coerce_value("workers", dotenv_data["NUM_WORKERS"])
        
    # APP_LOG_LEVEL -> log_level
    if "APP_LOG_LEVEL" in dotenv_data and dotenv_data["APP_LOG_LEVEL"] is not None:
        config["log_level"] = coerce_value("log_level", dotenv_data["APP_LOG_LEVEL"])

    # Layer 4: OS Environment Variables (APP_* prefix)
    for env_key, env_val in os.environ.items():
        if env_key.startswith("APP_"):
            key_name = env_key[4:].lower()
            if key_name in config:
                config[key_name] = coerce_value(key_name, env_val)

    # Layer 5: Query parameter overrides (?set=key=value)
    if set:
        for override in set:
            if "=" in override:
                key, val = override.split("=", 1)
                if key in config:
                    config[key] = coerce_value(key, val)

    # Ensure types across all parameters
    config["port"] = coerce_value("port", config["port"])
    config["workers"] = coerce_value("workers", config["workers"])
    config["debug"] = coerce_value("debug", config["debug"])

    # Secret Masking
    response_config = config.copy()
    response_config["api_key"] = "****"

    return response_config
