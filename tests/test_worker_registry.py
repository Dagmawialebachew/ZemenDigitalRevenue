from __future__ import annotations

import pytest

from workers.errors import PermanentJobError
from workers.registry import JobRegistry


async def handler(_ctx, _job):
    return {"ok": True}


def test_registry_rejects_duplicate_job_type() -> None:
    registry = JobRegistry()
    registry.register("x", handler)
    with pytest.raises(ValueError):
        registry.register("x", handler)


def test_registry_reports_unknown_job_type_as_permanent() -> None:
    registry = JobRegistry()
    with pytest.raises(PermanentJobError) as exc:
        registry.handler("missing")
    assert exc.value.code == "UNKNOWN_JOB_TYPE"
