from langchain_core.messages import AIMessage

from agent import FitnessChat


def run_langchain_agent(user_input: str) -> str:
    chat = FitnessChat()
    messages = chat.send_message(user_input)
    for message in reversed(messages):
        content = getattr(message, "content", "")
        if isinstance(message, AIMessage) and content:
            return content if isinstance(content, str) else str(content)
    return ""
