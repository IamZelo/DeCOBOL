"""
Configuration settings for DeCOBOL.
Loads environment variables from .env file or system environment.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root if present
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH)
else:
    load_dotenv()


def _get_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val.strip())
    except ValueError:
        return default


@dataclass
class Settings:
    # Local LLM settings (OpenAI-compatible llama-server)
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "http://localhost:8080/v1"))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "sk-no-key-required"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "decobol-local"))
    llm_temperature: float = field(default_factory=lambda: _get_float("LLM_TEMPERATURE", 0.1))
    llm_max_tokens: int = field(default_factory=lambda: _get_int("LLM_MAX_TOKENS", 4096))
    llm_timeout_seconds: int = field(default_factory=lambda: _get_int("LLM_TIMEOUT_SECONDS", 180))
    mock_llm: bool = field(default_factory=lambda: _get_bool("MOCK_LLM", False))

    # llama-server settings
    llama_model_file: str = field(
        default_factory=lambda: os.getenv("LLAMA_MODEL_FILE", "qwen2.5-coder-7b-instruct-q4_k_m.gguf")
    )
    llama_ctx_size: int = field(default_factory=lambda: _get_int("LLAMA_CTX_SIZE", 16384))
    llama_gpu_layers: int = field(default_factory=lambda: _get_int("LLAMA_GPU_LAYERS", 99))
    llama_port: int = field(default_factory=lambda: _get_int("LLAMA_PORT", 8080))

    # Flask API settings
    flask_port: int = field(default_factory=lambda: _get_int("FLASK_PORT", 5000))
    flask_debug: bool = field(default_factory=lambda: _get_bool("FLASK_DEBUG", False))
    max_retries: int = field(default_factory=lambda: _get_int("MAX_RETRIES", 2))
    max_workers: int = field(default_factory=lambda: _get_int("MAX_WORKERS", 2))
    java_package: str = field(default_factory=lambda: os.getenv("JAVA_PACKAGE", ""))

    # Project directories
    project_root: Path = field(default_factory=lambda: _PROJECT_ROOT)

    # Local filesystem workspace (docs/LOCAL_DEPLOYMENT_WORKFLOW.md).
    # These are the only two paths the fs tools may ever read/write.
    # Defaults point at the vendored demo COBOL and a scratch output folder so
    # the backend is immediately useful with no .env at all. Inside Docker,
    # docker-compose.yml overrides both to the container's mount points
    # (/workspace/input, /workspace/output) — the env var name is the only
    # thing that has to stay the same between "run standalone" and "run in
    # Docker".
    input_root: str = field(
        default_factory=lambda: os.getenv("INPUT_ROOT", str(_PROJECT_ROOT / "examples" / "lendwise"))
    )
    output_root: str = field(
        default_factory=lambda: os.getenv("OUTPUT_ROOT", str(_PROJECT_ROOT / ".decobol-output"))
    )


# Global settings singleton
settings = Settings()
