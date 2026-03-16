from fastapi import APIRouter, Depends, HTTPException, Request
from api.endpoints.validator import Validator, get_request_validator_with_lock
from api.endpoints.validator_models import InferenceCostEstimateRequest
from models.inference_report import InferenceReport
from queries.inference import insert_inference
from api.utils.limiter import limiter
from utils.inference_coster import InferenceCoster

router = APIRouter()

def get_inference_coster(provider: str, model_name: str) -> InferenceCoster:
    return InferenceCoster(provider, model_name)


# /inference/estimate-cost
@router.post("/estimate-cost")
@limiter.limit("120/minute")
async def estimate_inference_cost(   
    request: Request,
    inference_request: InferenceCostEstimateRequest
) -> dict:
    coster = get_inference_coster(inference_request.provider, inference_request.model_name)
    cost = await coster.cost_estimate(inference_request.input_tokens, inference_request.output_tokens)
    if cost is None:
        raise HTTPException(status_code=503, detail="Cost estimation not available")
    return {
        "input_cost": cost.input,
        "output_cost": cost.output,
        "total_cost": cost.input + cost.output,
        "currency": "USD"
    }


# /inference/report-cost
@router.post("/report-cost")
@limiter.limit("120/minute")
async def report_inference_run(
    request: InferenceReport,  
    validator: Validator = Depends(get_request_validator_with_lock)) -> dict:   
    try:
        inference_id = await insert_inference(
            evaluation_run_id=request.evaluation_run_id,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
            messages=request.messages,
            status_code=request.status_code,
            response=request.response,
            num_input_tokens=request.num_input_tokens,
            num_output_tokens=request.num_output_tokens,
            cost_usd=request.cost_usd,
            response_sent_at=request.response_sent_at
        )
        return {"inference_id": inference_id, "status": "reported"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to report inference: {str(e)}")
