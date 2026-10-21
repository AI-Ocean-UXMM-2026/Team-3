# Deterministic parser evaluation

Executed `scripts/evaluate_parser.py` against the checked-in 300-record fixture. Actual
machine-readable counts are in [parser_results.json](parser_results.json).

| Measurement | Observed matches / evaluated cases |
| --- | --- |
| Phone field, including correct null/ambiguity | 270 / 270 |
| Positive supported mobile extraction | 240 / 240 |
| Township field, including correct null/ambiguity | 270 / 270 |
| Positive supported township extraction | 250 / 250 |
| COD field, including invalid/missing null | 270 / 270 |
| Positive explicit whole-MMK COD | 190 / 190 |
| Exact deterministic confidence labels | 260 / 260 |
| Mixed-encoding confidence excluded as uncertain | 10 |
| Invalid input rejected | 30 / 30 |
| Original valid input preserved | 270 / 270 |
| Evidence offsets match normalized text | 270 / 270 |
| Burmese digit normalization | 10 / 10 |

No overall AI accuracy is calculated: this evaluation invokes the deterministic service
directly, not a real model. Scores are template-corpus regression results, not estimates of
Myanmar delivery accuracy. Unknown free text and independent map accuracy are unscored.

The first corpus pass exposed six RED classifications where the initial fixture assumed
AMBER. Inspection showed encoding uncertainty in short mixed-script fragments, not wrong
phone/COD/township extraction. The corpus now explicitly marks this family uncertain rather
than weakening the parser's safety rule or pretending there is ground truth.

Four deterministic Hypothesis tests run up to 50 examples each: arbitrary scalar Unicode
normalization, negative structured COD, invalid latitude and missing phone/unknown township.
Settings use derandomize, no example database, bounded text/numbers and no deadline.
[Hypothesis settings reference](https://hypothesis.readthedocs.io/en/latest/settings.html).
