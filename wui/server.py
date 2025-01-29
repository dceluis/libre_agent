import uvicorn
import os
import sys
import argparse
import time
from typing import List

from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from contextlib import asynccontextmanager

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from reasoning_engine import LibreAgentEngine
from memory_graph import MemoryGraph

# Configuration defaults
deep_schedule = 10
graph_file = None

# Set up templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_file, deep_schedule, reasoning_model
    
    engine = LibreAgentEngine(
        deep_schedule=deep_schedule,
        reasoning_model=reasoning_model
    )
    
    app.state.engine = engine
    app.state.wm = engine.working_memory
    app.state.wm.register_observer(memory_callback)
    
    engine.start()
    yield
    engine.stop()

app = FastAPI(lifespan=lifespan)

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), 'static')), name="static")

# track websocket connections
active_connections: List[WebSocket] = []

def get_chat_history():
    """Retrieve chat history from memory graph"""
    memories = MemoryGraph().get_memories(memory_type='external', sort='timestamp', reverse=False)
    return [
        {
            "unit_name": mem['metadata'].get('unit_name', 'User'),
            "content": mem['content'],
            "timestamp": time.strftime('%H:%M:%S', time.localtime(mem['timestamp']))
        }
        for mem in memories
    ]

@app.get("/", response_class=HTMLResponse)
async def chat_interface(request: Request):
    chat_history = get_chat_history()
    return templates.TemplateResponse("chat.html", {"request": request, "messages": chat_history})

@app.post("/send_message")
async def handle_message(message: str = Form(...)):
    timestamp = time.strftime('%H:%M:%S')
    user_snippet = render_message_snippet("user", message, timestamp)
    await broadcast_snippet(user_snippet)

    # generate + broadcast the assistant response
    app.state.wm.add_interaction("user", message)

    return HTMLResponse("")

async def memory_callback(memory):
    if memory['memory_type'] == 'external' and memory['metadata'].get('unit_name') == "ReasoningUnit":
        timestamp = time.strftime('%H:%M:%S', time.localtime(memory["timestamp"]))
        snippet = render_message_snippet("assistant", memory["content"], timestamp)
        await broadcast_snippet(snippet)

@app.websocket("/ws")
async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

def render_message_snippet(unit_name: str, content: str, timestamp: str) -> str:
    snippet = templates.get_template("message.html").render(
        request=None,
        message={"unit_name": unit_name, "content": content, "timestamp": timestamp},
        submit=True,
    )
    # wrap snippet w/ oob directive so htmx injects it into #chat-box
    oob_snippet = f"""
<div hx-swap-oob="beforeend" id="chat-box">
    {snippet}
</div>
"""
    return oob_snippet

async def broadcast_snippet(snippet: str):
    for conn in active_connections:
        await conn.send_text(snippet)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chat Interface Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--graph-file")
    parser.add_argument("--deep-schedule", type=int, default=10)
    parser.add_argument('--reasoning-model', type=str, default="gemini/gemini-2.0-flash-exp")

    args = parser.parse_args()
    graph_file = args.graph_file
    deep_schedule = args.deep_schedule
    reasoning_model = args.reasoning_model

    uvicorn.run(app, host=args.host, port=args.port)
