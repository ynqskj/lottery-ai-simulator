from dataclasses import dataclass, field
from typing import Any, Dict, Tuple, Optional


Pick3D = Tuple[int, int, int]
Pick5D = Tuple[int, int, int, int, int]


@dataclass(frozen=True)
class SsqPick:
    red: Tuple[int, int, int, int, int, int]
    blue: int

    @property
    def red_text(self) -> str:
        return " ".join(f"{value:02d}" for value in self.red)

    @property
    def number_text(self) -> str:
        return f"{self.red_text} + {self.blue:02d}"


@dataclass(frozen=True)
class DltPick:
    front: Tuple[int, int, int, int, int]
    back: Tuple[int, int]

    @property
    def front_text(self) -> str:
        return " ".join(f"{value:02d}" for value in self.front)

    @property
    def back_text(self) -> str:
        return " ".join(f"{value:02d}" for value in self.back)

    @property
    def number_text(self) -> str:
        return f"{self.front_text} + {self.back_text}"


@dataclass(frozen=True)
class QxcPick:
    front: Tuple[int, int, int, int, int, int]
    special: int

    @property
    def front_text(self) -> str:
        return " ".join(str(value) for value in self.front)

    @property
    def number_text(self) -> str:
        return f"{self.front_text} + {self.special:02d}"


@dataclass(frozen=True)
class QlcPick:
    numbers: Tuple[int, int, int, int, int, int, int]

    @property
    def number_text(self) -> str:
        return " ".join(f"{value:02d}" for value in self.numbers)


@dataclass(frozen=True)
class QlcDrawNumbers:
    basic: Tuple[int, int, int, int, int, int, int]
    special: int

    @property
    def basic_text(self) -> str:
        return " ".join(f"{value:02d}" for value in self.basic)

    @property
    def number_text(self) -> str:
        return f"{self.basic_text} + {self.special:02d}"


@dataclass(frozen=True)
class Kl8Pick:
    numbers: Tuple[int, ...]

    @property
    def number_text(self) -> str:
        return " ".join(f"{value:02d}" for value in self.numbers)


@dataclass(frozen=True)
class Draw3D:
    issue: str
    draw_date: str
    numbers: Pick3D
    source: str = "17500"
    prize_amounts: Dict[str, float] = field(default_factory=dict)
    special_prize_active: Optional[bool] = None
    prize_pool: Optional[float] = None

    @property
    def number_text(self) -> str:
        return "".join(str(n) for n in self.numbers)


@dataclass(frozen=True)
class Draw5D:
    issue: str
    draw_date: str
    numbers: Pick5D
    source: str = "17500-pl5"
    prize_amounts: Dict[str, float] = field(default_factory=dict)
    special_prize_active: Optional[bool] = None
    prize_pool: Optional[float] = None

    @property
    def number_text(self) -> str:
        return "".join(str(n) for n in self.numbers)


@dataclass(frozen=True)
class DrawSSQ:
    issue: str
    draw_date: str
    numbers: SsqPick
    source: str = "17500-ssq"
    prize_amounts: Dict[str, float] = field(default_factory=dict)
    special_prize_active: Optional[bool] = None
    prize_pool: Optional[float] = None


@dataclass(frozen=True)
class DrawDLT:
    issue: str
    draw_date: str
    numbers: DltPick
    source: str = "17500-dlt"
    prize_amounts: Dict[str, float] = field(default_factory=dict)
    special_prize_active: Optional[bool] = None
    prize_pool: Optional[float] = None


@dataclass(frozen=True)
class DrawQXC:
    issue: str
    draw_date: str
    numbers: QxcPick
    source: str = "17500-qxc"
    prize_amounts: Dict[str, float] = field(default_factory=dict)
    special_prize_active: Optional[bool] = None
    prize_pool: Optional[float] = None


@dataclass(frozen=True)
class DrawQLC:
    issue: str
    draw_date: str
    numbers: QlcDrawNumbers
    source: str = "17500-qlc"
    prize_amounts: Dict[str, float] = field(default_factory=dict)
    special_prize_active: Optional[bool] = None
    prize_pool: Optional[float] = None


@dataclass(frozen=True)
class DrawKL8:
    issue: str
    draw_date: str
    numbers: Tuple[int, ...]
    source: str = "17500-kl8"
    prize_amounts: Dict[str, float] = field(default_factory=dict)
    special_prize_active: Optional[bool] = None
    prize_pool: Optional[float] = None

    @property
    def number_text(self) -> str:
        return " ".join(f"{value:02d}" for value in self.numbers)


@dataclass(frozen=True)
class BetResult:
    issue: str
    draw_numbers: Any
    pick_numbers: Any
    hit: bool
    cost: int
    payout: float
    payout_basis: str = "estimated"


@dataclass(frozen=True)
class BacktestResult:
    game_name: str
    total_draws: int
    total_bets: int
    total_cost: int
    total_payout: int
    hit_distribution: Dict[str, int]
    bet_results: Tuple[BetResult, ...]

    @property
    def roi(self) -> float:
        if self.total_cost == 0:
            return 0.0
        return self.total_payout / self.total_cost
