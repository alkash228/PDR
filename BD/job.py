import json
import re
from pathlib import Path

from domrf import ProjectDeclarations

from BD.config import DOWNLOAD_DIR, DRIVER_PATH
from BD.complexes import fetch_names

STATE_PATH = Path(__file__).resolve().parent / "state.json"


def _folder_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', " ", name).strip(" .")
    return cleaned or "complex"


def _file_name(url: str) -> str:
    stem = url.rstrip("/").split("/")[-1].split("?")[0]
    if not stem.lower().endswith(".pdf"):
        stem += ".pdf"
    return stem


def _load_state() -> dict[str, list[str]]:
    if not STATE_PATH.is_file():
        return {}
    data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _save_state(state: dict[str, list[str]]) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_once() -> None:
    if not DRIVER_PATH.strip() or not DOWNLOAD_DIR.strip():
        raise SystemExit("Пропишите DRIVER_PATH и DOWNLOAD_DIR в BD/config.py")
    names = [name.strip() for name in fetch_names() if str(name).strip()]
    if not names:
        print("Список комплексов пуст. Добавьте запрос в BD/complexes.py")
        return
    download_root = Path(DOWNLOAD_DIR)
    state = _load_state()
    with ProjectDeclarations(DRIVER_PATH) as catalog:
        for name in names:
            try:
                links = catalog.links(name)
            except Exception as error:
                print(f"{name}: {error}")
                continue
            known = set(state.get(name, []))
            fresh = [url for url in links if url not in known]
            if not fresh:
                print(f"{name}: без изменений")
                continue
            folder = download_root / _folder_name(name)
            for url in fresh:
                path = catalog.save(url, folder / _file_name(url))
                known.add(url)
                print(f"{name}: скачан {path.name}")
            state[name] = sorted(known)
            _save_state(state)
