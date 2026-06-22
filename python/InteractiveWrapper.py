'''
This is a Mixin class, that adds functionality for 
guideboxes for each instance of the underlying PCell drawn in produce_impl,
allowing the user to move or rotate instances of the underlying PCell in the GUI.
'''
class ParamSweep(pya.PCellDeclarationHelper):
    
    def __init__(self):
        super().__init__()
        # ... other params ...
        
        self.param("show_guides", self.TypeBoolean, 
                  "Show Position Guides (movable handles)", 
                  default=False)  # Off by default
        
        self.param("_guide_handles", self.TypeList, "Position Guides",
                  default=[], hidden=True)
        
        self.param("_handle_map", self.TypeString, "Handle mapping",
                  default="{}", hidden=True)
        
        self.param("_manual_transforms", self.TypeString,
                  "Manual position adjustments", default="{}", hidden=True)
    
    def coerce_parameters_impl(self):
        """Detect moved handles and update transforms"""
        import json
        
        if not self.show_guides or not self._guide_handles:
            return
        
        # Get handle mapping
        handle_map = json.loads(self._handle_map) if self._handle_map else {}
        
        transforms = {}
        
        for idx, handle in enumerate(self._guide_handles):
            # Get (row, col) for this handle
            key = handle_map.get(str(idx))
            if not key:
                continue
            
            row_idx, col_idx = map(int, key.split(','))
            
            # Calculate default position
            x_default = col_idx * self.col_spacing
            y_default = row_idx * self.row_spacing
            
            # Get actual position from handle
            if isinstance(handle, pya.DBox):
                actual_pos = handle.center()
            elif isinstance(handle, pya.DPoint):
                actual_pos = handle
            else:
                continue
            
            # Calculate displacement
            dx = actual_pos.x - x_default
            dy = actual_pos.y - y_default
            
            # Store if moved
            if abs(dx) > 0.01 or abs(dy) > 0.01:
                transforms[key] = {'dx': dx, 'dy': dy}
        
        # Update manual transforms
        self._manual_transforms = json.dumps(transforms)
    
    def produce_impl(self):
        """Generate sweep with movable position guides"""
        import json
        dbu = self.layout.dbu
        
        transforms = json.loads(self._manual_transforms) if self._manual_transforms else {}
        
        guide_handles = []
        handle_map = {}
        idx = 0
        
        for col_idx in range(self.n_cols):
            for row_idx in range(self.n_rows):
                # Default position
                x_default = col_idx * self.col_spacing
                y_default = row_idx * self.row_spacing
                
                # Apply transform
                key = f"{row_idx},{col_idx}"
                if key in transforms:
                    x_pos = x_default + transforms[key]['dx']
                    y_pos = y_default + transforms[key]['dy']
                else:
                    x_pos, y_pos = x_default, y_default
                
                # Create instance
                params = self.params_at_index(row_idx, col_idx)
                inst = self.insert_labeled_variant(
                    params,
                    pya.Trans(int(x_pos / dbu), int(y_pos / dbu))
                )
                
                # Create guide handle
                if self.show_guides:
                    handle_size = 10.0  # 10µm box
                    handle = pya.DBox(
                        x_pos - handle_size/2, y_pos - handle_size/2,
                        x_pos + handle_size/2, y_pos + handle_size/2
                    )
                    guide_handles.append(handle)
                    handle_map[str(idx)] = key
                
                idx += 1
        
        # Update parameters
        self._guide_handles = guide_handles
        self._handle_map = json.dumps(handle_map)