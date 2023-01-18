from Delta import LoadableModules
import inspect
from pathlib import Path
import shutil

INSTALLER_DIR = "/usr/delta/python_interfaces/install"
FIL_DATA_DIR = "/var/lib/DeltaControls/Files"
LOADABLE_DIR = "/usr/delta/python_interfaces/loadable"

def find_module_in_callstack():
    """
    Return name and fil instance of loadable module in callstack.
    """
    for fr in inspect.stack():
        full_path = Path(fr.filename).resolve()
        try:
            rel_path = full_path.relative_to(Path(LoadableModules.LOADABLE_DIR))
        except ValueError:
            continue 
        # check if this is a script in a directory with the same name
        if str(rel_path.parent) == str(rel_path.stem):
            return rel_path.stem, LoadableModules.get_fil_instance(rel_path.stem)

    raise Exception(f"Module not found in {LoadableModules.LOADABLE_DIR}")


def get_module_data_dir(module_name=None):
    """
    Build path to data directory for a module.

    Arguments:
        module_name -- (optional) Get data directory for this module.  Not needed when called 
            from within a loadable module, in this case it will be retrieved from the callstack.
    """
    if module_name is None:
        module_name, fil_instance = find_module_in_callstack()

    module_data_dir = Path(LOADABLE_DIR) / ".data" / module_name
    module_data_dir.mkdir(parents=True, exist_ok=True)

    return module_data_dir


def clear_module_data_dir(module_name=None):
    """Delete all files in a module's data directory."""
    shutil.rmtree(get_module_data_dir(module_name=module_name))

