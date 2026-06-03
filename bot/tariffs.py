from dataclasses import dataclass


@dataclass(frozen=True)
class Tariff:
    key: str
    title: str
    description: str
    amount_rub: int

    @property
    def amount_kopecks(self) -> int:
        return self.amount_rub * 100


TARIFFS: dict[str, Tariff] = {
    "light": Tariff(
        key="light",
        title="Лайт",
        description="Лайт-тариф",
        amount_rub=600,
    ),
    "basic": Tariff(
        key="basic",
        title="Базовый минимум",
        description="Базовый минимум",
        amount_rub=900,
    ),
    "luxury": Tariff(
        key="luxury",
        title="Роскошный максимум",
        description="Роскошный максимум",
        amount_rub=2000,
    ),
}


def get_tariff(key: str) -> Tariff:
    try:
        return TARIFFS[key]
    except KeyError as exc:
        raise ValueError(f"Unknown tariff: {key}") from exc
