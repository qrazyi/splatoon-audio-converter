"""Read-only release checks. Downloads/installations are never automatic."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import __version__

REPOSITORY = "qrazyi/splatoon-audio-converter"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
RELEASES_URL = REPOSITORY_URL + "/releases"


@dataclass(frozen=True)
class Release:
    version: str
    url: str


def version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError("The release version is not in v1.2.3 format.")
    return tuple(map(int, match.groups()))


def parse_release(data: dict) -> Release | None:
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name", "")
    if version(tag) <= version(__version__):
        return None
    url = data.get("html_url", "")
    if not url.startswith(RELEASES_URL + "/tag/"):
        raise ValueError("The update does not point to this project's GitHub Releases.")
    return Release(tag, url)


def check() -> Release | None:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
        headers={"User-Agent": "Splatoon-Audio-Converter", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("The update response is unexpectedly large.")
        return parse_release(json.loads(raw))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise RuntimeError("No public release was found. The repository may be private or not have a release yet.") from None
        if error.code in (403, 429):
            raise RuntimeError("GitHub is limiting update checks. Please try again later.") from None
        raise RuntimeError("GitHub could not provide update information. Try again later.") from None
    except urllib.error.URLError:
        raise RuntimeError("Could not reach GitHub. Check your internet connection or try again later.") from None
