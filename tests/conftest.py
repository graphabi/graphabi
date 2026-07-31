from collections.abc import Iterator
from pathlib import Path

import pytest

from graphabi.demo import DemoResult, run_demo


@pytest.fixture(scope="session")
def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def demo_result() -> Iterator[DemoResult]:
    result = run_demo()
    yield result
