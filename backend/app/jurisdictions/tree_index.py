import uuid
from collections.abc import Sequence

from app.jurisdictions.jurisdiction_models import Jurisdiction


class TreeIndex:
    """Every jurisdiction; siblings keep the order they were loaded in."""

    def __init__(self, nodes: Sequence[Jurisdiction]) -> None:
        self.nodes = list(nodes)
        self.by_id = {j.id: j for j in self.nodes}
        self.children_of: dict[uuid.UUID | None, list[Jurisdiction]] = {}
        for j in self.nodes:
            self.children_of.setdefault(j.parent_id, []).append(j)
        self._chains: dict[uuid.UUID, list[Jurisdiction]] = {}

    def chain(self, j: Jurisdiction) -> list[Jurisdiction]:
        """Self first, then each ancestor up to the root."""
        cached = self._chains.get(j.id)
        if cached is None:
            parent = self.by_id.get(j.parent_id) if j.parent_id else None
            cached = [j, *self.chain(parent)] if parent else [j]
            self._chains[j.id] = cached
        return cached

    def children(self, j: Jurisdiction) -> list[Jurisdiction]:
        return self.children_of.get(j.id, [])
