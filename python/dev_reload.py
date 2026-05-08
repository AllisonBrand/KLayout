import importlib
import sys

def reload_modules(py_modules):
    """Reload the python modules, or import them if they haven't been already.

    py_modules: iterable of module names to reload/import, e.g. ['ParamSweep', 'MyPCell']

    Returns a dictionary mapping module names to their module objects.
    """
    
    loaded_modules = {}
    for module_name in py_modules:

        if module_name in sys.modules: # Reload the module if it's already imported
            module = importlib.reload(sys.modules[module_name])
            print(f"Reloaded python module: {module_name}")
            
        else: # Otherwise import the module
            module = importlib.import_module(module_name)
            print(f"Imported python module: {module_name}")

        loaded_modules[module_name] = module
        
    return loaded_modules

if __name__ == '__main__':
  # Allows me to get around Klayout's caching behavior during development by reloading this module when I run it, 
  # so that I can test edits to this module without needing to restart Klayout.
  import importlib
  import sys
  if 'dev_reload' in sys.modules: # Reload this module if it's already imported
          importlib.reload(sys.modules['dev_reload'])
          print('Reloaded python module: dev_reload')