# KlayoutPymacros
 a backup for my Klayout Pymacros


Wrapper is a class that finds the underlying PCell declaration, reads it's parameters into the Wrapper PCell, and provides functions for adding instaces of the underlying PCell. Sweep is a child of Wrapper, and adds parameters for definining a sweep, has methods for parsing the sweep, including complicated expressions of other parameters. 