from lottery_sim.issue_calendar import normalize_issue
from lottery_sim.prize_rules import evaluate_draw_prize
import json
import hashlib
import math
import heapq
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

from lottery_sim.models import (
    BacktestResult,
    BetResult,
    DltPick,
    Draw3D,
    Draw5D,
    DrawDLT,
    DrawKL8,
    DrawQLC,
    DrawQXC,
    Kl8Pick,
    QlcPick,
    QxcPick,
)
from lottery_sim.recommendations import Candidate


DEFAULT_WINDOWS: Tuple[int, ...] = (5, 10, 30, 60, 100, 200)


@dataclass(frozen=True)
class NumberGroupSpec:
    name: str
    min_number: int
    max_number: int
    pick_count: int


@dataclass(frozen=True)
class GenericMlAdapter:
    game_code: str
    game_name: str
    groups: Tuple[NumberGroupSpec, ...]
    extract_groups: Callable[[Any], Tuple[Tuple[int, ...], ...]]
    build_pick: Callable[[Tuple[Tuple[int, ...], ...]], Any]


@dataclass(frozen=True)
class BinaryLogisticModel:
    weights: Tuple[float, ...]


@dataclass(frozen=True)
class NumberGroupModel:
    spec: NumberGroupSpec
    model: BinaryLogisticModel


@dataclass(frozen=True)
class GenericMlModel:
    game_code: str
    game_name: str
    feature_names: Tuple[str, ...]
    windows: Tuple[int, ...]
    min_history: int
    training_draw_count: int
    training_target_count: int
    groups: Tuple[NumberGroupModel, ...]
    history_until_issue: str = ""
    training_epochs: int = 0
    history_fingerprint: str = ""


def ml_adapter_for_game(game_code: str, pick_size: int = 10) -> GenericMlAdapter:
    if game_code == "3d":
        return _pick3_adapter("3d", "福彩3D直选")
    if game_code == "pl3":
        return _pick3_adapter("pl3", "排列三直选")
    if game_code == "pl5":
        return _pl5_adapter()
    if game_code == "qxc":
        return _qxc_adapter()
    if game_code == "qlc":
        return _qlc_adapter()
    if game_code == "kl8":
        return _kl8_adapter(pick_size)
    if game_code == "dlt":
        return _dlt_adapter()
    raise ValueError(f"unsupported ML game: {game_code}")


