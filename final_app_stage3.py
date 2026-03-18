import os
import json
import re
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.workflow import Event, StartEvent, StopEvent, Workflow, step, Context
from llama_index.core.llms import ChatMessage
from llama_index.embeddings.cohere import CohereEmbedding
from llama_index.llms.cohere import Cohere
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone
import gradio as gr

load_dotenv()

# הגדרות מודלים
Settings.llm = Cohere(model="command-r-08-2024", api_key=os.getenv("COHERE_API_KEY"))
Settings.embed_model = CohereEmbedding(api_key=os.getenv("COHERE_API_KEY"), model_name="embed-multilingual-v3.0")

# --- הגדרת אירועים ---
class RouteEvent(Event):
    destination: str
    query: str

# --- ה-Workflow החכם ---
class SmartTaskRouter(Workflow):
    
    def __init__(self, index, structured_data_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = index
        self.structured_data_path = structured_data_path
        self.query = None

    @step
    async def router(self, ctx: Context, ev: StartEvent) -> RouteEvent:
        query = ev.get("query")
        self.query = query

        # לוגיקה חכמה לניתוב
        query_lower = query.lower()
        structured_patterns = [
            r'\b(מהן|אילו|רשימה|החלטות|טכנולוגיות|סטטוס)\b',
            r'\b(כל ה|תן לי|הצג|הראה)\b.*\b(החלטות|טכנולוגיות|כללים|אזהרות)\b',
            r'\b(עדכני|אחרון|חדש|אחרונה)\b',
            r'\b(רגיש|אזהרה|זהיר|מסוכן)\b',
        ]

        should_use_structured = any(re.search(pattern, query, re.IGNORECASE) for pattern in structured_patterns)

        list_keywords = ["רשימה", "אילו", "מהן", "החלטות", "טכנולוגיות", "סטטוס", "כללים", "אזהרות"]
        if any(word in query for word in list_keywords):
            should_use_structured = True

        destination = "structured" if should_use_structured else "semantic"
        return RouteEvent(destination=destination, query=query)

    @step
    async def handle_structured(self, ev: RouteEvent) -> StopEvent:
        if ev.destination != "structured":
            return None

        # טעינת הנתונים המובנים
        with open(self.structured_data_path, "r", encoding="utf-8") as f:
            structured_data = json.load(f)

        # שלב 1: שלח ל-LLM ליצור שאילתה מתוך הסכמה
        schema_desc = self._describe_schema(structured_data)
        
        prompt = f"""אתה עוזר לעיבוד שאילתות מובנות מתוך JSON.

סכמת הנתונים:
{schema_desc}

שאלת המשתמש: {ev.query}

בהתאם לסכמה, החזר JSON בעברית עם המלצה:
{{
  "items_type": "decisions|rules|warnings",
  "filters": {{"field": "value"}},
  "explanation": "הסבר קצר"
}}"""

        messages = [ChatMessage(role="user", content=prompt)]
        response = Settings.llm.chat(messages)
        
        try:
            response_text = str(response).replace("assistant: ", "").strip()
            query_suggestion = json.loads(response_text)
            items_type = query_suggestion.get("items_type", "decisions")
            filters = query_suggestion.get("filters", {})
        except Exception as e:
            # fallback
            items_type = "decisions"
            filters = {}

        # שלב 2: בצע את השאילתה
        items = structured_data["items"].get(items_type, [])
        filtered_items = self._filter_items(items, filters, ev.query)

        # שלב 3: בנה תשובה
        if not filtered_items:
            result = f"לא נמצאו {items_type} התואמים לשאלתך."
        else:
            result = f"נמצאו {len(filtered_items)} {items_type}:\n\n"
            for item in filtered_items:
                result += self._format_item(item, items_type)
                if item.get("source"):
                    src = item["source"]
                    line_range = src.get('line_range', [0, 0])
                    result += f"  📍 {src.get('file', 'unknown')} | שורה {line_range[0]}\n"

        return StopEvent(result=result)

    def _describe_schema(self, data):
        """תיאור הסכמה עבור ה-LLM"""
        return """
## סכמת הנתונים

### Decisions (החלטות טכניות)
כל החלטה מכילה: title, summary, tags (architecture, backend, frontend, etc.), source metadata

### Rules (כללים הנחיות)
כל כלל מכילה: rule (טקסט), scope (תחום יישום), source metadata

### Warnings (אזהרות סיכונים)
כל אזהרה מכילה: message, severity (high/medium/low), source metadata

כל פריט מכיל source עם:
- tool: הכלי שבו הופיע
- file: נתיב הקובץ
- anchor: כותרת הסעיף
- line_range: טווח השורות [start, end]
"""

    def _filter_items(self, items, filters, query):
        """סינון פריטים בהתאם לפילטרים"""
        filtered = items
        query_lower = query.lower()
        
        # סינון לפי השאלה
        if "backend" in query_lower:
            filtered = [item for item in filtered if "backend" in str(item).lower()]
        elif "frontend" in query_lower:
            filtered = [item for item in filtered if "frontend" in str(item).lower()]
        elif "database" in query_lower or "מסד" in query_lower:
            filtered = [item for item in filtered if ("database" in str(item).lower() or "postgres" in str(item).lower())]
        
        return filtered

    def _format_item(self, item, item_type):
        """עיצוב פריט להצגה"""
        if item_type == "decisions":
            return f"• **{item.get('title', 'N/A')}**: {item.get('summary', 'N/A')}\n"
        elif item_type == "rules":
            return f"• **כלל**: {item.get('rule', 'N/A')}\n"
        elif item_type == "warnings":
            return f"• **⚠️ אזהרה**: {item.get('message', 'N/A')} (חומרה: {item.get('severity', 'unknown')})\n"
        return f"• {item}\n"

    @step
    async def handle_semantic(self, ev: RouteEvent) -> StopEvent:
        if ev.destination != "semantic":
            return None

        retriever = self.index.as_retriever(similarity_top_k=3)
        nodes = retriever.retrieve(ev.query)

        from llama_index.core import get_response_synthesizer
        synth = get_response_synthesizer(response_mode="tree_summarize")
        response = synth.synthesize(ev.query, nodes)
        return StopEvent(result=str(response))

# --- אתחול ---
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index = pc.Index("rag-project")
vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

workflow = SmartTaskRouter(index=index, structured_data_path="structured_data_full.json", verbose=True)

async def chat(message, history):
    """Async function for Gradio to handle workflow calls"""
    result = await workflow.run(query=message)
    return str(result)

if __name__ == "__main__":
    gr.ChatInterface(fn=chat, title="🚀 SmartTask AI Agent - Stage 3 (LLM Query)").launch()
