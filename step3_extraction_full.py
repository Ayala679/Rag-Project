import os
import json
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.core.llms import ChatMessage
from llama_index.llms.cohere import Cohere

load_dotenv()

# הגדרת LLM
Settings.llm = Cohere(model="command-r-08-2024", api_key=os.getenv("COHERE_API_KEY"))

def find_line_range(content, text_snippet):
    """מציאת מספר השורה של text snippet בקובץ"""
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if text_snippet in line:
            return [i+1, i+1]
    return [0, 0]

def find_anchor(content, text_snippet):
    """מציאת anchor (כותרת הסעיף) לפריט"""
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if text_snippet in line:
            # חפש כותרת לאחור
            for j in range(i, -1, -1):
                if lines[j].startswith('#'):
                    return lines[j].replace('#', '').strip()
    return ""

def extract_decisions_from_content(content, file_path, tool_name):
    """חילוץ החלטות מתוכן קובץ"""
    decisions = []
    lines = content.split('\n')
    
    # תבניות לחילוץ החלטות
    patterns = [
        r'(?:בחירת|בחרנו|נבחר|הוחלט)\s+(.+?)(?::|[:])',
        r'### .*(?:בחירה|החלטה|Decision).*\n(.+)',
    ]
    
    for i, line in enumerate(lines):
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # קבל קצת context
                summary_lines = []
                for j in range(i+1, min(i+3, len(lines))):
                    if lines[j].strip() and not lines[j].startswith('#'):
                        summary_lines.append(lines[j].strip())
                
                summary = " ".join(summary_lines)[:200]
                
                decision = {
                    "id": f"dec-{len(decisions)+1:03d}",
                    "title": title,
                    "summary": summary,
                    "tags": ["architecture", "decision"],
                    "source": {
                        "tool": tool_name,
                        "file": file_path,
                        "anchor": find_anchor(content, line),
                        "line_range": [i+1, i+1]
                    },
                    "observed_at": datetime.now().isoformat()
                }
                decisions.append(decision)
    
    return decisions

def extract_rules_from_content(content, file_path, tool_name):
    """חילוץ כללים/הנחיות מתוכן קובץ"""
    rules = []
    lines = content.split('\n')
    
    keywords = ["חובה", "צריך", "מומלץ", "כלל", "חייב", "אסור"]
    
    for i, line in enumerate(lines):
        if not line.strip() or line.startswith('#'):
            continue
        
        if any(keyword in line for keyword in keywords):
            # נקה עיצוב markdown
            clean_line = re.sub(r'[*_`#]', '', line).strip()
            
            rule = {
                "id": f"rule-{len(rules)+1:03d}",
                "rule": clean_line,
                "scope": "general",
                "notes": "",
                "source": {
                    "tool": tool_name,
                    "file": file_path,
                    "anchor": find_anchor(content, line),
                    "line_range": [i+1, i+1]
                },
                "observed_at": datetime.now().isoformat()
            }
            rules.append(rule)
    
    return rules

def extract_warnings_from_content(content, file_path, tool_name):
    """חילוץ אזהרות/סיכונים מתוכן קובץ"""
    warnings = []
    lines = content.split('\n')
    
    keywords = ["זהיר", "רגיש", "אזהרה", "סיכון", "בעייתי", "מסוכן", "אסור"]
    
    for i, line in enumerate(lines):
        if not line.strip() or line.startswith('#'):
            continue
        
        if any(keyword in line for keyword in keywords):
            clean_line = re.sub(r'[*_`#]', '', line).strip()
            
            warning = {
                "id": f"warn-{len(warnings)+1:03d}",
                "area": "general",
                "message": clean_line,
                "severity": "medium",
                "source": {
                    "tool": tool_name,
                    "file": file_path,
                    "anchor": find_anchor(content, line),
                    "line_range": [i+1, i+1]
                },
                "observed_at": datetime.now().isoformat()
            }
            warnings.append(warning)
    
    return warnings

def extract_structured_data():
    """חילוץ מובנה של נתונים מתוך קבצי md"""
    
    # טעינת מסמכים
    documents = SimpleDirectoryReader('./data').load_data()
    
    # אתחול collections
    all_decisions = []
    all_rules = []
    all_warnings = []
    sources = []
    
    # עיבוד כל מסמך
    for doc in documents:
        file_path = doc.metadata.get('file_path', '')
        file_path_obj = Path(file_path)
        tool_name = "unknown"
        
        # רשום את המקור
        source_entry = {
            "tool": tool_name,
            "root_path": str(file_path_obj.parent),
            "files": [{
                "path": file_path,
                "last_modified": datetime.now().isoformat(),
                "hash": ""
            }]
        }
        sources.append(source_entry)
        
        content = doc.text
        
        # חילוץ פריטים
        decisions = extract_decisions_from_content(content, file_path, tool_name)
        rules = extract_rules_from_content(content, file_path, tool_name)
        warnings = extract_warnings_from_content(content, file_path, tool_name)
        
        all_decisions.extend(decisions)
        all_rules.extend(rules)
        all_warnings.extend(warnings)
    
    # בנייצ סכמה סופית
    structured_data = {
        "schema_version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "sources": sources,
        "items": {
            "decisions": all_decisions,
            "rules": all_rules,
            "warnings": all_warnings
        }
    }
    
    # שמירה לקובץ
    with open('structured_data_full.json', 'w', encoding='utf-8') as f:
        json.dump(structured_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Extracted {len(all_decisions)} decisions, {len(all_rules)} rules, {len(all_warnings)} warnings")
    print(f"📄 Saved to structured_data_full.json")
    
    return structured_data

if __name__ == "__main__":
    extract_structured_data()
