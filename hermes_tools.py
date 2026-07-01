"""
Local implementation of hermes_tools functions for autonomous Hermes system.

This module provides the same functionality that would normally come from the
hermes-tools package, but is included directly in the repository for portability.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

def read_file(path: str, limit: int = 500, offset: int = 1) -> Dict[str, Any]:
    """
    Read a file with line-based pagination.
    
    Args:
        path: Path to the file
        limit: Maximum number of lines to read
        offset: Line number to start from (1-indexed)
    
    Returns:
        Dict with content, total_lines, file_size, etc.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # Apply pagination
        start_line = offset - 1
        end_line = min(start_line + limit, total_lines)
        
        selected_lines = lines[start_line:end_line]
        content = ''.join(selected_lines)
        
        # Get file size
        file_size = os.path.getsize(path)
        
        return {
            "content": content,
            "total_lines": total_lines,
            "file_size": file_size,
            "truncated": end_line < total_lines,
            "hint": f"Use offset={end_line + 1} to continue reading (showing {start_line + 1}-{end_line} of {total_lines} lines)",
            "is_binary": False,
            "is_image": False
        }
    except FileNotFoundError:
        return {"error": f"File not found: {path}"}
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}

def write_file(path: str, content: str, cross_profile: bool = False) -> Dict[str, Any]:
    """
    Write content to a file, completely replacing existing content.
    
    Args:
        path: Path to the file
        content: Content to write
        cross_profile: Allow writing to other profiles (default False)
    
    Returns:
        Dict with status and file path
    """
    try:
        # Ensure directory exists
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "status": "success",
            "path": path,
            "message": f"File written successfully to {path}"
        }
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as e:
        return {"error": f"Failed to write file: {str(e)}"}

def patch(path: str, old_string: str, new_string: str, replace_all: bool = False) -> Dict[str, Any]:
    """
    Targeted find-and-replace edits in files.
    
    Args:
        path: Path to the file to edit
        old_string: String to find and replace
        new_string: Replacement text
        replace_all: Replace all occurrences instead of requiring a unique match
    
    Returns:
        Dict with operation result and unified diff
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Simple string replacement
        if replace_all:
            new_content = original_content.replace(old_string, new_string)
        else:
            if old_string not in original_content:
                return {
                    "status": "error",
                    "message": f"String not found: {old_string[:50]}...",
                    "path": path
                }
            new_content = original_content.replace(old_string, new_string, 1)
        
        if new_content == original_content:
            return {
                "status": "no_change",
                "message": "No changes needed",
                "path": path
            }
        
        # Write the modified content
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return {
            "status": "success",
            "path": path,
            "message": "File patched successfully",
            "replaced": new_content != original_content
        }
    except Exception as e:
        return {"error": f"Failed to patch file: {str(e)}"}

def skill_manage(action: str, name: str, content: str = None, old_string: str = None, new_string: str = None, replace_all: bool = False, category: str = None, file_path: str = None, file_content: str = None) -> Dict[str, Any]:
    """
    Manage skills (create, update, delete, write_file, remove_file).
    
    Args:
        action: 'create', 'patch', 'edit', 'delete', 'write_file', or 'remove_file'
        name: Skill name (lowercase, hyphens/underscores, max 64 chars)
        content: Full SKILL.md content (for create/edit)
        old_string: Text to find and replace (for patch/edit)
        new_string: Replacement text (for patch/edit)
        replace_all: Replace all occurrences instead of requiring unique match (for patch/edit)
        category: Optional category/domain for organizing the skill
        file_path: Path to a supporting file within the skill directory
        file_content: Content for the supporting file (for write_file)
    
    Returns:
        Dict with operation result
    """
    try:
        # Skills are stored in ~/.hermes/skills/ by default
        skills_dir = Path.home() / '.hermes' / 'skills'
        skills_dir.mkdir(parents=True, exist_ok=True)
        
        if category:
            skill_dir = skills_dir / category / name
        else:
            skill_dir = skills_dir / name
        
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        SKILL_MD = skill_dir / "SKILL.md"
        
        if action == "create":
            # Create new skill
            if content is None:
                return {"error": "Content is required for create action"}
            
            if SKILL_MD.exists():
                return {"error": f"Skill '{name}' already exists"}
            
            with open(SKILL_MD, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "status": "success",
                "action": "create",
                "skill_dir": str(skill_dir),
                "message": f"Skill '{name}' created successfully"
            }
        
        elif action in ["patch", "edit"]:
            # Update existing skill
            if not SKILL_MD.exists():
                return {"error": f"Skill '{name}' does not exist"}
            
            with open(SKILL_MD, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            if old_string is None:
                return {"error": "old_string is required for patch/edit action"}
            
            # Simple string replacement
            if replace_all:
                new_content = original_content.replace(old_string, new_string)
            else:
                if old_string not in original_content:
                    return {
                        "status": "error",
                        "message": f"String not found: {old_string[:50]}...",
                        "skill": name
                    }
                new_content = original_content.replace(old_string, new_string, 1)
            
            if new_content == original_content:
                return {
                    "status": "no_change",
                    "message": "No changes needed",
                    "skill": name
                }
            
            with open(SKILL_MD, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return {
                "status": "success",
                "action": action,
                "skill": name,
                "message": f"Skill '{name}' updated successfully"
            }
        
        elif action == "delete":
            # Delete skill
            if not skill_dir.exists():
                return {"error": f"Skill '{name}' does not exist"}
            
            import shutil
            shutil.rmtree(skill_dir)
            
            return {
                "status": "success",
                "action": "delete",
                "skill": name,
                "message": f"Skill '{name}' deleted successfully"
            }
        
        elif action == "write_file":
            # Write file within skill directory
            if file_path is None:
                return {"error": "file_path is required for write_file action"}
            
            file_path = skill_dir / file_path
            
            if file_content is None:
                return {"error": "file_content is required for write_file action"}
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file_content)
            
            return {
                "status": "success",
                "action": "write_file",
                "skill": name,
                "file_path": str(file_path),
                "message": f"File written to skill '{name}'"
            }
        
        elif action == "remove_file":
            # Remove file from skill directory
            if file_path is None:
                return {"error": "file_path is required for remove_file action"}
            
            file_path = skill_dir / file_path
            
            if not file_path.exists():
                return {"error": f"File not found in skill '{name}': {file_path}"}
            
            file_path.unlink()
            
            return {
                "status": "success",
                "action": "remove_file",
                "skill": name,
                "file_path": str(file_path),
                "message": f"File removed from skill '{name}'"
            }
        
        else:
            return {"error": f"Unknown action: {action}"}
    
    except Exception as e:
        return {"error": f"Failed to manage skill: {str(e)}"}

def web_search(query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Search the web for information.
    
    Args:
        query: Search query
        limit: Maximum number of results
    
    Returns:
        Dict with search results
    """
    try:
        # This is a simplified implementation
        # For production use, integrate with actual search API
        # For now, return a placeholder response
        
        return {
            "data": {
                "web": [
                    {
                        "url": f"https://example.com/search?q={query}",
                        "title": f"Search Results for '{query}'",
                        "description": "This is a placeholder response. For actual web search, integrate with an API like Tavily, Google Search API, or similar."
                    }
                ]
            },
            "message": "Web search placeholder - integrate with actual search API for production use"
        }
    except Exception as e:
        return {"error": f"Failed to perform web search: {str(e)}"}
