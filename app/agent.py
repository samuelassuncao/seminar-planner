from google.adk.agents import Agent
from google.adk.apps import App
from app.models import SeminarPlan, SeminarRequest

from app.prompts import SEMINAR_PLANNER_INSTRUCTION

    
root_agent = Agent(
    name="seminar_planner",
    model="gemini-3.5-flash-lite",
    description="Agente especializado em planejamento de seminários acadêmicos.",
    instruction=SEMINAR_PLANNER_INSTRUCTION,
    output_schema=SeminarPlan,
)


app = App(
    root_agent=root_agent,
    name="app",
)