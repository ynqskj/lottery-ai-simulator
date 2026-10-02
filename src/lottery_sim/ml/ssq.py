from lottery_sim.issue_calendar import normalize_issue
from lottery_sim.prize_rules import evaluate_draw_prize
import json
import heapq
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from lottery_sim.games.ssq import SsqGame
from lottery_sim.ml.generic import history_fingerprint, _rank_group_products
from lottery_sim.models import BacktestResult, BetResult, DrawSSQ, SsqPick
from lottery_sim.recommendations import Candidate


DEFAULT_WINDOWS: Tuple[int, ...] = (5, 10, 30, 60, 100, 200)


@dataclass(frozen=True)
class BinaryLogisticModel:
    weights: Tuple[float, ...]


@dataclass(frozen=True)
class SsqMlModel:
    feature_names: Tuple[str, ...]
    windows: Tuple[int, ...]
    min_history: int
    training_draw_count: int
    training_target_count: int
    red_model: BinaryLogisticModel
    blue_model: BinaryLogisticModel
    history_until_issue: str = ""
    training_epochs: int = 0
    history_fingerprint: str = ""


def train_ssq_ml_model(
    draws: Sequence[DrawSSQ],
    min_history: int = 30,
    windows: Sequence[int] = DEFAULT_WINDOWS,
    epochs: int = 30,
    learning_rate: float = 0.04,
    l2: float = 0.001,
) -> SsqMlModel:
    ordered = tuple(sorted(draws, key=lambda draw: normalize_issue(draw.issue)))
    if len(ordered) <= min_history:
        raise ValueError("not enough draws to train SSQ ML model")

    feature_names = _feature_names(tuple(windows))
    red_rows = _build_rows(ordered, min_history, tuple(windows), max_number=33, red=True)
    blue_rows = _build_rows(ordered, min_history, tuple(windows), max_number=16, red=False)
    return SsqMlModel(
        history_until_issue=ordered[-1].issue,
        training_epochs=epochs,
        history_fingerprint=history_fingerprint(ordered),
        feature_names=feature_names,
        windows=tuple(windows),
        min_history=min_history,
        training_draw_count=len(ordered),
        training_target_count=len(ordered) - min_history,
        red_model=BinaryLogisticModel(_fit_logistic(red_rows, len(feature_names), epochs, learning_rate, l2)),
        blue_model=BinaryLogisticModel(_fit_logistic(blue_rows, len(feature_names), epochs, learning_rate, l2)),
    )


def recommend_ssq_ml(draws: Sequence[DrawSSQ], model: SsqMlModel, count: int = 10) -> List[Candidate]:
    if not 1 <= count <= 1000:
        raise ValueError("candidate count must be between 1 and 1000")
    if not draws:
        raise ValueError("没有历史开奖数据")
    history = tuple(sorted(draws, key=lambda draw: normalize_issue(draw.issue)))
    red_scores = _score_numbers(history, model, max_number=33, red=True)
    blue_scores = _score_numbers(history, model, max_number=16, red=False)
    red_combos = _rank_red_combinations(red_scores, count)
    blue_choices = [((number,), score) for number, score in blue_scores]
    choices = _rank_group_products([red_combos, blue_choices], limit=count)
    if len(choices) != count:
        raise ValueError(f"无法满足请求的{count}注")
    candidates: List[Candidate] = []
    for (red, red_probability), (blue, blue_probability) in choices:
        pick = SsqPick(red=red, blue=blue[0])
        joint_score = (red_probability + blue_probability) / 2
        candidates.append(Candidate(
            rank=len(candidates) + 1,
            strategy_name="双色球机器学习",
            numbers=pick,
            number_text=pick.number_text,
            reason=f"模型均值评分{joint_score:.3f}，红球均值评分{red_probability:.3f}，蓝球评分{blue_probability:.3f}",
        ))
    return candidates


def _rank_red_combinations(scores, limit):
    ranked = sorted(scores, key=lambda item: (-item[1], item[0]))
    if len(ranked) < 6:
        return []
    def priority(indexes):
        numbers = tuple(sorted(ranked[index][0] for index in indexes))
        average = sum(ranked[index][1] for index in indexes) / 6
        return (-average, numbers, indexes)
    start = tuple(range(6))
    heap = [priority(start)]
    seen = {start}
    result = []
    while heap and len(result) < limit:
        negative_score, numbers, indexes = heapq.heappop(heap)
        result.append((numbers, -negative_score))
        for index in range(6):
            maximum = indexes[index+1] if index < 5 else len(ranked)
            if indexes[index]+1 >= maximum:
                continue
            adjacent = list(indexes)
            adjacent[index] += 1
            adjacent = tuple(adjacent)
            if adjacent not in seen:
                seen.add(adjacent)
                heapq.heappush(heap, priority(adjacent))
    return result


