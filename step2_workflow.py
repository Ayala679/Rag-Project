import os
from dotenv import load_dotenv
from llama_index.core import StorageContext, VectorStoreIndex, Settings
from llama_index.embeddings.cohere import CohereEmbedding
from llama_index.llms.cohere import Cohere
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone
from llama_index.core.workflow import (
    Event, 
    StartEvent, 
    StopEvent, 
    Workflow, 
    step,
    Context
)
import gradio as gr

# 1. טעינת מפתחות
load_dotenv()

# --- הגדרות מודלים (לפי סטאק הטכנולוגי שבמטלה) ---
Settings.llm = Cohere(
    model="command-r-08-2024", 
    api_key=os.getenv("COHERE_API_KEY")
)
Settings.embed_model = CohereEmbedding(
    api_key=os.getenv("COHERE_API_KEY"), 
    model_name="embed-multilingual-v3.0"
)

# --- הגדרת אירועים (Events) ---
class RetrievalEvent(Event):
    """אירוע שקורה אחרי ששלפנו מידע מה-DB"""
    nodes: list

# --- הגדרת ה-Workflow (ארכיטקטורת Event-Driven) ---
class RAGWorkflow(Workflow):
    
    def __init__(self, index, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = index
        self.query = None  # שמירת השאלה כ-instance variable

    @step
    async def run_retrieval(self, ctx: Context, ev: StartEvent) -> RetrievalEvent | StopEvent:
        query = ev.get("query")
        
        # שמירת השאלה כ-instance variable
        self.query = query
        
        # ולידציה בסיסית
        if not query or len(query.strip()) < 2:
            return StopEvent(result="השאלה קצרה מדי, נא לשאול שוב בפירוט.")

        print(f"Running step run_retrieval\nמבצע שליפה עבור: {query}")
        
        # שימוש ב-Retriever למציאת Nodes
        retriever = self.index.as_retriever(similarity_top_k=5)
        nodes = retriever.retrieve(query)
        
        # ולידציה: האם נמצאו תוצאות?
        if not nodes:
            return StopEvent(result="מצטער, לא מצאתי מידע רלוונטי במסמכים.")
            
        return RetrievalEvent(nodes=nodes)

    @step
    async def generate_response(self, ctx: Context, ev: RetrievalEvent) -> StopEvent:
        print("Running step generate_response")
        from llama_index.core import get_response_synthesizer
        
        # שליפת השאלה המקורית מה-instance variable
        query = self.query 
        
        # יצירת תשובה סופית (Synthesizing)
        synth = get_response_synthesizer(response_mode="tree_summarize")
        response = synth.synthesize(query, ev.nodes)
        
        return StopEvent(result=str(response))

# --- חיבור ל-Pinecone וטעינת האינדקס ---
def setup_index():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    # ודאי שהשם 'rag-project' תואם למה שהגדרת ב-Pinecone
    pinecone_index = pc.Index("rag-project")
    vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
    return VectorStoreIndex.from_vector_store(vector_store=vector_store)

# --- אתחול המערכת ---
try:
    index = setup_index()
    workflow = RAGWorkflow(index=index, timeout=60, verbose=True)
except Exception as e:
    print(f"שגיאה באתחול האינדקס: {e}")

# --- ממשק Gradio ---
async def chat_interface(message, history):
    try:
        # הרצת ה-Workflow
        result = await workflow.run(query=message)
        return result
    except Exception as e:
        return f"שגיאה בזמן הריצה: {str(e)}"

demo = gr.ChatInterface(
    fn=chat_interface, 
    title="📊 SmartTask Advisor - Workflow Edition (Step 2)"
)

if __name__ == "__main__":
    demo.launch()