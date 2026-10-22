# Final OTP compatibility fix

## Changes

- `backend/app/services/buyer_otp.py`: normalize OTP destinations with the installed `phonenumbers` Myanmar region metadata and require a valid Myanmar mobile number. This accepts the existing order validator's national `0991234567` input and formats it as `+95991234567`, while keeping the existing `09`, `+95`, `95`, and supported no-leading-zero national forms.
- `backend/app/services/buyer_otp.py`: treat only Twilio HTTP 404 responses with JSON integer code `20404` during cancellation as already terminal. Other provider errors remain unavailable/fail-closed.
- `backend/tests/test_buyer_confirmation.py`: add regressions for order-validator-compatible OTP start, supported and rejected phone inputs, terminal missing-resource cancellation with replacement SID persistence/use, unrelated or malformed cancellation errors, and verification-check 404 behavior.

## Verification

RED, before the service fix:

```powershell
& 'C:/Users/minth/Downloads/Ai ocean/lannpya-mtt/backend/.venv/Scripts/python.exe' -m pytest tests/test_buyer_confirmation.py -k 'myanmar_phone_normalization or otp_accepts_number_validated_by_order_phone_validator or twilio_resend_cancels_and_checks_the_stored_sid or twilio_unrelated_or_malformed_cancel_404_fails_closed or twilio_missing_resource_during_check_remains_fail_closed' -q --basetemp='C:/Users/minth/Downloads/Ai ocean/lannpya-flow/backend/.pytest-tmp-finalfix-red'
```

Result: **3 failed, 6 passed, 85 deselected**. Failures were the `0991234567` normalizer case, OTP start for the number accepted by the order validator, and resend after Twilio returned cancellation 404/code 20404.

GREEN, after the final test adjustments:

```powershell
& 'C:/Users/minth/Downloads/Ai ocean/lannpya-mtt/backend/.venv/Scripts/python.exe' -m pytest tests/test_buyer_confirmation.py -k 'myanmar_phone_normalization or otp_accepts_number_validated_by_order_phone_validator or twilio_resend_cancels_and_checks_the_stored_sid or twilio_unrelated_or_malformed_cancel_error_fails_closed or twilio_missing_resource_during_check_remains_fail_closed' -q --basetemp='C:/Users/minth/Downloads/Ai ocean/lannpya-flow/backend/.pytest-tmp-finalfix-final2'
```

Result: **13 passed, 85 deselected**. `git diff --check` was clean. The only test output warnings were three existing SWIG deprecation warnings.

## Provider error behavior

Cancellation continues only for the exact pair HTTP 404 and provider JSON integer code `20404`. Wrong provider codes, malformed/non-JSON 404 responses, and code 20404 on HTTP 500 stay fail-closed. A 404/code 20404 from verification check also stays fail-closed; the test confirms the challenge remains pending and failed-attempt counters do not change. No live provider requests were made.

## Concerns

No known concerns. The broad suite and browser flows were not rerun, per scope.
