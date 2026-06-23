import pya
from datetime import datetime
import traceback

from helpers.pya_helpers import create_text, text_pcell, get_converter, is_valid_param_type
    
class Wrapper(pya.PCellDeclarationHelper):
    """
    Wrapper for PCells that exposes the parameters of an underlying PCell.
    
    A generic PCell that can be subclassed for easy extensions to an existing PCell. 
    """  
    def __init__(self, source_pcell_name, lib_name, expose_params=True, use_existing=False):  
        """ Initializes the wrapper PCell by finding the underlying PCell declaration.
-        expose_params: if True, expose the parameters of the underlying PCell for user input.
        """
        try: 
            print(f'Called {source_pcell_name}_Wrapper.__init__()')
            super().__init__()
            
            self.src_pcell_name = source_pcell_name
            self.lib_name = lib_name
            self.use_existing = use_existing
            
            # Get the underlying PCell
            pcell_decl, lib = self._pcell_from_lib(source_pcell_name, lib_name) 
            self.src_pcell_decl = pcell_decl  #  PCell declaration of the underlying (source) PCell
            self.src_lib = lib #  library object of the underlying PCell
            self.src_params = self.__discover_param_decls() # dict {param_name: param_decl} 
            #                                                stores parameter declarations of the underlying PCell.
            
            # # TODO expand on and test use_existing features
            # self.param_values = self._details_from_layout(source_pcell_name) if use_existing else None 
            
            # Expose parameters of the underlying PCell for user input
            if expose_params: self.expose_src_params() 
            # If expose_params was False, the user can still call expose_src_params()
            # after defining their own parameters to control the order of the parameters in the GUI.
            
            # Collect errors during execution
            self.__errors = [] # Exception Objects

            print(f'Initialized an instance of {source_pcell_name}_Wrapper() at {datetime.now()}')
        except Exception as e:
            print(f"Error in {source_pcell_name}_Wrapper __init__: \n{traceback.format_exc()}")

    def display_text_impl(self):
        return f"{self.src_pcell_name}_Wrapper: " + \
        "This class is meant to be subclassed to extend functionality of underlying PCells."

    def produce_impl(self):
        """
        Implementation of the PCell interface: generates the layouts
        """
        print(f'{self.src_pcell_name}_Wrapper instance produce_impl at {datetime.now()}')
        # Insert an instance of the underlying PCell.
        self.insert_instance()      
            
    def expose_src_params(self):
        '''Exposes the parameters of the underlying PCell for user input by copying them into this wrapper PCell.
        
        i.e. copy over each parameter in the underlying PCell 
        by defining a parameter with the same attributes in this wrapper PCell.
        
        The order of the calls to self.param() determines the order of the parameters in the GUI,
        so expose_src_params() can be called by a child class after defining some of its own parameters 
        to control the order of the parameters in the GUI. Set expose_params=False in the constructor if you 
        want to call expose_src_params() manually after defining some parameters in the child class.
        '''
        # Set-up:
        # Fill self.src_params if it hasn't been filled already.
        if not self.src_params: 
            self.src_params = self.__discover_param_decls(use_existing=self.use_existing) 
        
        # Section header in the GUI.
        self.param("_params_header", self.TypeNone, f" {self.src_pcell_name} ".center(32, '═')) 
        
        # Copy over each parameter in the underlying PCell by defining a parameter with the same attributes in this wrapper PCell.
        copied_params = [] # For debug messaging
        for name, param_decl in self.src_params.values():
            # Checks that we haven't already copied this parameter over (in case expose_src_params is called multiple times).
            if not self.hasattr(name):
                self._copy_param(param_decl)
                copied_params.append(name)
                
        print(f"Copied parameters into '{self.src_pcell_name}_Wrapper wrapper: {copied_params}")  
    
    def src_parameters(self):
        '''Returns the parameters for the underlying (source) PCell, using the current values from this wrapper PCell,
        or defaults if there was an error getting the current values from this wrapper PCell.
        Returns: dict of {param_name: value}
        '''
        params = {}
        try:
            for param_name in self.src_params.keys():
                params[param_name] = getattr(self, param_name)
        except Exception:
            # Use defaults if there was an error getting the current values
            params = {param_name: param_decl.default for param_name, param_decl in self.src_params.items()}
        return params
            
    def __discover_param_decls(self, use_existing=False):
        ''' Discover parameter declarations of the underlying PCell. 
        Returns the paramter declarations of the underlying PCell in a dictionary {param_name: param_decl}.
    
        if use_existing: Overide default parameter values with actual parameter values from an existing PCell instance in the layout.
.       '''
        # # If we were able to get actual parameter values from an existing cell instance in the layout, 
        # # use those as the defaults in the wrapper PCell, so that the initial generated layout will match the existing cell instance. If not, just use the default values from the underlying PCell.
        # param_values = self._details_from_layout(self.src_pcell_name) if self.use_existing else None
        
        # Store each parameter declaration from the underlying PCell in a dictionary
        src_params = {}
        for param_decl in self.src_pcell_decl.get_parameters():
            # if param_values: 
            #     overide_default = param_values.get(param_decl.name)
            #     param_decl.default = overide_default

            src_params[param_decl.name] = param_decl
        
        return src_params
            
    def _copy_param(self, param_decl, default=None, name:str=None, type_code:int=None, description:str=None,
                         hidden:bool=None, readonly:bool=None, unit:str=None, 
                         max_value=None, min_value=None, choices=None):
            '''
            Helper function to copy a parameter declaration from the underlying PCell into this wrapper PCell, 
            by defining a parameter with the same attributes in this wrapper PCell.
            
            If any of the kwargs are given, they override the corresponding attribute of the parameter declaration from the 
            underlying PCell when the parameter is defined in this PCell.
            '''
            # For every paramter attribute: override if provided, otherwise use the value from param_decl
            name      = param_decl.name if name is None else str(name)
                
            if type_code is None:
                type_code = param_decl.type
            elif not is_valid_param_type(type_code):
                raise ValueError(f'Invalid type code for Klayout PCell parameter: {type_code}. Must be one of '
                                       ' pya.PCellParameterDeclaration.TypeInt, pya.PCellParameterDeclaration.TypeDouble,'
                                       ' pya.PCellParameterDeclaration.TypeString, pya.PCellParameterDeclaration.TypeLayer, etc.')
                
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
    
    def display_error_geom(self, errors, text_height_um=10.0):
            ''' Generate text geometry showing the errors.
            errors: list of error objects'''
            # Written by Claude-4-5-sonnet, with modifications
            
            # Show errors as text in the layout
            error_text = "ERRORS:\n\n" + "\n\n".join(map(str, errors))

            text_cell = text_pcell(error_text, 
                                   text_height_um,
                                   pya.LayerInfo(999, 0), # Error geometry layer
                                   self.layout)
            
            self.cell.insert(pya.CellInstArray(text_cell, pya.Trans(0, 0)))
            
            # text_region = create_text(
            #     error_text,
            #     height_um=10.0,
            #     dbu=self.layout.dbu,
            #     pos=pya.Point(0, 0)
            # )
            
            # error_layer = self.layout.layer(999, 0)
            # self.cell.shapes(error_layer).insert(text_region)
            
            # Print the errors to the console
            print(f"\n{'='*50}")
            print("PCELL PARAMETER ERRORS:")
            print("ERRORS:\n • " + "\n\n • ".join( # Each traceback is separated by '\n\n'
                  map(lambda err: ''.join(traceback.format_exception(err)),
                      errors)))
            print(f"{'='*50}\n")

    def insert_instance(self, params=None, trans:pya.Trans=None):
        '''Inserts an instance of the underlying PCell with the given parameters and optional transformation.
-       params: dict of {param_name: value} for the parameters of the underlying PCell instance. If none, will use the defaults.
-       trans: pya.Trans object '''
        if trans is None: trans = pya.Trans(0, 0)
        if params is None: params = self.src_parameters() # current parameter values from underlying PCell
        # TODO: Make it possible to use an existing cell instance in the layout,
        # using *change_pcell_parameters* creating new instances through add_pcell_variant,
        # to preserve any manual edits to the cell instance.
        pcell_var_id = self.layout.add_pcell_variant(self.src_lib,
                                            self.src_pcell_decl.id(), 
                                            params)
        self.cell.insert(pya.CellInstArray(pcell_var_id, trans))

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


