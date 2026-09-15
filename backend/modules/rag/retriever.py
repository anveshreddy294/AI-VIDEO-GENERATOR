from modules.rag.store import KnowledgeStore

def retrieve(session_id, query, top_k=5):
    return KnowledgeStore().retrieve(session_id, query, top_k)
