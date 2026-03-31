import subprocess


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

def get_git_sha():
    branch, sha = get_git_info()
    return sha


COMMIT_HASH = get_git_sha()