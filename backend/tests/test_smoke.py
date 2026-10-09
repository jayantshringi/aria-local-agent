"""Smoke tests verifying baseline testing harness and backend package health."""

import app


def test_smoke_harness():
    """Verify that pytest runs and basic assertions work."""
    assert True


def test_app_package_version():
    """Verify that the app package has a version identifier."""
    assert hasattr(app, "__version__")
    assert app.__version__ == "0.1.0"
