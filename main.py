from langchain_core.messages import AIMessage

from agent import FitnessChat


def _message_text(message) -> str:
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)


chat = FitnessChat()

while True:
    user_input = input("You: ")

    if user_input.lower() == "exit":
        break

    new_messages = chat.send_message(user_input)
    replies = [
        _message_text(message)
        for message in new_messages
        if isinstance(message, AIMessage) and _message_text(message)
    ]
    print("AI:", replies[-1] if replies else "")
