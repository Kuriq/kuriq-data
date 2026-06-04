from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


@dataclass
class StudySpaceRecord:
    name: str
    type: str
    address: str
    latitude: Decimal
    longitude: Decimal
    operating_hours: str | None = None
    phone: str | None = None
    has_wifi: bool = False
    has_power_outlet: bool = False
    is_active: bool = True
    last_updated_at: datetime | None = None

    def unique_key(self) -> tuple[str, str, str]:
        return (self.name.strip(), self.address.strip(), self.type.strip())

    @staticmethod
    def quantize_coordinate(value: float) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.0000001"), rounding=ROUND_HALF_UP)
