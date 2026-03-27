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
    request: Request,
    inference_report: InferenceReport,  
    validator: Validator = Depends(get_request_validator_with_lock)) -> dict:   
    try:
        inference_id = await insert_inference(
            evaluation_run_id=inference_report.evaluation_run_id,
            provider=inference_report.provider,
            model=inference_report.model,
            temperature=inference_report.temperature,
            messages=inference_report.messages,
            status_code=inference_report.status_code,
            response=inference_report.response,
            num_input_tokens=inference_report.num_input_tokens,
            num_output_tokens=inference_report.num_output_tokens,
            cost_usd=inference_report.cost_usd,
            response_sent_at=inference_report.response_sent_at
        )
        return {"inference_id": inference_id, "status": "reported"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to report inference: {str(e)}")
