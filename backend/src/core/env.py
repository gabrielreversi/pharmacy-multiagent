import os


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def optional(name: str, default: str) -> str:
    return os.getenv(name) or default
