from pathlib import Path

def print_tree(path, prefix="", ignore_folders=None):
    if ignore_folders is None:
        ignore_folders = ["__pycache__","logs",".ipynb_checkpoints","log1","loggers","log","pythonAPI-main"]
    
    path = Path(path)
    # Filter the directory items to exclude ignored folders
    items = [item for item in path.iterdir() if item.name not in ignore_folders]
    # Sort items so files/folders appear consistently
    items.sort(key=lambda p: p.name.lower())
    
    for i, item in enumerate(items):
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{item.name}")
        
        if item.is_dir():
            # Extend the prefix for subdirectories
            extension = "    " if is_last else "│   "
            print_tree(item, prefix + extension, ignore_folders)

# Example usage
print_tree("D:\\StockMarket\\StockMarket\\scripts\\claude\\experiment8\\")