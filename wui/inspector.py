import uvicorn
import os
import sys
import argparse
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from contextlib import asynccontextmanager

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory_graph import MemoryGraph
from logger import logger

# Configuration
graph_file = None

# Set up templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

@asynccontextmanager
async def lifespan(app: FastAPI):
    if graph_file:
        MemoryGraph.set_graph_file(graph_file)

        logger.info(f"Loaded memory graph from {graph_file}")
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), 'static')), name="static")

@app.get("/", response_class=HTMLResponse)
async def memory_inspector(request: Request):
    return templates.TemplateResponse("inspector.html", {"request": request})

@app.get("/api/memories", response_class=JSONResponse)
async def get_memories(request: Request):
    try:
        memory_graph = MemoryGraph()
        memories = memory_graph.get_memories(sort='timestamp', reverse=False)
        formatted = {
            "memories": [{
                "id": mem['memory_id'],
                "type": mem['memory_type'],
                "content": mem['content'],
                "metadata": mem['metadata'],
                "timestamp": mem['timestamp']
            } for mem in memories],
        }

        return { 'memories': formatted, "graph_file": graph_file }
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Memory Inspector Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--graph-file")

    args = parser.parse_args()
    graph_file = args.graph_file

    uvicorn.run(app, host=args.host, port=args.port)
