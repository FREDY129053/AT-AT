from pydantic import BaseModel
from typing import Literal

class AgentEventContract(BaseModel):
    agent_id: str
    agent_group: str = ""
    agent_type: str = ""
    curr_step: int
    max_steps: int
    terminate: Literal['error', 'success', '']  # DEBUG: ''
    obs_hash_prev: str
    obs_hash_curr: str
    step: int
    
    def __repr__(self) -> str:
        return f"<AgentEvent(agent_id='{self.agent_id}', agent_group='{self.agent_group}', agent_type='{self.agent_type}')>"