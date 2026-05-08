import pya
from datetime import datetime
import traceback
    
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
            
            # Expose parameters of the underlying PCell for user input
            if expose_params: self.expose_src_params()

            print(f'Initialized an instance of {source_pcell_name}_Wrapper() at {datetime.now()}')
        except Exception as e:
            print(f"Error in {source_pcell_name}_Wrapper __init__: \n{traceback.format_exc()}")
            
    def __discover_param_decls(self, use_existing=False):
        ''' Discover parameter declarations of the underlying PCell. 
        Returns the paramter declarations of the underlying PCell in a dictionary {param_name: param_decl}.
    
        if use_existing: Overide default parameter values with actual parameter values from an existing PCell instance in the layout.
.       '''
        # If we were able to get actual parameter values from an existing cell instance in the layout, 
        # use those as the defaults in the wrapper PCell, so that the initial generated layout will match the existing cell instance. If not, just use the default values from the underlying PCell.
        param_values = self._details_from_layout(self.src_pcell_name) if self.use_existing else None
        
        # Store each parameter declaration from the underlying PCell in a dictionary
        src_params = {}
        for param_decl in self.src_pcell_decl.get_parameters():
            if param_values: 
                overide_default = param_values.get(param_decl.name)
                param_decl.default = overide_default

            src_params[param_decl.name] = param_decl
        
        return src_params
            
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
        copied_params = []
        for name, param_decl in self.src_params.values():
            # Checks that we haven't already copied this parameter over (in case expose_src_params is called multiple times).
            if not self.hasattr(name):
                self.__copy_param(param_decl)
                copied_params.append(name)
                
        print(f"Copied parameters into '{self.src_pcell_name}_Wrapper wrapper: {copied_params}")  
            
    def __copy_param(self, param_decl):
        '''
        Helper function to copy a parameter declaration from the underlying PCell into this wrapper PCell, 
        by defining a parameter with the same attributes in this wrapper PCell.
        '''
        choices = list(zip(param_decl.choice_descriptions(), param_decl.choice_values())) if len(param_decl.choice_values()) > 0 else None
        # Copying over choices is complicated, because you have to check if the underlying PCell defined 
        # choices for this parameter, and only assign the choices argument if it did.
        # It will throw an error if you assign choices=None.
        if choices is not None:
            self.param(param_decl.name, param_decl.type, param_decl.description, 
                        default=param_decl.default, hidden=param_decl.hidden, readonly=param_decl.readonly,
                        unit=param_decl.unit, max_value=param_decl.max_value, min_value=param_decl.min_value,
                        choices=choices)
        else:
            self.param(param_decl.name, param_decl.type, param_decl.description, 
                        default=param_decl.default, hidden=param_decl.hidden, readonly=param_decl.readonly,
                        unit=param_decl.unit, max_value=param_decl.max_value, min_value=param_decl.min_value)
        
    def coerce_parameters_impl(self):
        """Called before display_text_impl and produce_impl. """
        pass

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
        
    def convert_to_type(self, value_str, param_type):
        """Convert string to proper parameter type"""
        try:
            # Int
            if param_type == pya.PCellParameterDeclaration.TypeInt:
                type_name = 'Int' # for error messages
                return int(value_str)
            # Double
            elif param_type == pya.PCellParameterDeclaration.TypeDouble:
                type_name = 'Double' # for error messages
                return float(value_str)
            # Boolean
            elif param_type == pya.PCellParameterDeclaration.TypeBoolean:
                type_name = 'Boolean' # for error messages
                if value_str.lower() in ('true', '1', 'yes'):
                    return True
                elif value_str.lower() in ('false', '0', 'no'):
                    return False
                else:
                    raise ValueError(f"Invalid boolean value: '{value_str}'. Expected True/False, 1/0, yes/no.")
            # String
            elif param_type == pya.PCellParameterDeclaration.TypeString:
                return value_str
            # Layer
            elif param_type == pya.PCellParameterDeclaration.TypeLayer:
                type_name = 'LayerInfo' # for error messages
                # Expecting format "layer_num/datatype_num", e.g. "1/0"
                parts = value_str.split('/')
                if len(parts) != 2:
                    raise ValueError(f"Invalid layer format: '{value_str}'. Expected 'layer_num/datatype_num'.")
                try:
                    layer_num = int(parts[0])
                    datatype_num = int(parts[1])
                except ValueError as e:
                    e.args = [f"Invalid layer format: '{value_str}'. Expected 'layer_num/datatype_num'."] + e.args[1:]
                    raise 
                return pya.LayerInfo(layer_num, datatype_num)
            else:
                # For complex types, return as-is and hope for the best
                return value_str
        except ValueError as e:
            e.add_note(f'Error converting "{value_str}" to type {type_name}.')
            raise
    
    


            
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