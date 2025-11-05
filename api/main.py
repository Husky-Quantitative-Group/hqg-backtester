from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import docker
import json
import tempfile
import os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BacktestRequest(BaseModel):
    code: str

@app.post("/backtest")
def run_backtest(request: BacktestRequest):
    try:
        client = docker.from_env()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, "user_code.py"), "w") as f:
                f.write(request.code)
            
            volumes = {
                temp_dir: {"bind": "/tmp/user", "mode": "rw"}
            }
            
            container = client.containers.run(
                "backtester-runner",
                command="python /app/run_strategy.py",
                volumes=volumes,
                detach=True,
                network_mode="none"
            )
            
            container.wait(timeout=60)
            logs = container.logs()
            container.remove()
            
            output = logs.decode('utf-8')
            return json.loads(output.strip().split('\n')[-1])
            
    except Exception as e:
        return {"success": False, "error": str(e)}