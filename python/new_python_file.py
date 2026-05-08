import pya

# CHANGE THIS to your actual file path
input_path = r"C:\Users\allis\Documents\Stanford\SrabantiLab\HEMT\learning2.oas"
output_path = r"C:\Users\allis\Documents\Stanford\SrabantiLab\HEMT\RECOVERED_FILE.oas"

layout = pya.Layout()
options = pya.LoadLayoutOptions()
options.warn_level = 0 # Suppress non-critical warnings

try:
    print(f"Attempting to read: {input_path}")

    layout.read(input_path, options)
    
    # If it gets here, the layout is in memory.
    # We will now delete any cell that has an invalid or empty name.
    for cell in layout.each_cell():
        if not cell.name or cell.name.strip() == "":
            print(f"Deleting nameless cell index: {cell.cell_index()}")
            layout.delete_cell(cell.cell_index())
            
    layout.write(output_path)
    print("Success! File saved to: " + output_path)
except Exception as e:
    print("Failed to read file: " + str(e))