import uvicorn
import os
import sys
import argparse
import time
from typing import List

from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from contextlib import asynccontextmanager

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import necessary components from your existing codebase
from reasoning_engine import LibreAgentEngine
from memory_graph import memory_graph

quick_schedule = 5
deep_schedule = 10
graph_file = None

# Set up templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_file
    global deep_schedule
    global quick_schedule

    engine = LibreAgentEngine(
        quick_schedule=quick_schedule,
        deep_schedule=deep_schedule,
        memory_graph_file=graph_file
    )

    working_memory = engine.working_memory

    app.state.wm = working_memory
    app.state.engine = engine

    working_memory.register_observer(memory_callback)
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
    memories = memory_graph.get_memories(memory_type='external', sort='timestamp', reverse=False)
    return [
        {
            "role": mem['metadata'].get('role', 'user'),
            "content": mem['content'],
            "timestamp": time.strftime('%H:%M:%S', time.localtime(mem['timestamp']))
        }
        for mem in memories
    ]

@app.get("/", response_class=HTMLResponse)
async def get_chat(request: Request):
    chat_history = get_chat_history()
    # you might add hx-websockets extension scripts here in the template
    return templates.TemplateResponse("chat.html", {"request": request, "messages": chat_history})

@app.post("/send_message", response_class=HTMLResponse)
async def send_message(request: Request, message: str = Form(...)):
    timestamp = time.strftime('%H:%M:%S', time.localtime())
    user_snippet = render_message_snippet(role="user", content=message, timestamp=timestamp)

    await broadcast_snippet(user_snippet)

    # generate + broadcast the assistant response
    app.state.wm.add_interaction("user", message)

    # return the user snippet for immediate local insert
    # return user_snippet

@app.get("/memories", response_class=HTMLResponse)
async def read_root():
    template = templates.get_template("inspector.html")
    return template.render()

@app.get("/api/memories", response_class=JSONResponse)
async def get_memories(request: Request):
    try:
        memories = memory_graph.get_memories(sort='timestamp', reverse=False)
        formatted = [
            {
                "memory_id": mem['memory_id'],
                "memory_type": mem['memory_type'],
                "content": mem['content'],
                "metadata": mem['metadata'],
                "timestamp": mem['timestamp']
            }
            for mem in memories
        ]
        return {"memories": formatted, "graph_file": memory_graph.graph_file}
    except Exception as e:
        return {"error": str(e)}, 400

async def memory_callback(memory):
    memory_type = memory['memory_type']
    content = memory["content"]
    role = memory["metadata"].get("role")
    timestamp = time.strftime('%H:%M:%S', time.localtime(memory["timestamp"]))

    if memory_type == 'external' and role == "assistant":
        assistant_snippet = render_message_snippet(role="assistant", content=content, timestamp=timestamp)
        await broadcast_snippet(assistant_snippet)
    # elif memory_type == 'internal' and self.print_internals:
    #     pass
    else:
        return

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

def render_message_snippet(role: str, content: str, timestamp: str) -> str:
    snippet = templates.get_template("message.html").render(
        request=None,
        message={"role": role, "content": content, "timestamp": timestamp},
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
    # broadcast a partial html snippet to every ws connection
    for conn in active_connections:
        await conn.send_text(snippet)

if __name__ == "__main__":
    # Parse CLI arguments
    parser = argparse.ArgumentParser()

    parser.add_argument("--graph-file", help="Path to the memory graph file", default=None)
    parser.add_argument('--deep-schedule', type=int, default=10, help='deep reflection schedule in minutes')
    parser.add_argument('--quick-schedule', type=int, default=5, help='quick reflection schedule in minutes')
    parser.add_argument("--host", help="Host address to bind the server", default="0.0.0.0")
    parser.add_argument("--port", help="Port number to bind the server", default=5000)

    args = parser.parse_args()

    if args.graph_file:
        graph_file = args.graph_file
    if args.quick_schedule:
        quick_schedule = args.quick_schedule
    if args.deep_schedule:
        deep_schedule = args.deep_schedule

    uvicorn.run(app, host=args.host, port=args.port)
