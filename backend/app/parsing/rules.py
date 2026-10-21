"""Conservative extraction rules. Unclear candidates stay null and retain evidence."""

import re

import phonenumbers

from app.parsing.places import find_townships, township_dictionary
from app.schemas.orders import AddressFields, ExtractionEvidence, FieldSource

PHONE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9+])(?:\+?95[ \t-]*(?:0[ \t-]*)?9|09)"
    r"(?:[ \t-]*[0-9]){1,14}(?![0-9])"
)
PHONE_LABEL = re.compile(
    r"(?:\b(?:phone|ph|tel|mobile)\b|ဖုန်း)[ \t]*[:=]?[ \t]*"
    r"(?P<value>\+?[0-9][0-9 \t-]*)",
    re.I,
)
COD_LABEL = r"(?:\bCOD\b|cash[ \t]+on[ \t]+delivery|ငွေချေ|ကျသင့်ငွေ|ကောက်ခံငွေ|ကုန်ဖိုး)"
AMOUNT = r"(?P<value>-?[0-9](?:[0-9,.]*[0-9])?(?:[kK])?)"
COD_PATTERNS = [
    re.compile(COD_LABEL + r"[ \t]*[:=]?[ \t]*(?:MMK[ \t]*)?" + AMOUNT, re.I),
    re.compile(r"(?<![0-9.,])" + AMOUNT + r"[ \t]*(?:ကျပ်|MMK)?[ \t]*(?:COD\b|ကောက်ခံရန်)", re.I),
]
IDENTIFIER_CONTEXT = re.compile(
    r"\b(?:order|invoice|tracking|receipt|id)[ \t]*(?:(?:no\.?|number)[ \t]*)?[#:=]?[ \t]*$",
    re.I,
)


def evidence(text: str, match: re.Match, value: str | int | None) -> ExtractionEvidence:
    return ExtractionEvidence(
        value=value,
        matched_text=text[match.start() : match.end()],
        start=match.start(),
        end=match.end(),
    )


def choose(
    field: str,
    candidates: list[ExtractionEvidence],
    rule: str,
    address: AddressFields,
    sources: dict[str, FieldSource],
    *,
    method: str = "rule",
    invalid: bool = False,
) -> None:
    values = {c.value for c in candidates if c.value is not None}
    status = "missing"
    if len(values) > 1:
        status = "ambiguous"
    elif invalid or (candidates and not values):
        status = "invalid"
    elif values:
        status = "extracted"
        setattr(address, field, next(iter(values)))
    sources[field] = FieldSource(method=method, status=status, rule=rule, evidence=candidates)


def extract_phones(text: str, address: AddressFields, sources: dict[str, FieldSource]) -> None:
    matches = list(PHONE_PATTERN.finditer(text))
    # Labelled malformed or non-mobile numbers must be reported, not silently ignored.
    matches += [
        m
        for m in PHONE_LABEL.finditer(text)
        if not any(m.start() < p.end() and m.end() > p.start() for p in matches)
    ]
    candidates = []
    invalid = False
    for match in matches:
        raw = match.groupdict().get("value") or match.group()
        compact = re.sub(r"[ \t-]", "", raw)
        if compact.startswith("959"):
            compact = "+" + compact
        if compact.startswith("+9509"):
            compact = "+959" + compact[5:]
        value = None
        try:
            number = phonenumbers.parse(compact, "MM")
            if (
                phonenumbers.is_valid_number_for_region(number, "MM")
                and phonenumbers.number_type(number) == phonenumbers.PhoneNumberType.MOBILE
                and not IDENTIFIER_CONTEXT.search(text[max(0, match.start() - 40) : match.start()])
            ):
                value = "0" + str(number.national_number)
        except phonenumbers.NumberParseException:
            pass  # The failed candidate is retained as invalid evidence below.
        invalid |= value is None
        candidates.append(evidence(text, match, value))
    choose(
        "phone_number", candidates, "mm-mobile-numbering-plan-v1", address, sources, invalid=invalid
    )


