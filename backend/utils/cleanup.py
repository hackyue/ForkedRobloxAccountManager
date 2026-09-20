import os
import time
from typing import List, Optional
from utils.paths import get_data_folder, get_cache_folder

def cleanup_temp_files(folders: Optional[List[str]] = None, max_age_seconds: float = 0.0) -> int:
    if folders is None:
        folders = [get_data_folder(), get_cache_folder()]
    
    cleaned_count = 0
    now = time.time()
    
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        try:
            entries = os.listdir(folder)
        except OSError:
            continue
        
        for entry in entries:
            if not entry.endswith(".tmp"):
                continue
            
            full_path = os.path.join(folder, entry)
            if not os.path.isfile(full_path):
                continue
            
            if max_age_seconds > 0:
                try:
                    mtime = os.path.getmtime(full_path)
                    if (now - mtime) < max_age_seconds:
                        continue
                except OSError:
                    continue
            
            try:
                os.unlink(full_path)
                cleaned_count += 1
            except (OSError, PermissionError):
                pass
                
    return cleaned_count
