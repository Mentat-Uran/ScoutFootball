"""Provider adapter manifest schema.

A manifest is a machine-readable declaration of what one registered
source adapter can do, how its input fields map to internal fields,
and what semantic loss the conversion introduces. Manifests are pure
metadata: they do not change ingester behavior and carry no secrets.

This is the first slice of I1 (开放互操作与本地视频回链): it gives the
maintainer and external contributors a single place to see which
sources are supported, what each source provides, and where the
conversion losses are. Later I1 work (atomic-SPADL alignment, video
references, tracking adapters, sync quality reports) will extend the
same manifest schema instead of inventing a parallel registry.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class AdapterCapability(StrEnum):
    """What kind of football data one adapter can provide.

    The set is intentionally small and operational (not a full ontology):
    each value names a category the project already consumes somewhere.
    Adapters that do not provide a capability simply omit it.
    """

    EVENT = "event"
    TRACKING = "tracking"
    VIDEO = "video"
    IDENTITY = "identity"
    MARKET_VALUE = "market_value"
    FIXTURE = "fixture"
    RESULT = "result"
    RATING = "rating"
    PLAYER_STATS = "player_stats"
    LINEUP = "lineup"
    INJURY = "injury"
    TRANSFER = "transfer"


class SchemaMapping(BaseModel):
    """One field-level mapping from a source column to an internal field.

    The conversion field names the loss category so consumers can filter
    on "show me only the fields that lose information" without reading
    every note:
    - ``direct``: 1:1 copy with no transformation.
    - ``unit_conversion``: value preserved but unit changed (e.g. minutes
      → seconds).
    - ``approximate``: value mapped through a heuristic that may not be
      exact for every row (e.g. position inference from event types).
    - ``derived``: internal field computed from one or more source
      fields; no single upstream column maps 1:1.
    - ``lost``: source field has no internal equivalent and is dropped.
    """

    model_config = ConfigDict(frozen=True)

    source_field: str
    internal_field: str
    conversion: str
    note: str = ""


class AdapterManifest(BaseModel):
    """Manifest for one registered source adapter.

    Manifests are conservative: if a capability or mapping is not yet
    documented, it is omitted rather than guessed. The ``maintained``
    flag distinguishes adapters the maintainer still runs from
    experimental or stopped ones.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    parser_version: str
    module_path: str
    capabilities: tuple[AdapterCapability, ...]
    schema_mappings: tuple[SchemaMapping, ...] = ()
    conversion_loss_notes: str = ""
    ingestion_cli: str = ""
    artifact_paths: tuple[str, ...] = ()
    maintained: bool = True
    notes: str = ""


class AdapterRegistry(BaseModel):
    """Aggregate of all adapter manifests the project knows about."""

    model_config = ConfigDict(frozen=True)

    generated_at: str
    package_version: str = ""
    manifests: tuple[AdapterManifest, ...] = ()

    def by_source(self, source_id: str) -> AdapterManifest | None:
        for manifest in self.manifests:
            if manifest.source_id == source_id:
                return manifest
        return None

    def with_capability(self, capability: AdapterCapability) -> tuple[AdapterManifest, ...]:
        return tuple(
            m for m in self.manifests if capability in m.capabilities
        )
