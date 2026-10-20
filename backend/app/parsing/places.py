import json
import re
from functools import lru_cache
from importlib.resources import files

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.orders import ExtractionEvidence, LocationVerification


@lru_cache(maxsize=1)
def township_dictionary() -> dict:
    return json.loads(files("app").joinpath("data/yangon_townships.json").read_text("utf-8"))


def find_townships(text: str) -> list[ExtractionEvidence]:
    candidates = []
    for place in township_dictionary()["townships"]:
        for alias in place["aliases"]:
            # Latin aliases need boundaries; Burmese is commonly written without spaces.
            pattern = re.escape(alias).replace(r"\ ", r"[ \t]+")
            if alias.isascii():
                pattern = rf"(?<![A-Za-z]){pattern}(?![A-Za-z])"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Insein Road in Hlaing is not a second township mention.
                if re.match(r"[ \t]*(?:road\b|rd\b|street\b|လမ်း)", text[match.end() :], re.I):
                    continue
                end = match.end()
                suffix = re.match(r"[ \t]*(?:township\b|မြို့နယ်)", text[end:], re.I)
                if suffix:
                    end += suffix.end()
                candidates.append(
                    ExtractionEvidence(
                        value=place["name"],
                        matched_text=text[match.start() : end],
                        start=match.start(),
                        end=end,
                    )
                )
    # Longest match wins at overlapping positions: North Dagon must not also match Dagon.
    selected = []
    for candidate in sorted(candidates, key=lambda c: c.end - c.start, reverse=True):
        if not any(candidate.start < old.end and candidate.end > old.start for old in selected):
            selected.append(candidate)
    return sorted(selected, key=lambda c: c.start)


class TrustedLocation(BaseModel):
    """Operator-reviewed catalog entry. Never accepted from the public parse request."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    township: str
    field: str = Field(pattern="^(street|landmark)$")
    name: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    dataset: str = Field(min_length=1)
    source_url: HttpUrl


class LocationCatalog:
    def __init__(self, entries: tuple[TrustedLocation, ...] = ()):
        # No trusted street/landmark dataset was supplied. Fail closed by default.
        self.entries = entries

    def verify(self, township: str | None, field: str, value: str | None) -> LocationVerification:
        if not township or not value:
            return LocationVerification()
        key = " ".join(value.casefold().split())
        matches = [
            entry
            for entry in self.entries
            if entry.township == township
            and entry.field == field
            and key in {" ".join(a.casefold().split()) for a in (entry.name, *entry.aliases)}
        ]
        if len(matches) != 1:
            return LocationVerification()
        entry = matches[0]
        return LocationVerification(
            status="verified", dataset=entry.dataset, source_url=str(entry.source_url)
        )
