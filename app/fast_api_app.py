import asyncio
import contextlib
import json
import os
import uuid
from collections.abc import AsyncIterator

from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.genai import types
from google.genai.errors import ServerError

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.models import FinalSeminarPlan, SeminarRequest
from app.prompts import build_seminar_prompt
from app.pptx_generator import generate_pptx


load_dotenv()


FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173",
)

allow_origins = [
    FRONTEND_URL,
]

otel_to_cloud = False

AGENT_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)


# Agente temporário para diagnóstico do ADK
test_agent = Agent(
    name="test_agent",
    model="gemini-3.5-flash",
    instruction="Responda apenas: OK",
)

test_app = App(
    root_agent=test_agent,
    name="test_app",
)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    session_service = services.get_session_service()

    # Runner principal
    runner = Runner(
        app=adk_app,
        session_service=session_service,
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )

    app.state.runner = runner
    app.state.session_service = session_service
    app.state.agent_app_name = adk_app.name

    # Runner temporário para teste do ADK
    test_runner = Runner(
        app=test_app,
        session_service=session_service,
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )

    app.state.test_runner = test_runner
    app.state.test_app_name = test_app.name

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
            types.Part(text=prompt),
        ],
    )

    final_response = None

    try:
        async with asyncio.timeout(180):
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=message,
            ):
                if event.is_final_response():
                    final_response = event.content

    except ServerError as e:
        print("ERRO DO GEMINI:", repr(e))

        raise HTTPException(
            status_code=503,
            detail=(
                "O serviço de IA está temporariamente indisponível. "
                "Tente novamente em alguns instantes."
            ),
        ) from e

    except TimeoutError as e:
        print("TIMEOUT AO GERAR PLANEJAMENTO")

        raise HTTPException(
            status_code=504,
            detail=(
                "A geração do planejamento demorou mais do que o esperado. "
                "Tente novamente."
            ),
        ) from e

    except Exception as e:
        print("ERRO AO EXECUTAR O AGENTE:", repr(e))

        raise HTTPException(
            status_code=500,
            detail="Ocorreu um erro ao gerar o planejamento.",
        ) from e

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
            detail="Erro ao processar a resposta do agente.",
        ) from e

    return response_json


@app.get("/api/test-adk")
async def test_adk():
    runner = app.state.test_runner
    session_service = app.state.session_service
    app_name = app.state.test_app_name

    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    message = types.Content(
        role="user",
        parts=[
            types.Part(text="Responda apenas: OK"),
        ],
    )

    try:
        async with asyncio.timeout(60):
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=message,
            ):
                if event.is_final_response():
                    return {
                        "response": event.content.parts[0].text,
                    }

    except Exception as e:
        print("ERRO TESTE ADK:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {e}",
        ) from e

    return {
        "response": "Nenhuma resposta final",
    }


@app.post("/api/seminars/pptx")
async def export_seminar_pptx(plan: FinalSeminarPlan):
    pptx_file = generate_pptx(plan)

    return Response(
        content=pptx_file.getvalue(),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        ),
        headers={
            "Content-Disposition": (
                'attachment; filename="seminar-plan.pptx"'
            )
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )