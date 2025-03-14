
# numpy hook to ensure all required components are included
hiddenimports = [
    'numpy.core.multiarray',
    'numpy.core.numeric',
    'numpy.core.umath',
    'numpy.core._methods',
    'numpy.lib.format',
    'numpy.random',
    'numpy.linalg',
    'numpy.core._dtype_ctypes',
]

# Make sure numpy's C extensions are properly collected
import numpy
import os
from PyInstaller.utils.hooks import collect_dynamic_libs

binaries = collect_dynamic_libs('numpy')

# Safely add data files only if they exist
datas = []
numpy_dir = os.path.dirname(numpy.__file__)
for txt_file in ['LICENSE.txt', 'THANKS.txt']:
    full_path = os.path.join(numpy_dir, txt_file)
    if os.path.exists(full_path):
        datas.append((full_path, 'numpy'))
