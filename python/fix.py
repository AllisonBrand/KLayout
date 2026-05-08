# import gdsast

# input_file = 'C:\Users\allis\Documents\Stanford\SrabantiLab\HEMT\learning.gds'

# with open(input_file, "rb") as f:
#     gds = gdsast.load(f)

# for cell in gds.cells:
#     if not cell.name:
#         print(f"Found cell with empty name at index: {cell.index}")

import sys

for name, module in sys.modules.items():
    print(name, module)