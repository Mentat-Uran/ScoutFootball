"""Shared pytest fixtures and configuration."""

from __future__ import annotations

import warnings
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _close_matplotlib_figures() -> Generator[None]:
    """Close all matplotlib figures after each test to prevent memory leaks."""
    yield
    try:
        import matplotlib.pyplot as plt

        plt.close("all")
    except ImportError:
        pass


# Suppress known harmless warnings
warnings.filterwarnings(
    "ignore",
    message="Mean of empty slice",
    category=RuntimeWarning,
)
warnings.filterwarnings(
    "ignore",
    message=".*set_tight_layout.*",
    category=PendingDeprecationWarning,
)
