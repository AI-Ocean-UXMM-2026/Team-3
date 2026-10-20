"""Verify real loopback HTTP endpoints; always stop the server started here."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx2 as httpx

from app.schemas.orders import ParseResponse


def main() -> None:
    # Windows pipes may default to cp1252; samples contain actual Burmese text.
    sys.stdout.reconfigure(encoding="utf-8")
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--mode", choices=["rules", "hybrid"], default="hybrid")
    mode = arguments.parse_args().mode
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "LANNPYA_PARSER_MODE": mode, "LANNPYA_AI_PROVIDER": "mock"},
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            deadline = time.monotonic() + 30
            while True:
                if server.poll() is not None:
                    raise RuntimeError("Smoke server exited before becoming ready")
                try:
                    health = client.get("/health")
                    break
                except httpx.ConnectError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Smoke server did not become ready") from None
                    time.sleep(0.1)
            assert health.status_code == 200
            assert health.json() == {"status": "ok", "service": "LannPya AI"}
            response = client.post(
                "/api/orders/parse",
                json={
                    "raw_text": "လှိုင်မြို့နယ် ဗဟိုလမ်း အဆွေတော်နား",
                },
            )
            assert response.status_code == 200
            parsed = ParseResponse.model_validate(response.json())
            assert not parsed.is_mock and parsed.confidence == "RED"
            assert parsed.address.township == "Hlaing"
            valid = client.post(
                "/api/orders/parse",
                json={
                    "raw_text": "၀၉၇၉၁၂၃၄၅၆၇၊ လှိုင်မြို့နယ်၊ ဗဟိုလမ်း၊ COD ၂၅၀၀၀",
                },
            )
            valid_parsed = ParseResponse.model_validate(valid.json())
            assert valid.status_code == 200
            assert valid_parsed.address.phone_number == "09791234567"
            assert valid_parsed.address.cod_amount == 25000
            assert valid_parsed.confidence == "AMBER"
            hybrid_ai = None
            if mode == "hybrid":
                enriched = client.post(
                    "/api/orders/parse",
                    json={
                        "raw_text": "09791234567, Hlaing, COD 25000, address: behind red gate",
                    },
                )
                assert enriched.status_code == 200
                enriched_data = ParseResponse.model_validate(enriched.json())
                assert enriched_data.ai.status == "mock" and enriched_data.ai.is_mock
                assert enriched_data.address.phone_number == "09791234567"
                assert enriched_data.address.cod_amount == 25000
                assert enriched_data.address.landmark is None
                hybrid_ai = enriched_data.ai.model_dump()
            invalid = client.post("/api/orders/parse", json={"raw_text": " "})
            assert invalid.status_code == 422
            print(
                json.dumps(
                    {
                        "health": {"http_status": health.status_code, "body": health.json()},
                        "missing_phone_parse": {
                            "http_status": response.status_code,
                            "confidence": parsed.confidence,
                        },
                        "rules_parse": {
                            "http_status": valid.status_code,
                            "is_mock": valid_parsed.is_mock,
                            "address": valid_parsed.address.model_dump(),
                            "confidence": valid_parsed.confidence,
                        },
                        "empty_text_http_status": invalid.status_code,
                        "parser_mode": mode,
                        "hybrid_ai": hybrid_ai,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


if __name__ == "__main__":
    main()
