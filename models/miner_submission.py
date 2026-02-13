from dataclasses import dataclass

@dataclass
class MinerSubmission:    
    created_at: str
    github_account: str
    gist_id: str
    hotkey: str    
    signature: str


    def to_dict(self):
        return {
            "created_at": self.created_at,
            "github_account": self.github_account,
            "gist_id": self.gist_id,
            "hotkey": self.hotkey,
            "signature": self.signature
        }