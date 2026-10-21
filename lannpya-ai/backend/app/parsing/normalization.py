import logging
import re
import unicodedata
from functools import lru_cache

from myanmar.converter import convert
from myanmartools import ZawgyiDetector

from app.schemas.orders import NormalizationInfo, ValidationReason

logger = logging.getLogger(__name__)
DIGITS = str.maketrans("၀၁၂၃၄၅၆၇၈၉", "0123456789")


@lru_cache(maxsize=1)
def detector() -> ZawgyiDetector:
    return ZawgyiDetector()


def normalize_text(original: str) -> tuple[str, NormalizationInfo]:
    info = NormalizationInfo(encoding="non_myanmar")
    text = original
    # Myanmar digits alone do not need encoding detection.
    if re.search(r"[\u1000-\u103f\u1050-\u109f]", text):
        probability = detector().get_zawgyi_probability(text)
        info.encoding = "unicode_or_undetermined"
        if probability >= 0.95:
            info.encoding = "zawgyi"
            try:
                converted = convert(text, "zawgyi", "unicode")
                # python-myanmar can emit u-vowel before i-vowel; order these
                # two marks consistently. This does not repair arbitrary spelling.
                text = converted.replace("\u102f\u102d", "\u102d\u102f")
                info.zawgyi_converted = True
                info.warnings.append(
                    ValidationReason(
                        code="ZAWGYI_CONVERSION_REVIEW",
                        message=(
                            "Zawgyi was converted locally; confirm the converted address spelling."
                        ),
                    )
                )
            except Exception as exc:
                logger.warning("Local Zawgyi conversion failed: %s", type(exc).__name__)
                info.warnings.append(
                    ValidationReason(
                        code="ZAWGYI_CONVERSION_FAILED",
                        message=(
                            "Zawgyi conversion failed; original text retained. "
                            "Unicode confirmation is required."
                        ),
                    )
                )
        elif probability > 0.05:
            info.encoding = "ambiguous"
            info.warnings.append(
                ValidationReason(
                    code="ENCODING_UNCERTAIN",
                    message=(
                        "Encoding could not be safely determined; text was not converted. "
                        "Confirm Unicode text."
                    ),
                )
            )
    text = unicodedata.normalize("NFC", text)
    info.digits_normalized = text != text.translate(DIGITS)
    return text.translate(DIGITS), info
