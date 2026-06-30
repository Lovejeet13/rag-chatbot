import os
import json
from query_classifier import classify_query

def load_config(config_path="config.json"):
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "retrieval_k": 5,
        "summary_k": 8,
        "confidence_threshold": 1.2
    }

def get_all_documents(db):
    """
    Extract all Document objects stored in the FAISS database.
    """
    if hasattr(db, "docstore") and hasattr(db.docstore, "_dict"):
        return list(db.docstore._dict.values())
    return []

def get_chunk_lookup(all_docs):
    """
    Create a lookup map of {(source, page, chunk_index): doc} for neighbor retrieval.
    """
    lookup = {}
    for doc in all_docs:
        meta = doc.metadata
        source = meta.get("source")
        page = meta.get("page")
        chunk_idx = meta.get("chunk_index")
        if source is not None and page is not None and chunk_idx is not None:
            lookup[(source, page, chunk_idx)] = doc
    return lookup

def expand_with_neighbors(retrieved_docs, chunk_lookup):
    """
    Retrieve previous and next chunks if they are from the same document and page.
    """
    expanded_set = {}
    
    for doc in retrieved_docs:
        # Add the original doc
        meta = doc.metadata
        source = meta.get("source")
        page = meta.get("page")
        chunk_idx = meta.get("chunk_index")
        
        doc_key = (source, page, chunk_idx)
        expanded_set[doc_key] = doc
        
        if source is not None and page is not None and chunk_idx is not None:
            # Check previous chunk
            prev_key = (source, page, chunk_idx - 1)
            if prev_key in chunk_lookup:
                expanded_set[prev_key] = chunk_lookup[prev_key]
                
            # Check next chunk
            next_key = (source, page, chunk_idx + 1)
            if next_key in chunk_lookup:
                expanded_set[next_key] = chunk_lookup[next_key]
                
    # Convert back to list
    return list(expanded_set.values())

def merge_strings_with_overlap(s1, s2):
    """
    Finds the overlap between the end of s1 and start of s2 and merges them.
    If no overlap is found, joins them with a newline.
    """
    s1_clean = s1.rstrip()
    s2_clean = s2.lstrip()
    
    max_overlap = min(len(s1_clean), len(s2_clean))
    for i in range(max_overlap, 0, -1):
        if s1_clean.endswith(s2_clean[:i]):
            return s1_clean + s2_clean[i:]
            
    return s1 + "\n" + s2

def merge_consecutive_chunks(docs):
    """
    Deduplicates, sorts, and merges consecutive chunks of the same document & page.
    """
    if not docs:
        return []
        
    # 1. Deduplicate by key (source, page, chunk_index)
    seen = set()
    deduped_docs = []
    for doc in docs:
        meta = doc.metadata
        key = (meta.get("source"), meta.get("page"), meta.get("chunk_index"))
        if key not in seen:
            seen.add(key)
            deduped_docs.append(doc)
            
    # 2. Sort by source, page, and chunk_index
    sorted_docs = sorted(
        deduped_docs,
        key=lambda d: (d.metadata.get("source", ""), d.metadata.get("page", 0), d.metadata.get("chunk_index", 0))
    )
    
    # 3. Merge consecutive chunks
    merged_docs = []
    for doc in sorted_docs:
        if not merged_docs:
            # Add a copy so we don't mutate elements in place
            from langchain_core.documents import Document
            merged_docs.append(Document(page_content=doc.page_content, metadata=dict(doc.metadata)))
        else:
            last_doc = merged_docs[-1]
            last_meta = last_doc.metadata
            curr_meta = doc.metadata
            
            # Check if they are consecutive chunks from the same source and page
            same_source = last_meta.get("source") == curr_meta.get("source")
            same_page = last_meta.get("page") == curr_meta.get("page")
            consecutive = last_meta.get("chunk_index") is not None and curr_meta.get("chunk_index") is not None and (curr_meta.get("chunk_index") == last_meta.get("chunk_index") + 1)
            
            if same_source and same_page and consecutive:
                # Merge page content removing duplicate overlap
                last_doc.page_content = merge_strings_with_overlap(last_doc.page_content, doc.page_content)
                # Keep the last chunk index as the upper boundary
                last_meta["chunk_index"] = curr_meta.get("chunk_index")
            else:
                from langchain_core.documents import Document
                merged_docs.append(Document(page_content=doc.page_content, metadata=dict(doc.metadata)))
                
    return merged_docs

