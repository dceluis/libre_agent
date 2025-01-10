from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import sys
import asyncio
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import necessary components from your existing codebase
from working_memory import WorkingMemory
from memory_graph import memory_graph
from logger import logger

app = FastAPI()

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), 'static')), name="static")

# Set up templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

# Initialize working memory
working_memory = WorkingMemory()

# In-memory storage for messages (for simplicity)
def get_chat_history():
    """Retrieve chat history from memory graph"""
    memories = memory_graph.get_memories(memory_type='external', sort='timestamp', reverse=False)
    return [
        {
            "role": mem['metadata'].get('role', 'user'),
            "content": mem['content'],
            "timestamp": mem['timestamp']
        }
        for mem in memories
    ]

@app.get("/", response_class=HTMLResponse)
async def get_chat(request: Request):

    logger.info(f"Chat page accessed.")

    chat_history = get_chat_history()

    return templates.TemplateResponse("chat.html", {"request": request, "messages": chat_history})

@app.post("/send_message", response_class=HTMLResponse)
async def send_message(request: Request, message: str = Form(...)):
    logger.info(f"User sent message: {message}")

    # Process the message using your AI assistant
    response = await generate_response(message)

    # Return the latest message to update the chat
    return templates.TemplateResponse("message.html", {"request": request, "message": {"role": "user", "content": message}})

async def generate_response(message: str) -> str:
    try:
        # Add user message to working memory
        working_memory.add_interaction("user", message)

        # Retrieve the latest assistant message from working memory
        last_assistant = working_memory.get_last_assistant_output()

        if last_assistant:
            return last_assistant
        else:
            return "I'm here to help!"
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return "Sorry, I encountered an error processing your request."

if __name__ == "__main__":
    # Parse CLI arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph-file", help="Path to the memory graph file", default=None)
    parser.add_argument("--host", help="Host address to bind the server", default="0.0.0.0")
    parser.add_argument("--port", help="Port number to bind the server", default=5000)
    args = parser.parse_args()

    if args.graph_file:
        memory_graph.set_graph_file_path(args.graph_file)

    uvicorn.run(app, host=args.host, port=args.port)
