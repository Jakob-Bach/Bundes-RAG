from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DipQueryFilters(BaseModel):
    endpoint: Literal["drucksache", "plenarprotokoll"]
    datum_start: date | None = None
    datum_end: date | None = None
    wahlperiode: int | None = None
    dokumentnummer: str | None = None
    drucksachetyp: str | None = None
    zuordnung: Literal["BT", "BR", "BV", "EK"] | None = None
    # Only meaningful for endpoint == "drucksache"; the DIP API has no
    # equivalent content filters for plenarprotokoll.
    urheber: list[str] = Field(default_factory=list)
    ressort_fdf: list[str] = Field(default_factory=list)
    titel: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _content_filters_require_drucksache(self) -> "DipQueryFilters":
        if self.endpoint == "plenarprotokoll" and (self.urheber or self.ressort_fdf or self.titel):
            raise ValueError(
                "urheber/ressort_fdf/titel filters are only valid for the drucksache endpoint"
            )
        return self


class ClarificationRequest(BaseModel):
    question: str


class QueryAgentResult(BaseModel):
    filters: DipQueryFilters | None = None
    clarification: ClarificationRequest | None = None

    @model_validator(mode="after")
    def _exactly_one_branch_set(self) -> "QueryAgentResult":
        if (self.filters is None) == (self.clarification is None):
            raise ValueError("exactly one of filters or clarification must be set")
        return self