def format_context_and_citations(merged_docs):
    """
    Format merged chunks into a structured context string and citation block.
    """
    if not merged_docs:
        return "", ""
        
    context_parts = []
    citations = []
    
    for doc in merged_docs:
        src = doc.metadata.get("source", "Unknown Document")
        page = doc.metadata.get("page", 0) + 1 # Convert to 1-indexed
        section = doc.metadata.get("section", "General")
        
        context_parts.append(
            f"--- START OF CHUNK (Source: {src}, Page: {page}, Section: {section}) ---\n"
            f"{doc.page_content}\n"
            f"--- END OF CHUNK ---\n"
        )
        
        citation_str = f"- `{src}` (Page {page}, Section: {section})"
        if citation_str not in citations:
            citations.append(citation_str)
            
    context_str = "\n".join(context_parts)
    citation_block = "\n\n**Sources:**\n" + "\n".join(citations)
    
    return context_str, citation_block

def retrieve_routed_documents(query, db, config_path="config.json"):
    """
    Main retrieval entry point. Classifies query and routes to the best retrieval strategy.
    
    Returns:
        docs (list): List of retrieved Document objects.
        status (str): "success", "low_confidence", or "no_documents".
    """
    config = load_config(config_path)
    retrieval_k = config.get("retrieval_k", 5)
    summary_k = config.get("summary_k", 8)
    confidence_threshold = config.get("confidence_threshold", 1.2)
    
    # Classify the query
    classification = classify_query(query)
    query_type = classification["type"]
    
    all_docs = get_all_documents(db)
    chunk_lookup = get_chunk_lookup(all_docs)
    
    retrieved_docs = []
    need_confidence_check = False
    min_distance = 999.0
    
    # 1. PAGE_QUERY Routing
    if query_type == "PAGE_QUERY":
        requested_page = classification["page_num"] - 1 # Convert to 0-indexed
        
        # Filter all chunks matching this page
        # If a specific source is mentioned in query, filter by source too
        mentioned_source = None
        query_lower = query.lower()
        for doc in all_docs:
            src = doc.metadata.get("source", "")
            if src and src.lower() in query_lower:
                mentioned_source = src
                break
                
        for doc in all_docs:
            if doc.metadata.get("page") == requested_page:
                if mentioned_source is None or doc.metadata.get("source") == mentioned_source:
                    retrieved_docs.append(doc)
                    
        # Sort by chunk_index
        retrieved_docs = sorted(retrieved_docs, key=lambda d: d.metadata.get("chunk_index", 0))
        
    # 2. SECTION_QUERY Routing (Resume only)
    elif query_type == "SECTION_QUERY":
        target_section = classification["section"]
        
        # Check if we have any Resume document
        has_resume = any(doc.metadata.get("document_type") == "Resume" for doc in all_docs)
        
        if has_resume:
            for doc in all_docs:
                if doc.metadata.get("document_type") == "Resume" and doc.metadata.get("section") == target_section:
                    retrieved_docs.append(doc)
            
            # Sort by chunk_index
            retrieved_docs = sorted(retrieved_docs, key=lambda d: d.metadata.get("chunk_index", 0))
            
        # Fallback to similarity search if no resume or no section chunks found
        if not retrieved_docs:
            results_with_scores = db.similarity_search_with_score(query, k=retrieval_k)
            retrieved_docs = [doc for doc, score in results_with_scores]
            if results_with_scores:
                min_distance = min(score for doc, score in results_with_scores)
                need_confidence_check = True
                
    # 3. SUMMARY_QUERY Routing
    elif query_type == "SUMMARY_QUERY":
        results_with_scores = db.similarity_search_with_score(query, k=summary_k)
        retrieved_docs = [doc for doc, score in results_with_scores]
        if results_with_scores:
            min_distance = min(score for doc, score in results_with_scores)
            need_confidence_check = False
            
    # 4. GENERAL_QUERY, CODE_QUERY, COMPARE_QUERY Routing
    else:
        results_with_scores = db.similarity_search_with_score(query, k=retrieval_k)
        retrieved_docs = [doc for doc, score in results_with_scores]
        if results_with_scores:
            min_distance = min(score for doc, score in results_with_scores)
            need_confidence_check = True
            
    # Apply Confidence Check (distance score threshold)
    if need_confidence_check and retrieved_docs:
        if min_distance > confidence_threshold:
            return [], "low_confidence"
            
    if not retrieved_docs:
        return [], "no_documents"
        
    # Expand with neighbors
    expanded_docs = expand_with_neighbors(retrieved_docs, chunk_lookup)
    
    # Merge consecutive chunks
    final_docs = merge_consecutive_chunks(expanded_docs)
    return final_docs, "success"
