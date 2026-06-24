import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv(".env", override=True)
from api.models import ConversationMessage
from api.routers.chat import _build_retrieval_query

history = [ConversationMessage(role="user", content="What techniques reduce hallucinations in LLMs?")]

tests = [
    "tell me more about the first paper",
    "what are the limitations?",
    "can you elaborate on that?",
    "explain more about RLHF",
    "What papers discuss knowledge distillation?",
    "which paper had the best results?",
]

for msg in tests:
    q = _build_retrieval_query(msg, history)
    tag = "(expanded) " if q != msg else "(unchanged)"
    print(tag, repr(msg))
    if q != msg:
        print("          ->", repr(q[:100]))
