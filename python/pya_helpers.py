import warnings
from collections.abc import Iterable

import pya

def move_box_to(box, lowerleft, pos='LL'):
    '''Return a copy of the box translated so that it's lower left corner is at the given point.
    box: a pya.Box object
    lowerleft: a pya.Point or an iterable containing the (x, y) coordinates
    
    pos: a string indicating which point of the box to align with the given coordinates.
             'LL' (default): align the lower left corner of the box with the given coordinates
             'C': align the center of the box with the given coordinates
             'UR': align the upper right corner of the box with the given coordinates
        '''
    # Validate inputs
    if not isinstance(box, pya.Box):
        raise TypeError('Input shape must be a pya.Box')
    try: 
        lowerleft = as_point(lowerleft)
    except TypeError as e:
        e.add_note('lowerleft must be convertable to a pya.Point in the argument to move_box_to')
        raise
        
    if pos == 'LL' or pos.lower().replace(' ', '') == 'lowerleft':
        return box.moved(pya.Point(lowerleft.x - box.bbox().p1.x, lowerleft.y - box.bbox().p1.y))
    elif pos == 'C' or pos.lower() == 'center':
        return box.moved(pya.Point(lowerleft.x - (box.bbox().p1.x + box.bbox().p2.x) / 2, lowerleft.y - (box.bbox().p1.y + box.bbox().p2.y) / 2))
    elif pos == 'UR' or pos.lower().replace(' ', '') == 'upperright':
        return box.moved(pya.Point(lowerleft.x - box.bbox().p2.x, lowerleft.y - box.bbox().p2.y))
    else:
        raise ValueError("pos must be 'LL', 'C', 'UR', or their verbose variants ('lower left', 'center', 'upper right').")

def create_text(text_string, height_um, dbu, pos=None, trans=None) -> pya.Region:
    """
    Generate and return text as a Region containing polygons.
    
    Args:
   -    text_string: String to render
   -    height_um: Text height in microns
   -    dbu: microns per dbu (layout.dbu)
   -    pos: pya.Point, pya.Vector or an iterable containing the (x, y) coordinates of the position to place the center of the text. This will be the position of the center of the text bounding box.
   -    trans: pya.Trans object for arbitrary transformations
        """
    # TODO: Text height is not working correctly, it's always shorter than the specified height. Figure out why and fix it.

    # Create text
    gen = pya.TextGenerator.default_generator()
    text_region = gen.text(text_string, dbu,
                           mag = height_um / gen.dheight())
    
    # Apply arbitrary transformation if a valid one is provided.
    if isinstance(trans, pya.Trans):
       text_region.transform(trans)
    
    # Position it
    if pos is not None:
        try:
            pos = as_point(pos)
        except TypeError as e:
            e.add_note('pos must be convertable to a pya.Point in the argument to create_text')
            raise
    else:
        pos = pya.Point(0, 0) # default to origin if no position is provided
    offset = pos - text_region.bbox().center()
    text_region.transform(pya.Trans(offset.x, offset.y))
      
    return text_region

def add_label(text_string, height_um, x_um, y_um, layout, cell, layer):
    """Add text label as polygon geometry
    Args:
        text_string: String to render
        height_um: Text height in microns
        x, y: Position in microns of bottom left corner of text bbox
        layout: pya.Layout object
        cell: pya.Cell to insert into
        layer_info: pya.LayerInfo or layer index"""
    dbu = layout.dbu

    # Create text 
    text_region = create_text(text_string, height_um, pos=(x_um/dbu, y_um/dbu), dbu=dbu)

    # Insert
    layer_idx = layout.layer(layer) if isinstance(layer, pya.LayerInfo) else layer
    cell.shapes(layer_idx).insert(text_region)

def as_point(point):
    '''Convert an input into a into a pya.Point. Input must be a pya.Point, pya.Vector,
    or an iterable containing (x, y) coordinates in dbu.'''
    if isinstance(point, pya.Point):
        return point
    elif isinstance(point, pya.Vector):
        return pya.Point(point)
    elif isinstance(point, Iterable) and len(point) == 2:
        return pya.Point(point[0], point[1])
    else:
        raise TypeError('point must must be convertable to a pya.Point. Received: ' + repr(point))

