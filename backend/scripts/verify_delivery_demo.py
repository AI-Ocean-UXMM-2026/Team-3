"""One-command isolated real-HTTP demo verification and redacted frontend samples."""

import json

from demo_mvp import LocalDemo

from app.db.session import BACKEND_ROOT


def main():
    demo = LocalDemo()
    try:
        demo.setup_and_verify()
        demo.close()
        summary = demo.verify_persistence(demo.orders["cod_delivery"])
        output = BACKEND_ROOT.parent / "docs/overnight_audit"
        output.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"summary": summary, "samples": demo.cases}, ensure_ascii=False, indent=2
        )
        for secret in demo.redactions:
            payload = payload.replace(secret, "[REDACTED_DEMO_VALUE]")
        assert not any(secret in payload for secret in demo.redactions)
        (output / "frontend_samples.json").write_text(payload + "\n", encoding="utf-8")
        (output / "demo_results.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"passed": True, **summary}, indent=2))
    finally:
        demo.close()


if __name__ == "__main__":
    main()
