"""
Qt 리소스 컴파일 스크립트
resources.qrc를 resources_rc.py로 컴파일 (PyQt6 호환)
"""

import base64
import xml.etree.ElementTree as ET
from pathlib import Path

def compile_resources():
    """Qt 리소스 파일을 Python 모듈로 컴파일"""
    qrc_file = Path(__file__).parent / "resources.qrc"
    output_file = Path(__file__).parent / "resources_rc.py"
    
    print(f"Compiling {qrc_file} -> {output_file}")
    
    try:
        # QRC 파일 파싱
        tree = ET.parse(qrc_file)
        root = tree.getroot()
        
        resources = {}
        
        # 각 qresource 처리
        for qresource in root.findall('qresource'):
            prefix = qresource.get('prefix', '')
            
            # 각 파일 처리
            for file_elem in qresource.findall('file'):
                file_path = file_elem.text
                resource_name = f"{prefix}/{file_path.split('/')[-1]}"
                
                # 실제 파일 경로
                actual_path = Path(__file__).parent / file_path
                
                if not actual_path.exists():
                    print(f"  Warning: File not found: {actual_path}")
                    continue
                
                # 파일 읽기 및 base64 인코딩
                with open(actual_path, 'rb') as f:
                    file_data = f.read()
                    encoded = base64.b64encode(file_data).decode('ascii')
                
                resources[resource_name] = encoded
                print(f"  Added: {resource_name} ({len(file_data)} bytes)")
        
        # Python 모듈 생성
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('# -*- coding: utf-8 -*-\n\n')
            f.write('"""\n')
            f.write('Qt Resources Module\n')
            f.write('Auto-generated from resources.qrc\n')
            f.write('DO NOT EDIT MANUALLY\n')
            f.write('"""\n\n')
            f.write('import base64\n')
            f.write('from PyQt6.QtCore import QFile, QIODevice\n\n')
            f.write('# Resource data\n')
            f.write('_RESOURCES = {\n')
            
            for name, data in resources.items():
                f.write(f'    "{name}": "{data}",\n')
            
            f.write('}\n\n')
            
            # 리소스 등록 함수
            f.write('def qInitResources():\n')
            f.write('    """Initialize Qt resources"""\n')
            f.write('    pass\n\n')
            
            f.write('def qCleanupResources():\n')
            f.write('    """Cleanup Qt resources"""\n')
            f.write('    pass\n\n')
            
            f.write('def get_resource_data(resource_path: str) -> bytes:\n')
            f.write('    """Get resource data by path (e.g., ":/buttons/정지.png")"""\n')
            f.write('    # Remove :/ prefix if present\n')
            f.write('    if resource_path.startswith(":/"): \n')
            f.write('        resource_path = resource_path[2:]\n')
            f.write('    \n')
            f.write('    if resource_path in _RESOURCES:\n')
            f.write('        return base64.b64decode(_RESOURCES[resource_path])\n')
            f.write('    return b""\n\n')
            
            f.write('def resource_exists(resource_path: str) -> bool:\n')
            f.write('    """Check if resource exists"""\n')
            f.write('    if resource_path.startswith(":/"): \n')
            f.write('        resource_path = resource_path[2:]\n')
            f.write('    return resource_path in _RESOURCES\n\n')
            
            f.write('# Auto-initialize\n')
            f.write('qInitResources()\n')
        
        print(f"\n✓ Resources compiled successfully!")
        print(f"  Output: {output_file}")
        print(f"  Total resources: {len(resources)}")
        return True
        
    except Exception as e:
        print(f"✗ Compilation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    success = compile_resources()
    sys.exit(0 if success else 1)
