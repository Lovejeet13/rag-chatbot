import os
import json
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

def load_config(config_path="config.json"):
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "chunk_size": 700,
        "chunk_overlap": 120,
        "supported_sections": {}
    }

def classify_document_type(full_text, total_pages, file_name):
    ext = os.path.splitext(file_name.lower())[1]
    text_lower = full_text.lower()
    
    # 1. Resume detection
    resume_keywords = ["experience", "education", "skills", "projects", "employment", "achievements", "work history"]
    resume_hits = sum(1 for kw in resume_keywords if kw in text_lower)
    if total_pages <= 3 and resume_hits >= 3:
        return "Resume"
        
    # 2. Research Paper detection
    paper_keywords = ["abstract", "introduction", "conclusion", "references", "methodology", "literature review"]
    paper_hits = sum(1 for kw in paper_keywords if kw in text_lower)
    if paper_hits >= 3:
        return "Research Paper"
        
    # 3. Book detection
    if total_pages >= 50:
        return "Book"
        
    # 4. Notes detection
    if ext == ".txt" and total_pages <= 10:
        return "Notes"
        
    return "General Document"

def detect_section_header(line, section_keywords):
    """
    Check if a line represents a section header by matching keyword patterns.
    """
    line_clean = line.strip().lower().rstrip(":").strip()
    if not line_clean or len(line_clean) > 40:
        return None
        
    for section_name, keywords in section_keywords.items():
        for kw in keywords:
            # Check exact match or check if line equals keyword
            if line_clean == kw.lower():
                return section_name
    return None

def process_document_to_chunks(pages, file_name, config_path="config.json"):
    """
    Takes a list of langchain Documents (one per page) and returns split chunks with rich metadata.
    """
    config = load_config(config_path)
    chunk_size = config.get("chunk_size", 700)
    chunk_overlap = config.get("chunk_overlap", 120)
    section_keywords = config.get("supported_sections", {})
    
    # Extract full text to classify document type
    full_text = "\n".join([page.page_content for page in pages])
    total_pages = len(pages)
    doc_type = classify_document_type(full_text, total_pages, file_name)
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )
    
    processed_chunks = []
    chunk_counter = 0
    active_section = "General"
    
    for page_idx, page in enumerate(pages):
        page_content = page.page_content
        page_num = page.metadata.get("page", page_idx)
        
        # Split text on this page
        raw_chunks = splitter.split_text(page_content)
        
        for raw_chunk in raw_chunks:
            # Check if this chunk contains a new section heading
            lines = raw_chunk.split("\n")
            for line in lines:
                detected = detect_section_header(line, section_keywords)
                if detected:
                    active_section = detected
                    break # Use the first detected section header in the chunk
            
            # Construct rich metadata
            meta = {
                "source": file_name,
                "page": page_num,
                "section": active_section,
                "document_type": doc_type,
                "chunk_index": chunk_counter
            }
            
            processed_chunks.append(Document(page_content=raw_chunk, metadata=meta))
            chunk_counter += 1
            
    return processed_chunks
