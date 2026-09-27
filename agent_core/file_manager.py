import os
import shutil
import json
import pickle
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import stat

class FileManager:
    """Handles all file operations with backup and safety features"""
    
    def __init__(self, project_path: Union[str, Path]):
        """
        Initialize FileManager with project path
        
        Args:
            project_path: Path to the project directory
        """
        self.project_path = Path(project_path)
        self.backup_dir = self.project_path / '.agent_backup'
        self.temp_dir = self.project_path / '.agent_temp'
        self._create_directories()
        
    def _create_directories(self):
        """Create necessary directories if they don't exist"""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Create .gitignore for backup directory
        gitignore_path = self.backup_dir / '.gitignore'
        if not gitignore_path.exists():
            with open(gitignore_path, 'w') as f:
                f.write('# Ignore all files in backup directory\n*\n!.gitignore\n')
    
    def _get_backup_path(self, file_path: str) -> Path:
        """Get the backup path for a file"""
        return self.backup_dir / file_path
    
    def _get_temp_path(self, file_path: str) -> Path:
        """Get the temporary path for a file"""
        return self.temp_dir / file_path
    
    def _ensure_directory_exists(self, file_path: Path):
        """Ensure the directory for a file exists"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _backup_file(self, file_path: str) -> bool:
        """
        Create a backup of a file before modification
        
        Args:
            file_path: Path to the file to backup
            
        Returns:
            bool: True if backup was successful, False otherwise
        """
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return False
        
        backup_path = self._get_backup_path(file_path)
        self._ensure_directory_exists(backup_path)
        
        try:
            # Create timestamped backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_with_timestamp = backup_path.parent / f"{backup_path.stem}_{timestamp}{backup_path.suffix}"
            shutil.copy2(full_path, backup_with_timestamp)
            
            # Also keep a latest backup
            shutil.copy2(full_path, backup_path)
            return True
        except Exception as e:
            print(f"Error backing up {file_path}: {e}")
            return False
    
    def read_file(self, file_path: str, encoding: str = 'utf-8') -> Optional[str]:
        """
        Read file content
        
        Args:
            file_path: Path to the file
            encoding: File encoding (default: utf-8)
            
        Returns:
            str: File content or None if file doesn't exist
        """
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return None
        
        try:
            with open(full_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(full_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                return None
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return None
    
    def read_file_binary(self, file_path: str) -> Optional[bytes]:
        """
        Read file content as binary
        
        Args:
            file_path: Path to the file
            
        Returns:
            bytes: File content or None if file doesn't exist
        """
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return None
        
        try:
            with open(full_path, 'rb') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading binary file {file_path}: {e}")
            return None
    
    def write_file(self, file_path: str, content: Union[str, bytes], 
                   backup: bool = True, encoding: str = 'utf-8') -> bool:
        """
        Write content to file with optional backup
        
        Args:
            file_path: Path to the file
            content: Content to write (string or bytes)
            backup: Whether to create a backup (default: True)
            encoding: File encoding (default: utf-8)
            
        Returns:
            bool: True if write was successful, False otherwise
        """
        full_path = self.project_path / file_path
        
        # Create backup if requested and file exists
        if backup and full_path.exists():
            self._backup_file(file_path)
        
        # Ensure directory exists
        self._ensure_directory_exists(full_path)
        
        try:
            # Write to temp file first for safety
            temp_path = self._get_temp_path(file_path)
            self._ensure_directory_exists(temp_path)
            
            if isinstance(content, str):
                with open(temp_path, 'w', encoding=encoding) as f:
                    f.write(content)
            else:
                with open(temp_path, 'wb') as f:
                    f.write(content)
            
            # Move temp file to target
            shutil.move(temp_path, full_path)
            return True
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass
            return False
    
    def create_file(self, file_path: str, content: Union[str, bytes] = "", 
                    encoding: str = 'utf-8') -> bool:
        """
        Create a new file
        
        Args:
            file_path: Path to the file
            content: Content to write (default: empty)
            encoding: File encoding (default: utf-8)
            
        Returns:
            bool: True if file was created, False otherwise
        """
        full_path = self.project_path / file_path
        
        if full_path.exists():
            print(f"Warning: {file_path} already exists. Use update_file instead.")
            return False
        
        return self.write_file(file_path, content, backup=False, encoding=encoding)
    
    def update_file(self, file_path: str, content: Union[str, bytes],
                    encoding: str = 'utf-8') -> bool:
        """
        Update an existing file
        
        Args:
            file_path: Path to the file
            content: Content to write
            encoding: File encoding (default: utf-8)
            
        Returns:
            bool: True if file was updated, False otherwise
        """
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            print(f"Warning: {file_path} doesn't exist. Use create_file instead.")
            return False
        
        return self.write_file(file_path, content, backup=True, encoding=encoding)
    
    def delete_file(self, file_path: str, backup: bool = True) -> bool:
        """
        Delete a file with optional backup
        
        Args:
            file_path: Path to the file
            backup: Whether to create a backup (default: True)
            
        Returns:
            bool: True if file was deleted, False otherwise
        """
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return False
        
        # Create backup if requested
        if backup:
            self._backup_file(file_path)
        
        try:
            full_path.unlink()
            return True
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
            return False
    
    def move_file(self, source_path: str, dest_path: str, backup: bool = True) -> bool:
        """
        Move/rename a file
        
        Args:
            source_path: Source file path
            dest_path: Destination file path
            backup: Whether to create a backup (default: True)
            
        Returns:
            bool: True if file was moved, False otherwise
        """
        source_full = self.project_path / source_path
        dest_full = self.project_path / dest_path
        
        if not source_full.exists():
            return False
        
        # Create backup of destination if it exists
        if backup and dest_full.exists():
            self._backup_file(dest_path)
        
        try:
            # Ensure destination directory exists
            self._ensure_directory_exists(dest_full)
            shutil.move(source_full, dest_full)
            return True
        except Exception as e:
            print(f"Error moving {source_path} to {dest_path}: {e}")
            return False
    
    def copy_file(self, source_path: str, dest_path: str, backup: bool = True) -> bool:
        """
        Copy a file
        
        Args:
            source_path: Source file path
            dest_path: Destination file path
            backup: Whether to create a backup (default: True)
            
        Returns:
            bool: True if file was copied, False otherwise
        """
        source_full = self.project_path / source_path
        dest_full = self.project_path / dest_path
        
        if not source_full.exists():
            return False
        
        # Create backup of destination if it exists
        if backup and dest_full.exists():
            self._backup_file(dest_path)
        
        try:
            # Ensure destination directory exists
            self._ensure_directory_exists(dest_full)
            shutil.copy2(source_full, dest_full)
            return True
        except Exception as e:
            print(f"Error copying {source_path} to {dest_path}: {e}")
            return False
    
    def list_files(self, pattern: str = "*", recursive: bool = True, 
                   exclude_dirs: List[str] = None) -> List[str]:
        """
        List all files in project matching pattern
        
        Args:
            pattern: File pattern to match (default: "*")
            recursive: Whether to search recursively (default: True)
            exclude_dirs: Directories to exclude (default: ['.agent_backup', '.agent_temp', '.git'])
            
        Returns:
            List[str]: List of file paths relative to project root
        """
        if exclude_dirs is None:
            exclude_dirs = ['.agent_backup', '.agent_temp', '.git', '__pycache__', 'node_modules']
        
        files = []
        search_pattern = f"**/{pattern}" if recursive else pattern
        
        for file_path in self.project_path.glob(search_pattern):
            if not file_path.is_file():
                continue
            
            # Skip excluded directories
            if any(excluded in str(file_path.parent) for excluded in exclude_dirs):
                continue
            
            # Skip hidden files (optional)
            if file_path.name.startswith('.'):
                continue
            
            rel_path = str(file_path.relative_to(self.project_path))
            files.append(rel_path)
        
        return sorted(files)
    
    def list_files_by_extension(self, extensions: List[str], recursive: bool = True) -> Dict[str, List[str]]:
        """
        List files grouped by extension
        
        Args:
            extensions: List of file extensions to include (e.g., ['.py', '.js'])
            recursive: Whether to search recursively
            
        Returns:
            Dict[str, List[str]]: Dictionary with extensions as keys and file lists as values
        """
        result = {ext: [] for ext in extensions}
        
        for file_path in self.list_files(recursive=recursive):
            for ext in extensions:
                if file_path.endswith(ext):
                    result[ext].append(file_path)
                    break
        
        return result
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists
        
        Args:
            file_path: Path to the file
            
        Returns:
            bool: True if file exists, False otherwise
        """
        return (self.project_path / file_path).exists()
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get file information
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dict[str, Any]: File information or error dict
        """
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return {"exists": False, "error": "File not found"}
        
        try:
            stat_info = full_path.stat()
            return {
                "exists": True,
                "size": stat_info.st_size,
                "size_mb": round(stat_info.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                "accessed": datetime.fromtimestamp(stat_info.st_atime).isoformat(),
                "is_file": full_path.is_file(),
                "is_dir": full_path.is_dir(),
                "extension": full_path.suffix,
                "name": full_path.name,
                "path": str(full_path.relative_to(self.project_path))
            }
        except Exception as e:
            return {"exists": True, "error": str(e)}
    
    def get_directory_structure(self, max_depth: int = None) -> Dict[str, Any]:
        """
        Get the directory structure as a nested dictionary
        
        Args:
            max_depth: Maximum depth to traverse (None for unlimited)
            
        Returns:
            Dict[str, Any]: Directory structure
        """
        def build_structure(path: Path, current_depth: int = 0) -> Dict[str, Any]:
            if max_depth is not None and current_depth >= max_depth:
                return {"type": "max_depth_reached"}
            
            structure = {}
            
            for item in path.iterdir():
                if item.name.startswith('.'):
                    continue
                
                if item.is_dir():
                    structure[item.name] = build_structure(item, current_depth + 1)
                else:
                    structure[item.name] = {
                        "type": "file",
                        "size": item.stat().st_size,
                        "extension": item.suffix
                    }
            
            return structure
        
        return build_structure(self.project_path)
    
    def restore_backup(self, file_path: str, backup_timestamp: str = None) -> bool:
        """
        Restore a file from backup
        
        Args:
            file_path: Path to the file
            backup_timestamp: Specific backup timestamp to restore (None for latest)
            
        Returns:
            bool: True if restore was successful, False otherwise
        """
        backup_path = self._get_backup_path(file_path)
        
        if not backup_path.exists():
            return False
        
        # If specific timestamp is provided
        if backup_timestamp:
            backup_with_timestamp = backup_path.parent / f"{backup_path.stem}_{backup_timestamp}{backup_path.suffix}"
            if backup_with_timestamp.exists():
                shutil.copy2(backup_with_timestamp, self.project_path / file_path)
                return True
            return False
        
        # Restore latest backup
        try:
            shutil.copy2(backup_path, self.project_path / file_path)
            return True
        except Exception as e:
            print(f"Error restoring {file_path}: {e}")
            return False
    
    def list_backups(self, file_path: str = None) -> List[Dict[str, Any]]:
        """
        List available backups
        
        Args:
            file_path: Specific file path to list backups for (None for all)
            
        Returns:
            List[Dict[str, Any]]: List of backup information
        """
        backups = []
        
        if file_path:
            backup_path = self._get_backup_path(file_path)
            if backup_path.exists():
                # Get timestamped backups
                backup_dir = backup_path.parent
                pattern = f"{backup_path.stem}_*{backup_path.suffix}"
                for backup_file in backup_dir.glob(pattern):
                    timestamp = backup_file.stem.split('_')[-1]
                    backups.append({
                        "file": file_path,
                        "timestamp": timestamp,
                        "size": backup_file.stat().st_size,
                        "created": datetime.fromtimestamp(backup_file.stat().st_ctime).isoformat()
                    })
        else:
            # List all backups
            for backup_file in self.backup_dir.rglob('*'):
                if backup_file.is_file() and not backup_file.name.startswith('.'):
                    rel_path = backup_file.relative_to(self.backup_dir)
                    backups.append({
                        "file": str(rel_path),
                        "size": backup_file.stat().st_size,
                        "modified": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
                    })
        
        return sorted(backups, key=lambda x: x.get('created', x.get('modified', '')), reverse=True)
    
    def clean_backups(self, days_old: int = 30) -> int:
        """
        Remove backups older than specified days
        
        Args:
            days_old: Number of days to keep (default: 30)
            
        Returns:
            int: Number of backups removed
        """
        removed = 0
        cutoff = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        
        for backup_file in self.backup_dir.rglob('*'):
            if backup_file.is_file() and not backup_file.name.startswith('.'):
                if backup_file.stat().st_mtime < cutoff:
                    try:
                        backup_file.unlink()
                        removed += 1
                    except Exception as e:
                        print(f"Error removing backup {backup_file}: {e}")
        
        return removed
    
    def read_json(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read JSON file
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Dict[str, Any]: Parsed JSON content or None if error
        """
        content = self.read_file(file_path)
        if content is None:
            return None
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from {file_path}: {e}")
            return None
    
    def write_json(self, file_path: str, data: Dict[str, Any], 
                   indent: int = 2, backup: bool = True) -> bool:
        """
        Write JSON file
        
        Args:
            file_path: Path to JSON file
            data: Data to write
            indent: JSON indentation (default: 2)
            backup: Whether to create a backup (default: True)
            
        Returns:
            bool: True if write was successful, False otherwise
        """
        try:
            json_str = json.dumps(data, indent=indent, default=str)
            return self.write_file(file_path, json_str, backup=backup)
        except Exception as e:
            print(f"Error writing JSON to {file_path}: {e}")
            return False
    
    def read_pickle(self, file_path: str) -> Optional[Any]:
        """
        Read pickle file
        
        Args:
            file_path: Path to pickle file
            
        Returns:
            Any: Pickled object or None if error
        """
        content = self.read_file_binary(file_path)
        if content is None:
            return None
        
        try:
            return pickle.loads(content)
        except Exception as e:
            print(f"Error unpickling from {file_path}: {e}")
            return None
    
    def write_pickle(self, file_path: str, data: Any, backup: bool = True) -> bool:
        """
        Write pickle file
        
        Args:
            file_path: Path to pickle file
            data: Data to pickle
            backup: Whether to create a backup (default: True)
            
        Returns:
            bool: True if write was successful, False otherwise
        """
        try:
            pickle_bytes = pickle.dumps(data)
            return self.write_file(file_path, pickle_bytes, backup=backup)
        except Exception as e:
            print(f"Error pickling to {file_path}: {e}")
            return False
    
    def get_file_hash(self, file_path: str, algorithm: str = 'md5') -> Optional[str]:
        """
        Get file hash
        
        Args:
            file_path: Path to the file
            algorithm: Hash algorithm (default: 'md5')
            
        Returns:
            str: File hash or None if error
        """
        import hashlib
        
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return None
        
        try:
            hash_func = getattr(hashlib, algorithm)()
            with open(full_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            print(f"Error calculating hash for {file_path}: {e}")
            return None
    
    def is_binary_file(self, file_path: str) -> bool:
        """
        Check if a file is binary
        
        Args:
            file_path: Path to the file
            
        Returns:
            bool: True if file is binary, False otherwise
        """
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return False
        
        try:
            with open(full_path, 'rb') as f:
                chunk = f.read(1024)
                # Check for null bytes
                if b'\0' in chunk:
                    return True
                # Check for non-printable characters
                text_characters = bytearray([7, 8, 9, 10, 12, 13, 27]) + bytearray(range(0x20, 0x7f))
                return bool(chunk.translate(None, text_characters))
        except Exception:
            return True
    
    def get_relative_path(self, file_path: str) -> str:
        """
        Get relative path from project root
        
        Args:
            file_path: Absolute or relative path
            
        Returns:
            str: Relative path from project root
        """
        path = Path(file_path)
        try:
            return str(path.relative_to(self.project_path))
        except ValueError:
            return file_path
    
    def get_absolute_path(self, file_path: str) -> Path:
        """
        Get absolute path
        
        Args:
            file_path: Relative path
            
        Returns:
            Path: Absolute path
        """
        return (self.project_path / file_path).resolve()