def extract_cod(text: str, address: AddressFields, sources: dict[str, FieldSource]) -> None:
    candidates = []
    spans = set()
    invalid = False
    phone_spans = sources["phone_number"].evidence
    for pattern in COD_PATTERNS:
        for match in pattern.finditer(text):
            span = match.span("value")
            # In "<phone> COD <amount>", the reverse amount-before-COD rule
            # also sees the phone. It is not a second payment candidate. Keep
            # forward "COD <phone>" invalid, and retain unmatched COD markers.
            if pattern is COD_PATTERNS[1] and any(
                span[0] < p.end and span[1] > p.start for p in phone_spans
            ):
                continue
            if span in spans:
                continue
            spans.add(span)
            raw = match.group("value")
            # Only whole MMK, correct comma grouping, no guesses about k/lakh/decimals.
            valid = re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)", raw)
            suffix = text[span[1] :]
            unsafe_suffix = re.match(
                r"[ \t]*(?:[.:/0-9]|am\b|pm\b|နာရီ|သိန်း|သောင်း|သန်း|[kK]\b|"
                r"lakhs?\b|lacs?\b|million\b|thousand\b|x[ \t]*[0-9]|each\b|"
                r"USD\b|THB\b|SGD\b|CNY\b|RMB\b|EUR\b|dollars?\b|baht\b|[$฿¥€])",
                suffix,
                re.I,
            )
            expression_suffix = re.match(
                r"[ \t]*(?:ကျပ်|MMK|kyats?)?[ \t]*[+*/%\-]",
                suffix,
                re.I,
            )
            overlaps_phone = any(span[0] < p.end and span[1] > p.start for p in phone_spans)
            identifier = IDENTIFIER_CONTEXT.search(text[max(0, span[0] - 40) : span[0]])
            digits = raw.replace(",", "")
            value = int(digits) if valid and len(digits) <= 10 else None
            prepaid_conflict = bool(value) and re.search(
                r"\b(?:prepaid|paid|payment[ \t]+received)\b|ငွေရှင်းပြီး|ငွေချေပြီး",
                text,
                re.I,
            )
            if (
                unsafe_suffix
                or expression_suffix
                or overlaps_phone
                or identifier
                or prepaid_conflict
                or (value is not None and value > 1_000_000_000)
            ):
                value = None
            invalid |= value is None
            candidates.append(evidence(text, match, value))
    # An explicit COD marker with no usable amount is an unresolved payment instruction.
    labels = list(re.finditer(COD_LABEL, text, re.I))
    unmatched_labels = [
        label
        for label in labels
        if not any(label.start() < c.end and label.end() > c.start for c in candidates)
    ]
    for label in unmatched_labels:
        candidates.append(evidence(text, label, None))
        invalid = True
    choose("cod_amount", candidates, "explicit-cod-whole-mmk-v1", address, sources, invalid=invalid)


def extract_townships(text: str, address: AddressFields, sources: dict[str, FieldSource]) -> None:
    candidates = find_townships(text)
    # Explicit but unrecognized area names must also block dispatch when a known
    # township is mentioned elsewhere. No automatic choice of origin/destination.
    explicit = [
        r"(?<![\u1000-\u109f])[\u1000-\u109f]+[ \t]*မြို့နယ်",
        r"\b[A-Za-z]+(?:[ \t]+[A-Za-z]+){0,3}[ \t]+township\b",
        r"\btownship[ \t]*[:=][ \t]*[^,;\n၊။]+",
    ]
    unknown = []
    for pattern in explicit:
        for match in re.finditer(pattern, text, re.I):
            if not any(match.start() < c.end and match.end() > c.start for c in candidates):
                unknown.append(evidence(text, match, None))
    choose(
        "township",
        candidates + unknown,
        "yangon-alias-longest-match-v1",
        address,
        sources,
        method="dictionary",
        invalid=bool(unknown),
    )
    sources["township"].dataset = township_dictionary()["version"]


def masked_text(text: str, sources: dict[str, FieldSource], fields: tuple[str, ...]) -> str:
    chars = list(text)
    for field in fields:
        for item in sources[field].evidence:
            chars[item.start : item.end] = " " * (item.end - item.start)
    return "".join(chars)


def pattern_field(
    field: str,
    text: str,
    search_text: str,
    patterns: list[str],
    address: AddressFields,
    sources: dict[str, FieldSource],
) -> None:
    candidates = []
    for pattern in patterns:
        for match in re.finditer(pattern, search_text, re.I):
            value = (match.groupdict().get("value") or match.group()).strip()
            if value:
                candidates.append(evidence(text, match, value))
    # Prefer a labelled match that contains a shorter generic suffix match.
    candidates = [
        c
        for c in candidates
        if not any(
            other.start <= c.start
            and other.end >= c.end
            and other.end - other.start > c.end - c.start
            for other in candidates
        )
    ]
    choose(field, candidates, f"label-or-bounded-{field}-v1", address, sources)


