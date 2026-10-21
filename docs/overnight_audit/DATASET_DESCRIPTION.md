# Synthetic delivery corpus

`backend/tests/fixtures/delivery_corpus.json` contains **300 records**, generated from
30 explicit scenario families with ten controlled variations each. Rebuild from backend:

```powershell
.\.venv\Scripts\python.exe scripts\build_audit_corpus.py
```

The generator defines expected phone/COD/township and triage or explicit uncertainty
independently of parser output. Templates vary township aliases, amounts, floors, instructions
and representation. These are constructed regression messages, not 300 independent natural
customer observations. Phone-format fixtures are not reserved or proven unassigned: never
contact them. No geospatial coordinates are asserted as real ground truth.
Supported spelling aliases include Kamayut and San Chaung; unsupported `HLG t/s`
abbreviations explicitly expect no township match rather than a guessed area.

Families: Unicode, Burmese digits, Myanglish, mixed text, missing/invalid/duplicate/conflicting
phones, missing COD, prepaid, negative/huge/conflicting/decimal/foreign-currency COD, time-only,
unknown/multiple townships, landmark, floor/unit, instructions, prompt injection, NUL,
oversized input, whitespace, fixed Zawgyi spelling, Unicode noise, unlabelled amount,
contradictory notes and invalid coordinate text.

270 records are valid requests and 30 are intended validation failures (NUL, oversized or
blank). Ten short mixed-encoding records have no single expected triage: they may be AMBER
or RED if encoding is explicitly uncertain. These are excluded from exact confidence scoring.
Optional free-text extraction and arbitrary prose semantics are not scored. Coordinate text
in a message must not become a geocoded pin. Separate schema/property tests reject invalid
numeric coordinates. Fixed Zawgyi fixtures exercise supported conversion, not a claim of
general encoding accuracy.
