import pya

class RightTriangle(pya.PCellDeclarationHelper):
  '''
  Right triangle with the origin at the right angle corner. 
  The acute corners are at (width, 0) and (0, height)
  width and height can be negative to change the triangle orientation. They are specified in microns.
  '''

  def __init__(self):

    super().__init__()
    # declare the parameters
    self.param("l", self.TypeLayer, "Layer", default=pya.LayerInfo(1, 0))
    self.param("width", self.TypeInt, "Width", default=200)
    self.param("height", self.TypeInt, "Height", default=200)
    
    

  def display_text_impl(self):
    # Provide a descriptive text for the cell
  
    width = str(self.width)
    height = str(self.height)
      
    return f"Right Triangle: width {width}, height {height}"
  
  def coerce_parameters_impl(self):
    pass
  
  def produce_impl(self):
    pts = [pya.Point(0, 0), pya.Point(self.width / self.layout.dbu, 0), pya.Point(0, self.height / self.layout.dbu)]
    self.cell.shapes(self.l_layer).insert(pya.Polygon(pts))
    #Debug:
    # print(f"Shape count: {self.cell.shapes(self.l_layer).size()}")
    # print(f"Width: {self.width} ")
    # print(f"Height: {self.height} ")
    # print(f"Cell bbox: {self.cell.bbox()}")

  def can_create_from_shape_impl(self):
    '''determine if we have a shape that we can use to derive the PCell parameters from and return true in that case'''
    return False
  
  def parameters_from_shape_impl(self):
    pass
    
  def transformation_from_shape_impl(self):
    pass
    
if __name__ == "__main__":
  #triangle = RightTriangle()
  #triangle.produce_impl()
  RightTriangle().produce_impl()
  # optional:
  # def can_create_from_shape_impl(self):
  #   TODO: 
  # 
  # optional:
  # def parameters_from_shape_impl(self):
  #   TODO: change parameters using set_x to reflect the parameter for the
  #   given shape
  # 
  # optional:
  # def transformation_from_shape_impl(self):
  #   TODO: return a RBA::Trans object for the initial transformation of
  #   the instance
  # 
  # optional:
  # def wants_lazy_evaluation(self):
  #   TODO: return "True" here if the PCell takes a long time to compute.
  #   In lazy mode, the user has to acknowledge parameter changes before 
  #   they are executed.