def get_bbox_point(spec_str:str, bbox:pya.Box) -> pya.Point:
    '''Returns the point from the bounding box as a pya.Point.
    
-   spec_str: specifies where the anchor point is on the bbox
-   bbox: bounding box, a pya.Box
    ''' # TODO: Make it work for words without spaces, like 'lowerleft'
    # Split spec_str into x and y specification:
    spec_str = spec_str.strip().lower().replace(',', ' ')
    if spec_str in ('center', 'c'):
        anchor_y, anchor_x = 'c', 'c'
    elif len(spec_str) == 2:
        anchor_y, anchor_x = spec_str
    else: # Assume it's in the format 'y_pos x_pos'
        anchor_y, anchor_x = spec_str.split()
    
    # Parse y-specification:
    if anchor_y in ('top', 't', 'upper', 'u'):
        y = bbox.top
    elif anchor_y in ('bottom', 'b', 'lower', 'l'):
        y = bbox.bottom
    elif anchor_y in ('center', 'c'):
        y = int((bbox.top + bbox.bottom) / 2)
    else:
        raise RuntimeError(f'Location must be formatted like: ' + 
                            '"y_pos x_pos", where y_pos is in ("top", "t", "upper", "u", "bottom", "b", "lower", "l", "center", "c") and ' + 
                            'x_pos is in ("right", "r", "left",  "l", "center", "c"), or anchor specification can be just "center", or "c".' +
                            ' Case-insensitive.')
    
    # Parse x-specification:
    if anchor_x in ('right', 'r'):
        x = bbox.right
    elif anchor_x in ('left',  'l'):
        x = bbox.left
    elif anchor_x in ('center', 'c'):
        x = int((bbox.right + bbox.left) / 2)
    else:
        raise RuntimeError(f'Location must be formatted like: ' + 
                            '"y_pos x_pos", where y_pos is in ("top", "t", "upper", "u", "bottom", "b", "lower", "l", "center", "c") and ' + 
                            'x_pos is in ("right", "r", "left",  "l", "center", "c"), or it can be just "center", or "c".' +
                            ' Case-insensitive.')
        
    return pya.Point(x, y)

def discover_pcell_params(pcell_decl:pya.PCellDeclaration=None, lib_name:str='', pcell_name:str='') -> list:
    """
    Discover parameters from a PCellDeclaration
    If pcell_decl is given, will use that. Otherwise will try to find the PCellDeclaration using lib_name and pcell_name.
    
    Returns: list of dicts with parameter info, 
    or None if the PCellDeclaration cannot be found from lib_name and pcell_name.
    """
    # Checking
    if not isinstance(pcell_decl, pya.PCellDeclaration):
        # Get the PCellDeclaration from the pcell name and library name.
        if not lib_name or not pcell_name:
            raise TypeError("discover_pcell_params() requires either 'pcell_decl' "
                             "or both 'lib_name' and 'pcell_name'")
        
        lib = pya.Library.library_by_name(lib_name)
        if not lib:
            warnings.warn(f"Library '{lib_name}' not found.")
            return None
        
        pcell_decl = lib.layout().pcell_declaration(pcell_name)
        if not pcell_decl:
            warnings.warn(f"PCell '{pcell_name}' not found in Library '{lib_name}'.")
            return None
    
    # Get parameter declarations
    param_decls = pcell_decl.get_parameters()
    
    params_info = []
    for param_decl in param_decls:
        param_info = {
            'name': param_decl.name,
            'description': param_decl.description,
            'default': param_decl.default,
            'type': param_decl.type,  # PCellParameterDeclaration type constants
            'unit': param_decl.unit if hasattr(param_decl, 'unit') else '',
            'hidden': param_decl.hidden if hasattr(param_decl, 'hidden') else False,
            'readonly': param_decl.readonly if hasattr(param_decl, 'readonly') else False
        }
        params_info.append(param_info)
    
    return params_info
  
def pcell_from_layout(target_pcell_name):
      # Search currently active layout for target_pcell_name
      app = pya.Application.instance()
      if not app:
          raise Exception("No running instance of KLayout found.")
      
      mw = app.main_window()
      if not mw:
          raise Exception("No main window found in KLayout.")
      
      view = mw.current_view()
      if not view:
          raise Exception("No current view found in KLayout.")
      
      cv = view.active_cellview()
      if not cv.is_valid():
          raise Exception("No active cellview found in KLayout.")
      
      layout = cv.layout()
      cell = layout.cell(target_pcell_name)
      if not cell:
          raise Exception(f"Cell '{target_pcell_name}' not found in currently active layout.")
              
      if not cell.is_pcell_variant():
          raise Exception(f"'{target_pcell_name}' is not a PCell instance.")
      
      pcell_decl = cell.pcell_declaration()
      if not pcell_decl:
          raise Exception(f"PCell declaration for '{target_pcell_name}' could not be retrieved from the layout.")
      
      # Actual parameters values for this instance, to use as defaults in the wrapper PCell parameters:
      actual_values = cell.pcell_parameters_by_name()
      
      print(f"Found PCell declaration for '{target_pcell_name}' in the currently active layout.")
      
      return pcell_decl, actual_values

