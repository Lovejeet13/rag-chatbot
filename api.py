import os
import shutil
import uuid
import json
import time
import asyncio
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import fitz # PyMuPDF
import zipfile
import xml.etree.ElementTree as ET

from dotenv import load_dotenv, find_dotenv
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

# Load modular backend scripts
from create_memory_forLLM import get_embedding_model
from connect_memory_with_llm import load_llm, HUGGINGFACE_REPO_ID
from ingestion_parser import process_document_to_chunks
from custom_retriever import retrieve_routed_documents, format_context_and_citations
from prompt_templates import get_grounded_prompt

# Load environment
load_dotenv(find_dotenv())

app = FastAPI(title="RAG Chatbot API")

# Add CORS Middleware for React frontend on Port 5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = "config.json"
SESSIONS_DIR = os.path.join("data", "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# In-memory session store: session_id -> session dict
# Schema: { "id": str, "title": str, "timestamp": str, "pinned": bool, "uploaded_files": List[dict], "messages": List[dict], "vector_db": FAISS }
SESSIONS: Dict[str, Dict[str, Any]] = {}

class ConfigUpdate(BaseModel):
    chunk_size: int
    chunk_overlap: int
    retrieval_k: int
    summary_k: int
    confidence_threshold: float
    enable_ocr: bool
    streaming: bool
    show_sources: bool

class SessionUpdate(BaseModel):
    title: str = None
    pinned: bool = None

class ChatPayload(BaseModel):
    message: str

# --- CONFIG MANAGEMENT ---

def read_config():
    default_config = {
        "chunk_size": 700,
        "chunk_overlap": 120,
        "retrieval_k": 5,
        "summary_k": 8,
        "confidence_threshold": 1.45,
        "enable_ocr": False,
        "streaming": True,
        "show_sources": False
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception:
            pass
    return default_config

def save_config(config_data):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
    except Exception as e:
        print(f"Failed to write config: {e}")

# --- DOCUMENT PARSERS ---

def parse_docx(file_path):
    try:
        with zipfile.ZipFile(file_path) as docx:
            xml_content = docx.read('word/document.xml')
            root = ET.fromstring(xml_content)
            paragraphs = []
            for para in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                text = ''.join(node.text for node in para.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text)
                if text.strip():
                    paragraphs.append(text)
            return '\n\n'.join(paragraphs)
    except Exception as e:
        print(f"DOCX parser error: {e}")
        return ""

# EasyOCR cached load
_ocr_reader = None
def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _ocr_reader

def run_ocr_on_bytes(image_bytes):
    reader = get_ocr_reader()
    result = reader.readtext(image_bytes, detail=0, paragraph=True)
    return "\n\n".join(result)

def process_stored_files(session_id: str, filenames: List[str], enable_ocr: bool = False) -> List[Document]:
    documents = []
    session_path = os.path.join(SESSIONS_DIR, session_id)
    
    for filename in filenames:
        file_path = os.path.join(session_path, filename)
        if not os.path.exists(file_path):
            continue
            
        if filename.lower().endswith('.pdf'):
            try:
                with fitz.open(file_path) as doc_fitz:
                    for i, page_fitz in enumerate(doc_fitz):
                        text = page_fitz.get_text()
                        if enable_ocr and (not text or len(text.strip()) < 50):
                            try:
                                pix = page_fitz.get_pixmap(dpi=90)
                                img_bytes = pix.tobytes("png")
                                ocr_text = run_ocr_on_bytes(img_bytes)
                                if ocr_text.strip():
                                    text = ocr_text
                            except Exception as e:
                                print(f"OCR failed for page {i+1} of {filename}: {e}")
                        
                        metadata = {"source": filename, "page": i}
                        documents.append(Document(page_content=text, metadata=metadata))
            except Exception as e:
                print(f"Error parsing PDF {filename}: {e}")
                
        elif filename.lower().endswith('.txt'):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                documents.append(Document(page_content=content, metadata={"source": filename, "page": 0}))
            except Exception as e:
                print(f"Error parsing TXT {filename}: {e}")
                
        elif filename.lower().endswith('.docx'):
            try:
                content = parse_docx(file_path)
                if content.strip():
                    documents.append(Document(page_content=content, metadata={"source": filename, "page": 0}))
            except Exception as e:
                print(f"Error parsing DOCX {filename}: {e}")
                
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            try:
                if enable_ocr:
                    with open(file_path, "rb") as f:
                        img_bytes = f.read()
                    ocr_text = run_ocr_on_bytes(img_bytes)
                    if ocr_text.strip():
                        documents.append(Document(page_content=ocr_text, metadata={"source": filename, "page": 0}))
            except Exception as e:
                print(f"Error OCR image {filename}: {e}")
                
    return documents

def rebuild_vector_db(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        return
        
    filenames = [f["name"] for f in session["uploaded_files"]]
    if not filenames:
        session["vector_db"] = None
        return
        
    config = read_config()
    documents = process_stored_files(session_id, filenames, enable_ocr=config.get("enable_ocr", False))
    documents = [doc for doc in documents if doc.page_content and doc.page_content.strip()]
    
    if not documents:
        session["vector_db"] = None
        return
        
    # Group by source and chunk
    grouped = {}
    for doc in documents:
        src = doc.metadata.get("source", "Unknown")
        if src not in grouped:
            grouped[src] = []
        grouped[src].append(doc)
        
    text_chunks = []
    for src, pages in grouped.items():
        sorted_pages = sorted(pages, key=lambda p: p.metadata.get("page", 0))
        chunks = process_document_to_chunks(sorted_pages, src)
        text_chunks.extend(chunks)
        
    text_chunks = [c for c in text_chunks if c.page_content and c.page_content.strip()]
    
    if not text_chunks:
        session["vector_db"] = None
        return
        
    embedding_model = get_embedding_model()
    db = FAISS.from_documents(text_chunks, embedding_model)
    session["vector_db"] = db

# --- ENDPOINTS ---

@app.get("/api/config")
def get_config():
    return read_config()

@app.post("/api/config")
def update_config(payload: ConfigUpdate):
    config = payload.dict()
    save_config(config)
    return config

@app.get("/api/sessions")
def get_sessions():
    res = []
    for s_id, s in SESSIONS.items():
        res.append({
            "id": s["id"],
            "title": s["title"],
            "timestamp": s["timestamp"],
            "pinned": s["pinned"],
            "uploaded_files": s["uploaded_files"],
            "messages": [
                {"role": m["role"], "content": m["content"], "timestamp": m["timestamp"], "sources": m.get("sources", [])}
                for m in s["messages"]
            ]
        })
    # Sort pinned first, then newest first
    pinned = [s for s in res if s["pinned"]]
    unpinned = [s for s in res if not s["pinned"]]
    return pinned + unpinned

@app.post("/api/sessions")
def create_session():
    s_id = str(uuid.uuid4())
    timestamp = time.strftime("%Y-%m-%d %H:%M")
    session = {
        "id": s_id,
        "title": "New Chat",
        "timestamp": timestamp,
        "pinned": False,
        "uploaded_files": [],
        "messages": [],
        "vector_db": None
    }
    SESSIONS[s_id] = session
    os.makedirs(os.path.join(SESSIONS_DIR, s_id), exist_ok=True)
    return {
        "id": s_id,
        "title": session["title"],
        "timestamp": session["timestamp"],
        "pinned": session["pinned"],
        "uploaded_files": [],
        "messages": []
    }

@app.put("/api/sessions/{session_id}")
def update_session(session_id: str, payload: SessionUpdate):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.title is not None:
        session["title"] = payload.title
    if payload.pinned is not None:
        session["pinned"] = payload.pinned
    return {
        "id": session_id,
        "title": session["title"],
        "pinned": session["pinned"]
    }

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    if session_id in SESSIONS:
        del SESSIONS[session_id]
    session_path = os.path.join(SESSIONS_DIR, session_id)
    if os.path.exists(session_path):
        shutil.rmtree(session_path)
    return {"status": "success"}

@app.post("/api/sessions/{session_id}/duplicate")
def duplicate_session(session_id: str):
    orig = SESSIONS.get(session_id)
    if not orig:
        raise HTTPException(status_code=404, detail="Session not found")
        
    s_id = str(uuid.uuid4())
    timestamp = time.strftime("%Y-%m-%d %H:%M")
    
    # Duplicate files on disk
    orig_path = os.path.join(SESSIONS_DIR, session_id)
    new_path = os.path.join(SESSIONS_DIR, s_id)
    os.makedirs(new_path, exist_ok=True)
    if os.path.exists(orig_path):
        for f in os.listdir(orig_path):
            shutil.copy2(os.path.join(orig_path, f), os.path.join(new_path, f))
            
    dup_session = {
        "id": s_id,
        "title": f"{orig['title']} (Copy)",
        "timestamp": timestamp,
        "pinned": False,
        "uploaded_files": list(orig["uploaded_files"]),
        "messages": list(orig["messages"]),
        "vector_db": orig["vector_db"] # share active vector index
    }
    SESSIONS[s_id] = dup_session
    return {
        "id": s_id,
        "title": dup_session["title"],
        "timestamp": dup_session["timestamp"],
        "pinned": dup_session["pinned"],
        "uploaded_files": dup_session["uploaded_files"],
        "messages": [
            {"role": m["role"], "content": m["content"], "timestamp": m["timestamp"], "sources": m.get("sources", [])}
            for m in dup_session["messages"]
        ]
    }

@app.post("/api/sessions/{session_id}/upload")
def upload_file(session_id: str, file: UploadFile = File(...)):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    filename = file.filename
    session_path = os.path.join(SESSIONS_DIR, session_id)
    file_path = os.path.join(session_path, filename)
    
    # Save file to disk
    with open(file_path, "wb") as f:
        f.write(file.file.read())
        
    size_bytes = os.path.getsize(file_path)
    size_kb = size_bytes / 1024
    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
    
    # Extract page count if PDF
    pages = 1
    if filename.lower().endswith('.pdf'):
        try:
            with fitz.open(file_path) as doc_fitz:
                pages = len(doc_fitz)
        except Exception:
            pass
            
    # Add metadata to list
    file_metadata = {
        "name": filename,
        "size": size_str,
        "pages": pages
    }
    
    # Avoid duplicate file entries
    session["uploaded_files"] = [f for f in session["uploaded_files"] if f["name"] != filename]
    session["uploaded_files"].append(file_metadata)
    
    # Trigger reindexing
    rebuild_vector_db(session_id)
    
    # Auto rename session if it is New Chat
    if session["title"] == "New Chat" and session["uploaded_files"]:
        session["title"] = f"Chat: {filename[:20]}"
        
    return {
        "uploaded_files": session["uploaded_files"],
        "title": session["title"]
    }

@app.delete("/api/sessions/{session_id}/documents/{filename}")
def delete_document(session_id: str, filename: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session["uploaded_files"] = [f for f in session["uploaded_files"] if f["name"] != filename]
    file_path = os.path.join(SESSIONS_DIR, session_id, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        
    # Reindex remaining files
    rebuild_vector_db(session_id)
    
    return {"uploaded_files": session["uploaded_files"]}

# --- SSE STREAMING & CHAT ---

@app.post("/api/sessions/{session_id}/chat")
def handle_chat(session_id: str, payload: ChatPayload):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    user_query = payload.message
    timestamp = time.strftime("%H:%M")
    
    # Save user message to memory
    session["messages"].append({
        "role": "user",
        "content": user_query,
        "timestamp": timestamp,
        "sources": []
    })
    
    config = read_config()
    db = session.get("vector_db")
    
    # Verify vector db exists
    if db is None:
        fallback_msg = "Please upload documents above before asking questions."
        session["messages"].append({
            "role": "assistant",
            "content": fallback_msg,
            "timestamp": timestamp,
            "sources": []
        })
        return {
            "role": "assistant",
            "content": fallback_msg,
            "timestamp": timestamp,
            "sources": []
        }
        
    # Retrieve routed documents
    retrieved_docs, status = retrieve_routed_documents(user_query, db)
    
    if status in ("low_confidence", "no_documents") or not retrieved_docs:
        fallback_msg = "I couldn't find this information in the uploaded documents."
        session["messages"].append({
            "role": "assistant",
            "content": fallback_msg,
            "timestamp": timestamp,
            "sources": []
        })
        return {
            "role": "assistant",
            "content": fallback_msg,
            "timestamp": timestamp,
            "sources": []
        }
        
    # Format context
    context_str, citation_block = format_context_and_citations(retrieved_docs)
    
    # Format citations
    sources = []
    for doc in retrieved_docs:
        src_name = os.path.basename(doc.metadata.get("source", "Unknown Document"))
        page = doc.metadata.get("page", 0) + 1
        sec = doc.metadata.get("section", "General")
        chip = f"{src_name} (Page {page}, {sec})"
        if chip not in sources:
            sources.append(chip)
            
    # Format conversation history
    history_str = ""
    recent = session["messages"][:-1][-4:]
    for m in recent:
        role_lbl = "User" if m["role"] == "user" else "Assistant"
        history_str += f"{role_lbl}: {m['content']}\n"
    if not history_str:
        history_str = "No previous conversation history."
        
    custom_prompt = get_grounded_prompt(history_str)
    final_prompt = custom_prompt.format(context=context_str, question=user_query)
    
    # If streaming configuration is off, return simple JSON
    if not config.get("streaming", True):
        try:
            llm = load_llm(HUGGINGFACE_REPO_ID)
            response = llm.invoke(final_prompt)
            content = response.content.strip()
            
            # Grounded checks
            if "couldn't find" in content.lower() or "not find" in content.lower():
                content = "I couldn't find this information in the uploaded documents."
                sources = []
                
            session["messages"].append({
                "role": "assistant",
                "content": content,
                "timestamp": timestamp,
                "sources": sources
            })
            return {
                "role": "assistant",
                "content": content,
                "timestamp": timestamp,
                "sources": sources
            }
        except Exception as e:
            err = f"Error generating response: {e}"
            session["messages"].append({
                "role": "assistant",
                "content": err,
                "timestamp": timestamp,
                "sources": []
            })
            return {
                "role": "assistant",
                "content": err,
                "timestamp": timestamp,
                "sources": []
            }
            
    # For streaming, return Server Sent Events
    async def sse_event_stream():
        nonlocal final_prompt, timestamp, session, sources
        try:
            llm = load_llm(HUGGINGFACE_REPO_ID)
            stream_generator = llm.stream(final_prompt)
            full_response = ""
            
            for chunk in stream_generator:
                text = chunk.content if hasattr(chunk, "content") else str(chunk)
                full_response += text
                yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
                await asyncio.sleep(0.01)
                
            cleaned = full_response.strip()
            # Grounded check
            if "couldn't find" in cleaned.lower() or "not find" in cleaned.lower():
                cleaned = "I couldn't find this information in the uploaded documents."
                sources = []
                # Clear and send final correction
                yield f"data: {json.dumps({'type': 'corrected', 'content': cleaned})}\n\n"
                
            session["messages"].append({
                "role": "assistant",
                "content": cleaned,
                "timestamp": timestamp,
                "sources": sources
            })
            
            yield f"data: {json.dumps({'type': 'done', 'sources': sources})}\n\n"
        except Exception as e:
            err = f"Streaming generation error: {e}"
            yield f"data: {json.dumps({'type': 'error', 'content': err})}\n\n"
            
    return StreamingResponse(sse_event_stream(), media_type="text/event-stream")

# Serve Frontend static files
frontend_path = os.path.join("frontend", "dist")
if os.path.exists(frontend_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="assets")
    
    @app.get("/{catchall:path}")
    async def serve_frontend(catchall: str):
        target_file = os.path.join(frontend_path, catchall)
        if os.path.exists(target_file) and os.path.isfile(target_file):
            return FileResponse(target_file)
        index_file = os.path.join(frontend_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend build files not found")
