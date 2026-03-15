from fastapi import APIRouter, HTTPException, Request
from models.inference_report import InferenceReport
from queries.inference import insert_inference
from api.utils.limiter import limiter

router = APIRouter()

# /inference/report-run
@router.post("/report-run")
@limiter.limit("60/minute")
async def report_inference_run(request: Request, inference: InferenceReport) -> dict:   
    try:
        inference_id = await insert_inference(
            evaluation_run_id=inference.evaluation_run_id,
            provider=inference.provider,
            model=inference.model,
            temperature=inference.temperature,
            messages=inference.messages,
            status_code=inference.status_code,
            response=inference.response,
            num_input_tokens=inference.num_input_tokens,
            num_output_tokens=inference.num_output_tokens,
            cost_usd=inference.cost_usd,
            response_sent_at=inference.response_sent_at
        )
        return {"inference_id": inference_id, "status": "reported"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to report inference: {str(e)}")

