from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from ab_agent.nodes.ingest import start_node
from ab_agent.schemas import GlobalState, AgentInput
from ab_agent.nodes.uxagent_node import uxagent_node

def continue_to_tasks(state: GlobalState) -> list[Send]:
    # state["tasks"] уже содержит список задач от generate_tasks
    return [
        Send("process_task", {"task": task})  # отправить каждую задачу в ноду "process_task"
        for task in state.tasks
    ]

builder = StateGraph(GlobalState, input_schema=AgentInput)

builder.add_node("generate_tasks", start_node)
builder.add_node("process_task", uxagent_node)

builder.add_edge(START, "generate_tasks")
builder.add_conditional_edges("generate_tasks", continue_to_tasks, path_map=["process_task"])
builder.add_edge("process_task", END)

graph = builder.compile()