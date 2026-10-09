"""FastAPI layer.

Routes call the same tool functions the agent calls, with tool_context=None. There is no
second implementation of any calculation here, which is what guarantees a planner dragging
a slider sees exactly what the agent would have said.
"""
