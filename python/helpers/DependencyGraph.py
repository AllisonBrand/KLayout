# Written by Claude-4-5-Sonnet
# I just read every line, made minor edits and added comments

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
    
    def topological_sort(self, fail_if_cycle=True):
        """Return nodes in evaluation order.
        
        If fail_if_cycle is True, raise ValueError on detection of a cycle.
        
        If fail_if_cycle is False, then returns (eval_order, cycle), where cycle is a subgraph containing the 
        cycle as a dict of {node: [dependencies]}. Will be an empty {} if no cycle is found. """
        
        # Counts of incoming edges (dependencies) for each node
        in_degree = {node: len(self.graph[node]) for node in self.graph}
        
        # Add dependencies that aren't in graph as keys (these have zero of their own dependencies)
        for node in self.graph:
            for dep in self.graph[node]:
                if dep not in in_degree:
                    in_degree[dep] = 0
        
        # Kahn's algorithm (Breadth-First-Search)
        queue = deque([node for node, degree in in_degree.items() if degree == 0]) # Stores nodes with zero unresolved dependencies
        eval_order = [] # Stores nodes in an order in which they can be evaluated.
        
        while queue: 
            node = queue.popleft() # O(1)
            eval_order.append(node) # Resolve node
            
            for dependent in self.graph:
                if node in self.graph[dependent]:
                    # Decrement dependency count for each *dependent* node that depended on the resolved *node*
                    in_degree[dependent] -= 1
                    # Check, was *node* the last dependency of *dependent*?
                    if in_degree[dependent] == 0: # All dependencies have been cleared.
                        queue.append(dependent) # O(1)
        
        if fail_if_cycle:

            if len(eval_order) != len(in_degree):
                # There is a cycle!
                raise ValueError('Cycle Detected!')
            
            return eval_order
        
        else:
            
            cycle = {}
            if len(eval_order) != len(in_degree):
                # There is a cycle!
                cycle = {k: self.graph[k] for k in (in_degree.keys() - set(eval_order))}
            
        return eval_order, cycle
    
    def kahn_algorithm(self):
        '''Kahn's algorithm (Breadth-First-Search)
        Returns a list of nodes in evaluation order, and a cycle subgraph, if found.
        If no cycle is found, cycle is an empty {}'''
        # Counts of incoming edges (dependencies) for each node
        in_degree = {node: len(self.graph[node]) for node in self.graph}
        
        # Add dependencies that aren't in graph as keys (these have zero of their own dependencies)
        for node in self.graph:
            for dep in self.graph[node]:
                if dep not in in_degree:
                    in_degree[dep] = 0
        
        # Kahn's algorithm (Breadth-First-Search)
        queue = deque([node for node, degree in in_degree.items() if degree == 0]) # Stores nodes with zero unresolved dependencies
        eval_order = [] # Stores nodes in an order in which they can be evaluated.
        
        while queue: 
            node = queue.popleft() # O(1)
            eval_order.append(node) # Resolve node
            
            for dependent in self.graph:
                if node in self.graph[dependent]:
                    # Decrement dependency count for each *dependent* node that depended on the resolved *node*
                    in_degree[dependent] -= 1
                    # Check, was *node* the last dependency of *dependent*?
                    if in_degree[dependent] == 0: # All dependencies have been cleared.
                        queue.append(dependent) # O(1)
        
        if len(eval_order) != len(in_degree):
            # There is a cycle!
            pass
            
        return eval_order, cycle