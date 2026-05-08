import pya
from datetime import datetime
import traceback
    

class Template(pya.PCellDeclarationHelper):
    """

    """  
    def __init__(self):
        """ Constructor: provides the PCell parameter definitions. """
        try: 

            super().__init__()
        
            # Declare parameters
            self.param("l", self.TypeLayer, "Layer", default=pya.LayerInfo(1, 0))
            self.param("text", self.TypeString, "Text", default='Row Var: {r}, Col Var: {c}')
            
            # Internal Variables: 

            # For debugging:
            self.__err_msg = ''  # store error messages to display in the layout if produce_impl fails, so that I can see them without needing to check the console output.

            # Cache for detecting changes
            self.__prev = None
            
            print(f'Initialized an instance of Template() at {datetime.now()}')
        except Exception as e:
            print(f"Error in Template __init__: \n{traceback.format_exc()}")
            self.__err_msg = f"Error in Template __init__: {e}\n"
    
    def coerce_parameters_impl(self):
        """
        Called before display_text_impl and produce_impl.
        """
        try:
                pass
        except Exception as e:
            print(f"Error in Template coerce_parameters_impl: \n{traceback.format_exc()}")
            self.__err_msg += f"coerce_parameters_impl: {e}\n"



    def display_text_impl(self):
        """
        PCell interface implementation
        """
        try: 
            text = f'Template()'
            print('Template instance display_text called: ' + text)
        except Exception as e:
            print(f"Error in display_text_impl: \n{traceback.format_exc()}")
            text = f'Template (?)'
            self.__err_msg += f"display_text_impl: {e}\n"
            
        if self.__err_msg:
                text += f'\nERRORS:\n {self.__err_msg}'

        return text
    

    
    def can_create_from_shape_impl(self):
        """
        PCell interface implementation
        """
        try: 
            print('Template instance can_create_from_shape_impl called.')
            return False
        except Exception as e:
            print(f"Error in can_create_from_shape_impl: \n{traceback.format_exc()}")
            self.__err_msg += f"can_create_from_shape_impl: {e}\n"
            return False
    
    def parameters_from_shape_impl(self):
        """
        PCell interface implementation
        """
        try:
                pass # Change this!
        except Exception as e:
            print(f"Error in Template parameters_from_shape_impl: \n{traceback.format_exc()}")
            self.__err_msg += f"parameters_from_shape_impl: {e}\n"
    
    def transformation_from_shape_impl(self):
        """
        PCell interface implementation
        """
        try:
                return pya.Trans() # Change this!
        except Exception as e:
            print(f"Error in Template transformation_from_shape_impl: \n{traceback.format_exc()}")
            self.__err_msg += f"transformation_from_shape_impl: {e}\n"
            return pya.Trans()
        
        
        
    
    def produce_impl(self):
    
        """
        Implementation of the PCell interface: generates the layouts
        """
        dbu = self.layout.dbu
        try: 
            
            # ------- Create Layers -------------
            #   Mesa etch (inverse)
            mesa_layer = self.layout.layer(1, 0, "mesa")
            #   S, D contacts
            contacts   = self.layout.layer(2, 0, "contacts")
            #   Gate pads and finger
            gate_pads  = self.layout.layer(3, 0, "gate_pads")


            # Create copies of all the dimensions in database units for easier use in layout generation
            sep_GD = self.sep_GD / self.layout.dbu
            sep_SG = self.sep_SG / self.layout.dbu

            # ------- Draw ParrText -------------
            
                
        except Exception as e:
            print(f"produce_impl error error: \n{traceback.format_exc()}")
            self.__err_msg += f"produce_impl error: {e}\n"
            # Insert a default shape to prevent empty cell
            self.cell.shapes(self.layout.layer(0, 0)).insert(pya.Box(0, 0, 100/dbu, 100/dbu))