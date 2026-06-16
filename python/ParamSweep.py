import pya
from datetime import datetime
import traceback
import ast
import operator
import re
import numpy as np
import warnings
# from string.templatelib import Interpolation, Template

# TODO: Better-looking display for evaluated row, col, matrix expressions

from pya_helpers import create_text, get_bbox_point, as_point, get_converter, is_valid_param_type, is_numeric_param_type, PARAM_TYPES
from general_helpers import parse_range, UserInputError, first_valid
from DependencyGraph import DependencyGraph
    
def custom_sweep_pcell(source_pcell_name:str, lib_name:str, use_existing:bool=False) -> pya.PCellDeclarationHelper:
    '''Defines a custom PCell that wraps the given target PCell. The custom PCell helps the user create a parametric 
    sweep of parameters in the underlying PCell as an array of labeled variations. 
    
    Exposes the parameters of the underlying PCell, with added array and labeling functionality.
-    source_pcell_name: The name of the PCell to create this ParamSweep wrapper around.  
-    lib_name: The name of the library containing the target pcell. 
-    use_existing: If true, will search the currently active layout for an existing cell with the given target cell name. This cell will define the default parameter vaules for the wrapper PCell.
    '''
        
    class ParamSweep(pya.PCellDeclarationHelper):
        """
        Wrapper for PCells that creates an array of labeled variations of the underlying PCell (a parametric sweep).
        
        User can define a row sweep and a column sweep. A sweep can each be defined using any one parameter of the underlying PCell. 
        params that are not explicitly swept can be given as expressions of the swept parameters
        """  # TODO Currently, only numeric params can be given as expressions, boolean expressions would be nice too.
        # Parameters that can be given as expressions must be made to accept TypeString, instead of the expected param type.
        # That means they lose KLayout's automatic type-checking and formatting. 
        # If the user defines a sweep with a param that is not exposed as TypeString, then I can't update the input box 
        # in the underlying PCell params section to say (for example) 'row_swept', and the value there will silently ignored.
        def __init__(self):  
            """ Constructor: provides the PCell parameter definitions. """
            try: 
                print(f'Called {source_pcell_name}_ParamSweep.__init__()')
                super().__init__()
                
                # Get the underlying PCell
                pcell_decl, lib = self._pcell_from_lib(source_pcell_name, lib_name)
                param_values = self._details_from_layout(source_pcell_name) if use_existing else None # TODO expand on and test use_existing features
                # Unfortunately, there is no way to get the library object from a PCell instance, 
                # so the user has to provide it even if they have an existing cell instance.
                
                # Internal Variables: 
                #   params that are not explicitly swept can be given as expressions using the swept parameters
                #   
                self.src_pcell_decl = pcell_decl  #  PCell declaration of the underlying (source) PCell
                self.src_lib = lib #  library object of the underlying PCell
                self.src_params = {} # will be filled with parameter declarations of the underlying PCell.
                # Each value in evaluated_params should be stored in a np.ndarry whose shape indicates whether it is a row sweep, col sweep, matrix, or scalar:
                self.evaluated_params = {} # {param_name: value(s)_evaluated_in_the_correct_type}, values stored as np.ndarray
                self._expr_param_types = {} # {param_name: required type code} for params whose values may be given as expressions
                self.literal_params = {} # {param_name: scalar values}
                self.row_param_name = '' # will hold param_name that row sweep is defined with
                self.col_param_name = '' # will hold param_name that _col_sweep is defined with
                self._dependency_graph = DependencyGraph() # tracks which params depend on which
                self.n_rows = self.n_cols = 1
                
                # Collect errors and warnings
                self.__errors = [] # Exception Objects
                self.__warnings = [] # String warnings to user

                # Cache for detecting changes
                self.__prev = None # TODO: actually use this?
                                
                # I added "_" before every paramter name to reduce the risk that any underlying PCell params get overriden.
                
                self.wrapper_defaults = {'_row_pad': 100.0,
                                         '_col_pad': 100.0,
                                         '_label_height': 30.0}
                
                # Sweep Array Configuration 
                self.param("__sweep_header", self.TypeNone, " Sweep Configuration ".center(32, '═')) # Just holds the section header in the GUI.
                self.param("_row_sweep", self.TypeString, "Define Row Sweep", default='') # sep_GD: 1, 2, 3
                self.param("_col_sweep", self.TypeString, "Define Col Sweep", default='') # gate_len: 0.5, 1, 2
                self.param("_row_pad", self.TypeString, "Row Padding (µm)", default    = str(self.wrapper_defaults['_row_pad']))
                self.param("_col_pad", self.TypeString, "Column Padding (µm)", default = str(self.wrapper_defaults['_col_pad']))

                # Labeling
                self.param("__label_header", self.TypeNone, " Labeling ".center(32, '═')) # Just holds the section header in the GUI.
                self.param("_format_str", self.TypeString, "Label Format", default="GS:{sep_SG}, G:{gate_len}, GD:{sep_GD}")
                self.param("_l_label", self.TypeLayer, "Label Text Layer", default=pya.LayerInfo(1, 0))
                self.param("_label_height", self.TypeString, "Label Height (µm)", default = str(self.wrapper_defaults['_label_height']))
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
                
                # ============= Underlying PCell parameters ============= 
                
                self.param("__params_header", self.TypeNone, f" {source_pcell_name} ".center(32, '═')) # Just holds the section header in the GUI.
                
                # Expose parameters of the underlying PCell for user input
                #    i.e. copy over each parameter in the underlying PCell 
                #    by defining a parameter with the same attributes in this wrapper PCell.
                
                for param_decl in pcell_decl.get_parameters():
                    
                    # If we were able to get actual parameter values from an existing cell instance in the layout, 
                    # use those as the defaults in the wrapper PCell, so that the initial generated layout will match the existing cell instance. If not, just use the default values from the underlying PCell.
                    if param_values:
                        param_decl.default = param_values.get(param_decl.name) 
                        
                    # Allow for expressions for numerical parameters that are not set with a drop down menu:
                    # - the input type and default value must be changed to TypeString
                    has_drop_down = len(param_decl.choice_values()) > 0
                    type_code = param_decl.type
                    default = None
                    if is_numeric_param_type(param_decl.type) and not has_drop_down:
                        type_code = self.TypeString
                        default = str(param_decl.default)
                        # Store this param's name in a list of parameters which will need evaluating.
                        self._expr_param_types[param_decl.name] = param_decl.type
                    
                    
                    # Copy parameter to this wrapper PCell
                    self.__copy_param(param_decl, default=default, type_code=type_code)  # also adds parameter declaration to self.src_params
                    
                print(f"Copied parameters into '{source_pcell_name}_ParamSweep wrapper: {list(self.src_params.keys())}")   
                print(f'{self._expr_param_types=}')
                
                # ============= Messaging the user ============= 
                self.param("_msg", self.TypeString, "Messages:", default="", readonly=True) # For errors and warnings
                
                print(f'Initialized an instance of {source_pcell_name}_ParamSweep() at {datetime.now()}')
            except Exception as e:
                print(f"Error in {source_pcell_name}_ParamSweep __init__: \n{traceback.format_exc()}")
        
        # TODO: Warnings if 
        # -  Label _format_str references scalar paramters.
        
        def coerce_parameters_impl(self):
            """
            Called before display_text_impl and produce_impl.
            """
            # TODO: Finish implementing error messages to the user for bad input in GUI window?
            print(f'Called {source_pcell_name}_ParamSweep.coerce_parameters_impl()')
           
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

            except Exception as e:
                self.__errors.append(e)
            
            try:     
                # Show any errors and warnings accumulated during the function calls:
                if self.__errors:
                    # Print all errors to the console
                    for err in self.__errors:
                        print(f"Error in {source_pcell_name}_ParamSweep coerce_parameters_impl:")
                        traceback.print_exception(err)
                    
                    # Add the errors to self._msg, so the user can see them in the GUI
                    self._msg = 'ERRORS:\n  • ' + \
                                '\n  • '.join(map(str, self.__errors)) + '\n'
                
                # Add any warnings to self._msg, so the user can see them in the GUI             
                if self.__warnings:
                    self._msg += 'Warnings:\n  • ' + \
                                '\n  • '.join(self.__warnings)
            
            except Exception as e:
                print(f"Error in {source_pcell_name}_ParamSweep coerce_parameters_impl, when trying to print other errors:")
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
                                    text_height = self.get_value('_label_height', j, i))
                        
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
                    self.display_error_geom()
                except Exception:
                    # Insert a default shape to prevent empty cell
                    self.cell.shapes(self.layout.layer(0, 0)).insert(pya.Box(0, 0, 100/dbu, 100/dbu))
                
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

        def validate_row_col_pads(self):
            ''' Make sure that _row_pad is either scalar or only depends on the row sweep.
                Same for _col_pad.'''
            self.evaluated_params['_row_pad'] = row_pad = np.asarray(self.evaluated_params['_row_pad'])
            self.evaluated_params['_col_pad'] = col_pad = np.asarray(self.evaluated_params['_col_pad'])
            
             # Check if row pad is either scalar or depends only on the row sweep.
            if row_pad.size != 1 and row_pad.shape != (self.n_rows, 1):
                    # Set row pad to a valid scalar instead
                    row_pad = first_valid(self.get_value('_row_pad'), self.wrapper_defaults['_row_pad'])
                    self.evaluated_params['_row_pad'] = np.asarray(row_pad)
                    setattr(self, '_row_pad', str(row_pad)) # Reset in GUI too.
                    self.__warnings.append("Row Pad must be either scalar or be the same shape as row sweep. "
                                            f"Reseting to {row_pad} um.")
              
            # Check if col pad is either scalar or depends only on the col sweep.      
            if col_pad.size != 1 and col_pad.shape != (1, self.n_cols):
                    # Set col pad to a valid scalar instead
                    col_pad = first_valid(self.get_value('_col_pad'), self.wrapper_defaults['_col_pad'])
                    self.evaluated_params['_col_pad'] = np.asarray(col_pad)
                    setattr(self, '_row_pad', str(row_pad)) # Reset in GUI too.
                    self.__warnings.append("Col Pad must be either scalar or be the same shape as col sweep. "
                                            f"Reseting to {col_pad} um.")

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
                deps = self._parse_expr_dependencies(expr)
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
                    value = np.asarray(self._safe_eval(expr, context))
                    
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
 
        def _parse_expr_dependencies(self, expr):
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
        
        def _safe_eval(self, expr, context, max_depth=100):
            """Safely evaluate mathematical expression with NumPy array support
                
                Args:
                    expr: Expression string
                    context: Dict of variables (can contain NumPy arrays or scalars)
                
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
                  
        def display_error_geom(self):
            ''' Generate text geometry showing the content of self.__errors'''
            # Written by Claude-4-5-sonnet, with minor modifications
            
            error_text = "ERRORS:\n  • " + "\n  • ".join(map(str, self.__errors))
        
            text_region = create_text(
                error_text,
                height_um=10.0,
                dbu=self.layout.dbu,
                pos=pya.Point(0, 0)
            )
            
            error_layer = self.layout.layer(999, 0)
            self.cell.shapes(error_layer).insert(text_region)
            
            print(f"\n{'='*50}")
            print("PCELL PARAMETER ERRORS:")
            print("ERRORS:\n" + "\n\n".join(
                  map(lambda err: ''.join(traceback.format_exception(err)),
                      self.__errors)))
            print(f"{'='*50}\n")
        
        def insert_labeled_variant(self, params, trans=pya.Trans(0, 0), align=None, label_offset=None, text_height=None):
            '''Inserts an labeled variant of the underlying PCell with the given parameters.

-           trans: pya.Trans If given, the transformation is applied after alignment
-           align: 'UR', 'UL', 'BR', 'BL', or 'C'. If given, aligns the specified corner of the instance's bbox to the origin.
-           label_offset: pya.Point or pya.Vector or (x, y) tuple. If given, used to offset the label position from the anchor position specified by *self._label_anchor*.

            Returns the instance from self.cell.insert.'''
            dbu = self.layout.dbu
            # TODO: Make it possible to use an existing cell instance in the layout,
            # using *change_pcell_parameters* creating new instances through add_pcell_variant,
            # to preserve any manual edits to the cell instance.
            
            # Cell container for the label and the PCell variant
            labeled_variant = self.layout.create_cell(f"Labeled_{source_pcell_name}_Variant")
            
            # Add the variant cell
            variant_cell = self.create_variant(params) # Creates variant of underlying PCell as a cell in the main layout:
            labeled_variant.insert(pya.CellInstArray(variant_cell, pya.Trans(0, 0)))
                        
            # Add label for the variant
            label_offset = pya.Vector(0, 0) if label_offset is None else pya.Vector(as_point(label_offset))
            label_anchor = get_bbox_point(self._label_anchor, labeled_variant.bbox())
            text_center = label_anchor + label_offset
            text_height = self.get_value('_label_height') if text_height is None else text_height
            label = self.create_label(params, text_center, text_height)
            labeled_variant.shapes(self._l_label_layer).insert(label)
            
            

            if align:            
                anchor = pya.Vector(get_bbox_point(align, labeled_variant.bbox()))
                trans.disp = trans.disp - anchor
            
            return self.cell.insert(pya.CellInstArray(labeled_variant, trans))
        
        # def insert_cell(self, cell, into=None)
                
        def create_variant(self, params):
            '''Create a variant of underlying PCell as a cell in the main layout, and 
            return the cell object'''
            # Create cell in the main layout
            print('create_variant called with params: ', params)
            
            #  Checking, shouldn't be necessary
            typed_params = params.copy()
            # for param_name, value in params.items():
            #     if param_name in self.src_params.keys():
            #         param_type = self.src_params[param_name].type
            #         converter = get_converter(param_type)
            #         typed_params[param_name] = converter(value)


            # Create cell in the main layout
            pcell_var_id = self.layout.add_pcell_variant(self.src_lib,
                                                self.src_pcell_decl.id(), 
                                                typed_params)
            # Fetch and return the cell object
            return self.layout.cell(pcell_var_id)
 
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
                
        # def generate_sweep(self):
        #     '''Parses the _row_sweep and _col_sweep parameters into a list of dictionaries of parameter values for each variation in the sweep, 
        #     and a dictionary of the fixed parameters that are not being swept over.
            
        #     Returns: (fixed_params, _row_sweep, _col_sweep)
        #         where fixed_params is a dict of {param_name: value} for the parameters that are not being swept over, 
        #         and _row_sweep and _col_sweep are lists of dicts of {param_name: value} for each variation in the row and column sweeps, respectively.
        #     '''
        #     def dict_zip(sweep_dict):
        #         '''Converts a dictionary of {param_name: [values]} into a 
        #         list of dictionaries of {param_name: value} for each iteration.
                
        #         For example, {'a': [1, 2], 'b': [3, 4]} would be converted into the sequence: 
        #         {'a': 1, 'b': 3}, {'a': 2, 'b': 4}
                
        #         Returns a list of [{param_name: value}, ...] 
        #         '''
        #         # Check for empty sweep_dict:
        #         if sweep_dict is None or len(sweep_dict) == 0:
        #             return [{}] 
                
        #         # Check that the lists of values in sweep_dict are all the same length:
        #         lengths = [len(values) for values in sweep_dict.values()]
        #         if len(set(lengths)) > 1:
        #             raise ValueError(f"All parameters in a sweep must have the same number of values. Found lengths: {lengths}")
        #         num_variations = lengths[0]
                
        #         # Convert from {param_name: [values]} to list of {param_name: value} for each variation:
        #         variations = []
        #         for i in range(num_variations):
        #             variations.append({param_name: sweep_dict[param_name][i] for param_name in sweep_dict.keys()})
                    
        #         return variations
                
        #     fixed_params = self.get_src_params() # current parameter values from underlying PCell
            
        #     # TODO: I haven't implented secondary row or column sweeps
            
        #     # TODO: Extract details like the label placement, and arrays of identical variants
        #     # from existing cell in the layout.
        #     # TODO: Create a menu action or a macro to use existing cells in the layout
        #     # as the source for the sweep. (The existing cells have to contain PCells).
            
        #     # Remove the swept parameters from the fixed parameters dict
        #     for key in self.parsed_row_sweep.keys():
        #         fixed_params.pop(key) 
        #     for key in self.parsed_col_sweep.keys():
        #         fixed_params.pop(key)
            
        #     # generator of dicts of {param_name: value} for each variation in the row sweep
        #     _row_sweep = dict_zip(self.parsed_row_sweep) 
        #     _col_sweep = dict_zip(self.parsed_col_sweep) 
            
        #     return fixed_params, _row_sweep, _col_sweep

            
        def __copy_param(self, param_decl, default=None, name:str=None, type_code:int=None, description:str=None,
                         hidden:bool=None, readonly:bool=None, unit:str=None, 
                         max_value=None, min_value=None, choices=None):
            '''
            Helper function to copy a parameter declaration from the underlying PCell into this wrapper PCell, 
            by defining a parameter with the same attributes in this wrapper PCell.
            
            If any of the kwargs are given, they override the corresponding attribute of the parameter declaration from the 
            underlying PCell when the parameter is defined in this PCell.
            
            Also stores the parameter declarations of the underlying PCell in a dictionary 
            *self.src_params* for easy access when generating the sweep.
            '''
            # For every paramter attribute: override if provided, otherwise use the value from param_decl
                
            if type_code is None:
                type_code = param_decl.type
            elif not is_valid_param_type(type_code):
                raise ValueError(f'Invalid type code for Klayout PCell parameter: {type_code}. Must be one of '
                                       ' pya.PCellParameterDeclaration.TypeInt, pya.PCellParameterDeclaration.TypeDouble,'
                                       ' pya.PCellParameterDeclaration.TypeString, pya.PCellParameterDeclaration.TypeLayer, etc.')
                
            name      = param_decl.name if name is None else str(name)
            describe  = param_decl.description if description is None else str(description)
            default   = param_decl.default if default is None else get_converter(type_code)(default)
            hidden    = param_decl.hidden if hidden is None else hidden in (True, 'True', 1, '1', 'yes')
            readonly  = param_decl.readonly if readonly is None else readonly in (True, 'True', 1, '1', 'yes') 
            unit      = param_decl.unit if unit is None else str(unit)
            min_value = param_decl.min_value if min_value is None else min_value
            max_value = param_decl.max_value if max_value is None else max_value
            
            if choices is None and len(param_decl.choice_values()) > 0:
                choices = list(zip(param_decl.choice_descriptions(), param_decl.choice_values()))

            # It will throw an error if you assign choices=None. Only assign the choices argument if you have a value for it.
            if choices is not None:
                self.param(name, type_code, describe, 
                            default=default, hidden=hidden, readonly=readonly,
                            unit=unit, max_value=max_value, min_value=min_value,
                            choices=choices)
            else:
                self.param(name, type_code, describe, 
                            default=default, hidden=hidden, readonly=readonly,
                            unit=unit, max_value=max_value, min_value=min_value)
                
            # Store the parameter declarations of the underlying PCell in a 
            # dictionary for easy access when generating the sweep:
            self.src_params[param_decl.name] = param_decl
            
            # print(f'Copied param: {name} as type {PARAM_TYPES[type_code]} with default {default!r}')
            # print(f'Current Value: {name} = {getattr(self, name)}')
        
        def _pcell_from_lib(self, source_pcell_name, lib_name):
            '''Find the target PCell declaration in the given library.
            Returns  (PCell declaration object, Library object).
            Raises an exception if the library or PCell cannot be found.'''
            # Find the library
            lib = pya.Library.library_by_name(lib_name)
            if not lib:
                raise Exception(f"Library '{lib_name}' not found")
            
            # Search the library for source_pcell_name
            pcell_decl = lib.layout().pcell_declaration(source_pcell_name)
            if not pcell_decl:
                raise Exception(f"PCell '{source_pcell_name}' not found in library '{lib_name}'")
            
            print(f"Found PCell declaration for '{source_pcell_name}' in library '{lib_name}'")
            return pcell_decl, lib
        
        def _details_from_layout(self, source_pcell_name):
            '''Find the existing cell in the currently active layout with the given name.
            
            Returns: dict of it's parameter values {param_name: value}, 
            or raises an exception if the cell cannot be found or is not a PCell instance.
            '''
            # Search currently active layout for source_pcell_name
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
            cell = layout.cell(source_pcell_name)
            if not cell:
                raise Exception(f"Cell '{source_pcell_name}' not found in currently active layout.")
                    
            if not cell.is_pcell_variant():
                raise Exception(f"'{source_pcell_name}' is not a PCell instance.")
            
            print(f"Found PCell '{source_pcell_name}' in the currently active layout.")
            
            # Actual parameters values for this instance, to use as defaults in the wrapper PCell parameters:
            return cell.pcell_parameters_by_name()
        
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
            
        def _convert_to_type(self, value_str, param_type):
            """Convert string to proper parameter type."""
            convert_type = get_converter(param_type) # Function that converts a string to the correct type.
            try:
                convert_type(value_str)
            except ValueError as e:
                e.add_note(f'Error converting "{value_str}" to type {param_type}.')
                raise
        
        def __get_pcell_decl(self):
            '''
            Finds the target PCell's declaration, using local variables source_pcell_name and lib_name 
            from the enclosing function this PCell is defined in. *lib_name* is the name of the library 
            containing the target pcell. If not given, will search the currently active layout for the 
            an existing cell with the given target cell name.
            '''
            if lib_name: # Search the library for source_pcell_name
                lib = pya.Library.library_by_name(lib_name)
                if not lib:
                    raise Exception(f"Library {lib_name} not found")
            
                pcell_decl = lib.layout().pcell_declaration(source_pcell_name)
                if not pcell_decl:
                    raise Exception(f"PCell {source_pcell_name} not found in Library {lib_name}")
                
            else: # Search currently active layout for source_pcell_name
                existing_cell = self.layout.cell(self.cell_name)
                    
                if not existing_cell:
                    raise Exception(f"Cell '{self.cell_name}' not found in currently active layout.")

    return ParamSweep




# If it had been possible to dynamically add parameters to the PCell class after discovering the underlying PCell's parameters, 
# I would have done that instead of having the user go into scripting to define which PCells to wrap over:
# All parameters must be defined in the __init__ of the PCell. 
# So I have to define a new class for each underlying PCell I want to wrap over, which is not ideal.

    # # Reference to the underlying PCell
    # self.param("pcell_name", self.TypeString, "PCell to Array", default="HEMT")
    # self.param("library_name", self.TypeString, "Library Name", default="MyLib")
    # # To use existing, locally created cell instead:
    # self.param("use_existing_cell", self.TypeBoolean, "Use Existing Cell", default=False)

if __name__ == '__main__':
    try:
        import importlib
        import sys
        importlib.reload(sys.modules['pya_helpers'])
        importlib.reload(sys.modules['general_helpers'])
        from pya_helpers import get_converter
    
        # Usage:
        ParamSweepHEMT = custom_sweep_pcell("HEMT", "MyLib")
        convert = get_converter(ParamSweepHEMT.TypeInt)
        print(convert('1'))
        print(convert('2.00'))
        print(repr(ParamSweepHEMT._parse_values_to_type(1, '1:20:5', ParamSweepHEMT.TypeInt)))

        # # Register it
        # lib = pya.Library.library_by_name("MyLib")
        # lib.layout().register_pcell(f'HEMT_ParamSweep', ParamSweepHEMT())
    except Exception as e:
        print('ParamSweep error: ', traceback.format_exc())
        # f'{LIB_NAME} loaded with PCells: {list(PCELLS.keys()).extend(['HEMT'])}'