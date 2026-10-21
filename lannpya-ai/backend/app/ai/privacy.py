"""Fail-closed context builder for a future provider. No provider is called here."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.ai.base import ProviderInput
from app.parsing.places import township_dictionary
from app.schemas.orders import ParseResponse


class MinimalAddressContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    purpose: Literal["address_assistance"] = "address_assistance"
    township: str | None = None


def build_minimal_ai_input(parsed: ParseResponse) -> ProviderInput:
    # Never copy raw/normalized text, evidence, names, phones, COD, notes, or units.
    # Even arbitrary text in a future provider output cannot escape the allowlist.
    known = {place["name"] for place in township_dictionary()["townships"]}
    township = parsed.address.township if parsed.address.township in known else None
    context = MinimalAddressContext(township=township)
    return ProviderInput(raw_text=context.model_dump_json())
