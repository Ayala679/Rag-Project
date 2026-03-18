import os
from dotenv import load_dotenv

# רכיבי LlamaIndex לפי שלב א'
from llama_index.core import (
    VectorStoreIndex, 
    SimpleDirectoryReader, 
    Settings, 
    StorageContext, 
    get_response_synthesizer
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.cohere import CohereEmbedding
from llama_index.llms.cohere import Cohere
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone
import gradio as gr

# 1. טעינת מפתחות
load_dotenv()

# --- הגדרת Cohere LLM (עובד בחופש!) ---
Settings.llm = Cohere(
    model="command-r-08-2024",
    api_key=os.getenv("COHERE_API_KEY")
)

# --- שלב א': הכנת הנתונים (לפי ההוראות) ---

# א. Embedding - שימוש ב-Cohere (לפי ההוראות)
Settings.embed_model = CohereEmbedding(
    api_key=os.getenv("COHERE_API_KEY"),
    model_name="embed-multilingual-v3.0"
)

# ב. Chunking - שימוש ב-Node Parser (גדלנו מאוד כדי לכלול טבלאות שלמות)
Settings.node_parser = SentenceSplitter(chunk_size=4096, chunk_overlap=400)

def init_system():
    # ג. חיבור ל-Pinecone
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    pinecone_index = pc.Index("rag-project")
    
    vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # ד. Loading - טעינת קבצי ה-md (ודאי שיש תיקיית data עם קבצים)
    documents = SimpleDirectoryReader("./data").load_data()
    
    # ה. Metadata - הוספת הקשר (חובה לפי המטלה)
    for doc in documents:
        path = doc.metadata.get("file_path", "").lower()
        source = "Cursor" if "cursor" in path else "Claude" if "claude" in path else "General"
        doc.metadata.update({
            "tool": source,
            "project": "SmartTask"
        })

    # ו. יצירת האינדקס
    return VectorStoreIndex.from_documents(
        documents, 
        storage_context=storage_context
    )

# --- חלק שני: תשאול והסקה ---

print("מאתחל את המערכת... הפעם זה עולה.")
index = init_system()

def ask_rag(message, history):
    try:
        # שליפה וניסוח לפי שלב א' - שיפור למידע מלא יותר
        retriever = index.as_retriever(similarity_top_k=10)
        nodes = retriever.retrieve(message)
        
        # שימוש ב-tree_summarize להשגת מידע מלא יותר
        synth = get_response_synthesizer(
            response_mode="tree_summarize",
            use_async=False,
            streaming=False
        )
        response = synth.synthesize(message, nodes)
        return str(response)
    except Exception as e:
        return f"שגיאה: {str(e)}"

# ז. ממשק Gradio
demo = gr.ChatInterface(fn=ask_rag, title="📊 SmartTask Advisor - MVP")

if __name__ == "__main__":
    demo.launch()