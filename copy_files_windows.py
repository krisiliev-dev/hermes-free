#!/usr/bin/env python3
"""
Script to copy all necessary files from hermes-free repository to Hermes installation.
This ensures all autonomous system files are in the correct locations.
"""

import os
import shutil
import sys

def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

def copy_file(src, dst):
    """Copy a file with error handling"""
    try:
        dst_dir = os.path.dirname(dst)
        if dst_dir and not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        
        shutil.copy2(src, dst)
        print(f"  ✅ Copied: {os.path.basename(src)} → {dst}")
        return True
    except Exception as e:
        print(f"  ❌ FAILED to copy {src} to {dst}: {e}")
        return False

def main():
    print_section("Hermes-Free File Copier")
    
    # Detect paths based on OS
    if sys.platform == 'win32':
        hermes_install = os.path.expandvars(r'%LOCALAPPDATA%\hermes')
        repo_root = os.path.dirname(os.path.abspath(__file__))
    else:
        hermes_install = os.path.expanduser('~/.hermes')
        repo_root = os.path.dirname(os.path.abspath(__file__))
    
    print(f"\nHermes installation directory: {hermes_install}")
    print(f"Repository root: {repo_root}")
    
    # Check if Hermes installation exists
    if not os.path.exists(hermes_install):
        print(f"\n❌ ERROR: Hermes installation not found at {hermes_install}")
        print("   Please install Hermes first, then run this script.")
        return 1
    
    # Check if repo_root exists
    if not os.path.exists(repo_root):
        print(f"\n❌ ERROR: Repository root not found at {repo_root}")
        print("   Please run this script from the hermes-free directory.")
        return 1
    
    # Files to copy
    files_to_copy = {
        # Core autonomous system files
        f"{repo_root}/agent/agent_init.py": f"{hermes_install}/hermes-agent/agent/agent_init.py",
        f"{repo_root}/agent/rate_limit_wrapper.py": f"{hermes_install}/hermes-agent/agent/rate_limit_wrapper.py",
        f"{repo_root}/agent/model_rater.py": f"{hermes_install}/hermes-agent/agent/model_rater.py",
        f"{repo_root}/agent/auto_improve.py": f"{hermes_install}/hermes-agent/agent/auto_improve.py",
        
        # hermes_tools.py (CRITICAL - must be in repo root)
        f"{repo_root}/hermes_tools.py": f"{hermes_install}/hermes-agent/hermes_tools.py",
        
        # External monitor
        f"{repo_root}/rate_limit_monitor_external.py": f"{hermes_install}/hermes-agent/rate_limit_monitor_external.py",
        
        # Config
        f"{repo_root}/config.yaml": f"{hermes_install}/config.yaml",
    }
    
    print_section("Copying Files")
    
    success_count = 0
    failed_count = 0
    
    for src, dst in files_to_copy.items():
        if os.path.exists(src):
            if copy_file(src, dst):
                success_count += 1
            else:
                failed_count += 1
        else:
            print(f"  ⚠️  SKIPPED (not found): {os.path.basename(src)}")
            print(f"     Source: {src}")
    
    print_section("Summary")
    print(f"  Files found: {len(files_to_copy)}")
    print(f"  ✅ Successfully copied: {success_count}")
    print(f"  ❌ Failed to copy: {failed_count}")
    
    if failed_count > 0:
        print("\n  ⚠️  WARNING: Some files were not copied. Please check the errors above.")
        return 1
    else:
        print("\n  ✅ SUCCESS: All files copied successfully!")
        print(f"  📁 Hermes installation: {hermes_install}")
        print("\n  🚀 Next steps:")
        print("     1. Set your OPENROUTER_API_KEY environment variable")
        print("     2. Restart Hermes: hermes chat")
        return 0

if __name__ == "__main__":
    sys.exit(main())
