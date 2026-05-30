from langgraph.graph import StateGraph, MessagesState, START, END
from time import sleep

class State(MessagesState):
    field: int

def first(state: State):
    for i in range(1, 11):
        print(i)
        sleep(0.5)
    return {"messages": [{"role": "ai", "content": "69"}], "field": 69}
    # return {"messages": [{"role": "ai", "content": "69"}]}

def second(state: State):
    for i in range(50, 61):
        print(i)
        sleep(0.5)
    return {"messages": [{"role": "ai", "content": "67"}], "field": 67}
    # return {"messages": [{"role": "ai", "content": "67"}]}

def third(state: State):
    for i in range(90, 101):
        print(i)
        sleep(0.5)
    return {}

graph = StateGraph(State)

graph.add_node(first)
graph.add_node(second)
graph.add_node(third)

graph.add_edge(START, "first")
graph.add_edge(START, "second")
graph.add_edge("second", "third")
graph.add_edge("first", END)
graph.add_edge("third", END)

graph = graph.compile()

print(graph.get_graph(xray=True).draw_ascii())


messages = graph.invoke({"messages": [{"role": "user", "content": "hi!"}]}) # type: ignore
print(messages)