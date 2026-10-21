import random
from dataclasses import asdict, dataclass

from tools.logistics_lab.config import SimulationConfig

PLACES = (
    ("လှိုင်မြို့နယ်", "Hlaing"),
    ("Kamayut Township", "Kamaryut"),
    ("San Chaung Township", "Sanchaung"),
    ("Bahan Township", "Bahan"),
    ("Tamwe Township", "Tamwe"),
    ("North Dagon Township", "North Dagon"),
)
KINDS = (
    "complete",
    "sparse",
    "invalid_phone",
    "missing_address",
    "prepaid",
    "reschedule",
    "pin_confirmation",
    "conflicting_phone",
    "green_candidate",
)
DEMO_KINDS = (
    "pin_confirmation",
    "reschedule",
    "prepaid",
    "complete",
    "invalid_phone",
    "missing_address",
    "duplicate",
    "green_candidate",
    "sparse",
    "conflicting_phone",
)


@dataclass(frozen=True)
class PlannedOrder:
    reference: str
    merchant: int
    hub: int
    kind: str
    raw_text: str
    phone_last_four: str
    confirm: bool
    fail: bool
    duplicate_of: str | None = None

    def public(self):
        # Raw input and phone challenge fixture remain in memory only.
        return {k: v for k, v in asdict(self).items() if k not in {"raw_text", "phone_last_four"}}


def generate_plan(config: SimulationConfig) -> list[PlannedOrder]:
    randomizer = random.Random(config.seed)
    result = []
    for i in range(config.orders):
        kind = DEMO_KINDS[i % len(DEMO_KINDS)] if config.demo else randomizer.choice(KINDS)
        alias, _ = PLACES[i % len(PLACES)]
        phone = "0979" + f"{randomizer.randrange(10000000):07d}"
        amount = 0 if kind == "prepaid" else randomizer.choice((12000, 25000, 35000, 48000))
        parts = [phone, alias, f"Street: Demo lane {i + 1}", f"COD {amount}"]
        if kind == "invalid_phone":
            parts[0] = "phone: 09123"
        elif kind == "conflicting_phone":
            parts[0] += ", 09960000000"
        elif kind == "missing_address":
            parts[1:3] = ["Unknownville Township"]
        elif kind == "sparse":
            parts.pop(2)
        elif kind == "green_candidate":
            parts[2] = "Street: Demo candidate road"
            parts += ["landmark: Demo clothing shop", "floor: 2"]
        raw = ", ".join(parts)
        if i % 3 == 0:
            raw = raw.translate(str.maketrans("0123456789", "၀၁၂၃၄၅၆၇၈၉"))
        duplicate = None
        merchant, hub = i % config.merchants, i % config.hubs
        # Repeated input deliberately creates a distinct backend order: create has no dedup key.
        if i and (kind == "duplicate" or (not config.demo and i % 29 == 0)):
            original = result[0]
            raw, phone = original.raw_text, "0979000" + original.phone_last_four
            duplicate, merchant = original.reference, original.merchant
            kind = "duplicate"
        result.append(
            PlannedOrder(
                reference=f"LAB-{i + 1:05d}",
                merchant=merchant,
                hub=hub,
                kind=kind,
                raw_text=raw,
                phone_last_four=phone[-4:],
                confirm=kind in {"reschedule", "pin_confirmation"}
                or randomizer.random() < config.confirmation_rate,
                fail=(config.demo and i == 2)
                or (not config.demo and randomizer.random() < config.delivery_failure_rate),
                duplicate_of=duplicate,
            )
        )
    return result
