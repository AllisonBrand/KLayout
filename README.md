**This is a tool in Klayout scripting that can generate a parameter sweep PCell for any test structure that’s defined as a PCell.  This custom PCell lets the user create a parametric sweep as an array of labeled variations in the .gds file.**
The parameter sweep PCell exposes the parameters of the underlying PCell in its GUI window, and it made to have an intuitive UI. 

Users can define a row sweep and a column sweep. Numeric parameters can be defined as expressions of other parameters. This makes it possible to, for instance, define a sweep of gate-drain separation for a HEMT or FET structure, and then have the gate-source separation be a fixed fraction of that. Every variant of the pcell parameters is given a label with text geometry, which can be customized with syntax like "GD spacing: {GD_spacing}", where `GD_spacing` is a parameter name. The user can specify an array of duplicates for each labeled variant. 

# Usage:
Once you have the .lym file set up, it only requires two additional lines of code to create a parameter sweep PCell from an existing PCell!

You can copy-paste `pymacros/SweepLib.lym` to get started. Then add:

```
  sweep_pcell = Sweep.custom_sweep_pcell('PCell_Name', src_lib_name)
  lib.layout().register_pcell('Parameter_Sweep_PCell_Name', sweep_pcell())
```
(Here, lib is an instance of the `pya.Library` child class, SweepLib. )

*Your new PCell will show up as a new PCell in the library you registered it with the next time you open Klayout!*

# Implementation

The code is split into the following class hierachy:

**Wrapper < Sweep**

A Wrapper can wrap any PCell to create a new PCell the extends the functionality.
Wrapper is a class that finds the underlying PCell declaration, reads it's parameters into the Wrapper PCell, and provides functions for adding instaces of the underlying PCell. 

Sweep is a child of Wrapper, and adds parameters for definining a sweep, has methods for parsing the sweep, including complicated expressions of other parameters. 

# Advice:
1. When developing a PCell, NEVER save the .gds file when there is an un-caught error. Doing so can corrupt the cell tree in your .gds file, so Klayout will refuse to ever again open the file. Commercial software for working with .gds files will likely be able to open it, but you loose Klayout-specifc functionality. (I discovered this the hard way).

 I suggest wrapping the contents of each function that might error in a try-except block, and putting in some error geometry in case of a failure in `produce_impl`.
 
 Also, Klayout caches the python modules, so if you edit your python code while Klayout is open, you will not be able to see the changes in the GUI unless you reload them manually. I use python's `importlib` for this, you can see how in the `dev` branch.
 My MyLib .lym file in the `dev` branch loads all my PCells scripts to reload the python modules and MyLib library everytime the code is run, so edits to the code can be applied to the active layout without restarting Klayout.

2. Putting your long code into .py files instead of .lym files allows the IDE to show the beautiful code highlighting that you are used to!


