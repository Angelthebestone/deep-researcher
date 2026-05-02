from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator


_DEFAULT_DOTENV_ATTEMPTED = False


class MissingCredentialError(RuntimeError):
	pass


def load_dotenv(path: str | Path | None = None, override: bool = False) -> None:
	dotenv_path = _resolve_dotenv_path(path)
	if dotenv_path is None or not dotenv_path.is_file():
		return

	for key, value in _read_dotenv(dotenv_path):
		if not override and key in os.environ:
			continue
		os.environ[key] = value


def get_secret(key: str, default: str | None = None, required: bool = True) -> str | None:
	global _DEFAULT_DOTENV_ATTEMPTED

	value = os.getenv(key, default)
	if value:
		return value

	if not _DEFAULT_DOTENV_ATTEMPTED:
		_DEFAULT_DOTENV_ATTEMPTED = True
		load_dotenv()
		value = os.getenv(key, default)

	if required and not value:
		raise MissingCredentialError(
			f"Missing required credential: {key}. Set it in the environment or .env."
		)
	return value


def get_gemini_key(required: bool = True) -> str | None:
	return get_secret("GEMINI_API_KEY", required=required)


def get_groq_key(required: bool = True) -> str | None:
	return get_secret("GROQ_API_KEY", required=required)


def get_mistral_key(required: bool = True) -> str | None:
	return get_secret("MISTRAL_API_KEY", required=required)


def get_openrouter_key(required: bool = True) -> str | None:
	return get_secret("OPENROUTER_API_KEY", required=required)


def get_nvidia_key(required: bool = True) -> str | None:
	return get_secret("NVIDIA_API_KEY", required=required)


def get_huggingface_key(required: bool = True) -> str | None:
	return get_secret("HUGGINGFACE_API_KEY", required=required)


def get_tavily_key(required: bool = True) -> str | None:
	return get_secret("TAVILY_API_KEY", required=required)


def get_exa_key(required: bool = True) -> str | None:
	return get_secret("EXA_API_KEY", required=required)


def get_serper_key(required: bool = True) -> str | None:
	return get_secret("SERPER_API_KEY", required=required)


def _resolve_dotenv_path(path: str | Path | None) -> Path | None:
	if path is not None:
		candidate = Path(path).expanduser()
		if candidate.is_dir():
			candidate = candidate / ".env"
		return candidate

	current = Path.cwd().resolve()
	for directory in (current, *current.parents):
		candidate = directory / ".env"
		if candidate.is_file():
			return candidate
	return None


def _read_dotenv(path: Path) -> Iterator[tuple[str, str]]:
	for raw_line in path.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#"):
			continue
		if line.startswith("export "):
			line = line[7:].lstrip()
		if "=" not in line:
			continue
		key, value = line.split("=", 1)
		key = key.strip()
		if not key:
			continue
		value = value.strip()
		if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
			value = value[1:-1]
		yield key, value


__all__ = [
	"MissingCredentialError",
	"get_gemini_key",
	"get_groq_key",
	"get_mistral_key",
	"get_secret",
	"load_dotenv",
]