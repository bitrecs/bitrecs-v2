import os
import subprocess
from pathlib import Path

root_path = Path(__file__).parent.absolute()

def get_git_info():    
    build_sha = os.getenv('BUILD_SHA')
    if build_sha:
        branch = 'main'
        sha = build_sha
    else:
        # Fallback to local git (for local development)
        try:
            branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], text=True).strip()
            if not branch:
                branch = 'detached'
        except subprocess.CalledProcessError:
            branch = 'unknown'
        
        try:
            sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        except subprocess.CalledProcessError:
            sha = 'unknown'
    
    return branch, sha

if __name__ == '__main__':
    branch, sha = get_git_info()
    version_file_path = "/tmp/version.txt"
    with open(version_file_path, 'w') as f:
        f.write(f"{branch}\n{sha}\n")
    print(f"Version written: branch={branch}, sha={sha}")