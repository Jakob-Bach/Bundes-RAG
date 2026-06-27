from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator


class DocumentMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    dokumentnummer: str
    datum: date
    wahlperiode: int
    drucksachetyp: str | None = None
    titel: str | None = None
    pdf_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _flatten_fundstelle(cls, data):
        # The DIP API nests pdf_url under "fundstelle"; flatten it here so the
        # model can be built directly from raw API JSON while everywhere else
        # in the codebase just deals with a flat pdf_url field.
        if isinstance(data, dict) and "pdf_url" not in data:
            fundstelle = data.get("fundstelle")
            if isinstance(fundstelle, dict):
                data = {**data, "pdf_url": fundstelle.get("pdf_url")}
        return data
