import utils.logger as logger
from fastapi import APIRouter, Depends, HTTPException, Request, logger
from api.endpoints.validator import Validator, get_request_validator_with_lock
from api.endpoints.validator_models import InferenceCostEstimateRequest
from llm.llm_provider import LLM
from models.inference_report import InferenceReport
from queries.inference import get_cost_report_for_agent, insert_inference
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
        #raise HTTPException(status_code=503, detail="Cost estimation not available")
        logger.warning(f"Cost estimation not available for provider {inference_request.provider} and model {inference_request.model_name}")
        return {
            "input_cost": 0.0,
            "output_cost": 0.0,
            "total_cost": 0.0,
            "currency": "USD"
        }
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


# /inference/cost
@router.get("/cost")
@limiter.limit("120/minute")
async def get_agent_inference_cost(request: Request, agent_id: str) -> dict:
    try:
        report = await get_cost_report_for_agent(agent_id)
        return {"agent_id": agent_id, "inference_cost_report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve inference cost report: {str(e)}")


@router.get("/models")
@limiter.limit("120/minute")
async def list_available_models(request: Request) -> dict:
    try:
        combined_models = []

        # 1. Fetch and parse OpenRouter Models
        open_router_coster = get_inference_coster(LLM.OPEN_ROUTER.name, "")
        open_router_data = await open_router_coster.models()
        
        if open_router_data and "data" in open_router_data:
            for item in open_router_data["data"]:
                pricing = item.get("pricing", {})
                
                # Helper to handle OpenRouter's varied pricing formats (direct number vs dict)
                def get_or_price(val):
                    if isinstance(val, dict):
                        return float(val.get("usd", 0))
                    try:
                        return float(val or 0)
                    except (ValueError, TypeError):
                        return 0.0

                prompt_price = get_or_price(pricing.get("prompt")) * 1_000_000
                completion_price = get_or_price(pricing.get("completion")) * 1_000_000
                
                combined_models.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "provider": LLM.OPEN_ROUTER.name,
                    "description": item.get("description"),
                    "context_length": item.get("context_length"),
                    "pricing": {
                        "prompt_usd_1m": prompt_price,
                        "completion_usd_1m": completion_price,
                        "unit": "1M tokens"
                    },
                    "hot": True
                })

        # 2. Fetch and parse Chutes Models
        chutes_coster = get_inference_coster(LLM.CHUTES.name, "")
        chutes_data = await chutes_coster.models()
        
        if chutes_data and "items" in chutes_data:
            for item in chutes_data["items"]:
                if not item.get("public") or not item.get("hot"):
                    continue
                    
                price_info = item.get("current_estimated_price", {})
                
                # Check for standard per_million_tokens first
                tokens_pricing = price_info.get("per_million_tokens", {})
                if tokens_pricing:
                    # Check for nested .input.usd vs direct .usd
                    p_val = tokens_pricing.get("input", {})
                    prompt_price = p_val.get("usd") if isinstance(p_val, dict) else tokens_pricing.get("usd", 0)
                    
                    c_val = tokens_pricing.get("output", {})
                    completion_price = c_val.get("usd") if isinstance(c_val, dict) else tokens_pricing.get("usd", 0)
                    unit = "1M tokens"
                else:
                    # Fallback to per_request (common for Image/TTS/Audio models)
                    req_pricing = price_info.get("per_request", {})
                    req_price = req_pricing.get("usd") if isinstance(req_pricing, dict) else price_info.get("usd", 0)
                    prompt_price = req_price
                    completion_price = req_price
                    unit = "request"

                combined_models.append({
                    "id": item.get("slug") or item.get("chute_id"),
                    "name": item.get("name"),
                    "provider": LLM.CHUTES.name,
                    "description": item.get("tagline") or item.get("readme") or item.get("description"),
                    "context_length": None,
                    "pricing": {
                        "prompt_usd_1m": float(prompt_price or 0),
                        "completion_usd_1m": float(completion_price or 0),
                        "unit": unit
                    },
                    "hot": item.get("hot")
                })

        return {
            "total_count": len(combined_models),
            "models": combined_models
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve available models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve available models: {str(e)}")