import pya
from datetime import datetime
import traceback

from helpers.pya_helpers import create_text
    
class CircularHEMT(pya.PCellDeclarationHelper):
    """

    """  
    def __init__(self):
        """ Constructor: provides the PCell parameter definitions. """
        try: 

            super().__init__()
        
            # Declare parameters
            self.param("SG_sep", self.TypeDouble, "Source-Gate Separation (µm)", default=1)
            self.param("gate_len", self.TypeDouble, "Gate Length (µm)", default=1)
            self.param("DG_sep", self.TypeDouble, "Drain-Gate Separation (µm)", default=5)
            self.param("drain_rad", self.TypeDouble, "Drain Pad Radius (µm)", default=50)
            self.param("gate_rad", self.TypeDouble, "Gate Pad Radius (µm)", default=50)
            self.param("source_width", self.TypeDouble, "Source Pad Width (µm)", default=50)
            self.param("rounding", self.TypeDouble, "Corner Rounding Radius (µm)", default=10)
            self.param("slot_width", self.TypeDouble, "Width of Slot in Source Pad (µm)", default=10)
            self.param("gate_connector_width", self.TypeDouble, "Width of Gate through Slot in Source Pad (µm)", default=5)
            self.param("text_height", self.TypeDouble, "Text Height (µm)", default=25)
            self.param("num_points", self.TypeInt, "Number of Points to Resolve a Circle", default=64)
             
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
        # Reset:
        self.__err_msg = ''
        
        try:
            # Make sure that slot_width is bigger than gate_connector_width
            if self.slot_width < self.gate_connector_width:
                 self.slot_width = self.gate_connector_width + 2
            
        except Exception as e:
            print(f"Error in Template coerce_parameters_impl: \n{traceback.format_exc()}")
            self.__err_msg += f"coerce_parameters_impl: {e}\n"



    def display_text_impl(self):
        """
        PCell interface implementation
        """
        try: 
            text = f'CircularHEMT(SG={self.SG_sep}, G={self.gate_len}, DG={self.DG_sep})'
            print('CircularHEMT instance display_text called: ' + text)
        except Exception as e:
            print(f"Error in display_text_impl: \n{traceback.format_exc()}")
            text = f'CircularHEMT (?)'
            self.__err_msg += f"display_text_impl: {e}\n"
            
        if self.__err_msg:
                text += f'\nERRORS:\n {self.__err_msg}'

        return text
        
    
    def produce_impl(self):
    
        """
        Implementation of the PCell interface: generates the layouts
        """
        dbu = self.layout.dbu
                    
        # Convert to database units
        def to_dbu(um):
            return int(um / dbu)
        
        try: 
            # Create copies of the dimensions in database units for easier use in layout generation
            SG_sep = int(self.SG_sep / dbu)
            gate_len = int(self.gate_len / dbu)
            DG_sep = int(self.DG_sep / dbu)
            drain_rad = int(self.drain_rad / dbu)
            gate_rad = int(self.gate_rad / dbu)
            source_width = int(self.source_width / dbu)
            rounding = int(self.rounding / dbu)
            slot_width = int(self.slot_width / dbu)
            gate_connector_width = int(self.gate_connector_width / dbu)
            
            text_height = self.text_height
            num_points = self.num_points
            
            
            # ------- Define Layers -------------
            mesa_layer     = self.layout.layer(1, 0, "mesa") # Mesa etch (inverse)
            contacts_layer = self.layout.layer(2, 0, "contacts") # S, D contacts
            gate_layer     = self.layout.layer(3, 0, "gate_pads") # Gate pads and finger

            # ------- Draw CircularHEMT -------------
            
            # Calculate mesa radius
            mesa_radius = drain_rad + DG_sep + gate_len + SG_sep + source_width
            
            # Step 1: Draw mesa circle
            mesa = pya.Region()
            mesa.insert(pya.Polygon.ellipse(
                pya.Box(-mesa_radius, -mesa_radius, 
                         mesa_radius,  mesa_radius), num_points))
            
            # Create notch in mesa to reduce gate capacitance
            mesa_notch = pya.Box(source_width, slot_width)
            mesa_notch = pya.Region(
                mesa_notch.moved(
                dx = -mesa_radius - mesa_notch.left, 
                dy=0)
                )
            mesa = mesa - mesa_notch
            
            # Step 2: Draw drain pad (circle on contacts layer)
            drain_pad = pya.Region()
            drain_pad.insert(pya.Polygon.ellipse(
                pya.Box(-drain_rad, -drain_rad, 
                         drain_rad,  drain_rad), num_points))
            
            # Step 3: Draw source pad (outline of circle on contacts layer)
            outer_circle = pya.Region()
            outer_circle.insert(pya.Polygon.ellipse(
                pya.Box(-mesa_radius, -mesa_radius, 
                         mesa_radius, mesa_radius), num_points))
            
            inner_circle = pya.Region()
            inner_radius = mesa_radius - source_width
            inner_circle.insert(pya.Polygon.ellipse(
                pya.Box(-inner_radius, -inner_radius, 
                        inner_radius, inner_radius), num_points))
            
            source_pad = outer_circle - inner_circle
            
            # Create slot in source pad
            slot_rect = pya.Region(
                pya.Box(-mesa_radius, -slot_width//2,
                         0,            slot_width//2)
                                  )
            source_pad = source_pad - slot_rect
            
            # Step 5: Draw gate  
            gate = pya.Region()
            
            # Gate pad circle
            gate_pad_center_x = -int(mesa_radius + gate_rad * 1.1)
            gate_pad = pya.Polygon.ellipse(
                pya.Box(gate_pad_center_x - gate_rad, -gate_rad,
                        gate_pad_center_x + gate_rad, gate_rad), num_points)
            gate.insert(gate_pad)
            
            # Gate ring (outline of circle on gate layer)
            gate_inner_radius = drain_rad + DG_sep
            gate_outer_radius = gate_inner_radius + gate_len

            gate_outer = pya.Region(
                pya.Polygon.ellipse(
                    pya.Box(-gate_outer_radius, -gate_outer_radius,
                             gate_outer_radius,  gate_outer_radius),
                    num_points
                    )
                )
            
            gate_inner = pya.Region(
                pya.Polygon.ellipse(
                    pya.Box(-gate_inner_radius, -gate_inner_radius,
                             gate_inner_radius,  gate_inner_radius),
                    num_points
                    )
                )
            
            gate_ring = gate_outer - gate_inner
            gate.insert(gate_ring)
            
            # Connect gate pad to gate ring
            connector_length = gate_rad + source_width + SG_sep + gate_len //2
            connector = pya.Box(connector_length, gate_connector_width)
            # Position the right side of the connector box so it's embeded in the gate ring finger
            connector.move(
                dx = -(drain_rad + DG_sep + gate_len //2) - connector.right,
                dy=0
            )
            gate.insert(connector)
            
            # Merge all gate parts into one gate
            gate.merge()
            
            # Step 6: Round all shapes (mesa, contacts, gate)
            geometry = {'mesa':    pya.Region(),
                       'contacts': pya.Region(),
                       'gate':     pya.Region()
                       }
            
            # Round the polygons in each layer's pya.Region.
            for layer_name, region in zip(('mesa', 'contacts', 'gate'), (mesa, drain_pad + source_pad, gate)):
                for poly in region.each():
                    rounded = poly.round_corners(rounding, rounding, 32)
                    geometry[layer_name].insert(rounded)
            
           
            # Step 10: Create text
            text_G = create_text("G", text_height, dbu, 
                                pos=(gate_pad_center_x, 0))
            text_D = create_text("D", text_height, dbu, 
                                pos=(0, 0))
            text_S = create_text("S", text_height, dbu, 
                                pos=(mesa_radius - source_width//2, 0))
            
            # Subtract text from respective layers
            geometry['gate'] -= text_G
            geometry['contacts'] -= text_D + text_S
            
            # Add bridge rectangle to connect the center of "D" to rest of drain pad
            bridge_width = int(text_height/dbu * 0.1)  # Make bridge proportional to text
            bridge_height = int(text_height/dbu * 0.5)
            bridge = pya.Region(pya.Box(-bridge_width//2, -bridge_height,
                                         bridge_width//2, 0))
            geometry['contacts'] += bridge

            # Insert all shapes into the cell
            for layer, name in zip((mesa_layer, contacts_layer, gate_layer), ('mesa', 'contacts', 'gate')):
                self.cell.shapes(layer).insert(geometry[name].merge()) # Call merge just before inserting to clean up any overlaps
                        
        except Exception as e:
            print(f"produce_impl error error: \n{traceback.format_exc()}")
            self.__err_msg += f"produce_impl error: {e}\n"
            # Insert a default shape to prevent empty cell
            self.cell.shapes(self.layout.layer(0, 0)).insert(pya.Box(0, 0, 100/dbu, 100/dbu))