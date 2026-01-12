import subprocess
import sys

def get_git_info():
    try:
        # Get current branch
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], text=True).strip()
        if not branch:  # Handle detached HEAD
            branch = 'detached'
    except subprocess.CalledProcessError:
        branch = 'unknown'
    
    try:
        # Get commit SHA
        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    except subprocess.CalledProcessError:
        sha = 'unknown'
    
    return branch, sha

if __name__ == '__main__':
    branch, sha = get_git_info()
    with open('/tmp/version.txt', 'w') as f:
        f.write(f"{branch}\n{sha}\n")
    print(f"Version written: branch={branch}, sha={sha}")