"""
Debug.py - control message verbosity for debugging
Copyright (C) Delta Controls Inc.
"""

from pathlib import Path

debug_level = 0
# load default from file
try:
    default_level_path = Path(__file__).parent.absolute() / "default_debug_level"
    with open(default_level_path, "r") as default_file:
        debug_level = int(default_file.read())
except:
    pass

def set_debug_level(level):
    """Change debug level for current python process."""
    global debug_level
    debug_level = level

def get_debug_level():
    """Retrieve debug level for current python process."""
    return debug_level

def printd(message, level=2):
    """
    Conditionally print a message based on current debug_level
   
    Arguments:
    level -- print priority, in range 0 - 3
            0 -- always print, even in release
            1 -- print in debug but not release
            2, 3 -- print only if debug_level has been set to a higher value
        Note: Avoid using level 0 or 1 for recurring messages as this can flood the console.  
    """
    if debug_level >= level:
        print(message)
