"""Concept dependency graph. An edge A -> B means "B is a prerequisite of A".

Only 'hard' prerequisites are stored in `_prereqs` and used for root-cause tracing, ancestor search,
and remediation paths. 'soft' cross-links (`related`) are validated and stored separately in `_related`
and never affect root-cause tracing.
"""
from __future__ import annotations

from collections import deque


class GraphError(ValueError):
    pass


class ConceptGraph:
    def __init__(self, concepts: list[dict]):
        self.ids = [c["id"] for c in concepts]
        if len(set(self.ids)) != len(self.ids):
            raise GraphError("duplicate concept ids")
        self.concepts: dict[str, dict] = {c["id"]: c for c in concepts}
        known = set(self.ids)
        self._prereqs: dict[str, list[str]] = {}
        self._related: dict[str, list[str]] = {}
        for c in concepts:
            for p in c.get("prerequisites", []):
                if p not in known:
                    raise GraphError(f"{c['id']} lists unknown prerequisite {p}")
                if p == c["id"]:
                    raise GraphError(f"{c['id']} lists itself as a prerequisite")
            for r in c.get("related", []):
                if r not in known:
                    raise GraphError(f"{c['id']} lists unknown related concept {r}")
                if r == c["id"]:
                    raise GraphError(f"{c['id']} lists itself as related")
            self._prereqs[c["id"]] = list(c.get("prerequisites", []))
            self._related[c["id"]] = list(c.get("related", []))
        self._dependants: dict[str, list[str]] = {cid: [] for cid in self.ids}
        for cid, prs in self._prereqs.items():
            for p in prs:
                self._dependants[p].append(cid)
        self._check_acyclic()

    def _check_acyclic(self) -> None:
        state: dict[str, int] = {}  # 1 = visiting, 2 = done

        def visit(node: str, trail: list[str]) -> None:
            st = state.get(node)
            if st == 2:
                return
            if st == 1:
                raise GraphError("cycle: " + " -> ".join(trail + [node]))
            state[node] = 1
            for p in self._prereqs[node]:
                visit(p, trail + [node])
            state[node] = 2

        for cid in self.ids:
            visit(cid, [])

    # ---- queries ---------------------------------------------------------------------------
    def prereqs(self, cid: str) -> list[str]:
        return self._prereqs[cid]

    def related(self, cid: str) -> list[str]:
        return self._related.get(cid, [])

    def dependants(self, cid: str) -> list[str]:
        return self._dependants[cid]

    def dependents(self, cid: str) -> list[str]:
        return self._dependants[cid]

    def edges(self) -> list[tuple[str, str]]:
        """Hard (concept, prerequisite) pairs."""
        return [(cid, p) for cid in self.ids for p in self._prereqs[cid]]

    def soft_edges(self) -> list[tuple[str, str]]:
        """Soft (concept, related) pairs."""
        return [(cid, r) for cid in self.ids for r in self._related.get(cid, [])]

    def ancestors(self, cid: str) -> set[str]:
        """All transitive hard prerequisites of cid."""
        out: set[str] = set()
        stack = list(self._prereqs[cid])
        while stack:
            n = stack.pop()
            if n not in out:
                out.add(n)
                stack.extend(self._prereqs[n])
        return out

    def descendants(self, cid: str) -> set[str]:
        """All concepts that (transitively) depend on cid via hard edges."""
        out: set[str] = set()
        stack = list(self._dependants[cid])
        while stack:
            n = stack.pop()
            if n not in out:
                out.add(n)
                stack.extend(self._dependants[n])
        return out

    def distances_from(self, target: str) -> dict[str, int]:
        """Breadth-first distance from target down its hard prerequisite edges."""
        dist = {target: 0}
        q = deque([target])
        while q:
            n = q.popleft()
            for p in self._prereqs[n]:
                if p not in dist:
                    dist[p] = dist[n] + 1
                    q.append(p)
        return dist

    def path(self, target: str, root: str) -> list[str]:
        """Shortest hard-prerequisite chain, returned from root up to target (the remediation path)."""
        if target == root:
            return [target]
        parent: dict[str, str | None] = {target: None}
        q = deque([target])
        while q:
            n = q.popleft()
            if n == root:
                break
            for p in self._prereqs[n]:
                if p not in parent:
                    parent[p] = n
                    q.append(p)
        if root not in parent:
            return [root, target]
        chain = [root]
        while parent[chain[-1]] is not None:
            chain.append(parent[chain[-1]])  # type: ignore[arg-type]
        return chain

    def levels(self) -> dict[str, int]:
        """Longest-path level along hard edges: concepts with no prerequisites are level 0."""
        memo: dict[str, int] = {}

        def level(n: str) -> int:
            if n not in memo:
                prs = self._prereqs[n]
                memo[n] = 0 if not prs else 1 + max(level(p) for p in prs)
            return memo[n]

        return {cid: level(cid) for cid in self.ids}
