import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """El rate limiting (ver docs/SECURITY.md #9, core/throttling.py) usa
    el cache por defecto de Django para contar requests. Sin esto, los
    contadores persistirían entre tests dentro del mismo proceso de
    pytest y un test podría fallar por el estado que dejó otro test
    anterior sin relación alguna.
    """
    cache.clear()
    yield
    cache.clear()
