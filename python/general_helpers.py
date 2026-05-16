import numpy as np

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