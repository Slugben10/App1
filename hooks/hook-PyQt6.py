
# PyQt6 hook for better compatibility
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all PyQt6 submodules to ensure complete functionality
hiddenimports = collect_submodules('PyQt6')

# Collect all data files for PyQt6
datas = collect_data_files('PyQt6')
