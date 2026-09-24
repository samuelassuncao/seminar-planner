from google.adk.agents import Agent, SequentialAgent
from google.adk.apps import App

from app.agents.slide_content import slide_content_agent
from app.models import FinalSeminarPlan, SeminarPlan
from app.prompts import SEMINAR_PLANNER_INSTRUCTION


seminar_planner_agent = Agent(
    name="seminar_planner",
    model="gemini-3.5-flash",
    description=(
        "Agente especializado em planejamento "
        "de seminários acadêmicos."
    ),
    instruction=SEMINAR_PLANNER_INSTRUCTION,
    output_schema=SeminarPlan,
    output_key="seminar_plan",
)


seminar_pipeline = SequentialAgent(
    name="seminar_pipeline",
    sub_agents=[
        seminar_planner_agent,
        slide_content_agent,
    ],
)


root_agent = seminar_pipeline


app = App(
    root_agent=root_agent,
    name="app",
)