#   def _details_from_layout(self, source_pcell_name):
    #     '''Find the existing cell in the currently active layout with the given name.
        
    #     Returns: dict of it's parameter values {param_name: value}, 
    #     or raises an exception if the cell cannot be found or is not a PCell instance.
    #     '''
    #     # Search currently active layout for source_pcell_name
    #     app = pya.Application.instance()
    #     if not app:
    #         raise Exception("No running instance of KLayout found.")
        
    #     mw = app.main_window()
    #     if not mw:
    #         raise Exception("No main window found in KLayout.")
        
    #     view = mw.current_view()
    #     if not view:
    #         raise Exception("No current view found in KLayout.")
        
    #     cv = view.active_cellview()
    #     if not cv.is_valid():
    #         raise Exception("No active cellview found in KLayout.")
        
    #     layout = cv.layout()
    #     cell = layout.cell(source_pcell_name)
    #     if not cell:
    #         raise Exception(f"Cell '{source_pcell_name}' not found in currently active layout.")
                
    #     if not cell.is_pcell_variant():
    #         raise Exception(f"'{source_pcell_name}' is not a PCell instance.")
        
    #     print(f"Found PCell '{source_pcell_name}' in the currently active layout.")
        
    #     # Actual parameters values for this instance, to use as defaults in the wrapper PCell parameters:
    #     return cell.pcell_parameters_by_name()

# =======================================
        
# # Search currently active layout for source_pcell_name
# existing_cell = self.layout.cell(self.cell_name)


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
    pass