# Recreating ParamSweep as a subclass of Wrapper, because the current implentation is > 1200 lines in one file.
# As of 6-12-2026, new features will be added here, not to ParamSweep.

import pya
from datetime import datetime
import traceback
import ast
import re
import numpy as np

from pya_helpers import create_text, get_bbox_point, as_point, get_converter, is_numeric_param_type, PARAM_TYPES
from general_helpers import safe_eval, parse_range, UserInputError, first_valid
from DependencyGraph import DependencyGraph
from pcell_wrapper import Wrapper

def custom_sweep_pcell(source_pcell_name:str, lib_name:str, use_existing:bool=False) -> pya.PCellDeclarationHelper:
    '''Defines a custom PCell that wraps the given target PCell. The custom PCell helps the user create a parametric 
    sweep of parameters in the underlying PCell as an array of labeled variations. 
    
    Exposes the parameters of the underlying PCell, with added array and labeling functionality.
-    source_pcell_name: The name of the PCell to create this Sweep wrapper around.  
-    lib_name: The name of the library containing the target pcell. 
-    use_existing: If true, will search the currently active layout for an existing cell with the given target cell name. This cell will define the default parameter vaules for the wrapper PCell.
    '''
        
    class Sweep(Wrapper):
        """
        Wrapper for PCells that creates an array of labeled variations of the underlying PCell (a parametric sweep).
        
        User can define a row sweep and a column sweep. A sweep can each be defined using any one parameter of the underlying PCell. 
        params that are not explicitly swept can be given as expressions of the swept parameters
        """ 
        
        def __init__(self):
            try: 
                print(f'Called {source_pcell_name}_Sweep.__init__()')
                # Initialize Wrapper: finds the underlying PCell declaration and its parameters
                super().__init__(source_pcell_name, lib_name, expose_params=False)
                
                # Each value in evaluated_params should be stored in a np.ndarry whose shape indicates whether it is a row sweep, col sweep, matrix, or scalar:
                self.evaluated_params = {} # {param_name: value(s)_evaluated_in_the_correct_type}, values stored as np.ndarray
                self._expr_param_types = {} # {param_name: required type code} for params whose values may be given as expressions
                self.literal_params = {} # {param_name: scalar values}
                self.row_param_name = '' # will hold param_name that row sweep is defined with
                self.col_param_name = '' # will hold param_name that _col_sweep is defined with
                self._dependency_graph = DependencyGraph() # tracks which params depend on which
                self.n_rows = self.n_cols = 1
                
                # Collect warnings (Wrapper class already defines self.__errors and display_error_geom for error reporting)
                self.__warnings = [] # String warnings to user
                
                # I added "_" before every parameter name belonging to the wrapper PCell to reduce the risk that any underlying PCell params get overriden.
                                
                self.safe_defaults = {'_row_pad': 100.0,
                                      '_col_pad': 100.0,
                                      '_label_height': 30.0}
                
                # Use source parameters come up with illustrative defaults for _row_sweep, _col_sweep, _format_str:
                row_sweep, col_sweep, format_str = self._illustrative_defaults()
                
                # Sweep Array Configuration 
                self.param("__sweep_header", self.TypeNone, " Sweep Configuration ".center(32, '═')) # Just holds the section header in the GUI.
                self.param("_row_sweep", self.TypeString, "Define Row Sweep", default=row_sweep) # sep_GD: 1, 2, 3
                self.param("_col_sweep", self.TypeString, "Define Col Sweep", default=col_sweep) # gate_len: 0.5, 1, 2
                self.param("_row_pad", self.TypeString, "Row Padding (µm)", default    = str(self.safe_defaults['_row_pad']))
                self.param("_col_pad", self.TypeString, "Column Padding (µm)", default = str(self.safe_defaults['_col_pad']))

                # Labeling
                self.param("__label_header", self.TypeNone, " Labeling ".center(32, '═')) # Just holds the section header in the GUI.
                self.param("_format_str", self.TypeString, "Label Format", default=format_str) 
                self.param("_l_label", self.TypeLayer, "Label Text Layer", default=pya.LayerInfo(1, 0))
                self.param("_label_height", self.TypeString, "Label Height (µm)", default = str(self.safe_defaults['_label_height']))
                self.param("_label_rot", self.TypeInt, "Label Rotation", default=0, choices=[('0°', 0), ('90°', 1),  ('180°', 2), ('270°', 3)])
                self.param("_label_x", self.TypeString, "Label X Offset (µm)", default='0.0')
                self.param("_label_y", self.TypeString, "Label Y Offset (µm)", default='0.0')
                self.__label_anchor_choices = ["Top Left", "Top Right", "Bottom Left", "Bottom Right", "Top Center", "Bottom Center", "Center Right", "Center Left"]
                self.param("_label_anchor", self.TypeString, f"Label Anchor Point on {source_pcell_name}'s BBox", default="Top Left", 
                           choices=list(zip(self.__label_anchor_choices, self.__label_anchor_choices))) # choices = [(description, value), ...]
                
                # These param can accept expressions.
                # Record that they need to be evaluated to TypeDouble:
                for param_name in ('_row_pad', '_col_pad', '_label_height', '_label_x', '_label_y'):
                    self._expr_param_types[param_name] = self.TypeDouble
                
                # Underlying PCell parameters 
                self.expose_src_params()
                
                # ============= Duplicates Array ============= 
                self.param("__dup_header", self.TypeNone, " Duplicates Array ".center(32, '═')) # Just holds the section header in the GUI.
                # self.param("__dup_desc", self.TypeNone, "WIDTH and HEIGHT are optional keywords that represent the dimensions "
                #            "of one instance of the underlying PCELL once drawn.") # Holds descriptive text in the GUI.
                
                # TODO: Allow different numbers for rows and columns in the duplicates array across variants
                
                # Parameters to define array of duplicates
                self.param("_n_rows_dup", self.TypeInt, "# of Rows for Duplicates Array", default=3) 
                self.param("_n_cols_dup", self.TypeInt, "# of Columns for Duplicates Array", default=3)
                self.param("_row_pad_dup", self.TypeString, "Row Pad (µm), may be negative", default="10")
                self.param("_col_pad_dup", self.TypeString, "Column Pad (µm), may be negative", default="10")
                self.param("_stagger", self.TypeString, "Stagger (µm), a Δx applied to every second row", default="0")
            
                # These param can accept expressions.
                # Record that they need to be evaluated to TypeDouble:
                for param_name in ('_row_pad_dup', '_col_pad_dup', '_stagger'):
                    self._expr_param_types[param_name] = self.TypeDouble
                    
                
                # For Debugging:
                # Expression parameters are currently supported for numerical types that 
                # are not set with a drop down menu.
                # At this point, self._expr_param_types should contain the name and desired type 
                # for any such parameters defined in the underlying PCell and the wrapper PCell.
                print(f'{self._expr_param_types=}')
                
                # Messaging the user 
                self.param("_msg", self.TypeString, "Messages:", default="", readonly=True) # For errors and warnings
                
                # TODO: USE VERSION numbers to avoid breaking existing layouts!!
                # Version:
                self.param("_version", self.TypeString, "Version:", default="1.0.0", readonly=True, hidden=True) # Aids with backwards compatibility
                
                # Finished!
                print(f'Initialized an instance of {source_pcell_name}_Sweep() at {datetime.now()}')
                
            except Exception as e:
                print(f"Error in {source_pcell_name}_Sweep __init__: \n{traceback.format_exc()}")
                             
        def coerce_parameters_impl(self):
            """
            Called before display_text_impl and produce_impl.
            """
            # TODO: Finish implementing error messages to the user for bad input in GUI window?
            print(f'Called {source_pcell_name}_Sweep.coerce_parameters_impl()')
           
            # Clear whenever restarting from coerce_parameters_imp:
            self.evaluated_params = {}
            self.__errors = [] # Collect errors and warnings
            self.__warnings = []
            self._msg = ''
            
            try:
                # Parse the row and column sweep specifications into {param_name: [values]}
                self.parse_and_validate_sweeps()
                
                # Store literal params for convenient identification and access:
                self.literal_params = {p: getattr(self, p) for p in (self.src_params.keys() - self.expr_param_names())}
                
                # Evaluate expression parameters
                self.eval_params()
                
                # Make sure that _row_pad is either scalar or only depends on the row sweep.
                # Same for _col_pad.
                self.validate_row_col_pads()
                
                # Check if the label _format_str references valid parameters 
                # from the underlying PCell, and raise ValueError if it doesn't.
                self.validate_label_fstring()
                
                # Ensure that the number of rows and columns in the duplicates array are each >= 1:
                self._n_rows_dup = max(1, self._n_rows_dup)
                self._n_cols_dup = max(1, self._n_cols_dup)

            except Exception as e:
                self.__errors.append(e)
            
            try:     
                # Show any errors and warnings accumulated during the function calls:
                if self.__errors:
                    # Print all errors to the console
                    for err in self.__errors:
                        print(f"Error in {source_pcell_name}_Sweep coerce_parameters_impl:")
                        traceback.print_exception(err)
                    
                    # Add the errors to self._msg, so the user can see them in the GUI
                    self._msg = 'ERRORS:\n  • ' + \
                                '\n  • '.join(map(str, self.__errors)) + '\n'
                
                # Add any warnings to self._msg, so the user can see them in the GUI             
                if self.__warnings:
                    self._msg += 'Warnings:\n  • ' + \
                                '\n  • '.join(self.__warnings)
            
            except Exception as e:
                print(f"Error in {source_pcell_name}_Sweep coerce_parameters_impl, when trying to print other errors:")
                traceback.print_exception(e)
      
        def produce_impl(self):
            """
            Implementation of the PCell interface: generates the layouts.
            
            Accounts for bounding boxes so that the instances in the sweep don't overlap.
            self._row_pad determines the padding between rows. 
            self._col_pad sets the minimum padding between columns. If something in a row is wide, 
            it shifts the entire next column over to accommodate it.
            """
            print(f'{source_pcell_name}_ParamSweep produce_impl at {datetime.now()}')
            
            dbu = self.layout.dbu
            
            try:

                # If there are errors, show them instead of generating the geometery
                if self.__errors: raise Exception("Prior Errors. Cannot generate geometry.")
                    
                # =========================== Generate Geometery ===========================
                             
                # If no sweep defined, this will just create a single instance of the underlying PCell with the current parameters.
                
                # Create Parametric Sweep of underlying PCell:
                x_pos = 0
                for i in range(self.n_cols):                    
                    y_pos = 0
                    max_x = 0 # Save the x coordinate of the widest inserted instance.
                    
                    for j in range(self.n_rows):
                        # Create parameter set for this variation under the row and column sweep:
                        params = self.params_at_index(j, i) # dict of {param_name: value}
                        
                        # Insert the labeled geometry for this parameter set.
                        inst = self.insert_labeled_variant(
                                    params, 
                                    pya.Trans(x_pos, y_pos), 
                                    align='UL',
                                    label_offset = as_point((self.get_value('_label_x', j, i), 
                                                             self.get_value('_label_y', j, i)), scale_unit=dbu),
                                    text_height = self.get_value('_label_height', j, i),
                                    rows = self._n_rows_dup, # For array of duplicates
                                    cols = self._n_cols_dup,
                                    row_pad = self.get_value('_row_pad_dup', j, i),
                                    col_pad = self.get_value('_col_pad_dup', j, i),
                                    stagger = self.get_value('_stagger', j, i))
                        
                        row_pad = round( self.get_value('_row_pad', j, 0) / dbu )                       
                        # Update y_pos and x_pos based on the bbox:
                        y_pos = inst.bbox().bottom - row_pad
                    
                        # Update max_x as needed:
                        max_x = max( max_x, inst.bbox().right )

                    col_pad = round( self.get_value('_col_pad', 0, i) / dbu )
                    # Update y_pos
                    x_pos = max_x + col_pad
                
                print(f'produce_impl finished for {source_pcell_name}_ParamSweep at {datetime.now()}')
                
            except Exception as e:
                # Print errors to the console and display them as text geometry.
                # If a PCell function lets an error reach Klayout's caller, 
                # and the user saves the .gds file with the error it may result in file corruption.
                print(f"produce_impl error error: \n{traceback.format_exc()}")
                self.__errors.append(e)
                 
                try:
                    # Display errors as text geometry
                    self.display_error_geom(self.__errors)
                except Exception:
                    print(f"Error when displaying error geometry: \n{traceback.format_exc()}")
                    # Insert a default shape to prevent empty cell
                    self.cell.shapes(self.layout.layer(999, 0)).insert(pya.Box(0, 0, 100/dbu, 100/dbu)) # Layer 999 is for error geometry

        def display_text_impl(self):
            """
            PCell interface implementation
            """
            if self.__errors:
                    text = f'{source_pcell_name}_ParamSweep ({len(self.__errors)} error(s) - check console")'
                    print(f'{source_pcell_name}_ParamSweep instance display_text called: ' + text)
                    return text
            
            # If there are no errors:
            try: 
                text = f'{source_pcell_name}_ParamSweep({self.n_rows}x{self.n_cols})'
                print(f'{source_pcell_name}_ParamSweep instance display_text called: ' + text)

            except Exception as e:
                print(f"Error in display_text_impl: \n{traceback.format_exc()}")
                text = f'{source_pcell_name}_ParamSweep (?)'

            return text
                
        def expose_src_params(self):
            '''Exposes the parameters of the underlying PCell in the GUI by copying them into this wrapper PCell.
            
            To allow for expressions, converts the input type and default value to TypeString for numerical parameters that are not set with a drop down menu.
            '''
            self.param("__params_header", self.TypeNone, f" {source_pcell_name} ".center(32, '═')) # Just holds the section header in the GUI.
                
            # Expose parameters of the underlying PCell for user input
            #    i.e. copy over each parameter in the underlying PCell 
            #    by defining a parameter with the same attributes in this wrapper PCell.
            
            for param_decl in self.src_pcell_decl.get_parameters():
                # TODO Implement this?
                # # If we were able to get actual parameter values from an existing cell instance in the layout, 
                # # use those as the defaults in the wrapper PCell, so that the initial generated layout will match the existing cell instance. If not, just use the default values from the underlying PCell.
                # if self.param_values:
                #     param_decl.default = self.param_values.get(param_decl.name) 
                    
                    
                # Allow for expressions for numerical parameters that are not set with a drop down menu:
                # -> the input type and default value must be changed to TypeString
                has_drop_down = len(param_decl.choice_values()) > 0
                type_code = param_decl.type
                default = param_decl.default
                if is_numeric_param_type(param_decl.type) and not has_drop_down:
                    type_code = self.TypeString
                    default = str(default)
                    # Store this param's name in a list of parameters which will need evaluating.
                    self._expr_param_types[param_decl.name] = param_decl.type
                
                # Copy parameter to this wrapper PCell
                self._copy_param(param_decl, default=default, type_code=type_code)  # also adds parameter declaration to self.src_params
                    
            print(f"Copied parameters into '{source_pcell_name}_Sweep wrapper: {list(self.src_params.keys())}")
           
        def parse_and_validate_sweeps(self):
            '''Parse the row and column sweep specifications into param_name and values.
            
            Update self.row_param_name, self.col_param_name, self.evaluated_params, self.n_rows, and self.n_cols accordingly
            Store descriptive errors on failure in self.__errors, and store warnings in self.__warnings.'''
            # Reset. Store previously swept param names:
            prev_row_param, prev_col_param = self.row_param_name, self.col_param_name
            self.row_param_name = self.col_param_name = ''
            self.n_rows = self.n_cols = 1
            
            # Row Sweep
            if self._row_sweep:
                try: 
                    # Try to parse 
                    param_name, values = self._parse_sweep(self._row_sweep) # Performs validation and parsing
                    
                except UserInputError as e:
                    # Failed to parse:
                    self._row_sweep = e.annotated_input # Annotate row sweep with hints to the user
                    self.__errors.append(e)
                    self.n_rows = 0
                    
                else:
                    # Successful parse!
                    self.row_param_name = param_name
                    self.n_rows = len(values)
                    print(f'Parsed row sweep: {param_name} = ', values)
                    # Clear up any left over annotations:
                    self._row_sweep = re.sub('[?!]{2,}', '', self._row_sweep)
                    # Store parsed result with shape (n_rows, 1 column) to indicate it's a row sweep:
                    self.evaluated_params[param_name] = np.array(values)[:, np.newaxis] 
                    print(f'self.evaluated_params[{param_name}] = {np.array(values)[:, np.newaxis]}')
                    
            # Col Sweep
            if self._col_sweep:
                try:
                    # Try to parse 
                    param_name, values = self._parse_sweep(self._col_sweep) # Performs validation and parsing
                    
                except UserInputError as e:
                    # Failed to parse:
                    self._col_sweep = e.annotated_input # Annotate col sweep with hints to the user
                    self.__errors.append(e)
                    self.n_cols = 0
                    
                else: 
                    # Successful parse!
                    self.col_param_name = param_name
                    self.n_cols = len(values)
                    print(f'Parsed col sweep: {param_name} = ', values)
                    # Clear up any left over annotations:
                    self._col_sweep = re.sub('[?!]{2,}', '', self._col_sweep)
                    # Store parsed result with shape (1 row, n_cols) to indicate it's a col sweep:
                    self.evaluated_params[param_name] = np.array(values)[np.newaxis, :] 
                    print(f'self.evaluated_params[{param_name}] = {np.array(values)[:, np.newaxis]}')

                        
            # Check, because you can't control the same parameter through both row and column sweep:
            if self.row_param_name and self.row_param_name == self.col_param_name:
                # Annotate both _row_sweep and _col_sweep with hints to the user
                self._col_sweep = self._col_sweep.replace(self.col_param_name, f'{self.col_param_name}!!')
                self._row_sweep = self._row_sweep.replace(self.row_param_name, f'{self.row_param_name}!!')
                self.__errors.append(ValueError(f"Parameter '{self.col_param_name}' cannot be swept over in both row and column sweeps."))
                self.n_rows = self.n_cols = 0
                return
            
            # Update GUI on successful parse. 
            # Add hints to the user indicating when parameter(s) in the underlying 
            # PCell section of GUI are being controlled by row and col sweep.
            if self.row_param_name:
                # A parameter is controlled through the row sweep.
                # Make it say that in the GUI if possible.
                if isinstance(getattr(self, self.row_param_name), str): # It's a string, so it can be replaced with a message:
                    setattr(self, self.row_param_name, 'Set by Row Sweep.')
                else: # It's not TypeString, so the value will have to be left and ignored
                    self.__warnings.append(f'Note: {self.row_param_name} is overridden by row sweep.')
           
            if self.col_param_name:
                # A parameter is controlled through the col sweep.
                # Make it say that in the GUI if possible.
                if isinstance(getattr(self, self.col_param_name), str): # It's a string, so it can be replaced with a message:
                    setattr(self, self.col_param_name, 'Set by Col Sweep.')
                else: # It's not TypeString, so the value will have to be left and ignored
                    self.__warnings.append(f'Note: {self.col_param_name} is overridden by col sweep.')
                    
            # If a sweep no longer controls a given parameter, that parameter needs to set with 
            # a fixed value again (instead of "Set by ___ Sweep"). Use the default.
            for prev, new in ((prev_row_param, self.row_param_name), (prev_col_param, self.col_param_name)):
                if not prev:
                    continue
                prev_was_string = isinstance(getattr(self, prev), str)
                changed_sweep = prev != new
                if changed_sweep and prev_was_string:
                    setattr(self, prev, str(self.src_params[prev].default))

        def validate_row_col_pads(self):
            ''' Make sure that _row_pad is either scalar or only depends on the row sweep.
                Same for _col_pad.'''
            self.evaluated_params['_row_pad'] = row_pad = np.asarray(self.evaluated_params['_row_pad'])
            self.evaluated_params['_col_pad'] = col_pad = np.asarray(self.evaluated_params['_col_pad'])
            
             # Make sure that row pad is either scalar or depends only on the row sweep.
            if row_pad.size != 1 and row_pad.shape != (self.n_rows, 1):
                    # Set row pad to a valid scalar instead
                    row_pad = first_valid(self.get_value('_row_pad'), self.safe_defaults['_row_pad'])
                    self.evaluated_params['_row_pad'] = np.asarray(row_pad)
                    setattr(self, '_row_pad', str(row_pad)) # Reset in GUI too.
                    self.__warnings.append("Row Pad must be either scalar or be the same shape as row sweep. "
                                            f"Reseting to {row_pad} um.")
              
            # Make sure that col pad is either scalar or depends only on the col sweep.      
            if col_pad.size != 1 and col_pad.shape != (1, self.n_cols):
                    # Set col pad to a valid scalar instead
                    col_pad = first_valid(self.get_value('_col_pad'), self.safe_defaults['_col_pad'])
                    self.evaluated_params['_col_pad'] = np.asarray(col_pad)
                    setattr(self, '_row_pad', str(row_pad)) # Reset in GUI too.
                    self.__warnings.append("Col Pad must be either scalar or be the same shape as col sweep. "
                                            f"Reseting to {col_pad} um.")

        def validate_label_fstring(self):
            '''
            Check if the label _format_str references valid parameters 
            from the underlying PCell, and raise ValueError if it doesn't.
            '''
            validator = self.NoteMissingKeys(self.src_params.keys())
            self._format_str = self._format_str.format_map(validator)
            if validator.missing_keys: # The set of keys that were referenced in _format_str but not found in the underlying PCell parameters. Warn the user about these.
                raise ValueError(f"Label format string references parameters that are not in the underlying PCell: {validator.missing_keys}. " +
                                    f"Invalid names are marked with '??' in the label text.")
 
        class SoftReplace(dict):
            '''Helper class for soft replacement in a format string,
            so missing keys are left in the format string with '??' rather than throwing an error.'''
            def __missing__(self, key):
                print(f"Warning: parameter '{key}' not found for labeling. Leaving as is in the label text with '??'.")
                return '{' + key + '??}'
            
            def __getitem__(self, key):
                # Ignore '??' or '!!' annotations when checking key validity
                return super().__getitem__(key.rstrip('?!'))

        class NoteMissingKeys(dict):
            '''Helper class records missing keys, so that I can 
            warn the user about them when verifying a format string.
            Does not replace keys with values, just records which keys are missing and adds '??'
            to the key in the format string for missing keys.'''
            def __init__(self, valid_keys):
                d = {key: '{' + key + '}' for key in valid_keys}
                super().__init__(d)
                self.missing_keys = set() 
                
            def __getitem__(self, key):
                # Ignore '??' or '!!' annotations when checking key validity, and
                # prevent them from piling on if the same missing key is referenced multiple times:
                return super().__getitem__(key.rstrip('?!'))
        
            def __missing__(self, key):
                self.missing_keys.add(key)
                return '{' + key + '??}'

        def expr_param_names(self, search=False):
            '''Getter for the names of parameters which need to be evaluated as expressions.
            Swept parameters are excluded, as they are already controlled by row or col sweep.
            
            If *search*: check the src PCell params for any expression params that are 
            missing from either self._expr_param_types. If a param holds a value of type str,
            and the required type is a string, add it to self._expr_param_types and 
            this function's return value. This allows a param from the underlying PCelll 
            to be added to the dict of expression params just by declaring it as 
            TypeString in the ParamSweep.
            '''
            # Optional search: allows a param from the underlying PCelll 
            # to be added to the dict of expression params just by declaring it 
            # as TypeString in the ParamSweep
            if search: 
                # params expected to be literal:
                literal_params = self.src_params.keys() - self._expr_param_types.keys()
                for param_name in literal_params:
                    required_type = self.src_params[param_name].type
                    current_value = getattr(self, param_name)
                    # If there is a string value for this param, and the required type is not TypeString,
                    # it must be meant as an expression param.
                    if current_value and required_type is not self.TypeString and isinstance(current_value, str):
                        # This param is actually an expression param!
                        print(f'Warning: {param_name} is being implicitly interpreted as an expression, to type {PARAM_TYPES[required_type]}')
                        print(f'{repr(getattr(self, param_name))=}')
                        self._expr_param_types[param_name] = required_type
            
            # Params to evaluate (don't let the swept parameters be overwritten):
            #                  _expr_param_types.keys() includes all parameters that may be given as expressions
            expr_params = self._expr_param_types.keys() - {self.row_param_name, self.col_param_name}
            print(f'{expr_params=}')
            return expr_params
        
        def eval_params(self):
            '''Evaluate expression parameters.
            
            Validate syntax.
            Parse expressions into dependencies
            Determine evaluation order, check that it is acyclic.
            Fill in self.evaluated_params.
            
            Any errors are added to self.__errors
            '''
            # Reset dependency graph
            self._dependency_graph = DependencyGraph()
            # Params to evaluate 
            expr_params = self.expr_param_names()
            
            # Identify dependencies
            for param_name in expr_params:
                # Expression params must be string type!
                if not isinstance(getattr(self, param_name), str):
                    raise RuntimeError(f'{param_name} is expected to be a string type expression, '
                          f'but received {type(getattr(self, param_name))} instead: '
                          f'{repr(getattr(self, param_name))}'
                         )
                    
                expr = self.get_expr(param_name)
                deps = self._parse_dependencies(expr)
                self._dependency_graph.add_dependency(param_name, deps)
                
            # Determine evaluation order and check that it is acyclic.
            eval_order, cycle = \
                self._dependency_graph.topological_sort(fail_if_cycle=False)
                
            if cycle:
                # Message the user with annotations and errors,
                # but still go on to evaluate the other parameters
                self.__errors.append(ValueError(
                    'Cyclic dependencies found among params! Check the expressions:\n'
                    '\n'.join([f"{p} depends on: {', '.join(deps)}" \
                              for p, deps in cycle.items()])))
                # Annotate each param that's part of a cycle:
                for p in cycle.keys(): # Show "Cyclic Dependency" as the result, annotating the user's input box
                    setattr(self, p, f'{self.get_expr(param_name)} = Cyclic Dependency Detected!!')
                
            
            # Evaluate parameters.
            for name in eval_order:
                
                # First check if it's an expression parameter in need of evaluation,
                # or just some other name
                if name not in expr_params:
                    continue
                
                # Get user input and strip any " = parsed results" annotations
                expr = self.get_expr(name)
                # Type to convert to:
                required_type = self._expr_param_types[name]
                # Converter function that works for string literals
                convert = get_converter(required_type)
                
                # See if it's just a string value by trying a basic conversion
                try:
                    value = convert(expr) # Evaluate from string to the required type.
                    
                except Exception: 
                    pass # It needs to be parsed as an expression.
                
                else:
                    self.evaluated_params[name] = np.asarray(value)
                    continue # Success! - Continue the loop to next param.
                
                # ===============================================
                # Parse expression and annotate the GUI input box with the result.
                
                # TODO allow expressions for boolean or string 
                
                # Expressions can involve any other parameters, using one with the wrong type
                # will result in a relevant error.
                context = self.literal_params | self.evaluated_params
                # Add pi to the context if it's a numeric type:
                if is_numeric_param_type(required_type): 
                    context = {'pi': np.pi} | context
                
                # Attempt to evaluate expr, 
                # and annotate the content in the GUI input box to show the result
                try:
                    value = np.asarray(safe_eval(expr, context))
                    
                except Exception as e:
                    # Annotate the string in the input box to show the error
                    setattr(self, name, expr + f' = {e}')
                    self.__errors.append(ValueError(f'Failure to evaulate {name}: {expr} = {e}'))
                    
                else:
                    # Store evaluated result,
                    # Converting from float to int if needed:
                    if required_type == self.TypeInt:
                        value = value.astype(int)

                    self.evaluated_params[name] = value
                    # Annotate the string in the input box to show how's interpreted
                    setattr(self, name, expr + f' = {value}')
             
        def get_expr(self, param_name):
            '''Gives the expression associated with the given param_name.
            If the param is one that is allowed to be given as an expression, 
            get user input and try to strip any " = parsed results" annotations. 
            If this param can't associated with an expression, raise ValueError.
            '''
            # Check that it's actually one of the params that can 
            # have an expression as input. 
            # Is it in the dict of {param_name: type to evaulate to}?
            if param_name in self._expr_param_types.keys():
                return self._strip_annotation(
                        getattr(self, param_name))
            else:
                raise ValueError(f"{param_name} doesn't have an associated expression")
            
        def _parse_dependencies(self, expr):
            """Extract variable names from expression.
            Returns a set containing variable names.
            If it fails to parse, returns an empty set."""            
            variables = set()
            
            try:
                tree = ast.parse(expr, mode='eval')
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Name):
                        variables.add(node.id)
            except:
                pass
            
            return variables
     
        def _strip_annotation(self, input:str):
            '''
            Strips any " = parsed results" annotation that may have been added 
            in the user input box to show the user how their expression is interpreted.
            
            Given input the form "expr = result", gives just the expression.
            If input is already in the form "expr", returns as is. 
            
            '''
            # # Strip everything after the last "=", if "=" is found:
            # match = re.match(r'^(.*?)=[^=]+$', input)
            
            # If "=" is found, the "=" is not part of "<=", ">=", or "==",
            # and something comes after the "="
            # assume that's the annotation and strip it. Otherwise,
            # return the input as is.
            
            match = re.match(r'^(.+?)\s*(?<![<>=])=\s*[^=]', input)
            if match:
                expr = match.group(1)
            else:
                expr = input
                
            return expr
        
        def _illustrative_defaults(self):
            '''Come up with illustrative defaults for _row_sweep, _col_sweep, _format_str'''
            # We'll use the first suitable parameters from the source PCell
            # It's easier to guess valid sweep values if the parameter is a numeric type.
            numeric_param_gen = (name for name in self.src_params if is_numeric_param_type(self.src_params[name].type))
            row_var = next(numeric_param_gen, '')
            col_var = next(numeric_param_gen, '')
            
            row_sweep = col_sweep = format_str = ''
            var = []
            
            if row_var:
                values = np.array([1, 2, 3]) * self.src_params[row_var].default
                row_sweep = f"{row_var}: {', '.join(map(str, values))}"
                
                var.append(f'{{{row_var}}}')
    
            if col_var:
                default = self.src_params[col_var].default
                col_sweep = f'{col_var}: {default}:{3*default}:{default}' # start:stop:step
                
                var.append(f'{{{col_var}}}')
            
            format_str = ', '.join(var) or 'Label'
            
            return row_sweep, col_sweep, format_str

        def params_at_index(self, row:int, col:int):
            '''Returns dict of all the params for this index as {param_name: value}'''            
            params = {}
            
            # For each source PCell parameter,
            # Get the appropriate value for the given index
            # If there was no value(s), use the default.
            for name in self.src_params.keys():
                    
                value = first_valid(self.get_value(name, row, col), 
                                    self.src_params[name].default)
                
                params[name] = value
                
            return params
        
        def get_value(self, param_name, row=0, col=0):
            '''
            Returns the parameter value at the given sweep index, or None if not found. 
            
            Search order is self.evaluated_params, then self.literal_params. 
            If row, col index is not given and it's a swept parameter, will give the first value from the sweep.
            '''
            def index_broadcasted(values, row, col):
                ''' Returns the parameter value requested by the given index, effectively broadcasting
                scalar or vector values for indexes row, col. Each swept value should be stored in a np.ndarray whose shape 
                indicates whether it is a row sweep (r, 1), col sweep (1, c), or matrix (r, c). Scalars can be an array-like
                with one element or just the value. 
                '''
                if values is None: return None
                
                # Make sure value(s) is an a np.ndarray and not empty
                values = np.asarray(values)
                if values.size == 0: return None      
    
                # Scalar
                if values.size == 1:
                    return values.item()
                
                # Swept Parameter
                elif len(values.shape) == 2:
                    n_rows, n_cols = values.shape
                    
                    col = 0 if n_cols == 1 else col # Row Swept
                    row = 0 if n_rows == 1 else row # Col Swept
                    
                    return values.item(row, col)
                    
                # Problem
                elif len(values.shape) == 1:
                    raise RuntimeError(f'No way to determine whether parameter {name} is meant to be swept over rows of columns! '
                                        'self.evaluated_params had a 1D vector of values instead of a 2D array with shape (r, 1), '
                                        '(1, c), or (r, c).')
                
                # Problem
                elif len(values.shape) > 2:
                    raise RuntimeError(f'Too many dimensions for parameter {name} in sweep! '
                                        f'self.evaluated_params had a {len(values.shape)}D array of values instead of a 2D array '
                                        'with shape (r, 1), (1, c), or (r, c).')
               
            value = first_valid(
                    index_broadcasted(self.evaluated_params.get(param_name), row, col),
                    self.literal_params.get(param_name)
                    )        
            return value
        
        def insert_labeled_variant(self, params, trans=pya.Trans(0, 0), align=None, label_offset=None, text_height=None,
                                   rows=None, cols=None, row_pad=None, col_pad=None, stagger=None):
            '''Inserts a labeled array of duplicates for a variant of the underlying PCell with the given parameters.

-           trans: pya.Trans If given, the transformation is applied after alignment
-           align: 'UR', 'UL', 'BR', 'BL', or 'C'. If given, aligns the specified corner of the instance's bbox to the origin.
-           label_offset: pya.Point or pya.Vector or (x, y) tuple. If given, used to offset the label position from the anchor position specified by *self._label_anchor*.

            Returns the instance from self.cell.insert.'''
            def insert_dup_array(labeled_variant, params):
                '''Inserts an array of duplicate cells for the variant described by params'''
                variant_cell = self.create_variant(params) # Creates variant of underlying PCell as a cell in the main layout:

                # Parameters for the duplicate array
                dbu = self.layout.dbu
                nonlocal rows, cols, row_pad, col_pad, stagger
                
                rows = self._n_rows_dup if rows is None else rows
                cols = self._n_cols_dup if cols is None else cols
                height = variant_cell.bbox().height()
                width = variant_cell.bbox().width()
                row_pad = (self.get_value('_row_pad_dup') if row_pad is None else row_pad) / dbu
                col_pad = (self.get_value('_col_pad_dup') if col_pad is None else col_pad) / dbu
                row_disp = -(height + row_pad)
                col_disp = width + col_pad
                stagger = (self.get_value('_stagger') if stagger is None else stagger) / dbu
                
                # Insert the variant cells for each row:
                for r in range(rows): # 0, 1, ..., n_rows-1
                    # Shift every second row by stagger
                    shift_x = stagger if r % 2 != 0 else 0
                    
                    # This places one row
                    labeled_variant.insert(pya.CellInstArray(variant_cell, pya.Trans(shift_x, r*row_disp),
                                                            pya.Vector(0, 0),
                                                            pya.Vector(col_disp, 0),
                                                            1, 
                                                            cols))
                    
            def add_label(labeled_variant, params):
                '''Add a label to the duplicates array in the cell labeled_variant.'''
                nonlocal label_offset, text_height
                label_offset = pya.Vector(0, 0) if label_offset is None else pya.Vector(as_point(label_offset))
                label_anchor = get_bbox_point(self._label_anchor, labeled_variant.bbox())
                text_center = label_anchor + label_offset
                text_height = self.get_value('_label_height') if text_height is None else text_height
                label = self.create_label(params, text_center, text_height)
                labeled_variant.shapes(self._l_label_layer).insert(label)
            
            # TODO: Make it possible to use an existing cell instance in the layout,
            # using *change_pcell_parameters* creating new instances through add_pcell_variant,
            # to preserve any manual edits to the cell instance.
            
            # Cell container for the label and the PCell variant
            labeled_variant = self.layout.create_cell(f"Labeled_{source_pcell_name}_Variant")
            
            # Add an array of duplicants for the variant cell
            insert_dup_array(labeled_variant, params)
                        
            # Add label for the variant
            add_label(labeled_variant, params)
            
            if align:            
                anchor = pya.Vector(get_bbox_point(align, labeled_variant.bbox()))
                trans.disp = trans.disp - anchor
            
            return self.cell.insert(pya.CellInstArray(labeled_variant, trans))
                        
        def create_label(self, params, text_pos, text_height) -> pya.Region:
            '''Creates and returns a text label for an variant in the sweep, as a pya.Region.
            
-           params: dict of {param_name: value} for the parameters of the underlying PCell instance that this label is annotating, used to fill in the _format_str for the label text
-           text_pos: where to place the center of the text bonding box (pya.Point, pya,Vector, or (x, y) tuple in dbu)
-           text_height: Text height in microns for the label
            
            Returns the text as a pya.Region of polygons.
            '''
            dbu = self.layout.dbu
            
            # Checking:
            text_pos = as_point(text_pos)
            
            # Parse format str with the given params
            #   Makes sure floats are displayed without trailing zeros, and with no more than 3 significant digits:
            formatted_params = self.__format_params(params)
            text = self._format_str.format_map(self.SoftReplace(formatted_params))
            
            # Create text as polygons
            text_region = create_text(text, text_height, dbu, 
                                      trans=pya.Trans(rot = self._label_rot), # 0, 1, 2, 3 rotation convention
                                      pos=text_pos) 
            
            return text_region
        
        def __format_params(self, params):  
            '''Returns a new dict where the values for the TypeDouble params are replaced with  f'{value:.3g}'.
            This is a likely formatting need, reducing the number of digits to making the label concise.'''
            # TODO: Temporary method. It would be better to allow format strings. 
            # Python 3.14 has a Template string object that would do the parsing for me
            # Trying to use str.format_map with format strings won't work in coerce_params_impl,
            # because I want to replace with the key names leaving the user's input as is if there are no issues.
            # {gate_len:d} would throw an error if I tried to replace with the string 'gate_len' instead of a number
            formatted = params.copy()
            for param_name, value in formatted.items():
                if self.src_params[param_name].type == pya.PCellParameterDeclaration.TypeDouble:
                    formatted[param_name] = f'{float(value):.3g}'
            return formatted
                
            # TODO: Allow for selection of text alignment (centered, left, etc), 
            # or make it depend on the choice of _label_anchor?

        def _parse_sweep(self, sweep_spec):
            '''Parses either *_row_sweep* or *_col_sweep* into parameter name and list of values to sweep over.
            
            Performs validation, and raises exceptions with descriptive error messages:
-           Checks that *sweep_spec* is in the correct format: param_name: value1, value2, ...
-           Check that the parameter it references actually exists in the underlying PCell.
-           Checks that the values can be parsed into the correct types for the underlying PCell parameter.
            
            Returns: (param_name, values_list) where param_name is the name of the parameter to sweep over, and 
            values_list is a list of the values to sweep over for that parameter.
            '''
            pattern = re.compile(r'''\s*([a-zA-Z_][a-zA-Z0-9_]*)[?!]*\s*: # (param name) followed by colon, ignoring any ?? or !! annotations 
                                                                          # that may have been added previously
                                 ((?:[^,]+,)*[^,]+)$''',  # (value1, value2, ...) at least one value, 
                                                          # separated by commas with optional whitespace.
                                 re.VERBOSE)
            
            match = pattern.match(sweep_spec)
            # Check that *sweep_spec* is in the correct format: param_name: value1, value2, ...
            if not match:
                raise ValueError(f"Sweep specification '{sweep_spec}' is not in the correct format. Should be 'param_name: value1, value2, ...'")
           
            # Check that the parameter it references actually exists in the underlying PCell.
            param_name = match.group(1)
            if param_name not in self.src_params:
                annotated_input = sweep_spec.replace(param_name, f'{param_name}??')
                raise UserInputError(annotated_input, 
                                     f"Sweep specification references parameter '{param_name}' "
                                     f"which does not exist in the underlying PCell '{source_pcell_name}'.",)
            
            # Parse values
            values_str = match.group(2)
            param_type = self.src_params[param_name].type
            try:
                # Attempt to convert the string values to the correct type for this parameter:
                values = self._parse_values_to_type(values_str, param_type)
            except UserInputError as e:
                # Annotate sweep_spec to hint the problem to the user
                e.annotated_input = sweep_spec.replace(values_str, e.annotated_input)
                e.add_note(f"Invalid value(s) in sweep specification '{sweep_spec}'.")
                raise
            
            # Succesful parse
            return param_name, values
        
        def _parse_values_to_type(self, values_str:str, param_type) -> list:
            '''Parse a comma-separated list of values, to a list of the specified type. 
            
            If the type is numeric, *values_str* may include colon-separated ranges, i.e. *start*:*stop*:*step* or *start*:*stop*.
            
            param_type: pya.PCellParameterDeclaration.TypeInt, pya.PCellParameterDeclaration.TypeDouble, pya.PCellParameterDeclaration.TypeString, pya.PCellParameterDeclaration.TypeLayer, etc.
            
            Returns a list [value, ...] of values in the specified type.
            '''
            def parse_value(s):
                '''Parse a string value into the desired type, and append to values.'''
                s = s.strip()
    
                if range_allowed and ':' in s: # Parse this value as a range
                    try:
                        # Parse the range string, and add on the values as strings
                        expanded_range = parse_range(s, PARAM_TYPES[param_type])
                        values.extend(expanded_range) 
                    except Exception as e: # Failed to parse as range
                        e.add_note(f'Failed to parse {s} as a numeric range.')
                        raise
                    
                else: # Convert string value to correct type and append.
                    values.append(convert_type(s))
                    
            values = [] # Will contain values in the specified type
            
            # Function that converts a string to the correct type.
            convert_type = get_converter(param_type)
            
            # If it's a numeric type (int or float), then ranges are allowed:
            range_allowed = is_numeric_param_type(param_type)
            
            # Iterate over the values_str, and parse each value
            for s in values_str.split(','):
                
                # Remove any annotations from previous runs
                if s.endswith('??') or s.endswith('!!'):
                    s = s[:-2]
                
                # Attempt to parse, and raise UserInputError with annotated values_str on failure
                try:
                    parse_value(s)
                except Exception as e:
                    # annotated version of values_str to indicate where the problem was
                    annotated = values_str.replace(s, f'{s}??')
                    raise UserInputError(annotated) from e
            
            # Successful parse!
            return values

    return Sweep