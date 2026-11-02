# tests/conftest.py
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--integration", action="store_true", default=False,
        help="Run integration tests that require a live server"
    )
    parser.addoption(
        "--server-url", default="http://127.0.0.1:8000",
        help="URL of live server for integration tests"
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: requires a running server"
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        skip_integration = pytest.mark.skip(reason="use --integration to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


@pytest.fixture(scope="session")
def live_server_url(request):
    return request.config.getoption("--server-url")
