# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import os
import uuid
import json

from fastapi import HTTPException
from google.genai import types

from app.models import FinalSeminarPlan, SeminarRequest
from app.prompts import build_seminar_prompt
from collections.abc import AsyncIterator

from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes

load_dotenv()
allow_origins = [
    "http://localhost:5173",
]
otel_to_cloud = False

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    session_service = services.get_session_service()

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.session_service = session_service
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=otel_to_cloud,
    lifespan=lifespan,
)

app.title = "seminar-planner"
app.description = "API for interacting with the Agent seminar-planner"

@app.post("/api/seminars", response_model=FinalSeminarPlan)
async def create_seminar(request: SeminarRequest):
    runner = app.state.runner
    session_service = app.state.session_service
    app_name = app.state.agent_app_name

    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    prompt = build_seminar_prompt(request)

    message = types.Content(
        role="user",
        parts=[
            types.Part(text=prompt)
        ],
    )

    final_response = None

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response():
            final_response = event.content

    if final_response is None:
        raise HTTPException(
            status_code=500,
            detail="O agente não retornou uma resposta.",
        )

    try:
        response_text = final_response.parts[0].text
        response_json = json.loads(response_text)
    except Exception as e:
        print("ERRO AO PROCESSAR RESPOSTA:", repr(e))
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar resposta: {e}",
        )

    return response_json


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
