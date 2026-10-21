import json

import pytest
from fastapi.testclient import TestClient
from myanmar.converter import convert

from app.ai.privacy import build_minimal_ai_input
from app.core.config import Settings
from app.main import create_app
from app.parsing.normalization import normalize_text
from app.parsing.places import LocationCatalog, TrustedLocation
from app.schemas.orders import AddressFields, ParseRequest, ParseResponse


@pytest.fixture
def client():
    with TestClient(create_app(Settings(_env_file=None, parser_mode="rules"))) as client:
        yield client


def parse(client, text):
    response = client.post("/api/orders/parse", json={"raw_text": text})
    assert response.status_code == 200, response.text
    return ParseResponse.model_validate(response.json())


def codes(result):
    return {reason.code for reason in result.validation_reasons}


def test_actual_burmese_extraction_and_evidence(client):
    text = (
        "  အမည်: မလှ\nဖုန်း: ၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ "
        "အဆွေတော်နား၊ ၄ ထပ်တိုက်၊ ညာဘက်ခန်း၊ COD: ၂၅,၀၀၀ ကျပ်၊ ညနေ ၃ နာရီမှ လာပါ  "
    )
    result = parse(client, text)
    assert result.original_text == text
    assert "09791234567" in result.normalized_text
    assert result.normalization.digits_normalized
    assert result.address == AddressFields(
        customer_name="မလှ",
        phone_number="09791234567",
        township="Hlaing",
        street="ဗဟိုလမ်း",
        landmark="အဆွေတော်နား",
        building_floor_unit="4 ထပ်တိုက်; ညာဘက်ခန်း",
        cod_amount=25000,
        delivery_instructions="ညနေ 3 နာရီမှ လာပါ",
        time_window="ညနေ 3 နာရီမှ",
    )
    assert result.is_mock is False
    assert result.provider == "rules"
    assert result.confidence == "AMBER"
    assert "LOCATION_UNVERIFIED" in codes(result)
    assert set(result.field_sources) == set(AddressFields.model_fields)
    for field, source in result.field_sources.items():
        assert source.status == "extracted", field
        assert source.method in {"rule", "dictionary"}
        assert source.rule
        assert source.evidence
        for item in source.evidence:
            assert item.matched_text == result.normalized_text[item.start : item.end]
    assert not result.field_sources["landmark"].verified
    assert result.location_verification.status == "unverified"
    assert "latitude" not in result.model_dump_json()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("09791234567", "09791234567"),
        ("၀၉၇၉၁၂၃၄၅၆၇", "09791234567"),
        ("09-791-234-567", "09791234567"),
        ("09 791 234 567", "09791234567"),
        ("+95 9 791 234 567", "09791234567"),
        ("+95 09 791 234 567", "09791234567"),
        ("959791234567", "09791234567"),
        ("09951234567", "09951234567"),
        ("09421234567", "09421234567"),
        ("095123456", "095123456"),
    ],
)
def test_phone_formats(client, raw, expected):
    result = parse(client, f"{raw}, Hlaing, Baho Road")
    assert result.address.phone_number == expected
    assert result.confidence == "AMBER"


@pytest.mark.parametrize(
    "raw", ["phone: 1234", "phone: 01234567", "09123456789", "09999999999", "09123"]
)
def test_invalid_phone_is_red(client, raw):
    result = parse(client, f"{raw}, Hlaing, Baho Road")
    assert result.address.phone_number is None
    assert result.confidence == "RED"
    assert "INVALID_PHONE_NUMBER" in codes(result)


def test_missing_phone(client):
    result = parse(client, "Hlaing, Baho Road")
    assert result.confidence == "RED"
    assert "MISSING_PHONE_NUMBER" in codes(result)


def test_multiple_phones_no_arbitrary_choice(client):
    result = parse(client, "09791234567 / 09951234567, Hlaing")
    assert result.address.phone_number is None
    assert result.field_sources["phone_number"].status == "ambiguous"
    assert result.confidence == "RED"


def test_duplicate_phone_aliases_not_ambiguous(client):
    result = parse(client, "09791234567 / +959791234567, Hlaing")
    assert result.address.phone_number == "09791234567"
    assert result.confidence == "AMBER"


def test_valid_and_invalid_phone_not_silently_selected(client):
    result = parse(client, "09791234567 / phone: 1234, Hlaing")
    assert result.confidence == "RED"
    assert result.address.phone_number is None


