"""Save validated assessment stages separately from accepted items."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict

from Backend.Core.assessment_checkpoints import AssessmentCheckpointStore
from Backend.Core.generation_requests import GenerationRequest, response_replay

_MAX_RESPONSE_BYTES = 131_072
_CHECKPOINTED_OPERATIONS = ("authoring", "solver", "batch_review", "difficulty")


def _stage_key(item_id: str, operation: str) -> str:
    return f"item-stage-v1:{item_id}:{operation}"


def discard_stages(
    store: AssessmentCheckpointStore, item_id: str, *, include_item: bool = False
) -> None:
    keys = tuple(
        _stage_key(item_id, operation) for operation in _CHECKPOINTED_OPERATIONS
    )
    store.discard_payloads((item_id, *keys) if include_item else keys)


def checkpoint_stage[Result](
    store: AssessmentCheckpointStore | None,
    item_id: str,
    operation: str,
    validate: Callable[[], Result],
    *,
    approved: Callable[[Result], bool] = lambda _: True,
    evidence_identity: str = "",
) -> Result:
    """Replay only an identical request and run the same validation again."""
    if store is None:
        return validate()
    key = _stage_key(item_id, operation)
    cached = store.load_payload(key)
    submitted: list[tuple[str, dict[str, object]]] = []
    replayed = False

    def intercept(
        request: GenerationRequest, generate: Callable[[], dict[str, object]]
    ) -> dict[str, object]:
        nonlocal replayed
        if request.operation != operation:
            return generate()
        identity = asdict(request)
        if evidence_identity:
            identity["evidence_identity"] = evidence_identity
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True).encode()
        ).hexdigest()
        response = cached.get("response") if cached else None
        if (
            not submitted
            and cached is not None
            and cached.get("request_sha256") == digest
            and isinstance(response, dict)
        ):
            replayed = True
        else:
            response = generate()
        submitted.append((digest, deepcopy(response)))
        return response

    def run() -> Result:
        token = response_replay.set(intercept)
        try:
            return validate()
        finally:
            response_replay.reset(token)

    try:
        result = run()
    except (KeyError, TypeError, ValueError):
        if not replayed or len(submitted) != 1:
            raise
        # Invalid cached content is not a model attempt. Re-run the same
        # stage once with fresh input rather than repairing a corrupt draft.
        store.discard_item(key)
        submitted.clear()
        cached = None
        replayed = False
        result = run()
    if not approved(result):
        if replayed:
            store.discard_item(key)
        return result
    if len(submitted) == 1 and not replayed:
        digest, response = submitted[0]
        if (
            len(json.dumps(response, ensure_ascii=False).encode())
            <= _MAX_RESPONSE_BYTES
        ):
            store.save_payload(key, {"request_sha256": digest, "response": response})
    return result
