"""Export the application's real OpenAPI document without database or provider calls."""

import json

from app.core.config import Settings
from app.db.session import BACKEND_ROOT
from app.main import create_app


def main():
    schema = create_app(Settings(_env_file=None, order_management_enabled=False)).openapi()
    output = BACKEND_ROOT.parent / "docs" / "OPENAPI.json"
    output.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    count = sum(len(methods) for methods in schema["paths"].values())
    print(f"Exported {count} operations to docs/OPENAPI.json; no database calls.")


if __name__ == "__main__":
    main()
