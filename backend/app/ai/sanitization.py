"""Conservative fragment allowlist, with character-preserving redaction.

Only payload is sent to adapters. origins stays inside the server for source mapping.
This is not universal PII recognition; unlabelled names can remain in address prose.
"""

import re
from dataclasses import dataclass

from app.ai.extraction import SanitizedAddressInput, SanitizedFragment
from app.parsing.places import township_dictionary
from app.schemas.orders import ParseResponse

ENRICHMENT_FIELDS = ("landmark", "building_floor_unit", "delivery_instructions")
SENSITIVE_LABEL = re.compile(
    r"\b(?:name|customer|phone|mobile|tel|email|bank|account|password|otp|invoice|order|"
    r"tracking|payment|price|cod|pin|gps|latitude|longitude|coordinates|passcode|"
    r"gate[ \t-]*code|door[ \t-]*code)\b|"
    r"အမည်|နာမည်|ကျသင့်ငွေ|ကောက်ခံငွေ|ကုန်ဖိုး|ငွေချေ|ဘဏ်|စကားဝှက်",
    re.I,
)
ADDRESS_CONTEXT = re.compile(
    r"^(?:(?:address|landmark|floor|unit|room|instructions?|note)\b|"
    r"လိပ်စာ|အထင်ကရ|အခန်း|မှတ်ချက်|ညွှန်ကြားချက်)|"
    r"\b(?:near|beside|opposite|behind|next[ \t]+to)\b",
    re.I,
)
PRIVATE_PATTERNS = [
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?:https?://|www\.)[^\s]+", re.I),
    re.compile(r"@[A-Za-z0-9_]+"),
    # Over-redact long numeric sequences (phones, accounts, order amounts).
    re.compile(r"(?<![0-9])[+]?[0-9][0-9 \t()\-]{3,}[0-9](?![0-9])"),
    re.compile(r"[-+]?[0-9]{1,3}\.[0-9]{3,}"),
]


@dataclass(frozen=True)
class PreparedAIRequest:
    payload: SanitizedAddressInput
    origins: dict[str, int]


def prepare_ai_request(parsed: ParseResponse, max_chars: int) -> PreparedAIRequest | None:
    text = parsed.normalized_text or ""
    requested = tuple(
        field for field in ENRICHMENT_FIELDS if parsed.field_sources[field].status != "extracted"
    )
    if not requested:
        return None
    masked = list(text)

    def redact(start: int, end: int) -> None:
        masked[start:end] = " " * (end - start)

    for field in ("customer_name", "phone_number", "cod_amount"):
        for item in parsed.field_sources[field].evidence:
            redact(item.start, item.end)
    # Remove reliably labelled names everywhere, including a repetition in a note.
    known_names = [c.value for c in parsed.field_sources["customer_name"].evidence if c.value]
    for name in known_names:
        for match in re.finditer(re.escape(str(name)), text, re.I):
            redact(*match.span())
    for pattern in PRIVATE_PATTERNS:
        for match in pattern.finditer(text):
            redact(*match.span())
    safe = "".join(masked)
    fragments, origins = [], {}
    total = 0
    # Commas delimit clauses; numeric clauses and unlabelled leading names are dropped.
    for clause in re.finditer(r"[^,;\n\r၊။]+", text):
        original = clause.group().strip()
        if SENSITIVE_LABEL.search(original):
            continue
        # Do not send already extracted notes/units just because another field is missing.
        if (
            (
                "delivery_instructions" not in requested
                and re.match(
                    r"^(?:instructions?\b|note\b|မှတ်ချက်|ညွှန်ကြားချက်)",
                    original,
                    re.I,
                )
            )
            or (
                "building_floor_unit" not in requested
                and re.match(
                    r"^(?:floor\b|unit\b|room\b|အခန်း)",
                    original,
                    re.I,
                )
            )
            or (
                "landmark" not in requested
                and re.match(
                    r"^(?:landmark\b|အထင်ကရ)",
                    original,
                    re.I,
                )
            )
        ):
            continue
        intersects = any(
            clause.start() < item.end and clause.end() > item.start
            for field in requested
            for item in parsed.field_sources[field].evidence
        )
        if not ADDRESS_CONTEXT.search(original) and not intersects:
            continue
        segment = safe[clause.start() : clause.end()]
        leading = len(segment) - len(segment.lstrip())
        segment = segment.strip()
        # An empty labelled clause is not useful to a model. Oversized clauses are
        # dropped whole rather than cutting through possible private information.
        content = re.sub(
            r"^(?:address|landmark|note|instructions?)[ \t]*[:=]?[ \t]*", "", segment, flags=re.I
        )
        if (
            not any(char.isalpha() for char in content)
            or len(segment) > 512
            or not segment
            or total + len(segment) > max_chars
        ):
            continue
        fragment_id = f"fragment_{len(fragments)}"
        fragments.append(SanitizedFragment(id=fragment_id, text=segment))
        origins[fragment_id] = clause.start() + leading
        total += len(segment)
        if len(fragments) == 8:
            break
    if not fragments:
        return None
    known = {place["name"] for place in township_dictionary()["townships"]}
    township = parsed.address.township if parsed.address.township in known else None
    return PreparedAIRequest(
        payload=SanitizedAddressInput(
            township=township, fragments=tuple(fragments), requested_fields=requested
        ),
        origins=origins,
    )
