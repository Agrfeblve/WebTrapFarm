from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import sys
from pathlib import Path
import json
import aiosqlite
import argparse

logger = logging.getLogger('my_server')
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)

from logging import FileHandler
file_handler = FileHandler('server.log')
file_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

parser = argparse.ArgumentParser(description='Server configuration')
parser.add_argument('--host', default='127.0.0.1', help='Host address to bind to')
parser.add_argument('--port', type=int, default=3000, help='Port number to listen on')
args = parser.parse_args()

# agent_name = args.agent_name
# db_path = args.db_path
# benchmark_name = args.benchmark_name

app = FastAPI(title="My API", description="API for saving emails and tweets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/", StaticFiles(directory="../websites"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("frontend_server:app", host=args.host, port=args.port)
