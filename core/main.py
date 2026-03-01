from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Syzygy Rosetta MVP")

class EvaluateRequest(BaseModel):
    prompt: str

def process_fn(prompt: str):
    return f"Echo: {prompt}"

@app.post("/evaluate")
def evaluate(req: EvaluateRequest):
    result = process_fn(req.prompt)
    return {"response": result}