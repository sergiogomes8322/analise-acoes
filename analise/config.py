import tomllib
from functools import cache
from pathlib import Path

CAMINHO = Path(__file__).resolve().parent.parent / "config.toml"


@cache
def carregar() -> dict:
    with CAMINHO.open("rb") as f:
        return tomllib.load(f)
