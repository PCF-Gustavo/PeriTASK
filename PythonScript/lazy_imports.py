# from functools import cache
# import importlib

# @cache
# def lazy_import(module_name):
#     return importlib.import_module(module_name)

# def lazy_imports(*imports):
#     g = globals()
#     for item in imports:
#         if isinstance(item, str):
#             g[item] = lazy_import(item)
#         else:
#             module_name, attr_name = item
#             g[attr_name] = getattr(
#                 lazy_import(module_name),
#                 attr_name
#             )

import importlib

_lazy_modules = {}

def lazy_import(module_name):
    if module_name not in _lazy_modules:
        _lazy_modules[module_name] = importlib.import_module(module_name)
    return _lazy_modules[module_name]


def lazy_imports(module_name, attr_name=None):
    modulo = lazy_import(module_name)
    if attr_name:
        return getattr(modulo, attr_name)
    return modulo