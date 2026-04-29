from typing import Literal

from langgraph.graph import StateGraph, START, END

from vigilador_tecnologico.pipeline.state import ResearchState
from vigilador_tecnologico.pipeline.nodes import (
    planificador_node,
    extraccion_web_node,
    evaluador_profundidad_node,
    reporte_node,
)

def router_profundidad(state: ResearchState) -> Literal["evaluador_profundidad_node", "reporte_node"]:
    research_plan = state.get("research_plan")
    if not isinstance(research_plan, dict):
        return "reporte_node"
    branches = research_plan.get("branches")
    if not isinstance(branches, list) or not branches:
        return "reporte_node"
    branch_cursor = state.get("branch_cursor", 0)
    if branch_cursor + 1 >= len(branches):
        return "reporte_node"
    return "evaluador_profundidad_node"


def build_research_graph() -> StateGraph:
    """Construye la máquina de estados explícita del Deep Research Loop."""
    workflow = StateGraph(ResearchState)
    workflow.add_node("planificador_node", planificador_node)
    workflow.add_node("extraccion_web_node", extraccion_web_node)
    workflow.add_node("evaluador_profundidad_node", evaluador_profundidad_node)
    workflow.add_node("reporte_node", reporte_node)
    workflow.add_edge(START, "planificador_node")
    workflow.add_edge("planificador_node", "extraccion_web_node")
    workflow.add_conditional_edges("extraccion_web_node", router_profundidad)
    workflow.add_edge("evaluador_profundidad_node", "extraccion_web_node")
    workflow.add_edge("reporte_node", END)
    return workflow.compile()
