import pya
from datetime import datetime
import traceback
import re
# from string.templatelib import Interpolation, Template


from pya_helpers import create_text, get_bbox_point, get_converter, is_valid_param_type, is_numeric_param_type
from general_helpers import parse_range, UserInputError
from DependencyGraph import DependencyGraph
    
def custom_sweep_pcell(source_pcell_name:str, lib_name:str, use_existing:bool=False) -> pya.PCellDeclarationHelper:
    '''Defines a custom PCell that wraps the given target PCell. The custom PCell helps the user create a parametric 
    sweep of parameters in the underlying PCell as an array of labeled variations. 
    
    Exposes the parameters of the underlying PCell, with added array and labeling functionality.
-    source_pcell_name: The name of the PCell to create this ParamSweep wrapper around.  
-    lib_name: The name of the library containing the target pcell. 
-    use_existing: If true, will search the currently active layout for an existing cell with the given target cell name. This cell will define the default parameter vaules for the wrapper PCell.
    '''
      # Really important comment
        
    class ParamSweep(pya.PCellDeclarationHelper):
        """
        Wrapper for PCells that creates an array of labeled variations of the underlying PCell (a parametric sweep).
        
        User can define a row sweep and a column sweep. A sweep can each be defined using any one parameter of the underlying PCell. 
        params that are not explicitly swept can be given as expressions of the swept parameters
        """  
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
                self.evaluated_params = {} # {param_name: value_evaluated_in_the_correct_type}
                self.parsed_row_sweep = {} # will hold {param_name: [values]}
                self.parsed_col_sweep = {} # will hold {param_name: [values]}
                self._dependency_graph = DependencyGraph() # tracks which params depend on which

                # Cache for detecting changes
                self.__prev = None # TODO: actually use this?
                
                # TODO: Add nice defaults for row_sweep and col_sweep. Discovery of source param decls must happen first. 
                # TODO:  Make ParamSweep a child class of Wrapper. Will help with ^^
                
                # Sweep Array Configuration 
                self.param("_sweep_header", self.TypeNone, " Sweep Configuration ".center(32, '═')) # Just holds the section header in the GUI.
                self.param("row_sweep", self.TypeString, "Define Row Sweep", default='') # sep_GD: 1, 2, 3
                self.param("col_sweep", self.TypeString, "Define Col Sweep", default='') # gate_len: 0.5, 1, 2
                self.param("row_pad", self.TypeDouble, "Row Padding (µm)", default=100.0)
                self.param("col_pad", self.TypeDouble, "Column Padding (µm)", default=100.0)

                # Labeling
                self.param("_label_header", self.TypeNone, " Labeling ".center(32, '═')) # Just holds the section header in the GUI.
                self.param("format_str", self.TypeString, "Label Format", default="GS:{sep_SG}, G:{gate_len}, GD:{sep_GD}")
                self.param("l_label", self.TypeLayer, "Label Text Layer", default=pya.LayerInfo(1, 0))
                self.param("label_height", self.TypeDouble, "Label Height (µm)", default=30.0)
                self.param("label_rot", self.TypeInt, "Label Rotation", default=0, choices=[('0°', 0), ('90°', 1),  ('180°', 2), ('270°', 3)])
                self.param("label_x", self.TypeDouble, "Label X Offset (µm)", default=0.0)
                self.param("label_y", self.TypeDouble, "Label Y Offset (µm)", default=0.0)
                self.__label_anchor_choices = ["Top Left", "Top Right", "Bottom Left", "Bottom Right", "Top Center", "Bottom Center", "Center Right", "Center Left"]
                self.param("label_anchor", self.TypeString, f"Label Anchor Point on {source_pcell_name}'s BBox", default="Top Left", 
                           choices=list(zip(self.__label_anchor_choices, self.__label_anchor_choices))) # choices = [(description, value), ...]
            
                # Underlying PCell parameters
                self.param("_params_header", self.TypeNone, f" {source_pcell_name} ".center(32, '═')) # Just holds the section header in the GUI.
                
                # Expose parameters of the underlying PCell for user input
                #    i.e. copy over each parameter in the underlying PCell 
                #    by defining a parameter with the same attributes in this wrapper PCell.
                
                for param_decl in pcell_decl.get_parameters():
                    # To allow expressions for numerical parameter values, the input type accepted must be changed to TypeString
                    if is_numeric_param_type(param_decl.type):
                        type_code = pya.PCellParameterDeclaration.TypeString
                    else: 
                        type_code = param_decl.type
                    
                    # If we were able to get actual parameter values from an existing cell instance in the layout, 
                    # use those as the defaults in the wrapper PCell, so that the initial generated layout will match the existing cell instance. If not, just use the default values from the underlying PCell.
                    if param_values:
                        param_decl.default = param_values.get(param_decl.name) 
                    
                    # Copy parameter to this wrapper PCell
                    self.__copy_param(param_decl, type_code=type_code)  # also adds parameter declaration to self.src_params
                    
                print(f"Copied parameters into '{source_pcell_name}_ParamSweep wrapper: {list(self.src_params.keys())}")            
                print(f'Initialized an instance of {source_pcell_name}_ParamSweep() at {datetime.now()}')
            except Exception as e:
                print(f"Error in {source_pcell_name}_ParamSweep __init__: \n{traceback.format_exc()}")
        
        def coerce_parameters_impl(self):
            """
            Called before display_text_impl and produce_impl.
            """
            # TODO: How to implement error messages to the user for bad input in GUI window?
            print(f'Called {source_pcell_name}_ParamSweep.coerce_parameters_impl()')
            self.__errors = [] # Collect all errors, and clear whenever restarting from coerce_parameters_impl.
            
            try:
                # Parse the row and column sweep specifications into {param_name: [values]}
                self.parse_and_validate_sweeps()
                # Debug:
                print(f'Parsed row sweep: {self.parsed_row_sweep}')
                print(f'Parsed col sweep: {self.parsed_col_sweep}')
            except Exception as e:
                self.__errors.append(e)
                print(f"Error in {source_pcell_name}_ParamSweep coerce_parameters_impl: \n{traceback.format_exc()}")
                
            try: 
                # Check if the label format_str references valid parameters 
                # from the underlying PCell, and raise ValueError if it doesn't.
                self.validate_label_fstring()
            except Exception as e:
                self.__errors.append(e)
                print(f"Error in {source_pcell_name}_ParamSweep coerce_parameters_impl: \n{traceback.format_exc()}")
                
            try:
                # Evaluate expression parameters
                self.eval_params()
            except Exception as e:
                self.__errors.append(e)
                print(f"Error in {source_pcell_name}_ParamSweep coerce_parameters_impl: \n{traceback.format_exc()}")           
                
        def parse_and_validate_sweeps(self):
            '''Parse the row and column sweep specifications into {param_name: [values]}.
            Raise descriptive errors on failure.'''
            # Row Sweep
            if self.row_sweep:
                try:
                    param_name, values = self._parse_sweep(self.row_sweep) # Performs validation and parsing
                except UserInputError as e:
                    self.row_sweep = e.annotated_input # Annotate row sweep with hints to the user
                    raise
                
                # Successful parse!
                self.parsed_row_sweep = {param_name: values} # Store parsed result
                # This parameter is controlled through the row sweep, so make it say that in the GUI.
                # self.setattr(param_name, 'Set by Row sweep.')
            else: 
                self.parsed_row_sweep = {}
            
            # Col Sweep
            if self.col_sweep:
                try:
                    param_name, values = self._parse_sweep(self.col_sweep) # Performs validation and parsing
                except UserInputError as e:
                    self.col_sweep = e.annotated_input # Annotate col sweep with hints to the user
                    raise
                # Can't control the same parameter through both row and column sweep:
                if param_name in self.parsed_row_sweep:
                    # Annotate both row_sweep and col_sweep with hints to the user
                    self.col_sweep = self.col_sweep.replace(param_name, f'{param_name}!!')
                    self.row_sweep = self.row_sweep.replace(param_name, f'{param_name}!!')
                    raise ValueError(f"Parameter '{param_name}' cannot be swept over in both row and column sweeps.")  
                
                # Successful parse!
                self.parsed_col_sweep = {param_name: values} # Store parsed result
                # This parameter is controlled through the col sweep, so make it say that in the GUI.
                # self.setattr(param_name, 'Set by Col sweep.')
            else:
                self.parsed_col_sweep = {}

        def validate_label_fstring(self):
            '''
            Check if the label format_str references valid parameters 
            from the underlying PCell, and raise ValueError if it doesn't.
            '''
            validator = self.NoteMissingKeys(self.src_params.keys())
            self.format_str = self.format_str.format_map(validator)
            if validator.missing_keys: # The set of keys that were referenced in format_str but not found in the underlying PCell parameters. Warn the user about these.
                raise ValueError(f"Label format string references parameters that are not in the underlying PCell: {validator.missing_keys}. " +
                                    f"Invalid names are marked with '??' in the label text.")

        def eval_params(self):
            '''Evaluate expression parameters.
            
            Discover dependency order and check that it is acyclic.
            '''
            # # Reset dependency graph
            # self._dependency_graph = DependencyGraph()
            
            # expr = getattr(self, expr_name)      
            for param_name in self.src_params.keys():
                
                input_value = getattr(self, param_name)
                required_type = self.src_params[param_name].type
                
                # Check if it needs to be evalauted:
                # It needs to be evaluated if it's a string, and the required type is not TypeString.
                if isinstance(input_value, str) and required_type != pya.PCellParameterDeclaration.TypeString: 
                    convert = get_converter(required_type)
                    try:
                        # See if it's just a string value or an expression by trying a basic conversion
                        value = convert(input_value) 
                    except Exception: 
                        # It's an expression.
                        # For now, only allow expressions in terms of swept parameters. TODO: allow buiding expressions with other parameters
                        # TODO allow expressions for boolean or string types
                        try:
                            value = self._evaluate_param(expr, context)
                            # Annotate the string in the input box to show how's interpreted
                            setattr(self, param_name, input_value + f' = {value}')
                        except Exception as e:
                            value = None
                            # Annotate the string in the input box to show the error
                            setattr(self, param_name, input_value + f' = {e}')
                            self.__errors.append(f'Failure to evaulate {param_name}: {input_value} = {e}')
                else:
                    value = input_value
                    
                self.evaluated_params = value 
                
        def display_text_impl(self):
            """
            PCell interface implementation
            """
            if self.__errors:
                    text = f'{source_pcell_name}_ParamSweep ({len(self._errors)} error(s) - check console")'
                    print(f'{source_pcell_name}_ParamSweep instance display_text called: ' + text)
                    return text
            
            try: 
                num_rows = len(next(iter(self.parsed_row_sweep.values()))) # TODO: Make sure this doesn't failt for empty row, col sweep
                num_cols = len(next(iter(self.parsed_col_sweep.values())))
                if num_rows < 1: num_rows = 1
                if num_cols < 1: num_cols = 1
                text = f'{source_pcell_name}_ParamSweep({num_rows}x{num_cols})'
                print(f'{source_pcell_name}_ParamSweep instance display_text called: ' + text)

            except Exception as e:
                print(f"Error in display_text_impl: \n{traceback.format_exc()}")
                text = f'{source_pcell_name}_ParamSweep (?)'

            return text
                  
        def produce_impl(self):
            """
            Implementation of the PCell interface: generates the layouts.
            
            Accounts for bounding boxes so that the instances in the sweep don't overlap.
            self.row_pad determines the padding between rows. 
            self.col_pad sets the minimum padding between columns. If something in a row is wide, 
            it shifts the entire next column over to accommodate it.
            """
            print(f'{source_pcell_name}_ParamSweep instance produce_impl at {datetime.now()}')
            dbu = self.layout.dbu
            
            if self.__errors: # If there are errors, show them instead of generating the geometery
                self.display_error_geom()
                return
            
            # Generate Geometery
            try: 
                fixed_params, row_sweep, col_sweep = self.generate_sweep()
                print('Generated sweep parameters in produce_impl:')
                print(f'fixed_params: {fixed_params}')
                print(f'row_sweep: {row_sweep}')
                print(f'col_sweep: {col_sweep}')
                
                # If no sweep defined, just create a single instance 
                # of the underlying PCell with the current parameters:
                if not row_sweep and not col_sweep:
                    self.insert_labeled_variant(fixed_params)
                
                # Create Parametric Sweep of underlying PCell:
                x_pos = 0
                for col_spec in col_sweep:
                    y_pos = 0
                    max_x = 0 # Save the x coordinate of the widest inserted instance.
                    for row_spec in row_sweep:
                        # Create parameter set for this variation by combining the fixed parameters with the 
                        # current row and column sweep parameters (dicts of {param_name: value}):
                        params = fixed_params | row_spec | col_spec
                        
                        inst = self.insert_labeled_variant(
                                    params, 
                                    pya.Trans(x_pos, y_pos), 
                                    align='UL')
                                                
                        # Update y_pos and x_pos based on the bbox:
                        y_pos = inst.bbox().bottom - int( self.row_pad / dbu)
                    
                        # Update max_x as needed:
                        max_x = max( max_x, inst.bbox().right )
                
                    # Update y_pos
                    x_pos = max_x + int( self.col_pad / dbu)
                

                #    TODO:   should be multiple copies, work on that later 
    
    
                #         
                print(f'produce_impl finished for {source_pcell_name}_ParamSweep instance at {datetime.now()}')
            except Exception as e:
                print(f"produce_impl error error: \n{traceback.format_exc()}")
                # Insert a default shape to prevent empty cell
                self.cell.shapes(self.layout.layer(0, 0)).insert(pya.Box(0, 0, 100/dbu, 100/dbu))
        
        def display_error_geom(self):
            ''' Generate text geometry showing the content of self.__errors'''
            # Written by Claude-4-5-sonnet
            error_text = "ERRORS:\n" + "\n".join(self._errors)
        
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
            for err in self._errors:
                print(f"  • {err}")
            print(f"{'='*50}\n")
        
        def insert_labeled_variant(self, params, trans=pya.Trans(0, 0), align=None):
            '''Inserts an labeled variant of the underlying PCell with the given parameters.
            
-           align: 'UR', 'UL', 'BR', 'BL', or 'C'. If given, aligns the specified corner of the instance's bbox to the origin. 
-           trans: pya.Trans If given, the transformation is applied after alignment

            Returns the instance from self.cell.insert.'''
            # TODO: Multiple copies! 
            # TODO: Make it possible to use an existing cell instance in the layout,
            # using *change_pcell_parameters* creating new instances through add_pcell_variant,
            # to preserve any manual edits to the cell instance.
            
            # Cell container for the label and the PCell variant
            labeled_variant = self.layout.create_cell(f"Labeled_{source_pcell_name}_Variant")
            
            # Add the variant cell
            variant_cell = self.create_variant(params) # Creates variant of underlying PCell as a cell in the main layout:
            labeled_variant.insert(pya.CellInstArray(variant_cell, pya.Trans(0, 0)))
                        
            # Add label for the variant
            label = self.create_label(params, variant_cell.bbox())
            labeled_variant.shapes(self.l_label_layer).insert(label)

            if align:            
                anchor = pya.Vector(get_bbox_point(align, labeled_variant.bbox()))
                trans.disp = trans.disp - anchor
            
            return self.cell.insert(pya.CellInstArray(labeled_variant, trans))
        
        # def insert_cell(self, cell, into=None)
                
        def create_variant(self, params):
            '''Create a variant of underlying PCell as a cell in the main layout, and 
            return the cell object'''
            # Create cell in the main layout
            pcell_var_id = self.layout.add_pcell_variant(self.src_lib,
                                                self.src_pcell_decl.id(), 
                                                params)
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
 
        def create_label(self, params, bbox):
            '''Creates a text label for an variant in the sweep, with the given parameters and position as a pya.Region.
            Text will be a region of polygons in the layout. It will be positioned based on *self.label_anchor*
            and text postion offset parameters, using the provided bbox.
            
-           params: dict of {param_name: value} for the parameters of the underlying PCell instance that this label is annotating, used to fill in the format_str for the label text
-           bbox: bbox of the object to label, or the object with a bbox() getter.
            
            Returns the Region object containing the text label.
            '''
            dbu = self.layout.dbu
            
            # Checking:
            # bbox
            if not isinstance(bbox, pya.Box):
                try:
                    bbox = bbox.bbox()
                except Exception:
                    raise TypeError('bbox must be a pya.Box or an object that has a bbox') from None
            
            # Parse format str with the given params
            #   Makes sure floats are displayed without trailing zeros, and with no more than 3 significant digits:
            formatted_params = self.__format_params(params)
            text = self.format_str.format_map(self.SoftReplace(formatted_params))
            
            # Position it          
            label_anchor = get_bbox_point(self.label_anchor, bbox)
            offset = pya.Vector(int(self.label_x/dbu), int(self.label_y/dbu))
            pos = label_anchor + offset # where to place the center of the text bonding box
            
            # Create text as polygons
            text_region = create_text(text, self.label_height, dbu, 
                                        trans=pya.Trans(rot = self.label_rot), # 0, 1, 2, 3 rotation convention
                                        pos=pos) 
            
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
                    formatted[param_name] = f'{value:.3g}'
            return formatted
                
            # TODO: Allow for selection of text alignment (centered, left, etc), 
            # or make it depend on the choice of label_anchor?
                
        def generate_sweep(self):
            '''Parses the row_sweep and col_sweep parameters into a list of dictionaries of parameter values for each variation in the sweep, 
            and a dictionary of the fixed parameters that are not being swept over.
            
            Returns: (fixed_params, row_sweep, col_sweep)
                where fixed_params is a dict of {param_name: value} for the parameters that are not being swept over, 
                and row_sweep and col_sweep are lists of dicts of {param_name: value} for each variation in the row and column sweeps, respectively.
            '''
            def dict_zip(sweep_dict):
                '''Converts a dictionary of {param_name: [values]} into a 
                list of dictionaries of {param_name: value} for each iteration.
                
                For example, {'a': [1, 2], 'b': [3, 4]} would be converted into the sequence: 
                {'a': 1, 'b': 3}, {'a': 2, 'b': 4}
                
                Returns a list of [{param_name: value}, ...] 
                '''
                # Check for empty sweep_dict:
                if sweep_dict is None or len(sweep_dict) == 0:
                    return [{}] 
                
                # Check that the lists of values in sweep_dict are all the same length:
                lengths = [len(values) for values in sweep_dict.values()]
                if len(set(lengths)) > 1:
                    raise ValueError(f"All parameters in a sweep must have the same number of values. Found lengths: {lengths}")
                num_variations = lengths[0]
                
                # Convert from {param_name: [values]} to list of {param_name: value} for each variation:
                variations = []
                for i in range(num_variations):
                    variations.append({param_name: sweep_dict[param_name][i] for param_name in sweep_dict.keys()})
                    
                return variations
                
            fixed_params = self.get_src_params() # current parameter values from underlying PCell
            
            # TODO: I haven't implented secondary row or column sweeps or dependence on swept parameters yet,
            # so there will only be one key in parsed_row_sweep and parsed_col_sweep:
            
            # TODO: Extract details like the label placement, and arrays of identical variants
            # from existing cell in the layout.
            # TODO: Create a menu action or a macro to use existing cells in the layout
            # as the source for the sweep. (The existing cells have to contain PCells).
            
            # Remove the swept parameters from the fixed parameters dict
            for key in self.parsed_row_sweep.keys():
                fixed_params.pop(key) 
            for key in self.parsed_col_sweep.keys():
                fixed_params.pop(key)
            
            # generator of dicts of {param_name: value} for each variation in the row sweep
            row_sweep = dict_zip(self.parsed_row_sweep) 
            col_sweep = dict_zip(self.parsed_col_sweep) 
            
            return fixed_params, row_sweep, col_sweep
            
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
            # Store the parameter declarations of the underlying PCell in a 
            # dictionary for easy access when generating the sweep:
            self.src_params[param_decl.name] = param_decl
            
            
            # For every paramter: override if provided, otherwise use the value from param_decl
            name = str(name) if name is not None else param_decl.name
            description = str(description) if description is not None else param_decl.description

            if type_code is not None:
                if is_valid_param_type(type_code):
                    param_decl.type = type_code
                else: raise ValueError(f'Invalid type code for Klayout PCell parameter: {type_code}. Must be one of '
                                       ' pya.PCellParameterDeclaration.TypeInt, pya.PCellParameterDeclaration.TypeDouble,'
                                       ' pya.PCellParameterDeclaration.TypeString, pya.PCellParameterDeclaration.TypeLayer, etc.')
            else: type_code = param_decl.type
            
            default = get_converter(type_code)(default) if default is not None else param_decl.default
            
            hidden   = hidden   in (True, 'True', 1, '1', 'yes') if hidden is not None else param_decl.hidden
            readonly = readonly in (True, 'True', 1, '1', 'yes') if readonly is not None else param_decl.readonly
            unit = str(unit) if unit is not None else param_decl.unit
            min_value = min_value if min_value is not None else param_decl.min_value
            max_value = max_value if max_value is not None else param_decl.max_value
            
            if choices is None and len(param_decl.choice_values()) > 0:
                choices = list(zip(param_decl.choice_descriptions(), param_decl.choice_values()))
    
            # It will throw an error if you assign choices=None. Only assign the choices argument if you have a value for it.
            if choices is not None:
                self.param(name, type_code, description, default, hidden, readonly,
                            unit, max_value, min_value, choices=choices)
            else:
                self.param(name, type_code, description, default, hidden, readonly,
                            unit, max_value, min_value)
        
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
            '''Parses either *row_sweep* or *col_sweep* into parameter name and list of values to sweep over.
            
            Performs validation, and raises exceptions with descriptive error messages:
-           Checks that *sweep_spec* is in the correct format: param_name: value1, value2, ...
-           Check that the parameter it references actually exists in the underlying PCell.
-           Checks that the values can be parsed into the correct types for the underlying PCell parameter.
            
            Returns: (param_name, values_list) where param_name is the name of the parameter to sweep over, and 
            values_list is a list of the values to sweep over for that parameter.
            '''
            pattern = re.compile(r'''\s*([a-zA-Z_][a-zA-Z0-9_]*)[?!]*\s*: # (param name) followed by colon, ignoring any ?? or !! annotations 
                                                                          # that may have been added previously
                                 ((?:[^,]+,)*[^,]+)$''',             # (value1, value2, ...) at least one value, separated by commas
                                                                     # with optional whitespace.
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
                        expanded_range = parse_range(s, convert_type)
                        values.extend(map(str, expanded_range)) 
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
        
        def get_src_params(self):
            '''Returns the parameters for the underlying (source) PCell, using the current values from this wrapper PCell,
            or the default if there is a problem evaluating the user's input
            Returns: dict of {param_name: value}
            '''
            params = {}
            for param_name in self.src_params.keys():
                value = self.evaluated_params.get(param_name)
                if not value:
                    value = self.src_params[param_name].default
                params[param_name] = value
            return params

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
        # Usage:
        ParamSweepHEMT = custom_sweep_pcell("HEMT", "MyLib")

        # Register it
        lib = pya.Library.library_by_name("MyLib")
        lib.layout().register_pcell(f'HEMT_ParamSweep', ParamSweepHEMT())
    except Exception as e:
        print('ParamSweep error: ', e)
        # f'{LIB_NAME} loaded with PCells: {list(PCELLS.keys()).extend(['HEMT'])}'