@pytest.mark.parametrize(
    "area,expected",
    [
        ("လှိုင်မြို့နယ်", "Hlaing"),
        ("hLaInG", "Hlaing"),
        ("Kamayut Township", "Kamaryut"),
        ("ကမာရွတ်မြို့နယ်", "Kamaryut"),
        ("Mayangone", "Mayangon"),
        ("North Dagon", "North Dagon"),
        ("Hlaing Thar Yar", "Hlaing Thar Yar"),
        ("လှိုင်သာယာမြို့နယ်", "Hlaing Thar Yar"),
        ("မြောက်ဒဂုံမြို့နယ်", "North Dagon"),
        ("South Okkalappa", "South Okkalapa"),
    ],
)
def test_controlled_township_aliases(client, area, expected):
    result = parse(client, f"09791234567, {area}")
    assert result.address.township == expected
    assert result.confidence == "AMBER"


@pytest.mark.parametrize(
    "area", ["Mandalay", "Unknown Township", "township: Atlantis", "မသိမြို့နယ်", "Hlaingxxx"]
)
def test_unknown_township(client, area):
    result = parse(client, f"09791234567, {area}")
    assert result.address.township is None
    assert result.confidence == "RED"


def test_multiple_townships_are_ambiguous(client):
    result = parse(client, "09791234567, Hlaing to Bahan, Baho Road")
    assert result.address.township is None
    assert result.confidence == "RED"
    assert "AMBIGUOUS_TOWNSHIP" in codes(result)
    assert {item.value for item in result.field_sources["township"].evidence} == {"Hlaing", "Bahan"}


def test_unknown_explicit_township_blocks_known_one(client):
    result = parse(client, "09791234567, Hlaing, Atlantis Township")
    assert result.address.township is None
    assert result.confidence == "RED"


def test_repeated_township_is_not_ambiguous(client):
    result = parse(client, "09791234567, Hlaing / လှိုင်မြို့နယ်")
    assert result.address.township == "Hlaing"


def test_road_named_after_township_does_not_create_false_ambiguity(client):
    result = parse(client, "09791234567, Hlaing, Insein Road")
    assert result.address.township == "Hlaing"
    assert result.address.street == "Insein Road"


@pytest.mark.parametrize(
    "amount,expected",
    [
        ("COD: 25,000 MMK", 25000),
        ("COD ၂၅၀၀၀ ကျပ်", 25000),
        ("ငွေချေ: ၃၀၀၀၀", 30000),
        ("ကျသင့်ငွေ 45000 ကျပ်", 45000),
        ("25000 ကျပ် ကောက်ခံရန်", 25000),
        ("cash on delivery: 42000", 42000),
        ("COD: 0", 0),
        ("COD: 25000, note: call before arrival", 25000),
    ],
)
def test_cod_context(client, amount, expected):
    result = parse(client, f"09791234567, Hlaing, {amount}")
    assert result.address.cod_amount == expected
    assert result.field_sources["cod_amount"].status == "extracted"


@pytest.mark.parametrize(
    "text",
    [
        "3 pm",
        "ညနေ ၃ နာရီမှ လာပါ",
        "floor 4, unit 301",
        "order 12345, 10th Street",
        "delivery fee: 2500 MMK",
        "price: 25000 MMK",
        "quantity 3, 25000",
        "09:00 AM",
    ],
)
def test_unrelated_numbers_are_not_cod(client, text):
    result = parse(client, f"09791234567, Hlaing, {text}")
    assert result.address.cod_amount is None
    assert result.field_sources["cod_amount"].status == "missing"


@pytest.mark.parametrize(
    "text",
    [
        "COD: -25000",
        "COD: 25k",
        "COD: 2,50",
        "COD: 25000.50",
        "COD: 3 pm",
        "COD: tomorrow",
        "COD: 09791234567",
        "COD: 2 သိန်း",
        "COD: " + "9" * 5000,
    ],
)
def test_invalid_cod_requires_confirmation(client, text):
    result = parse(client, f"09791234567, Hlaing, {text}")
    assert result.address.cod_amount is None
    assert result.confidence == "RED"
    assert result.field_sources["cod_amount"].status == "invalid"


def test_conflicting_cod_is_critical(client):
    result = parse(client, "09791234567, Hlaing, COD 25000, COD 35000")
    assert result.address.cod_amount is None
    assert result.confidence == "RED"
    assert "AMBIGUOUS_COD_AMOUNT" in codes(result)


def test_missing_address_and_unverified_landmarks(client):
    missing = parse(client, "09791234567")
    assert missing.confidence == "RED"
    vague = parse(client, "09791234567, Hlaing, near tea shop")
    assert vague.address.landmark == "tea shop"
    assert vague.confidence == "AMBER"
    assert not vague.field_sources["landmark"].verified
    multiple = parse(client, "09791234567, Hlaing, near tea shop, beside school")
    assert multiple.address.landmark is None
    assert multiple.field_sources["landmark"].status == "ambiguous"
    assert multiple.confidence == "AMBER"