def extract_fields(text: str) -> tuple[AddressFields, dict[str, FieldSource]]:
    address = AddressFields()
    sources = {field: FieldSource() for field in AddressFields.model_fields}
    extract_phones(text, address, sources)
    extract_cod(text, address, sources)
    pattern_field(
        "customer_name",
        text,
        text,
        [
            r"(?:^|[,;\n၊။])[ \t]*(?:name|customer|အမည်|နာမည်)[ \t]*[:=][ \t]*(?P<value>[^,;\n၊။]+)",
        ],
        address,
        sources,
    )
    search = masked_text(text, sources, ("customer_name", "phone_number", "cod_amount"))
    extract_townships(search, address, sources)
    # Match evidence must always point into actual normalized text, including spaces.
    for item in sources["township"].evidence:
        item.matched_text = text[item.start : item.end]
    search = masked_text(text, sources, ("customer_name", "phone_number", "cod_amount", "township"))
    pattern_field(
        "street",
        text,
        search,
        [
            r"(?:street|လမ်း)[ \t]*[:=][ \t]*(?P<value>[^,;\n၊။]+)",
            r"(?<![A-Za-z0-9])(?:[A-Za-z]+|[0-9]+(?:st|nd|rd|th)?)[ \t]+"
            r"(?:road|rd\.?|street|st\.?)(?![A-Za-z])",
            r"(?<![\u1000-\u109f0-9])[\u1000-\u109f0-9]+လမ်း(?:မကြီး|သွယ်)?",
        ],
        address,
        sources,
    )
    pattern_field(
        "landmark",
        text,
        search,
        [
            r"(?:landmark|အထင်ကရ)[ \t]*[:=][ \t]*(?P<value>[^,;\n၊။]+)",
            r"\b(?:near|beside|opposite|next[ \t]+to)[ \t]+(?P<value>[^,;\n၊။]+)",
            r"(?<![\u1000-\u109f])[\u1000-\u109f]+(?:နား|အနီး|ဘေး|ရှေ့)",
        ],
        address,
        sources,
    )
    # Floor and unit are complementary, unlike two competing floors or two units.
    parts = []
    ambiguous = False
    for kind, patterns in (
        (
            "floor",
            [
                r"(?:floor[ \t]*[:=]?[ \t]*[0-9]+|[0-9]+(?:st|nd|rd|th)?[ \t]+floor)",
                r"(?<![0-9])[0-9]+[ \t]*(?:ထပ်|လွှာ)(?:တိုက်)?",
            ],
        ),
        (
            "unit",
            [
                r"\b(?:unit|room)[ \t]*[:=]?[ \t]*[A-Za-z0-9-]+\b",
                r"(?:အခန်း)[ \t]*[:=]?[ \t]*[A-Za-z0-9-]+",
                r"(?:ညာ|ဘယ်)ဘက်ခန်း",
            ],
        ),
    ):
        temp_address, temp_sources = AddressFields(), {}
        pattern_field("building_floor_unit", text, search, patterns, temp_address, temp_sources)
        part = temp_sources["building_floor_unit"]
        ambiguous |= part.status == "ambiguous"
        parts.extend(part.evidence)
    source = sources["building_floor_unit"]
    if parts:
        source.method, source.rule = "rule", "explicit-floor-unit-v1"
        source.evidence = sorted(parts, key=lambda c: c.start)
        source.status = "ambiguous" if ambiguous else "extracted"
        if not ambiguous:
            address.building_floor_unit = "; ".join(dict.fromkeys(c.value for c in source.evidence))
    pattern_field(
        "delivery_instructions",
        text,
        search,
        [
            r"(?:instructions?|note|မှတ်ချက်|ညွှန်ကြားချက်)[ \t]*[:=][ \t]*(?P<value>[^,;\n၊။]+)",
            r"(?:မလာခင်[ \t]*ဖုန်းဆက်ပါ|ရောက်ရင်[ \t]*ဖုန်းဆက်ပါ|လုံခြုံရေးထံ[ \t]*ထားခဲ့ပါ)",
            r"(?:ညနေ|မနက်|နေ့လယ်)[ \t]*[0-9]+[ \t]*နာရီမှ[ \t]*လာပါ",
            r"\b(?:call before arrival|leave with security)\b",
        ],
        address,
        sources,
    )
    pattern_field(
        "time_window",
        text,
        search,
        [
            r"(?:ညနေ|မနက်|နေ့လယ်)[ \t]*[0-9]{1,2}(?::[0-9]{2})?[ \t]*နာရီ(?:မှ)?",
            r"\b[0-9]{1,2}(?::[0-9]{2})?[ \t]*(?:am|pm)\b",
        ],
        address,
        sources,
    )
    time_source = sources["time_window"]
    invalid_time = False
    for item in time_source.evidence:
        digits = re.search(r"([0-9]+)(?::([0-9]+))?", str(item.value))
        if digits and (not 1 <= int(digits[1]) <= 12 or (digits[2] and int(digits[2]) > 59)):
            item.value = None
            invalid_time = True
    if invalid_time:
        choose(
            "time_window", time_source.evidence, time_source.rule, address, sources, invalid=True
        )
        address.time_window = None
    return address, sources
