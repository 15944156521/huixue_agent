import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class PlanGraphState(TypedDict, total=False):
    user_input: str
    parsed_goal: dict[str, Any]
    rag_context: str
    plan_data: dict[str, Any]


class AdjustGraphState(TypedDict, total=False):
    adjust_query: str
    learning_status: dict[str, Any]
    rag_context: str
    adjustment: dict[str, Any]


def build_plan_workflow(parser, planner, retriever, top_k: int = 4):
    def parse_node(state: PlanGraphState):
        text = (state.get("user_input") or "").strip()
        return {"parsed_goal": parser.parse(text)}

    def retrieve_node(state: PlanGraphState):
        goal = state.get("parsed_goal") or {}
        query = json.dumps(goal, ensure_ascii=False) + "\n" + (state.get("user_input") or "")
        ctx = retriever.retrieve(query, top_k=top_k)
        return {"rag_context": ctx}

    def plan_node(state: PlanGraphState):
        goal = state.get("parsed_goal") or {}
        ctx = state.get("rag_context") or ""
        plan = planner.generate_plan(goal, rag_context=ctx)
        return {"plan_data": plan}

    graph = StateGraph(PlanGraphState)
    graph.add_node("parse", parse_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("plan", plan_node)
    graph.set_entry_point("parse")
    graph.add_edge("parse", "retrieve")
    graph.add_edge("retrieve", "plan")
    graph.add_edge("plan", END)
    return graph.compile()


def build_plan_workflow_from_parsed(planner, retriever, top_k: int = 4):
    """
    在 parsed_goal 已由上游（解析+用户补充）确定后，仅执行 RAG 检索与计划生成。
    初始状态需包含 parsed_goal 与 user_input（user_input 用于检索查询拼接）。
    """

    def retrieve_node(state: PlanGraphState):
        goal = state.get("parsed_goal") or {}
        query = json.dumps(goal, ensure_ascii=False) + "\n" + (state.get("user_input") or "")
        ctx = retriever.retrieve(query, top_k=top_k)
        return {"rag_context": ctx}

    def plan_node(state: PlanGraphState):
        goal = state.get("parsed_goal") or {}
        ctx = state.get("rag_context") or ""
        plan = planner.generate_plan(goal, rag_context=ctx)
        return {"plan_data": plan}

    graph = StateGraph(PlanGraphState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("plan", plan_node)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "plan")
    graph.add_edge("plan", END)
    return graph.compile()


def build_adjust_workflow(optimizer, retriever, top_k: int = 4):
    def retrieve_node(state: AdjustGraphState):
        q = state.get("adjust_query") or ""
        ctx = retriever.retrieve(q, top_k=top_k)
        return {"rag_context": ctx}

    def optimize_node(state: AdjustGraphState):
        status = state.get("learning_status") or {}
        ctx = state.get("rag_context") or ""
        adjustment = optimizer.optimize(status, rag_context=ctx)
        return {"adjustment": adjustment}

    graph = StateGraph(AdjustGraphState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("optimize", optimize_node)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "optimize")
    graph.add_edge("optimize", END)
    return graph.compile()