def test_floor_unit_instruction_and_time(client):
    result = parse(
        client, "09791234567, Kamaryut, 4th floor, room A3, note: call before arrival, 3 pm"
    )
    assert result.address.building_floor_unit == "4th floor; room A3"
    assert result.address.delivery_instructions == "call before arrival"
    assert result.address.time_window == "3 pm"


def test_conflicting_floors_and_time_are_explicit(client):
    result = parse(client, "09791234567, Hlaing, floor 4, floor 5, 3 pm, 5 pm")
    assert result.address.building_floor_unit is None
    assert result.field_sources["building_floor_unit"].status == "ambiguous"
    assert result.address.time_window is None
    assert result.field_sources["time_window"].status == "ambiguous"


def test_values_vary_with_input_and_nothing_is_fabricated(client):
    a = parse(client, "name: Ma Hla, 09791234567, Hlaing, COD 12000, Baho Road")
    b = parse(client, "name: Ko Min, 09951234567, Bahan, COD 56000, Parami Road")
    assert a.address.customer_name == "Ma Hla" and b.address.customer_name == "Ko Min"
    assert a.address.phone_number != b.address.phone_number
    assert a.address.township != b.address.township
    assert a.address.cod_amount != b.address.cod_amount
    assert a.address.street != b.address.street
    empty = parse(client, "hello")
    assert all(v is None for v in empty.address.model_dump().values())


@pytest.mark.parametrize(
    "unicode_text",
    [
        "လှိုင်မြို့နယ် ဗဟိုလမ်း အဆွေတော်နား",
        "ကမာရွတ်မြို့နယ် ပြည်လမ်း",
        "မြောက်ဥက္ကလာပမြို့နယ်",
    ],
)
def test_zawgyi_conversion(client, unicode_text):
    zawgyi = convert(unicode_text, "unicode", "zawgyi")
    result = parse(client, f"09791234567, {zawgyi}")
    assert result.original_text.endswith(zawgyi)
    assert result.normalization.encoding == "zawgyi"
    assert result.normalization.zawgyi_converted
    assert result.normalized_text.endswith(unicode_text)
    assert result.address.township is not None
    assert result.confidence == "AMBER"
    assert "ZAWGYI_CONVERSION_REVIEW" in codes(result)


def test_uncertain_encoding_is_not_silently_converted(client, monkeypatch):
    class Uncertain:
        def get_zawgyi_probability(self, text):
            return 0.5

    monkeypatch.setattr("app.parsing.normalization.detector", lambda: Uncertain())
    result = parse(client, "09791234567, လှိုင်မြို့နယ်")
    assert not result.normalization.zawgyi_converted
    assert "ENCODING_UNCERTAIN" in codes(result)
    assert result.confidence == "RED"


def test_conversion_failure_retains_text_and_warns(client, monkeypatch):
    def fail(*args):
        raise ValueError("private input")

    monkeypatch.setattr("app.parsing.normalization.convert", fail)
    text = "09791234567, ကမာ႐ြတ္ၿမိဳ႕နယ္"
    result = parse(client, text)
    assert result.original_text == result.normalized_text == text
    assert not result.normalization.zawgyi_converted
    assert "ZAWGYI_CONVERSION_FAILED" in codes(result)
    assert result.confidence == "RED"


def test_unicode_does_not_get_double_converted():
    text = "လှိုင်မြို့နယ် ဗဟိုလမ်း"
    normalized, info = normalize_text(text)
    assert normalized == text
    assert not info.zawgyi_converted


def test_fixed_zawgyi_sample_not_generated_by_converter(client):
    result = parse(client, "၀၉၇၉၁၂၃၄၅၆၇၊ လႈိင္ၿမိဳ႕နယ္၊ ဗဟိုလမ္း၊ အေဆြေတာ္နား")
    assert result.normalization.zawgyi_converted
    assert result.normalized_text == "09791234567၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ အဆွေတော်နား"
    assert result.address.street == "ဗဟိုလမ်း"
    assert result.address.landmark == "အဆွေတော်နား"


def trusted_fixture():
    # Synthetic trusted-catalog fixture only; never deployed as actual map data.
    return LocationCatalog(
        (
            TrustedLocation(
                township="Hlaing",
                field="street",
                name="Fixture Road",
                aliases=("Fixture Rd",),
                dataset="synthetic-test-only",
                source_url="https://example.test/location/1",
            ),
        )
    )


