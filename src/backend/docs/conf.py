import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "SécuApp Backend"
author = "RUELLE Thomas, DEMIR Erdem, CLAUS Gatien, MOMBAERTS Ciaran"
release = "1.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

templates_path = ["_templates"]
exclude_patterns = ["_build"]

html_theme = "alabaster"
