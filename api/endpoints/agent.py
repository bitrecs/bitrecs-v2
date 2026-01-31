from uuid import UUID
from models.agent import Agent
from fastapi import APIRouter, HTTPException, Request
from queries.agent import get_agent_by_evaluation_run_id
from utils.limiter import limiter

router = APIRouter()

# /agent/get-by-evaluation-run-id?evaluation_run_id=
@router.get("/get-by-evaluation-run-id")
@limiter.limit("60/minute")
async def agent_get_by_evaluation_run_id(request: Request, evaluation_run_id: UUID) -> Agent:
    agent = await get_agent_by_evaluation_run_id(evaluation_run_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent with evaluation run ID {evaluation_run_id} does not exist.")
    return agent