def test_green_requires_trusted_dataset_and_matching_township():
    with TestClient(create_app(Settings(_env_file=None), location_catalog=trusted_fixture())) as c:
        green = parse(c, "09791234567, Hlaing, Fixture Road")
        assert green.confidence == "GREEN"
        assert green.field_sources["street"].verified
        assert green.location_verification.dataset == "synthetic-test-only"
        assert green.location_verification.source_url == "https://example.test/location/1"
        wrong = parse(c, "09791234567, Bahan, Fixture Road")
        assert wrong.confidence == "AMBER"
        ambiguous = parse(c, "09791234567, Hlaing, Fixture Road, near school, near shop")
        assert ambiguous.confidence == "AMBER"
        critical = parse(c, "09791234567, Hlaing, Fixture Road, COD 10000, COD 20000")
        assert critical.confidence == "RED"


def test_duplicate_dataset_features_do_not_verify():
    catalog = trusted_fixture()
    catalog.entries = catalog.entries * 2
    assert catalog.verify("Hlaing", "street", "Fixture Road").status == "unverified"


def test_minimal_future_ai_payload_excludes_pii(client):
    result = parse(
        client,
        "name: Secret Customer, 09791234567, Hlaing, unit 345, COD 56000, note: Secret Customer",
    )
    payload = build_minimal_ai_input(result)
    assert json.loads(payload.raw_text) == {"purpose": "address_assistance", "township": "Hlaing"}
    for private in ["Secret Customer", "09791234567", "345", "56000", "note"]:
        assert private not in payload.raw_text
    result.address.township = "Secret Customer 09791234567"
    assert json.loads(build_minimal_ai_input(result).raw_text)["township"] is None


def test_rules_never_calls_ai_provider():
    from test_api import UnexpectedProvider

    with TestClient(create_app(Settings(_env_file=None), provider=UnexpectedProvider())) as c:
        assert parse(c, "09791234567, Hlaing").is_mock is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"raw_text": ""},
        {"raw_text": " \n "},
        {"raw_text": 12},
        {"raw_text": None},
        {"raw_text": "x" * 10001},
        {"raw_text": "hello", "verified": True},
    ],
)
def test_rules_request_validation(client, payload):
    assert client.post("/api/orders/parse", json=payload).status_code == 422


def test_rules_malformed_and_boundary_request(client):
    assert (
        client.post(
            "/api/orders/parse", content="{", headers={"Content-Type": "application/json"}
        ).status_code
        == 422
    )
    assert parse(client, "x" * 10000).confidence == "RED"
    with pytest.raises(ValueError):
        ParseRequest(raw_text=" " * 10000 + "a")


@pytest.mark.parametrize(
    "text", ["COD 25 lakh", "COD 25000+2500", "COD 25000 MMK + 2500", "COD 25x2"]
)
def test_unsupported_amount_expressions_not_truncated(client, text):
    result = parse(client, f"09791234567, Hlaing, {text}")
    assert result.address.cod_amount is None
    assert result.confidence == "RED"


@pytest.mark.parametrize("text", ["25 pm", "3:99 pm", "ညနေ ၂၅ နာရီ"])
def test_invalid_time_requires_review(client, text):
    result = parse(client, f"09791234567, Hlaing, {text}")
    assert result.address.time_window is None
    assert result.field_sources["time_window"].status == "invalid"


def test_parser_mode_defaults_and_configuration(monkeypatch):
    monkeypatch.delenv("LANNPYA_PARSER_MODE", raising=False)
    assert Settings(_env_file=None).parser_mode == "hybrid"
    monkeypatch.setenv("LANNPYA_PARSER_MODE", "mock")
    assert Settings(_env_file=None).parser_mode == "mock"
    monkeypatch.setenv("LANNPYA_PARSER_MODE", "invalid")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "text", ["COD 25 USD", "COD 25 THB", "COD 25 dollars", "prepaid, COD 25000"]
)
def test_foreign_currency_or_prepaid_conflict_requires_review(client, text):
    result = parse(client, f"09791234567, Hlaing, {text}")
    assert result.address.cod_amount is None
    assert result.field_sources["cod_amount"].status == "invalid"
    assert result.confidence == "RED"


def test_identifiers_do_not_turn_into_amounts_or_contact_numbers(client):
    cod = parse(client, "09791234567, Hlaing, order #123 COD")
    assert cod.address.cod_amount is None
    assert cod.confidence == "RED"
    phone = parse(client, "order: 09791234567, Hlaing")
    assert phone.address.phone_number is None
    assert phone.confidence == "RED"
