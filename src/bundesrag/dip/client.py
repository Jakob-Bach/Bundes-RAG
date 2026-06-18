from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Literal

import httpx
from tqdm import tqdm

from bundesrag.dip.models import DrucksacheMeta, PlenarprotokollMeta

DEFAULT_BASE_URL = "https://search.dip.bundestag.de/api/v1/"


class DipClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._http = http_client or httpx.Client(timeout=30.0)
        self._http.headers["Authorization"] = f"ApiKey {api_key}"

    def list_drucksachen(
        self,
        *,
        datum_start: date | None = None,
        datum_end: date | None = None,
        wahlperiode: int | None = None,
        dokumentnummer: str | None = None,
        drucksachetyp: str | None = None,
        zuordnung: Literal["BT", "BR", "BV", "EK"] | None = None,
        urheber: list[str] | None = None,
        ressort_fdf: list[str] | None = None,
        titel: list[str] | None = None,
        max_results: int | None = None,
    ) -> Iterator[DrucksacheMeta]:
        params = self._base_params(datum_start, datum_end, wahlperiode, dokumentnummer, zuordnung)
        if drucksachetyp:
            params["f.drucksachetyp"] = drucksachetyp
        if urheber:
            params["f.urheber"] = urheber
        if ressort_fdf:
            params["f.ressort_fdf"] = ressort_fdf
        if titel:
            params["f.titel"] = titel
        yield from self._paginate("drucksache", params, DrucksacheMeta, max_results)

    def list_plenarprotokolle(
        self,
        *,
        datum_start: date | None = None,
        datum_end: date | None = None,
        wahlperiode: int | None = None,
        dokumentnummer: str | None = None,
        zuordnung: Literal["BT", "BR", "BV", "EK"] | None = None,
        max_results: int | None = None,
    ) -> Iterator[PlenarprotokollMeta]:
        params = self._base_params(datum_start, datum_end, wahlperiode, dokumentnummer, zuordnung)
        yield from self._paginate("plenarprotokoll", params, PlenarprotokollMeta, max_results)

    @staticmethod
    def _base_params(
        datum_start: date | None,
        datum_end: date | None,
        wahlperiode: int | None,
        dokumentnummer: str | None,
        zuordnung: str | None,
    ) -> dict:
        params: dict = {}
        if datum_start:
            params["f.datum.start"] = datum_start.isoformat()
        if datum_end:
            params["f.datum.end"] = datum_end.isoformat()
        if wahlperiode:
            params["f.wahlperiode"] = wahlperiode
        if dokumentnummer:
            params["f.dokumentnummer"] = dokumentnummer
        if zuordnung:
            params["f.zuordnung"] = zuordnung
        return params

    def _paginate(self, endpoint: str, params: dict, model: type, max_results: int | None) -> Iterator:
        request_params = {**params, "format": "json"}
        cursor: str | None = None
        fetched = 0
        while True:
            if cursor is not None:
                request_params["cursor"] = cursor
            response = self._http.get(f"{self._base_url}{endpoint}", params=request_params)
            response.raise_for_status()
            payload = response.json()
            documents = payload.get("documents", [])
            for raw in documents:
                yield model.model_validate(raw)
                fetched += 1
                if max_results is not None and fetched >= max_results:
                    return
            next_cursor = payload.get("cursor")
            # The API signals "no more results" once the cursor stops changing.
            if not documents or next_cursor == cursor:
                return
            cursor = next_cursor

    def download_pdf(self, url: str, dest_path: Path) -> Path:
        if dest_path.exists():
            return dest_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with self._http.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0)) or None
            with open(dest_path, "wb") as f, tqdm(
                total=total, unit="B", unit_scale=True, desc=dest_path.name, leave=False
            ) as bar:
                for chunk in response.iter_bytes():
                    f.write(chunk)
                    bar.update(len(chunk))
        return dest_path

    def close(self) -> None:
        self._http.close()
