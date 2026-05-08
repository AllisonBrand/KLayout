import pya
from datetime import datetime
import traceback

from HEMT import HEMT

class HEMT_Array(HEMT):
    
    def __init__(self):
        super().__init__()
        
        # Section header in the GUI.
        self.param("_header", self.TypeNone, " Array Settings ".center(32, '═')) 
        self.param("pad_between", self.TypeDouble, "Space Between HEMTs (um)", default = 40.0)
        self.param("repeats", self.TypeInt, "# of Duplicates (even)", default = 10)
        
        print(f'Initialized an instance of HEMT_Array() at {datetime.now()}')
    
    def coerce_parameters_impl(self):
        
        # Ensure self.repeats is even and at least 2, rounding up:
        self.repeats = ((self.repeats + 1)  // 2) * 2 if self.repeats > 1 else 2
        
        super().coerce_parameters_impl()
        
    def cell_name_impl(self):
        return super().cell_name_impl().replace('HEMT', f'HEMT_Array{self.repeats}x')
    
    def display_text_impl(self):
        return super().display_text_impl().replace('HEMT', f'HEMT_Array{self.repeats}x')
    
    def produce_impl(self):
        '''
        An array of duplicate HEMTs, efficiently packed.
        Two rows, the number of columns is determined by *self.repeats*.
        Uses the flip_vert ability of HEMT() to flip the gate pad to be below the source, drain pads,
        so the top row's gate pads slot into the spaces between the bottom row's gate pads.
        '''
        try:
            dbu = self.layout.dbu
            
            # Get the library containing HEMT
            lib = pya.Library.library_by_name("MyLib")  # Replace with your library name
            if not lib:
                raise Exception("Library not found")
            
            hemt_pcell = lib.layout().pcell_declaration("HEMT")
            if not hemt_pcell:
                raise Exception("HEMT PCell not found")
            
            params = {
                'sep_GD': self.sep_GD,
                'sep_SG': self.sep_SG,
                'gate_len': self.gate_len,
                'width': self.width,
                'pad_size': self.pad_size,
                'text_height': self.text_height,
                'flip_vert': False,  # Not flipped
                'border': self.border,
                'radius': self.radius,
                'sep_G_mesa': self.sep_G_mesa,
                'tip_width': self.tip_width
            }
            
            # Create first HEMT variant (normal orientation) in the main layout
            hemt_id = self.layout.add_pcell_variant(lib, hemt_pcell.id(), params)
            # Create second HEMT variant (flipped) in the main layout
            hemt_flipped_id = self.layout.add_pcell_variant(lib, hemt_pcell.id(), params | {'flip_vert': True})
            
            # Calculate shifts
            hemt_cell = self.layout.cell(hemt_id) # Fetch the HEMT cell object to access it's bbox
            gate_bbox = hemt_cell.bbox(self.layout.layer(3, 0, "gate_pads"))
            shift_x = int(self.pad_between / dbu) + gate_bbox.width()
            shift_y = int(self.pad_between / dbu) + hemt_cell.bbox().top
            spacing = 2 * shift_x
            
            # Insert multiple instances of HEMT to form two rows, neatly stacked
            for i in range(self.repeats // 2):
                x = i * spacing
                
                # Normal instance
                self.cell.insert(pya.CellInstArray(hemt_id, pya.Trans(x, 0)))
                
                # Flipped instance  
                self.cell.insert(pya.CellInstArray(hemt_flipped_id, pya.Trans(x + shift_x, shift_y)))
            
            print('Finished executing HEMT_Array instance produce_impl()')
            
        except Exception as e:
            print(f"HEMT_Array produce_impl error: \n{traceback.format_exc()}")
            # Insert a default shape to prevent empty cell
            self.cell.shapes(self.layout.layer(0, 0)).insert(pya.Box(0, 0, 100, 100))
            
            
            
            
        #   # Create a helper cell for the HEMT pair (adds a sibling cell to the same layout this PCell is in)
        #     HEMT_pair = self.layout.create_cell("HEMT_pair")