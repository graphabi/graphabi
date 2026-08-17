"""Source definitions for the checked-in semantic regression corpus fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from examples.migration_support import one_edge_bundle
from examples.model_migration.example import (
    PROMPT,
    default_source,
    fixture_producers,
)
from examples.model_migration.example import (
    _trace as model_trace,
)
from examples.prompt_migration.example import (
    RecordedPromptModel,
    prompt_revisions,
)
from examples.prompt_migration.example import (
    _trace as prompt_trace,
)
from examples.tool_migration.example import (
    CachedQuoteRetriever,
    LocalMarketFeedRetriever,
)
from examples.tool_migration.example import (
    _trace as tool_trace,
)

from graphabi.contracts import load_contract
from graphabi.models import EdgeObservation, GraphRun, NodeExecution, SourceAccess, TraceBundle
from graphabi.models.traces import JsonValue

OBSERVED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CorpusCase:
    """One reproducible contract comparison and its asserted outcome."""

    case_id: str
    category: str
    rationale: str
    contract: dict[str, Any]
    baseline: TraceBundle
    candidate: TraceBundle
    expected_status: str
    expected_first_breaking_edge: str | None
    expected_findings: tuple[tuple[str, str, str], ...]


def _contract(
    graph: str,
    edge_id: str,
    producer: str,
    consumer: str,
    invariant: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": "0.2",
        "graph": graph,
        "nodes": [{"id": producer}, {"id": consumer, "terminal": True}],
        "graph_edges": [{"id": edge_id, "producer": producer, "consumer": consumer}],
        "edges": [
            {
                "id": edge_id,
                "producer": producer,
                "consumer": consumer,
                "invariants": [invariant],
            }
        ],
    }


def _simple_bundle(
    *,
    run_id: str,
    graph: str,
    edge_id: str,
    producer: str,
    consumer: str,
    output: dict[str, JsonValue],
    input_value: dict[str, JsonValue] | None = None,
    metadata: dict[str, JsonValue] | None = None,
    source_access: tuple[SourceAccess, ...] = (),
) -> TraceBundle:
    bundle = one_edge_bundle(
        run_id=run_id,
        graph_id=graph,
        graph_version="corpus-1",
        variant="baseline" if "baseline" in run_id else "candidate",
        edge_id=edge_id,
        producer=producer,
        consumer=consumer,
        output=output,
        metadata=metadata or {},
        source_access=source_access,
        observed_at=OBSERVED_AT,
    )
    if input_value is None:
        return bundle
    observation = bundle.edge_observations[0].model_copy(update={"input": input_value})
    return bundle.model_copy(update={"edge_observations": (observation,)})


def _single_evaluator_cases() -> tuple[CorpusCase, ...]:
    provenance_contract = _contract(
        "corpus_provenance",
        "researcher_to_verifier",
        "researcher",
        "verifier",
        {
            "id": "verified_requires_support",
            "evaluator": "provenance",
            "description": "Verified claims require an opened source recorded as supporting.",
            "severity": "breaking",
            "rule": "opened_supporting_source",
        },
    )
    source = SourceAccess(
        source_id="record-17",
        uri="fixture://corpus/provenance/record-17",
        attempted_at=OBSERVED_AT,
        opened=True,
        supports_claim=True,
    )
    skipped = source.model_copy(
        update={"opened": False, "supports_claim": None, "error": "source was not opened"}
    )
    provenance_output: dict[str, JsonValue] = {
        "claim": "Synthetic result 17 is valid.",
        "verified": True,
        "sources": ["record-17"],
    }
    provenance = CorpusCase(
        case_id="provenance",
        category="provenance",
        rationale=(
            "A structurally unchanged verified claim loses the source-access event that justified "
            "verification."
        ),
        contract=provenance_contract,
        baseline=_simple_bundle(
            run_id="provenance-baseline",
            graph="corpus_provenance",
            edge_id="researcher_to_verifier",
            producer="researcher",
            consumer="verifier",
            output=provenance_output,
            source_access=(source,),
        ),
        candidate=_simple_bundle(
            run_id="provenance-candidate",
            graph="corpus_provenance",
            edge_id="researcher_to_verifier",
            producer="researcher",
            consumer="verifier",
            output=provenance_output,
            source_access=(skipped,),
        ),
        expected_status="FAIL",
        expected_first_breaking_edge="researcher_to_verifier",
        expected_findings=(("verified_requires_support", "BREAKING", "LOGICAL_SINGLETON"),),
    )

    preservation_contract = _contract(
        "corpus_preservation",
        "planner_to_executor",
        "planner",
        "executor",
        {
            "id": "entities_must_survive",
            "evaluator": "set_preservation",
            "description": "Every requested entity must remain in the execution plan.",
            "severity": "breaking",
            "source_path": "input.required_entities",
            "destination_path": "output.entities",
        },
    )
    required: dict[str, JsonValue] = {"required_entities": ["north", "south"]}
    preservation = CorpusCase(
        case_id="preservation",
        category="preservation",
        rationale=(
            "The candidate keeps the output schema but silently drops one entity required by the "
            "consumer."
        ),
        contract=preservation_contract,
        baseline=_simple_bundle(
            run_id="preservation-baseline",
            graph="corpus_preservation",
            edge_id="planner_to_executor",
            producer="planner",
            consumer="executor",
            input_value=required,
            output={"entities": ["north", "south"]},
        ),
        candidate=_simple_bundle(
            run_id="preservation-candidate",
            graph="corpus_preservation",
            edge_id="planner_to_executor",
            producer="planner",
            consumer="executor",
            input_value=required,
            output={"entities": ["north"]},
        ),
        expected_status="FAIL",
        expected_first_breaking_edge="planner_to_executor",
        expected_findings=(("entities_must_survive", "BREAKING", "LOGICAL_SINGLETON"),),
    )

    units_contract = _contract(
        "corpus_units",
        "scorer_to_policy",
        "scorer",
        "policy",
        {
            "id": "risk_is_fraction",
            "evaluator": "unit_consistency",
            "description": "Risk is a dimensionless fraction between zero and one.",
            "severity": "breaking",
            "value_path": "output.risk",
            "unit_path": "output.unit",
            "expected_unit": "ratio",
            "representation_path": "output.representation",
            "expected_representation": "fraction",
        },
    )
    units = CorpusCase(
        case_id="units",
        category="units",
        rationale=(
            "A numeric field changes from a fractional ratio to a percentage while retaining the "
            "same primitive type."
        ),
        contract=units_contract,
        baseline=_simple_bundle(
            run_id="units-baseline",
            graph="corpus_units",
            edge_id="scorer_to_policy",
            producer="scorer",
            consumer="policy",
            output={"risk": 0.42, "unit": "ratio", "representation": "fraction"},
        ),
        candidate=_simple_bundle(
            run_id="units-candidate",
            graph="corpus_units",
            edge_id="scorer_to_policy",
            producer="scorer",
            consumer="policy",
            output={"risk": 42, "unit": "percent", "representation": "percent"},
        ),
        expected_status="FAIL",
        expected_first_breaking_edge="scorer_to_policy",
        expected_findings=(("risk_is_fraction", "BREAKING", "LOGICAL_SINGLETON"),),
    )

    authority_contract = _contract(
        "corpus_authority",
        "advisor_to_approver",
        "advisor",
        "approver",
        {
            "id": "advisor_cannot_decide",
            "evaluator": "authority",
            "description": "The advisor may recommend but cannot publish a decision.",
            "severity": "breaking",
            "source_path": "output.authority_level",
            "maximum_allowed": "recommendation",
        },
    )
    authority = CorpusCase(
        case_id="authority",
        category="authority",
        rationale=(
            "The candidate converts a recommendation into a published decision without changing "
            "the field shape."
        ),
        contract=authority_contract,
        baseline=_simple_bundle(
            run_id="authority-baseline",
            graph="corpus_authority",
            edge_id="advisor_to_approver",
            producer="advisor",
            consumer="approver",
            output={"authority_level": "recommendation", "text": "Review the rollout."},
        ),
        candidate=_simple_bundle(
            run_id="authority-candidate",
            graph="corpus_authority",
            edge_id="advisor_to_approver",
            producer="advisor",
            consumer="approver",
            output={"authority_level": "published", "text": "The rollout is approved."},
        ),
        expected_status="FAIL",
        expected_first_breaking_edge="advisor_to_approver",
        expected_findings=(("advisor_cannot_decide", "BREAKING", "LOGICAL_SINGLETON"),),
    )

    freshness_contract = _contract(
        "corpus_freshness",
        "retriever_to_ranker",
        "retriever",
        "ranker",
        {
            "id": "record_is_recent",
            "evaluator": "freshness",
            "description": "The ranker requires evidence observed within the previous hour.",
            "severity": "breaking",
            "timestamp_path": "metadata.evidence_observed_at",
            "max_age_seconds": 3600,
        },
    )
    freshness = CorpusCase(
        case_id="freshness",
        category="freshness",
        rationale=(
            "The replacement retriever returns a valid record whose evidence timestamp is too old "
            "for the consumer's explicit window."
        ),
        contract=freshness_contract,
        baseline=_simple_bundle(
            run_id="freshness-baseline",
            graph="corpus_freshness",
            edge_id="retriever_to_ranker",
            producer="retriever",
            consumer="ranker",
            output={"record_id": "synthetic-9"},
            metadata={"evidence_observed_at": (OBSERVED_AT - timedelta(minutes=30)).isoformat()},
        ),
        candidate=_simple_bundle(
            run_id="freshness-candidate",
            graph="corpus_freshness",
            edge_id="retriever_to_ranker",
            producer="retriever",
            consumer="ranker",
            output={"record_id": "synthetic-9"},
            metadata={"evidence_observed_at": (OBSERVED_AT - timedelta(days=2)).isoformat()},
        ),
        expected_status="FAIL",
        expected_first_breaking_edge="retriever_to_ranker",
        expected_findings=(("record_is_recent", "BREAKING", "LOGICAL_SINGLETON"),),
    )
    return provenance, preservation, units, authority, freshness


def _execution(
    node_id: str,
    occurrence_id: str,
    sequence: int,
    *,
    run_id: str,
    parents: tuple[str, ...] = (),
    branch_id: str | None = "main",
    incoming_edge_id: str | None = None,
) -> NodeExecution:
    return NodeExecution(
        schema_version="0.2",
        run_id=run_id,
        graph_id="corpus_occurrences",
        graph_version="corpus-1",
        node_id=node_id,
        occurrence_id=occurrence_id,
        parent_occurrence_id=parents[0] if parents else None,
        causal_parent_occurrence_ids=parents,
        incoming_edge_id=incoming_edge_id,
        causal_sequence=sequence,
        branch_id=branch_id,
        attempt=1,
        input={},
        output={},
        started_at=OBSERVED_AT,
        ended_at=OBSERVED_AT,
        duration_ms=0,
        status="success",
        framework="corpus",
        framework_version="1",
    )


def _occurrence_bundle(
    run_id: str,
    executions: tuple[NodeExecution, ...],
    edges: tuple[tuple[str, str, str, dict[str, JsonValue]], ...],
) -> TraceBundle:
    by_id = {item.occurrence_id: item for item in executions}
    observations = tuple(
        EdgeObservation(
            schema_version="0.2",
            run_id=run_id,
            graph_id="corpus_occurrences",
            graph_version="corpus-1",
            edge_id=edge_id,
            producer=by_id[producer_id].node_id,
            consumer=by_id[consumer_id].node_id,
            occurrence_id=f"edge:{index}",
            producer_occurrence_id=producer_id,
            consumer_occurrence_id=consumer_id,
            causal_sequence=index,
            branch_id=by_id[consumer_id].branch_id,
            attempt=1,
            input={},
            output=output,
            observed_at=OBSERVED_AT,
        )
        for index, (edge_id, producer_id, consumer_id, output) in enumerate(edges)
    )
    run = GraphRun(
        schema_version="0.2",
        run_id=run_id,
        graph_id="corpus_occurrences",
        graph_version="corpus-1",
        variant="baseline" if "baseline" in run_id else "candidate",
        started_at=OBSERVED_AT,
        ended_at=OBSERVED_AT,
        status="success",
        input={},
        output={},
        executions=executions,
    )
    return TraceBundle(
        schema_version="0.2",
        exported_at=OBSERVED_AT,
        runs=(run,),
        edge_observations=observations,
    )


def _occurrence_cases() -> tuple[CorpusCase, CorpusCase]:
    loop_contract = {
        "version": "0.2",
        "graph": "corpus_occurrences",
        "nodes": [{"id": "producer"}, {"id": "consumer", "terminal": True}],
        "graph_edges": [
            {"id": "producer_to_consumer", "producer": "producer", "consumer": "consumer"},
            {"id": "consumer_to_producer", "producer": "consumer", "consumer": "producer"},
        ],
        "edges": [
            {
                "id": "producer_to_consumer",
                "producer": "producer",
                "consumer": "consumer",
                "invariants": [
                    {
                        "id": "payload_required_each_iteration",
                        "evaluator": "completeness",
                        "description": "Every loop crossing must carry a non-empty payload.",
                        "severity": "breaking",
                        "destination_path": "output.payload",
                    }
                ],
            }
        ],
    }

    def loop_bundle(run_id: str, prefix: str, second_payload: str) -> TraceBundle:
        executions = (
            _execution("producer", f"{prefix}:p0", 0, run_id=run_id),
            _execution(
                "consumer",
                f"{prefix}:c0",
                1,
                run_id=run_id,
                parents=(f"{prefix}:p0",),
                incoming_edge_id="producer_to_consumer",
            ),
            _execution(
                "producer",
                f"{prefix}:p1",
                2,
                run_id=run_id,
                parents=(f"{prefix}:c0",),
                incoming_edge_id="consumer_to_producer",
            ),
            _execution(
                "consumer",
                f"{prefix}:c1",
                3,
                run_id=run_id,
                parents=(f"{prefix}:p1",),
                incoming_edge_id="producer_to_consumer",
            ),
        )
        return _occurrence_bundle(
            run_id,
            executions,
            (
                ("producer_to_consumer", f"{prefix}:p0", f"{prefix}:c0", {"payload": "first"}),
                ("consumer_to_producer", f"{prefix}:c0", f"{prefix}:p1", {"payload": "retry"}),
                (
                    "producer_to_consumer",
                    f"{prefix}:p1",
                    f"{prefix}:c1",
                    {"payload": second_payload},
                ),
            ),
        )

    loops = CorpusCase(
        case_id="loops",
        category="loops",
        rationale=(
            "Two executions of the same edge are paired by causal occurrence; only the second "
            "candidate crossing loses its required payload."
        ),
        contract=loop_contract,
        baseline=loop_bundle("loops-baseline", "b", "second"),
        candidate=loop_bundle("loops-candidate", "c", ""),
        expected_status="FAIL",
        expected_first_breaking_edge="producer_to_consumer",
        expected_findings=(
            ("payload_required_each_iteration", "BREAKING", "CAUSAL_MATCH"),
            ("payload_required_each_iteration", "PASS", "CAUSAL_MATCH"),
        ),
    )

    fanout_contract = _contract(
        "corpus_occurrences",
        "fan_out",
        "root",
        "worker",
        {
            "id": "branch_payload_required",
            "evaluator": "completeness",
            "description": "Each fan-out branch must receive a non-empty work item.",
            "severity": "breaking",
            "destination_path": "output.payload",
        },
    )

    def fanout_bundle(run_id: str, prefix: str, order: tuple[str, str]) -> TraceBundle:
        executions = (
            _execution("root", f"{prefix}:root", 0, run_id=run_id),
            *(
                _execution(
                    "worker",
                    f"{prefix}:{branch}",
                    index,
                    run_id=run_id,
                    parents=(f"{prefix}:root",),
                    branch_id=branch,
                    incoming_edge_id="fan_out",
                )
                for index, branch in enumerate(order, start=1)
            ),
        )
        return _occurrence_bundle(
            run_id,
            executions,
            tuple(
                ("fan_out", f"{prefix}:root", f"{prefix}:{branch}", {"payload": branch})
                for branch in order
            ),
        )

    fanout = CorpusCase(
        case_id="fan-out",
        category="fan-out",
        rationale=(
            "Two parallel branches remain correctly paired by branch and causal ancestry even "
            "when their scheduler order reverses."
        ),
        contract=fanout_contract,
        baseline=fanout_bundle("fanout-baseline", "b", ("left", "right")),
        candidate=fanout_bundle("fanout-candidate", "c", ("right", "left")),
        expected_status="PASS",
        expected_first_breaking_edge=None,
        expected_findings=(
            ("branch_payload_required", "PASS", "CAUSAL_MATCH"),
            ("branch_payload_required", "PASS", "CAUSAL_MATCH"),
        ),
    )
    return loops, fanout


def _migration_cases() -> tuple[CorpusCase, CorpusCase, CorpusCase]:
    baseline_prompt_revision, candidate_prompt_revision = prompt_revisions()
    replay_model = RecordedPromptModel()
    baseline_prompt = replay_model.run(baseline_prompt_revision)
    candidate_prompt = replay_model.run(candidate_prompt_revision)
    prompt_contract_path = ROOT / "examples/prompt_migration/contracts.yml"
    prompt_contract = load_contract(prompt_contract_path).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    prompt = CorpusCase(
        case_id="prompt-migration",
        category="prompt-migration",
        rationale=(
            "The same recorded model under a revised prompt escalates authority, skips source "
            "access, and drops evidence identifiers while preserving its output schema."
        ),
        contract=prompt_contract,
        baseline=prompt_trace("prompt_migration", baseline_prompt),
        candidate=prompt_trace("prompt_migration", candidate_prompt),
        expected_status="FAIL",
        expected_first_breaking_edge="advisor_to_decision_maker",
        expected_findings=(
            ("advice_must_remain_a_recommendation", "BREAKING", "LOGICAL_SINGLETON"),
            ("verified_requires_opened_supporting_source", "BREAKING", "LOGICAL_SINGLETON"),
            ("evidence_identifiers_required", "BREAKING", "LOGICAL_SINGLETON"),
        ),
    )

    baseline_retrieval = LocalMarketFeedRetriever().retrieve()
    candidate_retrieval = CachedQuoteRetriever().retrieve()
    tool_contract_path = ROOT / "examples/tool_migration/contracts.yml"
    tool_contract = load_contract(tool_contract_path).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    tool = CorpusCase(
        case_id="tool-migration",
        category="tool-migration",
        rationale=(
            "A cached retriever keeps the quote packet shape but weakens freshness, units, "
            "completeness, and provenance."
        ),
        contract=tool_contract,
        baseline=tool_trace("tool_migration", "baseline", baseline_retrieval),
        candidate=tool_trace("tool_migration", "candidate", candidate_retrieval),
        expected_status="FAIL",
        expected_first_breaking_edge="quote_retriever_to_risk_model",
        expected_findings=(
            ("quote_must_be_recent", "BREAKING", "LOGICAL_SINGLETON"),
            ("quote_value_must_be_usd", "BREAKING", "LOGICAL_SINGLETON"),
            ("quote_evidence_identifiers_required", "BREAKING", "LOGICAL_SINGLETON"),
            (
                "verified_quote_requires_opened_supporting_source",
                "BREAKING",
                "LOGICAL_SINGLETON",
            ),
        ),
    )

    baseline_producer, candidate_producer = fixture_producers()
    evidence = default_source()
    baseline_model = baseline_producer.produce(PROMPT, evidence)
    candidate_model = candidate_producer.produce(PROMPT, evidence)
    model_contract_path = ROOT / "examples/model_migration/contracts.yml"
    model_contract = load_contract(model_contract_path).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    model = CorpusCase(
        case_id="model-migration",
        category="model-migration",
        rationale=(
            "Two recorded model fixtures return the same structured claim, but the candidate has "
            "no supporting source-access event."
        ),
        contract=model_contract,
        baseline=model_trace("model_migration", "baseline", baseline_model),
        candidate=model_trace("model_migration", "candidate", candidate_model),
        expected_status="FAIL",
        expected_first_breaking_edge="model_producer_to_policy_gate",
        expected_findings=(
            (
                "verified_requires_opened_supporting_source",
                "BREAKING",
                "LOGICAL_SINGLETON",
            ),
        ),
    )
    return model, prompt, tool


def corpus_cases() -> tuple[CorpusCase, ...]:
    """Return the corpus in stable public order."""
    return (*_single_evaluator_cases(), *_occurrence_cases(), *_migration_cases())
