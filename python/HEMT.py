import pya
from pya_helpers import move_box_to, create_text
from datetime import datetime
import traceback
"""
"""    

class HEMT(pya.PCellDeclarationHelper):

  def __init__(self):
    """ Constructor: provides the PCell parameter definitions. """
    try: 

      super().__init__()
    
      # Declare parameters
      # Dimensions are in microns
      #    source-drain separation = sep_SG + channel_len + sep_GD
      self.param("sep_GD", self.TypeDouble, "Gate-Drain Spacing", hidden = False, default = 5.0)
      self.param("sep_SG", self.TypeDouble, "Source-Gate Spacing", hidden = False, default = 1.0)
      self.param("gate_len", self.TypeDouble, "Gate Channel Length", hidden = False, default = 1.0)
      # Width of active area (device width)
      self.param("width", self.TypeInt, "Active Area Width", hidden = False, default = 100)
      # How long S, D pads are in the direction perpendicular to the gate finger, and the side of the square gate pad
      self.param("pad_size", self.TypeInt, "Pad Size", hidden = False, default = 100)
      self.param("text_height", self.TypeInt, "Text Height", hidden = False, default = 10)
      # Whether the gate is positioned above or below source in y.
      self.param("flip_vert", self.TypeBoolean, "Flip Vertically?", hidden = False, default = False)
      self.param("border", self.TypeInt, "Border between S, D pads and edge of mesa", hidden = False, default = 7)
      self.param("radius", self.TypeInt, "Round Corners: radius", hidden = False, default = 7)
      # Important for reducing gate capacitance 
      self.param("sep_G_mesa", self.TypeInt, "Gate Pad - Mesa Spacing", hidden = False, default = 10)
      # Make the gate finger wider as it goes over the edge of the mesa, 
      # to reduce the likelihood that the tip peels off, or that the electrical connection between 
      # gate pad and gate finger is broken at the mesa edge.
      self.param("tip_width", self.TypeDouble, "Width of Gate Finger Tips", hidden = False, default = 3.0)
      # I use border/2 for the gate finger overreach. (One end of the gate finger extends to the gate pad, the other
      # extends beyond the mesa border by border/2, to ensure the gate can cut off current paths
      # self.param("gate_overreach", self.TypeInt, "Min Overreach of Gate Finger Beyond Mesa Edge", hidden = False, default = 10)

      # Internal variables (not parameters)
      self.__err_msg = '' # For debugging: store error messages to display in the layout if produce_impl fails, so that I can see them without needing to check the console output.
      
      print(f'Initialized an instance of HEMT() at {datetime.now()}')
    except Exception as e:
      print(f"Error in HEMT __init__: \n{traceback.format_exc()}")
      self.__err_msg = f"Error in HEMT __init__: {e}\n"
  
  def display_text_impl(self):
    """
    PCell interface implementation
    """
    try: 
      text = f'HEMT(GD = {self.sep_GD} um, SG = {self.sep_SG} um, gate len = {self.gate_len} um)'
      print('HEMT instance display_text called: ' + text)
    except Exception as e:
      print(f"Error in display_text_impl: \n{traceback.format_exc()}")
      text = f'HEMT ({e})'
    
    if self.__err_msg:
        text += f'\nERRORS:\n {self.__err_msg}'

    return text
  
  def coerce_parameters_impl(self):
    """
    PCell interface implementation
    """
    pass
 
  def cell_name_impl(self):
    return f'HEMT(SG:{self.sep_SG} um, G:{self.gate_len} um, GD:{self.sep_GD} um)'
  
  def produce_impl(self):
  
    """
    Implementation of the PCell interface: generates the layouts
    """
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
      gate_len = self.gate_len / self.layout.dbu
      # DEBUG:
      print(f'\nHEMT: width has type {type(self.width)} and value {self.width!r}\n')
      width = self.width / self.layout.dbu
      pad_size = self.pad_size / self.layout.dbu
      border = self.border / self.layout.dbu
      sep_G_mesa = self.sep_G_mesa / self.layout.dbu
      tip_width = self.tip_width / self.layout.dbu
      radius = self.radius / self.layout.dbu
      text_height = self.text_height / self.layout.dbu


      # Useful dimensions
      sep_SD = sep_SG + gate_len + sep_GD # source-drain separation
      
      # ------- Draw HEMT -------------
      
      
      # Draw Mesa
      #   mesa extent in y is (width + 2*mesa_border)
      mesa_height = (width + 2*border)
      #   mesa extent in x is (2*pad_size + sep_SD + + 2*mesa_border)
      mesa_width  = (sep_SD + 2*(pad_size + border))
      # Lower left corner of the mesa is at the origin:
      mesa = pya.Box(0, 0, mesa_width, mesa_height)
      self.cell.shapes(mesa_layer).insert(mesa)

      # Draw Source, Drain contacts

      # Source contact
      source = pya.Box(pad_size, width)
      source = move_box_to(source, (border, border))
      self.cell.shapes(contacts).insert(source)
      
      # Drain contact
      drain = move_box_to(source, ((border + pad_size + sep_SD),
                                    border))
      self.cell.shapes(contacts).insert(drain)

      # Gate
      gate_parts = [] # gate components to merge

      #   Gate pad:
      #   Approximately square, with vertical side length pad_size.
      #   With a separation of sep_G_mesa from the mesa edge.
      tip_extend = (tip_width - gate_len)/2
      if tip_extend < 0: tip_extend = 0
      gate_pad = pya.Box(pad_size + sep_SG + gate_len + tip_extend, pad_size)
      gate_pad = move_box_to(gate_pad, (border, (mesa_height + sep_G_mesa)))
      gate_parts.append(gate_pad)

      #   Gate finger
      gate_finger = pya.Box(gate_len, (mesa_height + sep_G_mesa + border/2))
      gate_finger = move_box_to(gate_finger, 
                                (source.right + sep_SG,
                                 mesa.bottom - border/2))
      gate_parts.append(gate_finger)

      #  Tips for gate finger, if tip_width is greater than gate_len.
      # Wider tips are less likely to peel off, ensuring that
        #   the gate can cut off current paths right at the edge of the mesa.
      # Tips are rectanges placed at the ends of the gate finger. 
      # They overlap with the mesa border by border/2. 
      if tip_width > gate_len:
        # The upper tip extends to the gate pad. 
        upper_tip = pya.Box(tip_width, sep_G_mesa + border)
        upper_tip = move_box_to(upper_tip,
                                [gate_finger.bbox().center().x, mesa_height + sep_G_mesa/2],
                                pos='Center')
        gate_parts.append(upper_tip)
        # The lower tip extends beyond the mesa border by just border/2.
        lower_tip = pya.Box(tip_width, border)
        lower_tip = move_box_to(lower_tip,
                                [gate_finger.bbox().center().x, 0],
                                pos='Center')
        gate_parts.append(lower_tip)

      #  Merge into one polgon for the gate.
      gate = pya.Region(gate_parts).merge()

      # ------  Flip Vertically ------ 
      # if flip_vert, make it so gate pad is below source pad:
      if self.flip_vert:
        gate.transform(pya.Trans.M0) # Mirror about x-axis
        # Mirroring about the global x-axis messes up the y-position, moving the center
        # of the gate finger from mesa.bbox().center().y to -mesa.bbox().center().y. 
        # This undoes that shift, so the gate stays where is should be.
        gate.move(dy = 2 * mesa.bbox().center().y)


      # Insert gate into cell layout
      self.cell.shapes(gate_pads).insert(gate)

      # ------ Round corners -----------------------
      for layer in [mesa_layer, contacts, gate_pads]:
        for shape in self.cell.shapes(layer):
            rounded_shape = shape.polygon.round_corners(radius, radius, n=32)
            self.cell.shapes(layer).insert(rounded_shape)
            self.cell.shapes(layer).erase(shape)

      # ------  Add text labels for source and drain ------ 
      for label, pad in [('Source', source), ('Drain', drain)]:
         # Position the text next to the  source and drain pads, 
         # centered in x, and with a separation of self.text_height/2 
         # from the edge of the mesa
         x = pad.bbox().center().x
         y = mesa.bbox().bottom - text_height if not self.flip_vert else mesa.bbox().top + text_height

         # Create the text region and insert it into the contacts layer 
         text = create_text(label, height_um = self.text_height, pos=(x, y), dbu=self.layout.dbu) # x, y in dbu
         self.cell.shapes(contacts).insert(text) 

      # Add text label for gate, centered in the gate pad
      pos = gate_pad.bbox().center()
      if self.flip_vert:
        # Move the text to the new position of the gate pad. 
        # The vertical flip does not update the position of gate_pad
        pos.y -= 2*(gate_pad.bbox().center().y - mesa.bbox().center().y)
      text = create_text('Gate', height_um = self.text_height, pos=pos, dbu=self.layout.dbu)
      # Subtract the text from the gate region, so that the text is negative space in the gate metal.
      gate = pya.Region(self.cell.shapes(gate_pads))
      gate -= text 
      # Insert edited gate pad
      self.cell.shapes(gate_pads).clear()
      self.cell.shapes(gate_pads).insert(gate)
       
      print('Finished executing HEMT instance produce_impl()')
  
      # #  Tips for gate finger, if wide_tips is True
      # if self.wide_tips:
      #   # Tip:
      #   # Points describing the outline of the tip
      #   pts = [pya.Point()]
      #   tip = pya.Polgon(pts)
      #   gate_parts.append(tip)
      #   # Next I want to mirror the tip about the x-axis (m0), to place another tip at the other end of the gate finger
      #   # since the gate finger extends the same distance above and below the x-axis. 
      #   m0 = pya.Trans(pya.Trans.M0)
      #   gate_parts.append(tip.transformed(m0))
        
    except Exception as e:
      print(f"produce_impl error: \n{traceback.format_exc()}")
      self.__err_msg += f"produce_impl error: {e}\n"
      # Insert a default shape to prevent empty cell
      self.cell.shapes(self.layout.layer(0, 0)).insert(pya.Box(0, 0, 100, 100))
   