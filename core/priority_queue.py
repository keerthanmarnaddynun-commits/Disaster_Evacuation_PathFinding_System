"""
Explicit priority queue primitives for pathfinding and scheduling.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(order=True)
class PrioritizedNode:
    """Generic wrapper to make any object heap-sortable."""

    priority: float
    item: Any = field(compare=False)


class MinHeapPQ(Generic[T]):
    """Min-heap priority queue with lazy decrease-key."""

    def __init__(self) -> None:
        self._heap: list[tuple[float, int, T]] = []
        self._counter = 0

    def push(self, priority: float, item: T) -> None:
        heapq.heappush(self._heap, (priority, self._counter, item))
        self._counter += 1

    def pop(self) -> tuple[float, T]:
        if not self._heap:
            raise IndexError("pop from empty MinHeapPQ")
        p, _, it = heapq.heappop(self._heap)
        return p, it

    def peek(self) -> tuple[float, T]:
        if not self._heap:
            raise IndexError("peek empty MinHeapPQ")
        p, _, it = self._heap[0]
        return p, it

    def decrease_key(self, item: T, new_priority: float) -> None:
        """Lazy: push duplicate; stale entries ignored by consumer."""
        self.push(new_priority, item)

    def __len__(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0


class MaxHeapPQ(Generic[T]):
    """Max-heap via negated priorities."""

    def __init__(self) -> None:
        self._heap: list[tuple[float, int, T]] = []
        self._counter = 0

    def push(self, priority: float, item: T) -> None:
        heapq.heappush(self._heap, (-priority, self._counter, item))
        self._counter += 1

    def pop(self) -> tuple[float, T]:
        if not self._heap:
            raise IndexError("pop from empty MaxHeapPQ")
        np, _, it = heapq.heappop(self._heap)
        return -np, it

    def __len__(self) -> int:
        return len(self._heap)


class IndexedPQ(Generic[T]):
    """Priority queue with O(log n) updates by item identity (sift-based)."""

    def __init__(self) -> None:
        self._heap: list[tuple[float, T]] = []
        self._index: dict[T, int] = {}

    def push(self, item: T, priority: float) -> None:
        if item in self._index:
            self.update_priority(item, priority)
            return
        pos = len(self._heap)
        self._index[item] = pos
        self._heap.append((priority, item))
        self._sift_up(pos)

    def pop(self) -> tuple[T, float]:
        if not self._heap:
            raise IndexError("pop from empty IndexedPQ")
        pri0, root = self._heap[0]
        last_p, last_it = self._heap[-1]
        self._heap.pop()
        del self._index[root]
        if not self._heap:
            return root, pri0
        self._heap[0] = (last_p, last_it)
        self._index[last_it] = 0
        self._sift_down(0)
        return root, pri0

    def peek(self) -> tuple[T, float]:
        if not self._heap:
            raise IndexError("peek empty")
        p, it = self._heap[0]
        return it, p

    def update_priority(self, item: T, new_priority: float) -> None:
        if item not in self._index:
            self.push(item, new_priority)
            return
        pos = self._index[item]
        old_p, _ = self._heap[pos]
        self._heap[pos] = (new_priority, item)
        if new_priority < old_p:
            self._sift_up(pos)
        else:
            self._sift_down(pos)

    def contains(self, item: T) -> bool:
        return item in self._index

    def __len__(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def _sift_up(self, pos: int) -> None:
        while pos > 0:
            parent = (pos - 1) // 2
            if self._heap[pos][0] >= self._heap[parent][0]:
                break
            self._swap(pos, parent)
            pos = parent

    def _sift_down(self, pos: int) -> None:
        n = len(self._heap)
        while True:
            smallest = pos
            left = 2 * pos + 1
            right = 2 * pos + 2
            if left < n and self._heap[left][0] < self._heap[smallest][0]:
                smallest = left
            if right < n and self._heap[right][0] < self._heap[smallest][0]:
                smallest = right
            if smallest == pos:
                break
            self._swap(pos, smallest)
            pos = smallest

    def _swap(self, i: int, j: int) -> None:
        self._heap[i], self._heap[j] = self._heap[j], self._heap[i]
        self._index[self._heap[i][1]] = i
        self._index[self._heap[j][1]] = j