def get_converter(param_type):
    '''Returns a function that converts a string to the given pya param type.
    param_type can be pya.PCellParameterDeclaration.TypeInt, pya.PCellParameterDeclaration.TypeDouble,
    pya.PCellParameterDeclaration.TypeString, pya.PCellParameterDeclaration.TypeLayer, etc.'''
    # Int
    if param_type == pya.PCellParameterDeclaration.TypeInt:
        return lambda s: int(float(s)//1) # Robust even on '1.0'
    # Double
    elif param_type == pya.PCellParameterDeclaration.TypeDouble:
        return float
    # String
    elif param_type == pya.PCellParameterDeclaration.TypeString:
        return str
    # List
    elif param_type == pya.PCellParameterDeclaration.TypeList:
        return list
    # Boolean
    elif param_type == pya.PCellParameterDeclaration.TypeBoolean:
        
        def to_bool(input):
            if isinstance(input, str):
                if input.lower() in ('true', '1', 'yes'):
                    return True
                elif input.lower() in ('false', '0', 'no'):
                    return False
                else:
                    raise ValueError(f"Invalid boolean value: '{input}'. Expected True/False, 1/0, yes/no, case-insensitive.")
            else:
                return bool(input)
            
        return to_bool
    # Layer
    elif param_type == pya.PCellParameterDeclaration.TypeLayer:
        
        def str_to_LayerInfo(string):
            '''Expecting format "layer_num/datatype_num", e.g. "1/0"'''
            # Check in case it was already pya.LayerInfo:
            if isinstance(string, pya.LayerInfo): return string
            
            # Convert string specification to LayerInfo
            parts = string.split('/')
            if len(parts) != 2:
                raise ValueError(f"Invalid layer format: '{string}'. Expected 'layer_num/datatype_num'.")
            try:
                layer_num = int(parts[0])
                datatype_num = int(parts[1])
            except ValueError as e:
                e.add_note(f"Invalid layer format: '{string}'. Expected 'layer_num/datatype_num'.")
                raise 
            return pya.LayerInfo(layer_num, datatype_num)
        
        return str_to_LayerInfo
        
    else: # For complex types, return as-is and hope for the best
        warnings.warn(f"Unclear how to convert a string to type {PARAM_TYPES[param_type]} "
                      f"in get_converter(param_type).")
        return lambda s: s

def is_valid_param_type(type_code:int):
    '''Returns True if the type_code is a valid type for a Klayout PCell parameter, False otherwise.
    
    Valid type codes are pya.PCellParameterDeclaration.TypeInt, pya.PCellParameterDeclaration.TypeDouble,
    pya.PCellParameterDeclaration.TypeString, pya.PCellParameterDeclaration.TypeLayer, etc.
    '''
    
    return type_code in PARAM_TYPES.keys()

def is_numeric_param_type(type_code:int):
    '''Return True if the type_code is pya.PCellParameterDeclaration.TypeDouble or pya.PCellParameterDeclaration.TypeInt'''
    return PARAM_TYPES.get(type_code) in ('int', 'double')

# {pya param type code: string type name}
PARAM_TYPES = {pya.PCellParameterDeclaration.TypeInt: 'int', 
               pya.PCellParameterDeclaration.TypeDouble: 'double',
               pya.PCellParameterDeclaration.TypeString: 'string', 
               pya.PCellParameterDeclaration.TypeLayer: 'LayerInfo', 
               pya.PCellParameterDeclaration.TypeBoolean: 'bool', 
               pya.PCellParameterDeclaration.TypeCallback: 'Callback', 
               pya.PCellParameterDeclaration.TypeList: 'list', 
               pya.PCellParameterDeclaration.TypeNone: 'None', 
               pya.PCellParameterDeclaration.TypeShape: 'Shape'}


if __name__ == '__main__':
    # Allows me to get around Klayout's caching behavior during development by reloading this module when I run it, 
    # so that I can test edits to this module without needing to restart Klayout.
    import importlib
    import sys
    if 'pya_helpers' in sys.modules: # Reload this module if it's already imported
        importlib.reload(sys.modules['pya_helpers'])
        print('Reloaded python module: pya_helpers')