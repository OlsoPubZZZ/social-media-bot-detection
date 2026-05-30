"""Provider registry — load data sources by name, including external plugins.

SMBD ships official adapters (`import`, `youtube`, `x`) and the Instagram
library provider. It deliberately ships **no scraper**: scraping violates most
platforms' terms and carries legal risk. Instead, this registry lets a
*separate, opt-in* package register its own :class:`~smbd.providers.base.Provider`
so users who choose to can plug it in — without that code living in this repo.

A plugin can be referenced two ways:

1. **Entry point** — a package declares, in its own ``pyproject.toml``::

       [project.entry-points."smbd.providers"]
       instascraper = "my_pkg.scraper:InstaScraper"

   then ``smbd comments <target> --provider instascraper`` just works once it's
   installed.

2. **Dotted path** — ``--provider my_pkg.scraper:InstaScraper`` (no install
   registration needed).

See ``docs/extending.md`` for the full contract and the ToS/legal warnings.
"""

from __future__ import annotations

import importlib
from importlib import metadata
from typing import List

from smbd.providers.base import Provider

_ENTRY_POINT_GROUP = "smbd.providers"


def _entry_points() -> List[metadata.EntryPoint]:
    eps = metadata.entry_points()
    # Python 3.10+ returns EntryPoints (with .select); 3.9 returns a dict.
    if hasattr(eps, "select"):
        return list(eps.select(group=_ENTRY_POINT_GROUP))
    return list(eps.get(_ENTRY_POINT_GROUP, []))  # type: ignore[attr-defined]


def available_plugins() -> List[str]:
    """Names of installed third-party providers registered via entry points."""
    return sorted(ep.name for ep in _entry_points())


def _resolve(name: str):
    # Dotted path form: "package.module:ClassName"
    if ":" in name:
        module_name, _, attr = name.partition(":")
        module = importlib.import_module(module_name)
        return getattr(module, attr)
    # Registered entry-point name
    for ep in _entry_points():
        if ep.name == name:
            return ep.load()
    plugins = available_plugins()
    hint = f" Installed plugins: {', '.join(plugins)}." if plugins else ""
    raise ValueError(
        f"Unknown provider {name!r}. Use 'import', 'youtube', or 'x', an installed "
        f"plugin name, or a 'package.module:Class' path.{hint}"
    )


def load_provider(name: str, api_key: str | None = None) -> Provider:
    """Instantiate an external provider by entry-point name or dotted path.

    Tries to pass ``api_key=`` if the provider accepts it, else constructs with
    no arguments (the provider is expected to read its own credentials).
    """
    cls = _resolve(name)
    if not (isinstance(cls, type) and issubclass(cls, Provider)):
        raise ValueError(f"{name!r} does not resolve to a smbd Provider subclass.")
    if api_key:
        try:
            return cls(api_key=api_key)  # type: ignore[call-arg]
        except TypeError:
            pass
    return cls()
