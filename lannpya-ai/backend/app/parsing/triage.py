from app.parsing.places import LocationCatalog
from app.schemas.orders import (
    AddressFields,
    Confidence,
    FieldSource,
    LocationVerification,
    NormalizationInfo,
    ValidationReason,
)


def classify(
    address: AddressFields,
    sources: dict[str, FieldSource],
    normalization: NormalizationInfo,
    catalog: LocationCatalog,
) -> tuple[Confidence, list[ValidationReason], LocationVerification]:
    reasons = list(normalization.warnings)
    critical = any(w.code in {"ENCODING_UNCERTAIN", "ZAWGYI_CONVERSION_FAILED"} for w in reasons)
    for field in ("phone_number", "township", "cod_amount"):
        source = sources[field]
        required = field != "cod_amount"
        if source.status in {"ambiguous", "invalid"} or (required and source.status == "missing"):
            critical = True
            code = f"{source.status.upper()}_{field.upper()}"
            reasons.append(
                ValidationReason(
                    code=code,
                    message=(
                        f"{field.replace('_', ' ').capitalize()} is {source.status}; "
                        "dispatcher confirmation is required."
                    ),
                )
            )
    if critical:
        return Confidence.RED, reasons, LocationVerification()

    for field in ("street", "landmark"):
        source = sources[field]
        if source.method == "ai" or source.requires_review:
            continue
        verification = catalog.verify(address.township, field, getattr(address, field))
        if source.status == "extracted" and verification.status == "verified":
            source.verified, source.dataset = True, verification.dataset
            if not reasons and all(
                s.status not in {"ambiguous", "invalid"} and not s.requires_review
                for s in sources.values()
            ):
                return (
                    Confidence.GREEN,
                    [
                        ValidationReason(
                            code="LOCATION_DATASET_MATCH",
                            message=(
                                "Valid Myanmar mobile format, matched township, and a "
                                "township-specific trusted location dataset match. "
                                "Reachability and delivery pin are not verified."
                            ),
                        )
                    ],
                    verification,
                )
    for field, source in sources.items():
        if source.status in {"ambiguous", "invalid"}:
            reasons.append(
                ValidationReason(
                    code=f"{source.status.upper()}_{field.upper()}",
                    message=(
                        f"{field.replace('_', ' ').capitalize()} needs confirmation; "
                        "candidates were not resolved automatically."
                    ),
                )
            )
    reasons.append(
        ValidationReason(
            code="LOCATION_UNVERIFIED",
            message=(
                "Phone format is valid and township matched, but location requires buyer "
                "or dispatcher confirmation. Extracted landmarks are not geospatial verification."
            ),
        )
    )
    if not catalog.entries:
        reasons.append(
            ValidationReason(
                code="LOCATION_DATASET_UNAVAILABLE",
                message="No trusted street/landmark catalog is configured; GREEN is disabled.",
            )
        )
    return Confidence.AMBER, reasons, LocationVerification()
