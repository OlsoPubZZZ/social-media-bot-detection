"""Provider registry / plugin-interface tests (no external packages needed)."""

import pytest

from smbd.providers.base import Provider
from smbd.providers.importer import ImportProvider
from smbd.providers.registry import available_plugins, load_provider


def test_load_by_dotted_path():
    p = load_provider("smbd.providers.importer:ImportProvider")
    assert isinstance(p, ImportProvider)
    assert isinstance(p, Provider)


def test_unknown_provider_raises_with_hint():
    with pytest.raises(ValueError, match="Unknown provider"):
        load_provider("definitely_not_installed")


def test_non_provider_dotted_path_rejected():
    # Resolves to a class that isn't a Provider subclass.
    with pytest.raises(ValueError, match="Provider subclass"):
        load_provider("smbd.config:Config")


def test_available_plugins_is_a_list():
    # No third-party plugins are installed in the test env; just shouldn't error.
    assert isinstance(available_plugins(), list)
