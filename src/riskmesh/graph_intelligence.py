"""Bounded iterative strongly-connected-components detection for payment networks."""
from collections import defaultdict

from riskmesh.models import Transaction


def circular_clusters(transactions: list[Transaction]) -> list[list[str]]:
    if len(transactions) > 20000:
        raise ValueError("Maximum 20000 transactions")
    edges = defaultdict(set)
    reverse = defaultdict(set)
    for tx in transactions:
        edges[tx.sender_account].add(tx.receiver_account)
        reverse[tx.receiver_account].add(tx.sender_account)
    nodes = set(edges) | set(reverse)
    if len(nodes) > 10000:
        raise ValueError("Maximum 10000 accounts")
    seen = set()
    order = []
    for root in sorted(nodes):
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(sorted(edges[root])))]
        while stack:
            node, neighbors = stack[-1]
            neighbor = next(neighbors, None)
            if neighbor is None:
                order.append(node)
                stack.pop()
            elif neighbor not in seen:
                seen.add(neighbor)
                stack.append((neighbor, iter(sorted(edges[neighbor]))))
    seen.clear()
    clusters = []
    for root in reversed(order):
        if root in seen:
            continue
        component = []
        queue = [root]
        seen.add(root)
        while queue:
            node = queue.pop()
            component.append(node)
            for neighbor in reverse[node]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        if len(component) > 1 or root in edges[root]:
            clusters.append(sorted(component))
    return sorted(clusters, key=lambda cluster: (-len(cluster), cluster))[:50]
