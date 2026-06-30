import React, { useState, useEffect, useRef } from 'react';
import { marked } from 'marked';
import UploadPanel from './UploadPanel';

// Set up custom marked renderer for code blocks
const renderer = new marked.Renderer();
renderer.code = function(args) {
  let text = '';
  let lang = '';
  if (typeof args === 'object' && args !== null) {
    text = args.text || '';
    lang = args.lang || '';
  } else {
    text = arguments[0] || '';
    lang = arguments[1] || '';
  }
  return `
    <div class="code-block-wrapper">
      <div class="code-header">
        <span>${lang || 'code'}</span>
        <button class="btn btn-sm btn-link text-light p-0 text-decoration-none copy-code-btn" data-code="${encodeURIComponent(text)}" type="button">
          <i class="bi bi-clipboard"></i> Copy
        </button>
      </div>
      <pre><code class="language-${lang}">${text}</code></pre>
    </div>
  `;
};

// Configure marked to render safe HTML and allow line breaks
marked.setOptions({
  breaks: true,
  gfm: true,
  renderer: renderer
});

export default function ChatWindow({
  session,
  config,
  onSendMessage,
  onRegenerateResponse,
  onEditMessage,
  onUploadFile,
  onDeleteDocument,
  isGenerating,
  onStopGeneration
}) {
  const [inputValue, setInputValue] = useState('');
  const [editingIdx, setEditingIdx] = useState(null);
  const [editingText, setEditingText] = useState('');
  const [copiedIdx, setCopiedIdx] = useState(null);
  
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const feedRef = useRef(null);

  // Auto-scroll to bottom of conversation
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session.messages, isGenerating]);

  // Event delegation to capture click on dynamically generated copy buttons inside markdown code blocks
  useEffect(() => {
    const handleContainerClick = (e) => {
      const copyBtn = e.target.closest('.copy-code-btn');
      if (copyBtn) {
        e.preventDefault();
        const encodedCode = copyBtn.getAttribute('data-code');
        const code = decodeURIComponent(encodedCode);
        navigator.clipboard.writeText(code);
        
        // Visual indicator of copy
        const originalHTML = copyBtn.innerHTML;
        copyBtn.innerHTML = '<i class="bi bi-check-lg text-success"></i> Copied';
        setTimeout(() => {
          copyBtn.innerHTML = originalHTML;
        }, 2000);
      }
    };
    
    const container = feedRef.current;
    if (container) {
      container.addEventListener('click', handleContainerClick);
    }
    return () => {
      if (container) {
        container.removeEventListener('click', handleContainerClick);
      }
    };
  }, [session.messages]);

  // Adjust input textarea height based on content
  const handleInputChange = (e) => {
    setInputValue(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitMessage();
    }
  };

  const submitMessage = () => {
    if (inputValue.trim() && !isGenerating) {
      onSendMessage(inputValue.trim());
      setInputValue('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleCopyMessage = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const startEdit = (idx, content) => {
    setEditingIdx(idx);
    setEditingText(content);
  };

  const saveEdit = (e) => {
    e.preventDefault();
    if (editingText.trim()) {
      onEditMessage(editingIdx, editingText.trim());
    }
    setEditingIdx(null);
  };

  const renderHTML = (markdownText) => {
    try {
      return { __html: marked.parse(markdownText || '') };
    } catch (e) {
      return { __html: markdownText || '' };
    }
  };

  return (
    <div className="chat-main">
      {/* Scrollable Timeline */}
      <div className="messages-feed" ref={feedRef}>
        <div className="chat-container-width">
          
          {/* File Upload Panel at the top - only visible when empty */}
          {(!session.messages || session.messages.length === 0) && (
            <>
              <UploadPanel 
                session={session} 
                onUploadFile={onUploadFile}
                onDeleteDocument={onDeleteDocument}
              />
              <hr className="my-4" style={{ borderColor: 'var(--border-color)', opacity: 0.5 }} />
            </>
          )}

          {/* Chat Timeline List */}
          {session.messages && session.messages.length > 0 ? (
            session.messages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              const isEditing = editingIdx === idx;

              return (
                <div key={idx} className="message-row">
                  <div className={`message-avatar ${isUser ? 'avatar-user' : 'avatar-assistant'}`}>
                    {isUser ? 'U' : 'AI'}
                  </div>

                  <div className="message-body">
                    {/* User Edit Mode */}
                    {isUser && isEditing ? (
                      <form onSubmit={saveEdit} className="d-flex flex-column gap-2 mt-1">
                        <textarea 
                          className="form-control" 
                          rows="3"
                          value={editingText}
                          onChange={(e) => setEditingText(e.target.value)}
                          autoFocus
                          style={{ fontSize: '0.95rem' }}
                        />
                        <div className="d-flex gap-2 justify-content-end">
                          <button type="submit" className="btn btn-sm btn-primary px-3 fw-semibold">Save & Submit</button>
                          <button type="button" className="btn btn-sm btn-outline-secondary px-3 fw-semibold" onClick={() => setEditingIdx(null)}>Cancel</button>
                        </div>
                      </form>
                    ) : (
                      // Normal message rendering
                      <div className="message-content">
                        {isUser ? (
                          <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                        ) : (
                          <div dangerouslySetInnerHTML={renderHTML(msg.content)} />
                        )}
                        
                        {/* Source tags */}
                        {config.show_sources && msg.sources && msg.sources.length > 0 && (
                          <div className="mt-3 pt-2 border-top" style={{ borderColor: 'var(--border-color)' }}>
                            <div className="small fw-bold text-muted mb-1" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.02rem' }}>Sources:</div>
                            <div className="d-flex flex-wrap">
                              {msg.sources.map((src, sIdx) => (
                                <span className="source-chip-tag" key={sIdx}>
                                  <i className="bi bi-file-earmark-text me-1"></i>
                                  {src}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Metadata & Actions row */}
                    {!isEditing && (
                      <div className="message-meta">
                        <span></span>
                        <div className="message-actions">
                          {isUser ? (
                            <button 
                              className="btn-action-icon" 
                              title="Edit Prompt"
                              onClick={() => startEdit(idx, msg.content)}
                            >
                              <i className="bi bi-pencil"></i> Edit
                            </button>
                          ) : (
                            <>
                              <button 
                                className="btn-action-icon" 
                                title="Copy response"
                                onClick={() => handleCopyMessage(msg.content, idx)}
                              >
                                <i className={`bi ${copiedIdx === idx ? 'bi-check-lg text-success' : 'bi-clipboard'}`}></i> {copiedIdx === idx ? 'Copied' : 'Copy'}
                              </button>
                              <button 
                                className="btn-action-icon" 
                                title="Regenerate answer"
                                onClick={() => onRegenerateResponse(idx)}
                              >
                                <i className="bi bi-arrow-clockwise"></i> Regenerate
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="text-center py-5">
              <h2 className="fw-bold mt-4 mb-2" style={{ background: 'var(--gradient-accent)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', letterSpacing: '-0.02rem' }}>How can I help you today?</h2>
              <p className="text-muted small">Upload your knowledge base files above to query and analyze them in real-time.</p>
            </div>
          )}

          {/* Typing indicator spinner */}
          {isGenerating && (
            <div className="d-flex align-items-center text-muted small ms-5 mb-4">
              <div className="typing-dots me-2">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <span>AI is writing...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input box Footer */}
      <div className="chat-input-footer">
        <div className="chat-container-width px-3 position-relative">
          
          {/* Stop generating floating button */}
          {isGenerating && (
            <div className="d-flex justify-content-center mb-3">
              <button 
                className="btn btn-sm btn-outline-danger fw-bold px-3 py-1.5 d-flex align-items-center gap-2 shadow-sm"
                onClick={onStopGeneration}
                style={{ borderRadius: '9999px', fontSize: '0.8rem', backgroundColor: 'var(--bg-secondary)' }}
              >
                <i className="bi bi-stop-circle-fill"></i> Stop Generating
              </button>
            </div>
          )}

          <div className="position-relative">
            <textarea 
              ref={textareaRef}
              rows="1"
              className="form-control chat-input-textarea shadow-sm"
              placeholder="Ask a question about your documents..."
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyPress}
              disabled={isGenerating}
            />
            <button 
              className="btn btn-link position-absolute end-0 top-50 translate-middle-y me-3 p-0 fs-5 d-flex align-items-center"
              onClick={submitMessage}
              disabled={!inputValue.trim() || isGenerating}
              style={{ color: 'var(--primary-color)', opacity: inputValue.trim() ? 1 : 0.4 }}
            >
              <i className="bi bi-arrow-up-circle-fill fs-4"></i>
            </button>
          </div>
          <div className="input-disclaimer">
            RAG Chatbot can make mistakes. Verify important details.
          </div>
        </div>
      </div>
    </div>
  );
}
