# === consistent_hashing.py ===

"""Consistent hashing implementation for distributed systems.

This module provides a consistent hashing ring that allows for efficient
distribution of keys across a set of nodes, with minimal reorganization
when nodes are added or removed.
"""

import hashlib
import bisect
from typing import List, Optional, Any


class ConsistentHashRing:
    """A consistent hashing ring implementation.
    
    Attributes:
        replicas: Number of virtual nodes (replicas) per physical node.
        ring: Sorted list of hash values on the ring.
        hash_to_node: Mapping from hash value to node name.
    """
    
    def __init__(self, replicas: int = 3) -> None:
        """Initialize the consistent hash ring.
        
        Args:
            replicas: Number of virtual nodes per physical node. More replicas
                     provide better load balancing but use more memory.
        """
        self.replicas: int = replicas
        self.ring: List[int] = []
        self.hash_to_node: dict = {}
        self.nodes: set = set()
    
    def _hash(self, key: str) -> int:
        """Generate a consistent hash value for the given key.
        
        Args:
            key: The key to hash.
            
        Returns:
            An integer hash value.
        """
        return int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16)
    
    def add_node(self, node: Any) -> None:
        """Add a node to the hash ring.
        
        Args:
            node: The node identifier to add.
        """
        if node in self.nodes:
            return
        self.nodes.add(node)
        for i in range(self.replicas):
            key = f"{node}#{i}"
            hash_value = self._hash(key)
            self.ring.append(hash_value)
            self.hash_to_node[hash_value] = node
        self.ring.sort()
    
    def remove_node(self, node: Any) -> None:
        """Remove a node from the hash ring.
        
        Args:
            node: The node identifier to remove.
        """
        if node not in self.nodes:
            return
        self.nodes.discard(node)
        for i in range(self.replicas):
            key = f"{node}#{i}"
            hash_value = self._hash(key)
            self.ring.remove(hash_value)
            del self.hash_to_node[hash_value]
    
    def get_node(self, key: str) -> Optional[Any]:
        """Get the node responsible for the given key.
        
        Args:
            key: The key to look up.
            
        Returns:
            The node responsible for the key, or None if the ring is empty.
        """
        if not self.ring:
            return None
        hash_value = self._hash(key)
        index = bisect.bisect_right(self.ring, hash_value) % len(self.ring)
        return self.hash_to_node[self.ring[index]]
    
    def get_nodes(self, key: str, count: int = 1) -> List[Any]:
        """Get multiple distinct nodes for a key (for replication).
        
        Args:
            key: The key to look up.
            count: Number of distinct nodes to return.
            
        Returns:
            A list of distinct nodes responsible for the key.
        """
        if not self.ring or count <= 0:
            return []
        
        hash_value = self._hash(key)
        index = bisect.bisect_right(self.ring, hash_value) % len(self.ring)
        result: List[Any] = []
        seen: set = set()
        
        while len(result) < count and len(seen) < len(self.nodes):
            node = self.hash_to_node[self.ring[index]]
            if node not in seen:
                seen.add(node)
                result.append(node)
            index = (index + 1) % len(self.ring)
        
        return result


def demo() -> None:
    """Demonstrate the consistent hashing ring with a simple example."""
    ring = ConsistentHashRing(replicas=3)
    
    # Add some nodes
    nodes = ["node_A", "node_B", "node_C", "node_D"]
    for node in nodes:
        ring.add_node(node)
    
    # Distribute some keys
    keys = ["user_1", "user_2", "user_3", "user_4", "user_5", "user_6"]
    distribution: dict = {node: 0 for node in nodes}
    
    for key in keys:
        assigned = ring.get_node(key)
        distribution[assigned] += 1
        replicas = ring.get_nodes(key, count=2)
        print(f"Key '{key}' -> primary: {assigned}, replicas: {replicas}")
    
    print(f"\nDistribution: {distribution}")
    
    # Demonstrate minimal disruption when a node is removed
    print("\nRemoving node_B...")
    ring.remove_node("node_B")
    moved = 0
    for key in keys:
        new_node = ring.get_node(key)
        print(f"Key '{key}' -> new node: {new_node}")
        if new_node is not None:
            distribution[new_node] += 0  # tracking only
    
    print(f"\nRemaining nodes: {sorted(ring.nodes)}")


if __name__ == "__main__":
    demo()