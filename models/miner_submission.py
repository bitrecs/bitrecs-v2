from dataclasses import dataclass

@dataclass
class MinerSubmission:    
    created_at: str
    github_account: str
    gist_id: str
    hotkey: str    
    signature: str