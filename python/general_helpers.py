import numpy as np
import operator
import ast

def safe_eval(expr, context, max_depth=100):
            """Safely evaluate mathematical expression with NumPy array support
                
                Args:
                    expr: Expression string
                    context: Dict of variables (can contain NumPy arrays or scalars)
                    max_depth: a maximum recursion depth (number of operations), protects against stack overflow
                
                Returns:
                    Result (scalar or NumPy array)"""
            # Allowed operations
            
            # Arithmetic
            ops = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.FloorDiv: operator.floordiv,
                ast.Pow: operator.pow,
                ast.BitXor: operator.pow, # ^ is usually expected to be pow, not xor.
                ast.Mod: operator.mod,
                ast.USub: operator.neg,
                ast.UAdd: operator.pos,
                ast.Mod: operator.mod
            }
            
            # Comparison 
            comparison_ops = {
                ast.Eq: operator.eq,
                ast.NotEq: operator.ne,
                ast.Lt: operator.lt,
                ast.LtE: operator.le,
                ast.Gt: operator.gt,
                ast.GtE: operator.ge,
            }
            
            depth_counter = 0
            
            def eval_node(node):
                '''Recursively evaluates ast node'''
                # Protects against stack overflow from malicious input:
                nonlocal depth_counter
                depth_counter += 1
                if depth_counter > max_depth:
                    raise RecursionError(f"Expression too complex (>{max_depth} operations)")
                
                # Recursively evaluate node:
                if isinstance(node, ast.Constant): # Number or np.ndarray
                    return node.value
                
                elif isinstance(node, ast.Name):   # Variable
                    if node.id in context:
                        value = context[node.id]
                        # Convert to NumPy array if not already
                        # This ensures consistent behavior
                        return np.asarray(value)
                    else:
                        raise ValueError(f"Unknown variable: {node.id}")
                    
                elif isinstance(node, ast.BinOp):  # Binary operation
                    if type(node.op) not in ops:
                        raise ValueError(f"Unsupported operation: {type(node.op)}.__name__")
                    return ops[type(node.op)](eval_node(node.left), eval_node(node.right))
                
                elif isinstance(node, ast.UnaryOp): # Unary operation
                    if type(node.op) not in ops:
                        raise ValueError(f"Unsupported operation: {type(node.op).__name__}")
                    return ops[type(node.op)](eval_node(node.operand))
                
                elif isinstance(node, ast.Compare):  # Comparison (e.g., a < b, or chained: a < b < c)
                    left = eval_node(node.left)
                    
                    # For chained comparisons, we need to AND all results
                    cumulative_result = None
                    
                    for op, comparator in zip(node.ops, node.comparators):
                        right = eval_node(comparator)
                        
                        op_type = type(op)
                        if op_type in comparison_ops:
                            result = comparison_ops[op_type](left, right)
                            
                            # Combine with previous results using AND
                            if cumulative_result is None:
                                cumulative_result = result
                            else:
                                cumulative_result = np.logical_and(cumulative_result, result)
                            
                            # For next comparison in chain: left becomes right
                            left = right
                        else:
                            raise ValueError(f"Unsupported comparison: {op_type.__name__}")
                        
                    return cumulative_result
                
                else:  # Something else
                    raise ValueError(f"Unsupported expression type: {type(node)}")
            
            try:
                tree = ast.parse(expr, mode='eval')
                return np.asarray(eval_node(tree.body))
            except SyntaxError:
                raise ValueError(f"Invalid expression syntax: {expr}")

def first_valid(*values, default=None):
    '''Returns the first values that isn't None in values, or default if no valid value is found.
    This is more concise than a loop with an if statement.
    '''
    return next((v for v in values if v is not None), default)

def parse_range(range_str:str, dtype=float):
    '''Parse range_str into a np.ndarray of values.
    
-   range_str: "start:stop", or "start:stop:step", with stop exclusive.
-   dtype: float or int
    '''
    # Parse range_str into start, stop, step
    range_parts = range_str.split(':')
    if len(range_parts) == 2:
        start, stop = range_parts
        step = 1
    elif len(range_parts) == 3:
        start, stop, step = range_parts
    else:
        raise ValueError(f'range_str {range_str} must be in the form "start:stop", or "start:stop:step".')
    
    # Check dtype
    if np.issubdtype(np.dtype(dtype), np.floating):
        dtype = float
    elif np.issubdtype(np.dtype(dtype), np.integer):
        dtype = int
    else:
        raise ValueError(f'dtype must specify float or integer. Got: {dtype}')
    
    # Convert strings to dtype:
    try:
        start = dtype(start)
        stop = dtype(stop)
        step = dtype(step)
    except ValueError as e:
        e.add_note(f'Could not parse {range_str} as a {dtype} range.')
        raise
    
    # Return np.ndarray holding the range:
    return np.arange(start, stop, step, dtype=dtype)

class UserInputError(ValueError):
    '''Accepts annotated_input, an annotated copy of the offending user input,
    to aid in precise feedback to the user.
    
    Use-case: the calling function can catch the UserInputError, and use annotated_input
    to show hints to the user without requiring them to visit the console log. This way,
    you don't need a separate function that repeats the processing of erroring 
    function in order to annotate the input.'''
    def __init__(self, annotated_input:str, *args):
        super().__init__(*args)
        self.annotated_input = annotated_input