def run_ssq_ml_backtest(
    draws: Sequence[DrawSSQ],
    min_train: int = 200,
    limit: int = 120,
    retrain_every: int = 20,
    min_history: int = 30,
    epochs: int = 12,
) -> BacktestResult:
    ordered = tuple(sorted(draws, key=lambda draw: normalize_issue(draw.issue)))
    if len(ordered) <= min_train:
        raise ValueError("not enough draws to backtest SSQ ML model")
    start = max(min_train, len(ordered) - limit if limit > 0 else min_train)
    game = SsqGame()
    hit_distribution = {level: 0 for level in game.prize_amounts}
    bet_results: List[BetResult] = []
    model = None
    trained_at = -1

    for target_index in range(start, len(ordered)):
        if model is None or target_index - trained_at >= retrain_every:
            training_history = ordered[:target_index]
            effective_min_history = min(min_history, max(1, len(training_history) - 1))
            model = train_ssq_ml_model(training_history, min_history=effective_min_history, epochs=epochs)
            trained_at = target_index

        target = ordered[target_index]
        pick = game.validate_pick(recommend_ssq_ml(ordered[:target_index], model, count=1)[0].numbers)
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


def save_ssq_ml_model(model: SsqMlModel, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "history_until_issue": model.history_until_issue,
        "training_epochs": model.training_epochs,
        "history_fingerprint": model.history_fingerprint,
        "feature_names": list(model.feature_names),
        "windows": list(model.windows),
        "min_history": model.min_history,
        "training_draw_count": model.training_draw_count,
        "training_target_count": model.training_target_count,
        "red_weights": list(model.red_model.weights),
        "blue_weights": list(model.blue_model.weights),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def load_ssq_ml_model(path: Path) -> SsqMlModel:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return SsqMlModel(
        history_until_issue=str(data.get("history_until_issue", "")),
        training_epochs=int(data.get("training_epochs", 0)),
        history_fingerprint=str(data.get("history_fingerprint", "")),
        feature_names=tuple(data["feature_names"]),
        windows=tuple(int(value) for value in data["windows"]),
        min_history=int(data["min_history"]),
        training_draw_count=int(data["training_draw_count"]),
        training_target_count=int(data["training_target_count"]),
        red_model=BinaryLogisticModel(tuple(float(value) for value in data["red_weights"])),
        blue_model=BinaryLogisticModel(tuple(float(value) for value in data["blue_weights"])),
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
    draws: Sequence[DrawSSQ],
    min_history: int,
    windows: Tuple[int, ...],
    max_number: int,
    red: bool,
) -> List[Tuple[Tuple[float, ...], int]]:
    rows: List[Tuple[Tuple[float, ...], int]] = []
    prefix_counts = _build_prefix_counts(draws, max_number=max_number, red=red)
    total_count = [0] * (max_number + 1)
    last_seen = [-1] * (max_number + 1)
    gap_sum = [0] * (max_number + 1)
    gap_count = [0] * (max_number + 1)
    max_gap = [0] * (max_number + 1)

    for target_index, draw in enumerate(draws):
        if target_index >= min_history:
            target_numbers = set(draw.numbers.red) if red else {draw.numbers.blue}
            for number in range(1, max_number + 1):
                rows.append((
                    _features_from_stats(
                        number=number,
                        max_number=max_number,
                        windows=windows,
                        history_count=target_index,
                        prefix_counts=prefix_counts[number],
                        total_count=total_count[number],
                        last_seen=last_seen[number],
                        gap_sum=gap_sum[number],
                        gap_count=gap_count[number],
                        max_gap=max_gap[number],
                    ),
                    1 if number in target_numbers else 0,
                ))

        appeared_numbers = draw.numbers.red if red else (draw.numbers.blue,)
        for number in appeared_numbers:
            if number < 1 or number > max_number:
                continue
            if last_seen[number] >= 0:
                gap = target_index - last_seen[number]
                gap_sum[number] += gap
                gap_count[number] += 1
                max_gap[number] = max(max_gap[number], gap)
            last_seen[number] = target_index
            total_count[number] += 1
    return rows


def _build_prefix_counts(draws: Sequence[DrawSSQ], max_number: int, red: bool) -> List[List[int]]:
    prefix_counts = [[0] * (len(draws) + 1) for _ in range(max_number + 1)]
    for number in range(1, max_number + 1):
        total = 0
        counts = prefix_counts[number]
        for index, draw in enumerate(draws):
            appeared = number in draw.numbers.red if red else number == draw.numbers.blue
            if appeared:
                total += 1
            counts[index + 1] = total
    return prefix_counts


def _features_from_stats(
    number: int,
    max_number: int,
    windows: Tuple[int, ...],
    history_count: int,
    prefix_counts: Sequence[int],
    total_count: int,
    last_seen: int,
    gap_sum: int,
    gap_count: int,
    max_gap: int,
) -> Tuple[float, ...]:
    frequencies = tuple(_prefix_frequency(prefix_counts, history_count, window) for window in windows)
    freq_all = total_count / history_count if history_count else 0.0
    omission = (history_count if last_seen < 0 else history_count - 1 - last_seen) / max(history_count, 1)
    avg_gap = (gap_sum / gap_count / max(history_count, 1)) if gap_count else 1.0
    scaled_max_gap = (max_gap / max(history_count, 1)) if gap_count else 1.0
    return (
        1.0,
        number / max_number,
        1.0 if number % 2 else 0.0,
        1.0 if number > max_number / 2 else 0.0,
        1.0 if number <= max_number / 3 else 0.0,
        1.0 if max_number / 3 < number <= max_number * 2 / 3 else 0.0,
        1.0 if number > max_number * 2 / 3 else 0.0,
        *frequencies,
        freq_all,
        omission,
        avg_gap,
        scaled_max_gap,
        _prefix_frequency(prefix_counts, history_count, 5) - _prefix_frequency(prefix_counts, history_count, 30),
        _prefix_frequency(prefix_counts, history_count, 10) - _prefix_frequency(prefix_counts, history_count, 60),
    )


def _prefix_frequency(prefix_counts: Sequence[int], history_count: int, window: int) -> float:
    if history_count <= 0:
        return 0.0
    start = max(0, history_count - window)
    denominator = history_count - start
    if denominator <= 0:
        return 0.0
    return (prefix_counts[history_count] - prefix_counts[start]) / denominator


def _features(
    history: Sequence[DrawSSQ],
    number: int,
    max_number: int,
    windows: Tuple[int, ...],
    red: bool,
) -> Tuple[float, ...]:
    appearances = [number in draw.numbers.red if red else number == draw.numbers.blue for draw in history]
    history_count = len(history)
    frequencies = tuple(_frequency(appearances, window) for window in windows)
    freq_all = sum(1 for value in appearances if value) / history_count if history_count else 0.0
    gaps = _gaps(appearances)
    omission = _current_omission(appearances) / max(history_count, 1)
    avg_gap = (sum(gaps) / len(gaps) / max(history_count, 1)) if gaps else 1.0
    max_gap = (max(gaps) / max(history_count, 1)) if gaps else 1.0
    return (
        1.0,
        number / max_number,
        1.0 if number % 2 else 0.0,
        1.0 if number > max_number / 2 else 0.0,
        1.0 if number <= max_number / 3 else 0.0,
        1.0 if max_number / 3 < number <= max_number * 2 / 3 else 0.0,
        1.0 if number > max_number * 2 / 3 else 0.0,
        *frequencies,
        freq_all,
        omission,
        avg_gap,
        max_gap,
        _frequency(appearances, 5) - _frequency(appearances, 30),
        _frequency(appearances, 10) - _frequency(appearances, 60),
    )


def _frequency(appearances: Sequence[bool], window: int) -> float:
    if not appearances:
        return 0.0
    scoped = appearances[-window:]
    return sum(1 for value in scoped if value) / len(scoped)


def _current_omission(appearances: Sequence[bool]) -> int:
    for offset, appeared in enumerate(reversed(appearances)):
        if appeared:
            return offset
    return len(appearances)


def _gaps(appearances: Sequence[bool]) -> List[int]:
    positions = [index for index, appeared in enumerate(appearances) if appeared]
    if len(positions) < 2:
        return []
    return [current - previous for previous, current in zip(positions, positions[1:])]


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


def _score_numbers(
    history: Sequence[DrawSSQ],
    model: SsqMlModel,
    max_number: int,
    red: bool,
) -> List[Tuple[int, float]]:
    weights = model.red_model.weights if red else model.blue_model.weights
    scores = [
        (
            number,
            _sigmoid(_dot(weights, _features(history, number, max_number, model.windows, red))),
        )
        for number in range(1, max_number + 1)
    ]
    return sorted(scores, key=lambda item: (-item[1], item[0]))


def _dot(weights: Sequence[float], features: Sequence[float]) -> float:
    return sum(weight * feature for weight, feature in zip(weights, features))


def _sigmoid(value: float) -> float:
    if value < -60:
        return 0.0
    if value > 60:
        return 1.0
    return 1 / (1 + math.exp(-value))
