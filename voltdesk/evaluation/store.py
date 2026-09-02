"""Checkpoint persistence for Phase 4 evaluation runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from voltdesk.contracts.evaluation import EvaluationResult, RecordResult
from voltdesk.contracts.routing import ModelChoice
from voltdesk.db.session import get_engine


@dataclass(frozen=True)
class PartialEvaluation:
    started_at: datetime
    model: ModelChoice
    git_sha: str
    results: list[RecordResult]


class EvaluationStore(Protocol):
    def start(
        self, run_id: str, started_at: datetime, model: ModelChoice, git_sha: str
    ) -> None: ...

    def load(self, run_id: str) -> PartialEvaluation | None: ...

    def checkpoint(self, run_id: str, results: list[RecordResult]) -> None: ...

    def finish(self, result: EvaluationResult) -> None: ...


class PostgresEvaluationStore:
    """Write partial and completed runs to the Phase 1 evaluation table."""

    def start(
        self, run_id: str, started_at: datetime, model: ModelChoice, git_sha: str
    ) -> None:
        statement = text(
            "INSERT INTO app.evaluation_runs "
            "(run_id, started_at, provider, model_id, git_sha, record_count, results) "
            "VALUES (:run_id, :started_at, :provider, :model_id, :git_sha, 0, '[]'::jsonb)"
        )
        self._update(
            statement,
            {
                "run_id": run_id,
                "started_at": started_at,
                "provider": model.provider.value,
                "model_id": model.model_id,
                "git_sha": git_sha,
            },
        )

    def load(self, run_id: str) -> PartialEvaluation | None:
        statement = text(
            "SELECT started_at, provider, model_id, git_sha, results "
            "FROM app.evaluation_runs WHERE run_id = :run_id"
        )
        with get_engine().connect() as connection:
            row = connection.execute(statement, {"run_id": run_id}).mappings().one_or_none()
        if row is None:
            return None
        raw_results = row["results"] if isinstance(row["results"], list) else []
        return PartialEvaluation(
            started_at=row["started_at"],
            model=ModelChoice(provider=row["provider"], model_id=row["model_id"]),
            git_sha=row["git_sha"],
            results=[RecordResult.model_validate(item) for item in raw_results],
        )

    def checkpoint(self, run_id: str, results: list[RecordResult]) -> None:
        statement = text(
            "UPDATE app.evaluation_runs SET record_count = :record_count, "
            "results = CAST(:results AS jsonb) WHERE run_id = :run_id"
        )
        self._update(
            statement,
            {
                "run_id": run_id,
                "record_count": len(results),
                "results": _results_json(results),
            },
        )

    def finish(self, result: EvaluationResult) -> None:
        statement = text(
            "UPDATE app.evaluation_runs SET finished_at=:finished_at, "
            "record_count=:record_count, exact_match_rate=:exact_match_rate, "
            "field_precision=:field_precision, field_recall=:field_recall, "
            "citation_correctness=:citation_correctness, "
            "abstention_precision=:abstention_precision, "
            "abstention_recall=:abstention_recall, p50_latency_ms=:p50_latency_ms, "
            "p95_latency_ms=:p95_latency_ms, total_cost_usd=:total_cost_usd, "
            "results=CAST(:results AS jsonb) WHERE run_id=:run_id"
        )
        payload = result.model_dump(mode="json", exclude={"model", "git_sha"})
        payload["results"] = _results_json(result.results)
        self._update(statement, payload)

    @staticmethod
    def _update(statement: TextClause, parameters: dict[str, object]) -> None:
        with get_engine().begin() as connection:
            connection.execute(statement, parameters)


def _results_json(results: list[RecordResult]) -> str:
    return json.dumps([result.model_dump(mode="json") for result in results])
