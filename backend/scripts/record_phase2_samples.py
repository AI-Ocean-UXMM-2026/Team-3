"""Record synthetic integration samples using actual API responses, never user data."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

SAMPLES = {
    "unicode_digits_cod": "၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ COD ၂၅၀၀၀",
    "missing_phone": "လှိုင်မြို့နယ် ဗဟိုလမ်း အဆွေတော်နား",
    "ambiguous_townships": "09791234567, Hlaing to Bahan, COD 25000",
    "fixed_zawgyi": "၀၉၇၉၁၂၃၄၅၆၇၊ လႈိင္ၿမိဳ႕နယ္၊ ဗဟိုလမ္း၊ အေဆြေတာ္နား",
    "time_is_not_cod": "09791234567, Kamaryut, 4th floor, room A3, 3 pm",
}


def main() -> None:
    samples = []
    with TestClient(create_app(Settings(_env_file=None, parser_mode="rules"))) as client:
        for name, text in SAMPLES.items():
            request = {"raw_text": text}
            response = client.post("/api/orders/parse", json=request)
            assert response.status_code == 200
            samples.append(
                {
                    "name": name,
                    "request": request,
                    "http_status": response.status_code,
                    "response": response.json(),
                }
            )
    output = Path(__file__).resolve().parents[2] / "docs" / "PHASE2_SAMPLE_RESPONSES.json"
    output.write_text(json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(samples)} actual synthetic-sample API responses in {output.name}")


if __name__ == "__main__":
    main()
