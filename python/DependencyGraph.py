# Written by Claude-4-5-Sonnet
# I just read it over, made minor edits and added comments

from collections import deque

class DependencyGraph:
    """Simple Directed graph for parameter dependencies"""
    
    def __init__(self):
        self.graph = {}  # {node: [dependencies]}
    
    def add_dependency(self, param, depends_on):
        """param depends on depends_on (list)"""
        if param not in self.graph:
            self.graph[param] = set()
        self.graph[param].update(depends_on)
    
    def has_cycle(self):
        """Check for cycles using Depth-First-Search."""
        visited = set() # Nodes that have already been checked for self-reference (i.e. cycles back to that node)
        recursion_stack = set() # Nodes currently in the recursive call stack (ancestors of the current node)
        
        def dfs(node):
            visited.add(node)
            recursion_stack.add(node)
            
            for neighbor in self.graph.get(node, default=[]):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in recursion_stack:
                    return True
            
            # No cycle back to node exists
            recursion_stack.remove(node)
            return False
        
        for node in self.graph:
            if node not in visited:
                if dfs(node):
                    return True
        return False
    
    def topological_sort(self):
        """Return nodes in evaluation order"""
        # Counts of incoming edges (dependencies) for each node
        in_degree = {node: len(self.graph[node]) for node in self.graph}
        
        # Add dependencies that aren't in graph as keys (these have zero of their own dependencies)
        for node in self.graph:
            for dep in self.graph[node]:
                if dep not in in_degree:
                    in_degree[dep] = 0
        
        # Kahn's algorithm (Breadth-First-Search)
        queue = deque([node for node, degree in in_degree.items() if degree == 0]) # Stores nodes with zero unresolved dependencies
        result = [] # Stores nodes in an order in which they can be evaluated.
        
        while queue: 
            node = queue.popleft() # O(1)
            result.append(node) # Resolve node
            
            for dependent in self.graph:
                if node in self.graph[dependent]:
                    # Decrement dependency count for each *dependent* node that depended on the resolved *node*
                    in_degree[dependent] -= 1
                    # Check, was *node* the last dependency of *dependent*?
                    if in_degree[dependent] == 0: # All dependencies have been cleared.
                        queue.append(dependent) # O(1)
        
        if len(result) != len(in_degree):
            raise ValueError("Cycle detected")
        
        return result