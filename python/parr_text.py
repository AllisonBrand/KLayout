import pya
from pya_helpers import move_box_to, create_text, add_label
from datetime import datetime
import traceback
import numpy as np

from pya_helpers import parse_range
  

class ParrText(pya.PCellDeclarationHelper):
  """
   Parameter array for text.
   Creates an array of text, where the text varies along rows and columns.
   User specifies a format string with two variables, e.g. 'Row Var: {r}, Col Var: {c}'.
   r and c are both a comma-separated list of values
   including colon-separated ranges, i.e. start:stop:step or start:stop.
   This controls the number of rows and columns, even if '{r}' or '{c}' is missing from the format string. 
   

   """  
  def __init__(self):
    """ Constructor: provides the PCell parameter definitions. """
    try: 

      super().__init__()
    
      # Declare parameters
      self.param("l", self.TypeLayer, "Layer", default=pya.LayerInfo(1, 0))
      self.param("format_str", self.TypeString, "Text Format String", default="{r}, {c}")
      self.param("row_var", self.TypeString, "Row Variable {r}\n" \
                 "a comma-separated list of values \n" \
                 "including colon-separated ranges, \n" \
                 "i.e. start:stop:step or start:stop.", 
                 default="0.5, 1:3, 7")
      self.param("col_var", self.TypeString, "Column Variable {c}\n" \
                 "format: same as row", 
                 default="A, B, C")
      self.param("row_spacing", self.TypeDouble, "Row Spacing (µm)", default=20.0)
      self.param("col_spacing", self.TypeDouble, "Col Spacing (µm)", default=100.0)
      self.param("text_height", self.TypeDouble, "Text Height (µm)", default=10)

      # Internal Variables: 

      self._parsed_row_vars = None
      self._parsed_col_vars = None

      # For debugging:
      self.__err_msg = ""  # store error messages to display in the layout if produce_impl fails, so that I can see them without needing to check the console output.

      # Cache for detecting changes
      self.__prev_row_var = None
      self.__prev_col_var = None
      

      print(f"Initialized an instance of ParrText() at {datetime.now()}")
    except Exception as e:
      print(f"Error in ParrText __init__: \n{traceback.format_exc()}")
      self.__err_msg = f"Error in ParrText __init__: {e}\n"
  
  def coerce_parameters_impl(self):
    """
    Called before display_text_impl and produce_impl.
    """
    try:
        # Ensure positive values
        if self.row_spacing < 0:
            self.row_spacing = 1
        if self.col_spacing < 0:
            self.col_spacing = 1
        if self.text_height <= 0:
            self.text_height = 2.0

        # Parse row_var and col_var as needed:
        # And clean up the whitespace in both (looks better and helps indicate how the string is being interpreted)
        if self.__prev_row_var != self.row_var:  # Check if row_var was updated
            # row_var has been changed. 
            self._parsed_row_vars = self._parse('row_var') # Parses row_var and cleans up the formatting
            self.__prev_row_var = self.row_var # Update to store new value
        
        if self.__prev_col_var != self.col_var: # Check if col_var was updated
            # col_var has been changed. 
            self._parsed_col_vars = self._parse('col_var') # Parses col_var and cleans up the formatting
            self.__prev_col_var = self.col_var # Update to store new value
        
        

    except Exception as e:
      print(f"Error in ParrText coerce_parameters_impl: \n{traceback.format_exc()}")
      self.__err_msg += f"Error in ParrText coerce_parameters_impl: {e}\n"


  def _parse(self, specifier:str, reformat:bool=True) -> list:
    """ Expand a var_str as a list of string values, and returns the list. 
    The var_str is specified by *specifier* as either 'row_var' or 'col_var'.

     *self.row_var* and *self.col_var* are both a comma-separated list of values, including colon-separated ranges, i.e. *start*:*stop*:*step* or *start*:*stop*.

     **Parameters**
    - specifier: 'row_var' or 'col_var'. If neither, will parse the given string instead, and ignore *reformat*.
    - reformat: Whether to reformat *row_var* or *col_var* in the process, so the whitespace is indicative of how the string was interpreted. 
     Ensures that there is a space after each comma and no space between elements of a range.

     
    Examples:
- 'A, B, C' -> ['A', 'B', 'C']
- '1:3:0.5' -> ['1.0', '1.5', '2.0', '2.5', '3.0']
- '0.5, 1:3, 7' -> ['0.5', '1', '2',  '3', '7']
     
    """
    if specifier.strip() == 'row_var':
       var_str = self.row_var
    elif specifier.strip() == 'col_var':
       var_str = self.col_var
    else: 
       var_str = specifier
       reformat = False

    # -------- Parse the var_str -------------
    parsed = []
    if reformat: # And clean up the var_str format if reformat is Truthy
        clean_var_str = ''

    for s in var_str.split(','):
        s = s.strip()
        if ':' in s:
            try:
               # Parse the range string, and add on the values as strings
               expanded_range = parse_range(s)
               parsed.extend(map(str, expanded_range))
               
               if reformat: # Successful parse, remove the white space to show it as one unit
                  s = rm_whitespace(s)
                  
            except Exception: # Faild to parse as range, just append as is
               parsed.append(s)
        else:
            parsed.append(s)
        
        if reformat: 
           clean_var_str += (f', {s}')

    if reformat and len(clean_var_str) > 2:
       clean_var_str = clean_var_str[2:] # Strip the leading ', '
       if specifier.strip() == 'row_var':
          self.row_var = clean_var_str
       elif specifier.strip() == 'col_var':
          self.col_var = clean_var_str

    return parsed


  def display_text_impl(self):
    """
    PCell interface implementation
    """
    try: 
      if '{r}' in self.format_str: 
         rows = self._parsed_row_vars
      else: rows = "'{r}' missing from format string: " + self.format_str
      if '{c}' in self.format_str: 
         cols = self._parsed_col_vars
      else: cols = "'{c}' missing from format string: " + self.format_str

      text = f'ParrText(Rows: {rows}, Cols: {cols})'
    except Exception as e:
      print(f"Error in display_text_impl: \n{traceback.format_exc()}")
      self.__err_msg += f'\n display_text_impl: {e}'
      text = f'ParrText (?)'
    
    if self.__err_msg:
        text += f'\nERRORS:\n {self.__err_msg}'

    print('ParrText instance display_text called: ' + text)

    return text
  

  
  def can_create_from_shape_impl(self):
    """
    PCell interface implementation
    """
    return False
  
  def parameters_from_shape_impl(self):
    """
    PCell interface implementation
    """
    pass
  
  def transformation_from_shape_impl(self):
    """
    PCell interface implementation
    """
    return pya.Trans()
    
  
  def produce_impl(self):
  
    """
    Implementation of the PCell interface: generates the layouts
    """
    try: 
        # Draw Text Array
        row_spacing = self.row_spacing / self.layout.dbu
        col_spacing = self.col_spacing / self.layout.dbu
        for i, r in enumerate(self._parsed_row_vars):
           row_text = self.format_str.replace('{r}', r)
           for j, c in enumerate(self._parsed_col_vars):
              text = row_text.replace('{c}', c)
              
              text_region = create_text(text, self.text_height, self.layout.dbu, 
                                        pos = (j*col_spacing, -i*row_spacing))
              
              self.cell.shapes(self.l_layer).insert(text_region)
        
        print(f"ParrText instance produce_impl finished at {datetime.now()}")
    except Exception as e:
      print(f"produce_impl error error: \n{traceback.format_exc()}")
      self.__err_msg += f"produce_impl error: {e}\n"
      # Return a default shape to prevent empty cell
      return pya.Box(0, 0, 100, 100)
    

def rm_whitespace(string):
   '''Returns the string with all whitespace removed.'''
   new_str = ''
   for char in string:
      if not char.isspace():
         new_str += char
    # string.translate(str.maketrans('','',remove=' \t\n\r\x0b\x0c'))
   return new_str
   

# TODO: auto-adjust row, col spacing in coerce to ensure that the text doesn't overlap.
# TODO: Use the minimum number of significant digits when displaying text, use 2, not 2.0
