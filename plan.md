# My plans for improving the code base.

## Currently:
I have Wrapper < Sweep

Sweep does expression parameters as well as Parameter Sweeping.

## Option 1: Mixins

### pya.PCellDeclarationHelper < **Wrapper**

Wrapper takes a Klayout PCell in it's init function, exposes the params of the underlying PCell, and has methods for adding variants of the underlying PCell. 

### Wrapper < **InteractiveWrapper**

Instances of the underlying PCell that are drawn by the code are not accessible to being manipulated in the GUI. InteractiveWrapper adds guideboxes for each instance, handles that let the user (indirectly) move or rotate instances drawn in the code. 

### Wrapper < **ExprWrapper** 

ExprWrapper redefines parameters so they can take expressions of other parameters as input. 

### ExprWrapper, InteractiveWrapper < **Sweep**

Defines parameter sweep.

### Meanwhile, to define a new PCell in a library that wraps an existing PCell:
 `custom_pcell(source_pcell_name:str, lib_name:str)`

Defines a new class inside the function whose `.__init__()` takes nothing, as expected by a PCell class definition. The `source_pcell_name` and `lib_name` are passed to the `__init__` of the choosen Wrapper class.  

## Option 2: Simple Inheritance

Wrapper < InteractiveWrapper < ExprWrapper < Sweep

-> No diamond inheritance tree. 


##  Features

Guide boxes

Sub-array for ParamSweep
- Discovery of translations, rotations (and default params?) from existing Cell in the Layout? (Convert to PCell command)
- Sub-array section in GUI:
    -  How many in the sub-array: integer
    - check box for guideboxes. When active, the other guideboxes disappear. Each instance in the subarray can be translated or rotated. Even if device structures are placed in sub-arrays, the usual guide-boxes should still represent individual instances of the underlying PCell. 
    - OR 
    
- Or a syntax that accepts a translation and rotation for a second instance. Rows and cols function as before. Add a readonly param: '# Duplicates' to compute `rows * cols * #instances-in-sub-array`

