import httpx
import secrets
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from api.endpoints.scoring import latest_set_info, screener_info
from api.endpoints.validator import get_connected_validators_info
from models.evaluation_set import EvaluationSetGroup
from queries.agent import get_agents_in_queue
from utils.network import get_client_ip

router = APIRouter()

# Create a local limiter instance this has its own storage separate from the main app
_limiter = Limiter(key_func=get_client_ip)

# /dashboard
@router.get("/")
@_limiter.limit("30/minute")
async def dashboard(request: Request):
    #return HTMLResponse(content="<h1>Bitrecs V2 Dashboard API is running.</h1>")    
    sg = EvaluationSetGroup("validator")
    queue = await get_agents_in_queue(sg)
    set_info = await latest_set_info()
    validators = get_connected_validators_info()
    screener = await screener_info()

    schemes = {
        "modern": {
            "bg": "#1e1e2e",
            "text": "#cdd6f4",
            "queue": "#89b4fa",
            "validators": "#a6e3a1",
            "set": "#f9e2af",
            "bars": ["#89b4fa", "#f38ba8", "#fab387"]
        },
        "ocean": {
            "bg": "#0d1b2a",
            "text": "#e0e1dd",
            "queue": "#415a77",
            "validators": "#778da9",
            "set": "#1b263b",
            "bars": ["#415a77", "#778da9", "#e0e1dd"]
        },
        "sunset": {
            "bg": "#2d1b2e",
            "text": "#f4e4c1",
            "queue": "#ff6b6b",
            "validators": "#f9a825",
            "set": "#f4a261",
            "bars": ["#e76f51", "#f4a261", "#e9c46a"]
        },
        "forest": {
            "bg": "#1a1f16",
            "text": "#d4e09b",
            "queue": "#6a994e",
            "validators": "#a7c957",
            "set": "#bc4749",
            "bars": ["#6a994e", "#a7c957", "#f2cc8f"]
        }
    }    
    
    scheme = secrets.choice(list(schemes.keys()))
    colors = schemes[scheme]

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Bitrecs V2 Dashboard</title>
    <style>
        body {{
            background-color: {colors['bg']};
            color: {colors['text']};
            font-family: Arial, sans-serif;
            margin: 20px;
        }}
        h1 {{
            text-align: center;
            font-size: 32px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .card {{
            padding: 30px;
            border-radius: 10px;
            text-align: center;
        }}
        .card h2 {{
            margin: 0 0 10px 0;
            font-size: 24px;
        }}
        .card .value {{
            font-size: 48px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .card .label {{
            font-size: 18px;
            opacity: 0.8;
        }}
        .queue {{ background-color: {colors['queue']}33; border: 2px solid {colors['queue']}; }}
        .validators {{ background-color: {colors['validators']}33; border: 2px solid {colors['validators']}; }}
        .set {{ background-color: {colors['set']}33; border: 2px solid {colors['set']}; }}
        .scores {{
            background-color: {colors['bg']};
            border: 2px solid {colors['text']}33;
        }}
        .score-bar {{
            display: flex;
            justify-content: space-around;
            margin-top: 20px;
        }}
        .score-item {{
            text-align: center;
        }}
        .score-item .bar {{
            width: 60px;
            height: 150px;
            border-radius: 5px;
            margin: 0 auto 10px;
            position: relative;
        }}
        .score-item .fill {{
            position: absolute;
            bottom: 0;
            width: 100%;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <h1>🚀 Bitrecs V2 Dashboard</h1>
    <div class="grid">
        <div class="card queue">
            <div class="value">{len(queue)}</div>
            <div class="label">Agents in Queue</div>
        </div>
        <div class="card validators">
            <div class="value">{len(validators)}</div>
            <div class="label">Connected Validators</div>
        </div>
        <div class="card set">
            <h2>Latest Set</h2>
            <div class="value">#{set_info.latest_set_id}</div>
            <div class="label">{str(set_info.latest_set_created_at)[:10]}</div>
        </div>
        <div class="card scores">
            <h2>Average Scores</h2>
            <div class="score-bar">
                <div class="score-item">
                    <div class="bar" style="background-color: {colors['bars'][0]}22;">
                        <div class="fill" style="background-color: {colors['bars'][0]}; height: {screener.screener_1_average_score*100}%;"></div>
                    </div>
                    <div>{screener.screener_1_average_score:.2f}</div>
                    <div class="label">S1</div>
                </div>
                <div class="score-item">
                    <div class="bar" style="background-color: {colors['bars'][1]}22;">
                        <div class="fill" style="background-color: {colors['bars'][1]}; height: {screener.screener_2_average_score*100}%;"></div>
                    </div>
                    <div>{screener.screener_2_average_score:.2f}</div>
                    <div class="label">S2</div>
                </div>
                <div class="score-item">
                    <div class="bar" style="background-color: {colors['bars'][2]}22;">
                        <div class="fill" style="background-color: {colors['bars'][2]}; height: {screener.validator_average_score*100}%;"></div>
                    </div>
                    <div>{screener.validator_average_score:.2f}</div>
                    <div class="label">Val</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""    
    return HTMLResponse(content=html)

