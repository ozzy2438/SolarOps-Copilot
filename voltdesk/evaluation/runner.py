"""Resumable golden-set execution and CLI. Owned by Phase 4."""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from voltdesk.contracts.evaluation import EvaluationResult, GoldenRecord, RecordResult
from voltdesk.contracts.routing import ModelChoice
from voltdesk.evaluation.execution import LiveRecordExecutor
from voltdesk.evaluation.store import EvaluationStore, PostgresEvaluationStore
from voltdesk.llm.pricing import assert_verified, get_price

_REPO_ROOT = Path(__file__).resolve().parents[2]
RecordExecutor = Callable[[GoldenRecord, ModelChoice], RecordResult]


def load_golden_set(path: str = "data/golden/records") -> list[GoldenRecord]:
    """Load, validate and deterministically order one JSON file per record."""
    requested = Path(path)
    root = requested if requested.is_absolute() else _REPO_ROOT / requested
    if not root.is_dir():
        raise FileNotFoundError(f"golden-set directory does not exist: {root}")
    records: list[GoldenRecord] = []
    seen: set[str] = set()
    for record_path in sorted(root.glob("*.json")):
        record = GoldenRecord.model_validate(json.loads(record_path.read_text(encoding="utf-8")))
        if record_path.stem != record.record_id:
            raise ValueError(
                f"golden record filename {record_path.name!r} does not match "
                f"record_id {record.record_id!r}"
            )
        if record.record_id in seen:
            raise ValueError(f"duplicate golden record_id: {record.record_id}")
        input_path = (_REPO_ROOT / record.input_path).resolve()
        if _REPO_ROOT not in input_path.parents or not input_path.is_file():
            raise FileNotFoundError(
                f"golden record {record.record_id} has missing or unsafe input_path"
            )
        seen.add(record.record_id)
        records.append(record)
    return records


def run(
    records: list[GoldenRecord],
    model: ModelChoice,
    *,
    resume_run_id: str | None = None,
    executor: RecordExecutor | None = None,
    store: EvaluationStore | None = None,
    git_sha: str | None = None,
) -> EvaluationResult:
    """Run or resume records, checkpointing after every completed record."""
    if not records:
        raise ValueError("an evaluation run requires at least one golden record")
    if len({record.record_id for record in records}) != len(records):
        raise ValueError("an evaluation run cannot contain duplicate record_ids")
    assert_verified(model.model_id)
    selected_store = store or PostgresEvaluationStore()
    selected_executor = executor or LiveRecordExecutor()
    selected_sha = git_sha or current_git_sha()
    run_id = resume_run_id or f"eval-{uuid.uuid4()}"
    started_at = datetime.now(UTC)
    completed: list[RecordResult] = []

    if resume_run_id is not None:
        state = selected_store.load(resume_run_id)
        if state is None:
            raise ValueError(f"evaluation run not found: {resume_run_id}")
        if state.model != model or state.git_sha != selected_sha:
            raise ValueError("a run may resume only with the same model and git SHA")
        started_at, completed = state.started_at, list(state.results)
    else:
        selected_store.start(run_id, started_at, model, selected_sha)

    requested_ids = {record.record_id for record in records}
    if unknown := {result.record_id for result in completed} - requested_ids:
        raise ValueError(f"resume state contains records outside this run: {sorted(unknown)}")
    completed_ids = {result.record_id for result in completed}
    for record in records:
        if record.record_id in completed_ids:
            continue
        completed.append(selected_executor(record, model))
        selected_store.checkpoint(run_id, completed)

    from voltdesk.evaluation.metrics import summarise

    finished_at = datetime.now(UTC)
    summary = summarise(completed).model_copy(
        update={
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "model": model,
            "git_sha": selected_sha,
            "record_count": len(completed),
            "results": completed,
        }
    )
    selected_store.finish(summary)
    return summary


def run_benchmark(models: list[ModelChoice]) -> list[EvaluationResult]:
    """Run the full golden set once per verified model."""
    if len(models) < 2:
        raise ValueError("a benchmark requires at least two models")
    for model in models:
        assert_verified(model.model_id)
    records = load_golden_set()
    return [run(records, model) for model in models]


def current_git_sha() -> str:
    """Return a commit object that exists in this repository's history."""
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    sha = completed.stdout.strip()
    subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return sha


def _choice(model_id: str) -> ModelChoice:
    price = get_price(model_id)
    return ModelChoice(provider=price.provider, model_id=price.model_id)


def _pilot(records: Sequence[GoldenRecord], per_task: int) -> list[GoldenRecord]:
    if per_task <= 0:
        return list(records)
    counts: Counter[str] = Counter()
    selected: list[GoldenRecord] = []
    for record in records:
        task = record.task_type.value
        if counts[task] < per_task:
            selected.append(record)
            counts[task] += 1
    return selected


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--model", help="One exact model id")
    mode.add_argument("--benchmark", action="store_true", help="Run Claude Opus 5 and GPT-4o")
    parser.add_argument("--pilot-per-task", type=int, default=0)
    parser.add_argument("--resume-run-id")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    records = _pilot(load_golden_set(), args.pilot_per_task)
    if args.benchmark:
        results = [
            run(records, model) for model in [_choice("claude-opus-5"), _choice("gpt-4o")]
        ]
    else:
        results = [run(records, _choice(args.model), resume_run_id=args.resume_run_id)]
    for result in results:
        print(result.model_dump_json(exclude={"results"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
