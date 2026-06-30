import re

def classify_query(query_text):
    query_clean = query_text.strip().lower()
    
    # 1. PAGE_QUERY
    # Matches "page 15", "pg 2", "p. 5", etc.
    page_match = re.search(r'\b(?:page|pg\.?|p\.?)\s*(\d+)\b', query_clean)
    if page_match:
        page_num = int(page_match.group(1))
        # Note: Users specify 1-indexed pages. We convert to 0-indexed page in retriever.
        return {
            "type": "PAGE_QUERY",
            "page_num": page_num
        }
        
    # 2. COMPARE_QUERY
    # Matches "compare", "difference", "vs", "versus"
    if re.search(r'\b(?:compare|comparison|difference|differences|versus|vs)\b', query_clean):
        return {
            "type": "COMPARE_QUERY"
        }
        
    # 3. CODE_QUERY
    # Matches "code", "snippet", "example", language names
    if re.search(r'\b(?:code|snippet|example|python|c\+\+|java|sql|javascript|html|css|programming|function|class)\b', query_clean):
        return {
            "type": "CODE_QUERY"
        }
        
    # 4. SUMMARY_QUERY
    # Matches "summarize", "summary", "overview", "what is this document about"
    if re.search(r'\b(?:summarize|summary|overview|outline|synopsis|about the document|about the pdf|important information|important info|main points|key points|general details|details of this|what is in this|what does this pdf contain|what does this document contain)\b', query_clean) or (re.search(r'\b(?:pdf|document)\b', query_clean) and re.search(r'\b(?:information|info|details|content|contents|about|explain)\b', query_clean)):
        return {
            "type": "SUMMARY_QUERY"
        }
        
    # 5. SECTION_QUERY
    # Check for section names in query
    section_patterns = {
        "Projects": r'\b(?:project|projects|portfolio|work samples)\b',
        "Skills": r'\b(?:skill|skills|technologies|tech|languages|frameworks|tools|stack)\b',
        "Experience": r'\b(?:experience|job|jobs|work|history|intern|internship|internships|employment|career)\b',
        "Education": r'\b(?:education|degree|degrees|university|college|academic|qualification|qualifications|school|study)\b',
        "Certificates": r'\b(?:certificate|certificates|certification|certifications|awards|achievements|courses)\b'
    }
    
    for section_name, pattern in section_patterns.items():
        if re.search(pattern, query_clean):
            return {
                "type": "SECTION_QUERY",
                "section": section_name
            }
            
    # 6. GENERAL_QUERY
    return {
        "type": "GENERAL_QUERY"
    }
