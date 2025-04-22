from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator
import os



@contextmanager
def move_to_isolated_dir(dirname:str='workdir_TIMESTAMP') -> Generator[None, None, None]:
    """
    Context to create a unique isolated directory for working in, and move cd into it (and exit on context end)

    Args:
        prefix (str): Prefix for the directory name. A timestamp will be appended to this prefix.
    """
    original_dir = Path.cwd()
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dirname = dirname.replace("TIMESTAMP", timestamp)
        
        isolated_dir = Path(dirname)
        isolated_dir.mkdir(exist_ok=True, parents=True)
        os.chdir(isolated_dir)
        yield
    finally:
        os.chdir(original_dir)
        # Optionally, remove the isolated directory if empty
        if not os.listdir(isolated_dir):
            os.rmdir(isolated_dir)


def make_str_pathsafe(s: str) -> str:
    """convert a string to one that is pathsafe"""
    return s.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')