def history_fingerprint(draws):
    """Hash the actual training observations, independent of caller order."""
    observations = [
        (draw.issue, draw.draw_date, asdict(draw.numbers) if is_dataclass(draw.numbers) else draw.numbers)
        for draw in sorted(draws, key=lambda draw: normalize_issue(draw.issue))
    ]
    payload = json.dumps(observations, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def train_generic_ml_model(
    draws: Sequence[Any],
    adapter: GenericMlAdapter,
    min_history: int = 30,
    windows: Sequence[int] = DEFAULT_WINDOWS,
    epochs: int = 30,
    learning_rate: float = 0.04,
    l2: float = 0.001,
) -> GenericMlModel:
    ordered = tuple(sorted(draws, key=lambda draw: normalize_issue(draw.issue)))
    if len(ordered) <= min_history:
        raise ValueError(f"not enough draws to train {adapter.game_code} ML model")

    feature_names = _feature_names(tuple(windows))
    group_models: List[NumberGroupModel] = []
    for group_index, spec in enumerate(adapter.groups):
        rows = _build_rows(ordered, adapter, group_index, min_history, tuple(windows))
        weights = _fit_logistic(rows, len(feature_names), epochs, learning_rate, l2)
        group_models.append(NumberGroupModel(spec=spec, model=BinaryLogisticModel(weights)))

    return GenericMlModel(
        game_code=adapter.game_code,
        game_name=adapter.game_name,
        feature_names=feature_names,
        windows=tuple(windows),
        min_history=min_history,
        training_draw_count=len(ordered),
        training_target_count=len(ordered) - min_history,
        groups=tuple(group_models),
        history_until_issue=ordered[-1].issue,
        training_epochs=epochs,
        history_fingerprint=history_fingerprint(ordered),
    )


def recommend_generic_ml(
    draws: Sequence[Any],
    model: GenericMlModel,
    adapter: GenericMlAdapter,
    count: int = 10,
    position_counts: Sequence[int] = (),
    combination_mode: str = "top",
) -> List[Candidate]:
    if not 1 <= count <= 1000:
        raise ValueError("候选数量必须在1到1000之间")
    if model.game_code != adapter.game_code:
        raise ValueError(f"model game {model.game_code} does not match adapter {adapter.game_code}")

    if tuple(g.spec for g in model.groups) != adapter.groups:
        raise ValueError("模型玩法与当前玩法不匹配，请重新训练")
    if not draws:
        raise ValueError("没有历史开奖数据")
    if combination_mode not in {"top", "full"}:
        raise ValueError("组合模式必须是top或full")
    history = tuple(sorted(draws, key=lambda draw: normalize_issue(draw.issue)))
    ranked_groups = [
        _score_group(history, adapter, group_index, group_model, model.windows)
        for group_index, group_model in enumerate(model.groups)
    ]
    group_variants = [
        _group_variants(scores, group_model.spec.pick_count, count)
        for scores, group_model in zip(ranked_groups, model.groups)
    ]

    pool_description = ""
    if position_counts:
        if any(g.pick_count != 1 for g in adapter.groups) or len(position_counts) != len(adapter.groups):
            raise ValueError("每位数量仅支持直选彩种，且必须与数位数量一致")
        if any(not isinstance(n, int) or not 1 <= n <= len(scores) for n, scores in zip(position_counts, ranked_groups)):
            raise ValueError("每位数量超过号码范围")
        group_variants = [[((number,), score) for number, score in scores[:n]] for n, scores in zip(position_counts, ranked_groups)]
        pool_description = "；号码池 " + " / ".join(",".join(str(number) for number, _ in scores[:n]) for n, scores in zip(position_counts, ranked_groups))
        total = math.prod(position_counts)
        if combination_mode == "full":
            if total > 1000:
                raise ValueError("完整组合超过1000注，请减少每位数量或选择前N注")
            count = total
        elif count > total:
            raise ValueError(f"号码池仅有{total}种组合，小于请求的{count}注")
    elif combination_mode == "full":
        raise ValueError("完整组合需要设置每位数量")

    candidates: List[Candidate] = []
    seen = set()
    for chosen in _rank_group_products(group_variants, limit=count):
        group_numbers = tuple(numbers for numbers, _ in chosen)
        probability = sum(score for _, score in chosen) / len(chosen)
        pick = adapter.build_pick(group_numbers)
        number_text = _number_text(pick)
        if number_text in seen:
            continue
        seen.add(number_text)
        candidates.append(Candidate(
            rank=len(candidates) + 1,
            strategy_name=f"{adapter.game_name}机器学习",
            numbers=pick,
            number_text=number_text,
            reason=f"模型均值评分{probability:.3f}，训练历史{model.training_draw_count}期{pool_description}",
        ))
        if len(candidates) >= count:
            return candidates

    raise ValueError(f"只能生成{len(candidates)}注，无法满足请求的{count}注")


def run_generic_ml_backtest(
    draws: Sequence[Any],
    adapter: GenericMlAdapter,
    game: Any,
    min_train: int = 200,
    limit: int = 120,
    retrain_every: int = 20,
    min_history: int = 30,
    epochs: int = 12,
) -> BacktestResult:
    ordered = tuple(sorted(draws, key=lambda draw: normalize_issue(draw.issue)))
    if len(ordered) <= min_train:
        raise ValueError(f"not enough draws to backtest {adapter.game_code} ML model")
    start = max(min_train, len(ordered) - limit if limit > 0 else min_train)
    hit_distribution = _initial_hit_distribution(game)
    bet_results: List[BetResult] = []
    model = None
    trained_at = -1

    for target_index in range(start, len(ordered)):
        if model is None or target_index - trained_at >= retrain_every:
            training_history = ordered[:target_index]
            effective_min_history = min(min_history, max(1, len(training_history) - 1))
            model = train_generic_ml_model(training_history, adapter, min_history=effective_min_history, epochs=epochs)
            trained_at = target_index

        target = ordered[target_index]
        pick = game.validate_pick(recommend_generic_ml(ordered[:target_index], model, adapter, count=1)[0].numbers)
        level, payout, basis = evaluate_draw_prize(game, target, pick)
        hit_distribution[level] = hit_distribution.get(level, 0) + 1
        bet_results.append(BetResult(
            issue=target.issue,
            draw_numbers=target.numbers,
            pick_numbers=pick,
            hit=payout > 0,
            cost=game.ticket_cost,
            payout=payout,
            payout_basis=basis,
        ))

    return BacktestResult(
        game_name=game.name,
        total_draws=len(bet_results),
        total_bets=len(bet_results),
        total_cost=sum(result.cost for result in bet_results),
        total_payout=sum(result.payout for result in bet_results),
        hit_distribution=hit_distribution,
        bet_results=tuple(bet_results),
    )


def save_generic_ml_model(model: GenericMlModel, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "history_until_issue": model.history_until_issue,
        "training_epochs": model.training_epochs,
        "history_fingerprint": model.history_fingerprint,
        "game_code": model.game_code,
        "game_name": model.game_name,
        "feature_names": list(model.feature_names),
        "windows": list(model.windows),
        "min_history": model.min_history,
        "training_draw_count": model.training_draw_count,
        "training_target_count": model.training_target_count,
        "groups": [
            {
                "spec": {
                    "name": group.spec.name,
                    "min_number": group.spec.min_number,
                    "max_number": group.spec.max_number,
                    "pick_count": group.spec.pick_count,
                },
                "weights": list(group.model.weights),
            }
            for group in model.groups
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def load_generic_ml_model(path: Path) -> GenericMlModel:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return GenericMlModel(
        history_until_issue=str(data.get("history_until_issue", "")),
        training_epochs=int(data.get("training_epochs", 0)),
        history_fingerprint=str(data.get("history_fingerprint", "")),
        game_code=str(data["game_code"]),
        game_name=str(data["game_name"]),
        feature_names=tuple(data["feature_names"]),
        windows=tuple(int(value) for value in data["windows"]),
        min_history=int(data["min_history"]),
        training_draw_count=int(data["training_draw_count"]),
        training_target_count=int(data["training_target_count"]),
        groups=tuple(
            NumberGroupModel(
                spec=NumberGroupSpec(
                    name=str(group["spec"]["name"]),
                    min_number=int(group["spec"]["min_number"]),
                    max_number=int(group["spec"]["max_number"]),
                    pick_count=int(group["spec"]["pick_count"]),
                ),
                model=BinaryLogisticModel(tuple(float(value) for value in group["weights"])),
            )
            for group in data["groups"]
        ),
    )


def _feature_names(windows: Tuple[int, ...]) -> Tuple[str, ...]:
    return (
        "bias",
        "number_norm",
        "is_odd",
        "is_big",
        "zone_low",
        "zone_mid",
        "zone_high",
        *(f"freq_{window}" for window in windows),
        "freq_all",
        "omission",
        "avg_gap",
        "max_gap",
        "trend_5_30",
        "trend_10_60",
    )


def _build_rows(
    draws: Sequence[Any],
    adapter: GenericMlAdapter,
    group_index: int,
    min_history: int,
    windows: Tuple[int, ...],
) -> List[Tuple[Tuple[float, ...], int]]:
    spec = adapter.groups[group_index]
    rows: List[Tuple[Tuple[float, ...], int]] = []
    states: Dict[int, Dict[str, Any]] = {
        number: {"total": 0, "last_seen": -1, "gap_sum": 0, "gap_count": 0, "max_gap": 0, "flags": []}
        for number in range(spec.min_number, spec.max_number + 1)
    }

    for target_index, draw in enumerate(draws):
        if target_index >= min_history:
            target_numbers = set(adapter.extract_groups(draw)[group_index])
            for number, state in states.items():
                rows.append((
                    _features_from_state(number, spec, windows, target_index, state),
                    1 if number in target_numbers else 0,
                ))

        appeared_numbers = set(adapter.extract_groups(draw)[group_index])
        for number, state in states.items():
            appeared = number in appeared_numbers
            state["flags"].append(appeared)
            if appeared:
                if state["last_seen"] >= 0:
                    gap = target_index - state["last_seen"]
                    state["gap_sum"] += gap
                    state["gap_count"] += 1
                    state["max_gap"] = max(state["max_gap"], gap)
                state["last_seen"] = target_index
                state["total"] += 1
    return rows


def _features_from_state(
    number: int,
    spec: NumberGroupSpec,
    windows: Tuple[int, ...],
    history_count: int,
    state: Dict[str, Any],
) -> Tuple[float, ...]:
    span = max(1, spec.max_number - spec.min_number)
    normalized = (number - spec.min_number) / span
    midpoint = spec.min_number + span / 2
    one_third = spec.min_number + span / 3
    two_thirds = spec.min_number + span * 2 / 3
    flags = state["flags"]
    frequencies = tuple(_frequency(flags, window) for window in windows)
    freq_all = state["total"] / history_count if history_count else 0.0
    omission = (history_count if state["last_seen"] < 0 else history_count - 1 - state["last_seen"]) / max(history_count, 1)
    avg_gap = (state["gap_sum"] / state["gap_count"] / max(history_count, 1)) if state["gap_count"] else 1.0
    max_gap = (state["max_gap"] / max(history_count, 1)) if state["gap_count"] else 1.0
    return (
        1.0,
        normalized,
        1.0 if number % 2 else 0.0,
        1.0 if number > midpoint else 0.0,
        1.0 if number <= one_third else 0.0,
        1.0 if one_third < number <= two_thirds else 0.0,
        1.0 if number > two_thirds else 0.0,
        *frequencies,
        freq_all,
        omission,
        avg_gap,
        max_gap,
        _frequency(flags, 5) - _frequency(flags, 30),
        _frequency(flags, 10) - _frequency(flags, 60),
    )


def _frequency(flags: Sequence[bool], window: int) -> float:
    if not flags:
        return 0.0
    scoped = flags[-window:]
    return sum(1 for value in scoped if value) / len(scoped)


def _fit_logistic(
    rows: Sequence[Tuple[Tuple[float, ...], int]],
    feature_count: int,
    epochs: int,
    learning_rate: float,
    l2: float,
) -> Tuple[float, ...]:
    weights = [0.0] * feature_count
    positives = sum(label for _, label in rows)
    negatives = max(len(rows) - positives, 1)
    positive_weight = negatives / max(positives, 1)

    for _ in range(max(1, epochs)):
        for features, label in rows:
            probability = _sigmoid(_dot(weights, features))
            sample_weight = positive_weight if label else 1.0
            error = (probability - label) * sample_weight
            for index, value in enumerate(features):
                penalty = l2 * weights[index] if index else 0.0
                weights[index] -= learning_rate * (error * value + penalty)
    return tuple(weights)


def _score_group(
    history: Sequence[Any],
    adapter: GenericMlAdapter,
    group_index: int,
    group_model: NumberGroupModel,
    windows: Tuple[int, ...],
) -> List[Tuple[int, float]]:
    spec = group_model.spec
    flags_by_number: Dict[int, List[bool]] = {
        number: []
        for number in range(spec.min_number, spec.max_number + 1)
    }
    for draw in history:
        appeared_numbers = set(adapter.extract_groups(draw)[group_index])
        for number, flags in flags_by_number.items():
            flags.append(number in appeared_numbers)

    scores = []
    for number, flags in flags_by_number.items():
        state = _state_from_flags(flags)
        features = _features_from_state(number, spec, windows, len(history), state)
        scores.append((number, _sigmoid(_dot(group_model.model.weights, features))))
    return sorted(scores, key=lambda item: (-item[1], item[0]))


def _state_from_flags(flags: Sequence[bool]) -> Dict[str, Any]:
    total = 0
    last_seen = -1
    gap_sum = 0
    gap_count = 0
    max_gap = 0
    for index, appeared in enumerate(flags):
        if not appeared:
            continue
        if last_seen >= 0:
            gap = index - last_seen
            gap_sum += gap
            gap_count += 1
            max_gap = max(max_gap, gap)
        last_seen = index
        total += 1
    return {
        "total": total,
        "last_seen": last_seen,
        "gap_sum": gap_sum,
        "gap_count": gap_count,
        "max_gap": max_gap,
        "flags": list(flags),
    }


def _group_variants(scores: Sequence[Tuple[int, float]], pick_count: int, count: int) -> List[Tuple[Tuple[int, ...], float]]:
    ranked = sorted(scores, key=lambda item: (-item[1], item[0]))
    if not 1 <= pick_count <= len(ranked):
        raise ValueError("选号数量超出号码范围")
    if pick_count == 1:
        return [((number,), score) for number, score in ranked[:count]]
    def priority(indexes):
        numbers = tuple(sorted(ranked[i][0] for i in indexes))
        score = sum(ranked[i][1] for i in indexes) / pick_count
        return (-score, numbers, indexes)
    start = tuple(range(pick_count))
    heap = [priority(start)]
    seen = {start}
    result = []
    while heap and len(result) < count:
        negative, numbers, indexes = heapq.heappop(heap)
        result.append((numbers, -negative))
        for index in range(pick_count):
            maximum = indexes[index+1] if index+1 < pick_count else len(ranked)
            if indexes[index]+1 >= maximum:
                continue
            neighbor = list(indexes)
            neighbor[index] += 1
            neighbor = tuple(neighbor)
            if neighbor not in seen:
                seen.add(neighbor)
                heapq.heappush(heap, priority(neighbor))
    return result


def _rank_group_products(group_variants, limit=None):
    """Enumerate joint choices in descending score without expanding the full product."""
    if not group_variants or any(not group for group in group_variants):
        return []
    groups = [sorted(group, key=lambda item: (-item[1], item[0])) for group in group_variants]
    capacity = math.prod(len(group) for group in groups)
    if limit is None:
        limit = min(capacity, 10000)
    def priority(indexes):
        chosen = tuple(groups[i][j] for i,j in enumerate(indexes))
        return (-sum(score for _,score in chosen), tuple(n for numbers,_ in chosen for n in numbers), indexes)
    start = (0,) * len(groups)
    heap = [priority(start)]
    seen = {start}
    result = []
    while heap and len(result) < limit:
        _,_,indexes = heapq.heappop(heap)
        result.append(tuple(groups[i][j] for i,j in enumerate(indexes)))
        for i in range(len(groups)):
            if indexes[i] + 1 >= len(groups[i]):
                continue
            adjacent = list(indexes)
            adjacent[i] += 1
            adjacent = tuple(adjacent)
            if adjacent not in seen:
                seen.add(adjacent)
                heapq.heappush(heap, priority(adjacent))
    return result


def _average_score(numbers: Iterable[int], score_map: Dict[int, float]) -> float:
    values = tuple(numbers)
    return sum(score_map[number] for number in values) / len(values)


def _dot(weights: Sequence[float], features: Sequence[float]) -> float:
    return sum(weight * feature for weight, feature in zip(weights, features))


def _sigmoid(value: float) -> float:
    if value < -60:
        return 0.0
    if value > 60:
        return 1.0
    return 1 / (1 + math.exp(-value))


def _number_text(value: Any) -> str:
    if hasattr(value, "number_text"):
        return value.number_text
    if isinstance(value, tuple):
        return "".join(str(item) for item in value)
    return str(value)


def _initial_hit_distribution(game: Any) -> Dict[str, int]:
    if not hasattr(game, "prize_amounts"):
        return {"direct_hit": 0, "miss": 0}
    labels = {}
    for level in game.prize_amounts:
        label = f"中{level}" if isinstance(level, int) else str(level)
        labels[label] = 0
    labels.setdefault("未中奖", 0)
    return labels


def _prize_level_and_payout(game: Any, draw_numbers: Any, pick: Any) -> Tuple[str, Any]:
    payout = game.payout(draw_numbers, pick)
    if hasattr(game, "prize_level"):
        return str(game.prize_level(draw_numbers, pick)), payout
    return ("direct_hit" if payout > 0 else "miss"), payout


def _pick3_adapter(game_code: str, game_name: str) -> GenericMlAdapter:
    groups = tuple(NumberGroupSpec(name=f"第{index + 1}位", min_number=0, max_number=9, pick_count=1) for index in range(3))

    def extract(draw: Draw3D) -> Tuple[Tuple[int, ...], ...]:
        return tuple((value,) for value in draw.numbers)  # type: ignore[return-value]

    def build(values: Tuple[Tuple[int, ...], ...]) -> Tuple[int, int, int]:
        return tuple(group[0] for group in values)  # type: ignore[return-value]

    return GenericMlAdapter(game_code=game_code, game_name=game_name, groups=groups, extract_groups=extract, build_pick=build)


def _pl5_adapter() -> GenericMlAdapter:
    groups = tuple(NumberGroupSpec(name=f"第{index + 1}位", min_number=0, max_number=9, pick_count=1) for index in range(5))

    def extract(draw: Draw5D) -> Tuple[Tuple[int, ...], ...]:
        return tuple((value,) for value in draw.numbers)  # type: ignore[return-value]

    def build(values: Tuple[Tuple[int, ...], ...]) -> Tuple[int, int, int, int, int]:
        return tuple(group[0] for group in values)  # type: ignore[return-value]

    return GenericMlAdapter(game_code="pl5", game_name="排列五直选", groups=groups, extract_groups=extract, build_pick=build)


def _qxc_adapter() -> GenericMlAdapter:
    groups = tuple(
        [NumberGroupSpec(name=f"前区第{index + 1}位", min_number=0, max_number=9, pick_count=1) for index in range(6)]
        + [NumberGroupSpec(name="特别号", min_number=0, max_number=14, pick_count=1)]
    )

    def extract(draw: DrawQXC) -> Tuple[Tuple[int, ...], ...]:
        return tuple((value,) for value in (*draw.numbers.front, draw.numbers.special))  # type: ignore[return-value]

    def build(values: Tuple[Tuple[int, ...], ...]) -> QxcPick:
        front = tuple(group[0] for group in values[:6])
        return QxcPick(front=front, special=values[6][0])  # type: ignore[arg-type]

    return GenericMlAdapter(game_code="qxc", game_name="7星彩", groups=groups, extract_groups=extract, build_pick=build)


def _qlc_adapter() -> GenericMlAdapter:
    groups = (NumberGroupSpec(name="号码", min_number=1, max_number=30, pick_count=7),)

    def extract(draw: DrawQLC) -> Tuple[Tuple[int, ...], ...]:
        return (tuple(sorted((*draw.numbers.basic, draw.numbers.special))),)

    def build(values: Tuple[Tuple[int, ...], ...]) -> QlcPick:
        return QlcPick(numbers=tuple(sorted(values[0])))  # type: ignore[arg-type]

    return GenericMlAdapter(game_code="qlc", game_name="七乐彩", groups=groups, extract_groups=extract, build_pick=build)


def _kl8_adapter(pick_size: int) -> GenericMlAdapter:
    groups = (NumberGroupSpec(name="号码", min_number=1, max_number=80, pick_count=pick_size),)

    def extract(draw: DrawKL8) -> Tuple[Tuple[int, ...], ...]:
        return (tuple(sorted(draw.numbers)),)

    def build(values: Tuple[Tuple[int, ...], ...]) -> Kl8Pick:
        return Kl8Pick(numbers=tuple(sorted(values[0])))

    return GenericMlAdapter(game_code="kl8", game_name=f"快乐8选{_kl8_label(pick_size)}", groups=groups, extract_groups=extract, build_pick=build)


def _dlt_adapter() -> GenericMlAdapter:
    groups = (
        NumberGroupSpec(name="前区", min_number=1, max_number=35, pick_count=5),
        NumberGroupSpec(name="后区", min_number=1, max_number=12, pick_count=2),
    )

    def extract(draw: DrawDLT) -> Tuple[Tuple[int, ...], ...]:
        return (tuple(sorted(draw.numbers.front)), tuple(sorted(draw.numbers.back)))

    def build(values: Tuple[Tuple[int, ...], ...]) -> DltPick:
        return DltPick(front=tuple(sorted(values[0])), back=tuple(sorted(values[1])))  # type: ignore[arg-type]

    return GenericMlAdapter(game_code="dlt", game_name="大乐透", groups=groups, extract_groups=extract, build_pick=build)


def _kl8_label(pick_size: int) -> str:
    labels = {
        1: "一",
        2: "二",
        3: "三",
        4: "四",
        5: "五",
        6: "六",
        7: "七",
        8: "八",
        9: "九",
        10: "十",
    }
    return labels.get(pick_size, str(pick_size))
