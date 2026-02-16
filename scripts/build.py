"""
Build Script for Croquis Application
Builds executable with PyInstaller and verifies icon integration
"""

import subprocess
import sys
from pathlib import Path
import shutil

def main():
    print("=" * 60)
    print("Croquis Application Build Script")
    print("=" * 60)
    
    project_root = Path(__file__).parent.parent
    spec_file = project_root / "Croquis.spec"
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"
    icon_src = project_root / "src" / "assets" / "icon.ico"
    
    # Verify icon exists
    if not icon_src.exists():
        print(f"❌ ERROR: Icon file not found at {icon_src}")
        sys.exit(1)
    
    print(f"✅ Icon file verified: {icon_src}")
    
    # Clean previous build
    print("\n🧹 Cleaning previous build...")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
        print("   Removed dist/")
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print("   Removed build/")
    
    # Run PyInstaller
    print(f"\n🔨 Building executable with {spec_file.name}...")
    try:
        result = subprocess.run(
            ["pyinstaller", str(spec_file), "--clean"],
            cwd=str(project_root),
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Build successful!")
        
        # Verify output - check both onefile and onedir formats
        exe_path = dist_dir / "Croquis.exe"
        if not exe_path.exists():
            exe_path = dist_dir / "Croquis" / "Croquis.exe"
        
        if exe_path.exists():
            print(f"\n✅ Executable created: {exe_path}")
            print(f"   Size: {exe_path.stat().st_size / (1024*1024):.2f} MB")
            
            # Check if icon was bundled
            icon_in_dist = exe_path.parent / "icon.ico"
            if icon_in_dist.exists():
                print(f"✅ Icon bundled: {icon_in_dist}")
            else:
                print(f"⚠️  Icon not found in dist folder (may be embedded in exe)")
        else:
            print(f"❌ ERROR: Executable not found at {exe_path}")
            sys.exit(1)
            
    except subprocess.CalledProcessError as e:
        print("❌ Build failed!")
        print(e.stderr)
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Build complete! 🎉")
    print("=" * 60)
    print(f"\nExecutable location: {exe_path}")
    print("\nTo run the application:")
    print(f"  {exe_path}")

if __name__ == "__main__":
    main()
