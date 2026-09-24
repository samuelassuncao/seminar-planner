from google.adk.agents import Agent

from app.models import FinalSeminarPlan
from app.prompts import SLIDE_CONTENT_INSTRUCTION


slide_content_agent = Agent(
    name="slide_content",
    model="gemini-3.6-flash",
    description=(
        "Agente especializado em desenvolver e refinar "
        "o conteúdo dos slides de seminários."
    ),
    instruction=f"""
{SLIDE_CONTENT_INSTRUCTION}

O planejamento produzido pelo agente anterior está disponível
no estado da sessão na variável:

{{seminar_plan}}

Utilize esse planejamento como entrada para executar sua tarefa.
Não solicite novamente essas informações ao usuário.
""",
    output_schema=FinalSeminarPlan,
)