from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Urheber(BaseModel):
    model_config = ConfigDict(extra="allow")

    bezeichnung: str
    titel: str
    rolle: str | None = None


class Fundstelle(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    dokumentart: str
    pdf_url: str | None = None


class DrucksacheMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    dokumentnummer: str
    datum: date
    wahlperiode: int
    drucksachetyp: str | None = None
    titel: str | None = None
    urheber: list[Urheber] = Field(default_factory=list)
    fundstelle: Fundstelle


class PlenarprotokollMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    dokumentnummer: str
    datum: date
    wahlperiode: int
    titel: str | None = None
    fundstelle: Fundstelle
