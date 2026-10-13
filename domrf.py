"""Поиск последних проектных деклараций на наш.дом.рф.

Пример::

    from domrf import ProjectDeclarations

    with ProjectDeclarations(r"C:\\path\\chromedriver.exe") as catalog:
        for url in catalog.links("Лисино"):
            print(url)
"""

from __future__ import annotations

import base64
import re
import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

PLACE_SPB = 78
HOST = "https://xn--80az8a.xn--d1aqf.xn--p1ai"
CATALOG = (
    f"{HOST}/%D0%BD%D0%BE%D0%B2%D0%BE%D1%81%D1%82%D1%80%D0%BE%D0%B9%D0%BA%D0%B8/"
    "%D1%81%D0%B0%D0%BD%D0%BA%D1%82-%D0%BF%D0%B5%D1%82%D0%B5%D1%80%D0%B1%D1%83%D1%80%D0%B3/"
)
_HOUSES_JS = r"""
async (name, place) => {
  const houses = [];
  const limit = 50;
  let offset = 0;
  let total = 0;
  do {
    const params = new URLSearchParams({
      offset: String(offset),
      limit: String(limit),
      place: String(place),
      searchValue: name,
    });
    const response = await fetch("/сервисы/api/kn/object?" + params.toString(), {
      headers: { accept: "application/json" },
    });
    const text = await response.text();
    if (!response.ok || text.startsWith("<")) {
      return { error: "Каталог не ответил JSON, статус " + response.status };
    }
    const payload = JSON.parse(text);
    const list = (payload.data && payload.data.list) || [];
    total = Number((payload.data && payload.data.total) || 0);
    for (const item of list) {
      houses.push({ id: item.objId, name: item.objCommercNm || "" });
    }
    offset += list.length;
    if (!list.length) break;
  } while (offset < total);
  return { total, houses };
}
"""

_DOCS_JS = r"""
async (objId) => {
  const response = await fetch("/сервисы/api/object/" + objId + "/document/rpd", {
    headers: { accept: "application/json" },
  });
  const text = await response.text();
  if (!response.ok || text.startsWith("<")) return [];
  const payload = JSON.parse(text);
  return payload.data || [];
}
"""

_FILE_JS = r"""
async (url) => {
  const response = await fetch(url);
  if (!response.ok) return { error: "status " + response.status };
  const bytes = new Uint8Array(await response.arrayBuffer());
  const parts = [];
  const size = 8192;
  for (let i = 0; i < bytes.length; i += size) {
    parts.push(String.fromCharCode.apply(null, bytes.subarray(i, i + size)));
  }
  return { data: btoa(parts.join("")) };
}
"""

_READY_JS = r"""
async () => {
  const response = await fetch("/сервисы/api/kn/object?offset=0&limit=1&place=78", {
    headers: { accept: "application/json" },
  });
  const text = await response.text();
  return response.ok && text.startsWith("{");
}
"""


def _call_page(driver: webdriver.Chrome, function_source: str, *args):
    script = f"""
    const done = arguments[arguments.length - 1];
    const fn = {function_source};
    const inputs = Array.prototype.slice.call(arguments, 0, arguments.length - 1);
    Promise.resolve(fn.apply(null, inputs))
      .then(done)
      .catch((err) => done({{ error: String(err) }}));
    """
    return driver.execute_async_script(script, *args)


def _issued_at(document: dict) -> datetime:
    raw = str(document.get("rpdIssueDttm") or "")
    for pattern in ("%d-%m-%Y %H:%M", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, pattern)
        except ValueError:
            continue
    return datetime.min


def _plain(value: str) -> str:
    text = value.casefold().replace("ё", "е")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return " ".join(text.split())


def _is_named_complex(commercial_name: str, query: str) -> bool:
    name = _plain(commercial_name)
    needle = _plain(query)
    if not name or not needle:
        return False
    return f" {needle} " in f" {name} "


def _latest(documents: list) -> dict | None:
    if not documents:
        return None
    newest = max(documents, key=_issued_at)
    if _issued_at(newest) == datetime.min:
        return documents[0]
    return newest


class ProjectDeclarations:
    """Каталог проектных деклараций Санкт-Петербурга.

    ``driver_path`` — путь к chromedriver.exe.
    ``links`` возвращает уникальные ссылки на последнюю декларацию каждого дома.
    """

    def __init__(self, driver_path: str, place: int = PLACE_SPB) -> None:
        path = Path(str(driver_path).strip().strip('"'))
        if not path.is_file():
            raise FileNotFoundError("Нет ChromeDriver")
        self.driver_path = path
        self.place = place
        self._driver: webdriver.Chrome | None = None

    def __enter__(self) -> ProjectDeclarations:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        if self._driver is None:
            return
        try:
            self._driver.quit()
        except WebDriverException:
            pass
        self._driver = None

    def links(self, name: str) -> list[str]:
        query = name.strip()
        if not query:
            raise ValueError("Пустое название комплекса.")
        driver = self._ensure_driver()
        listed = _call_page(driver, _HOUSES_JS, query, int(self.place))
        if isinstance(listed, dict) and listed.get("error"):
            raise RuntimeError(listed["error"])
        houses = [
            house
            for house in ((listed or {}).get("houses") or [])
            if _is_named_complex(str(house.get("name") or ""), query)
        ]
        found: list[str] = []
        seen: set[str] = set()
        for house in houses:
            document = _latest(_call_page(driver, _DOCS_JS, int(house["id"])) or [])
            url = (document or {}).get("rpdPdfLink") or ""
            if url and url not in seen:
                seen.add(url)
                found.append(url)
            time.sleep(0.15)
        return found

    def save(self, url: str, destination: str | Path) -> Path:
        payload = _call_page(self._ensure_driver(), _FILE_JS, url)
        if not isinstance(payload, dict) or payload.get("error") or not payload.get("data"):
            raise RuntimeError(f"Не скачалось: {url}")
        content = base64.b64decode(payload["data"])
        if not content.startswith(b"%PDF"):
            raise RuntimeError(f"Не скачалось: {url}")
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def _ensure_driver(self) -> webdriver.Chrome:
        if self._driver is not None:
            try:
                if self._driver.window_handles:
                    return self._driver
            except WebDriverException:
                self._driver = None
        profile = Path.home() / ".domrf-webdriver"
        profile.mkdir(exist_ok=True)
        options = Options()
        options.add_argument("--start-minimized")
        options.add_argument("--window-size=900,700")
        options.add_argument(f"--user-data-dir={profile}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        driver = None
        try:
            driver = webdriver.Chrome(service=Service(str(self.driver_path)), options=options)
            driver.set_page_load_timeout(60)
            driver.set_script_timeout(120)
            driver.get(CATALOG)
            for _ in range(40):
                if _call_page(driver, _READY_JS) is True:
                    self._driver = driver
                    return driver
                time.sleep(1)
        except WebDriverException:
            if driver is not None:
                try:
                    driver.quit()
                except WebDriverException:
                    pass
            raise RuntimeError("Нет Chrome") from None
        try:
            driver.quit()
        except WebDriverException:
            pass
        raise RuntimeError("Нет Chrome")
