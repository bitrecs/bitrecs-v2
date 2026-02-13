from pydantic import BaseModel

class MinerSubmission(BaseModel):    
    created_at: str
    github_account: str
    gist_id: str
    hotkey: str    
    signature: str

    def to_dict(self):
        return self.model_dump()  # Use Pydantic's method instead of custom