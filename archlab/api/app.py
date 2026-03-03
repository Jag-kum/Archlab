from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from archlab.api.schemas import SimulateRequest, SweepRequest
from archlab.cli.config import build_engine
from archlab.cli.sweep import run_sweep

app = FastAPI(
    title="ArchLab",
    description="Distributed Systems Simulator API",
    version="0.1.0",
)

STATIC_DIR = Path(__file__).parent / "static"


def _request_to_config(req) -> Dict[str, Any]:
    """Convert a Pydantic request model to the plain dict format build_engine expects."""
    raw = req.model_dump(exclude_none=True)
    config = {
        "components": raw["components"],
        "simulation": raw["simulation"],
    }
    for comp in config["components"]:
        st = comp.get("service_time")
        if isinstance(st, dict) and st.get("distribution") == "constant" and "value" not in st and "mean" not in st:
            pass
    return config


@app.post("/simulate")
def simulate(req: SimulateRequest):
    try:
        config = _request_to_config(req)
        engine = build_engine(config)
        engine.run()
        summary = engine.metrics.summary(sla=req.sla)
        return summary
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/sweep")
def sweep(req: SweepRequest):
    try:
        config = _request_to_config(req)
        results = run_sweep(
            config,
            param=req.param,
            values=req.values,
            seeds=req.seeds,
            sla=req.sla,
        )
        return {"param": req.param, "results": results}
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/", response_class=HTMLResponse)
def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
