import React, { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import SettingsModal from './components/SettingsModal';

const API_BASE = '/api';

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [config, setConfig] = useState({
    chunk_size: 700,
    chunk_overlap: 120,
    retrieval_k: 5,
    summary_k: 8,
    confidence_threshold: 1.45,
    enable_ocr: false,
    streaming: true,
    show_sources: false
  });
  
  const [theme, setTheme] = useState('dark');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  
  const abortControllerRef = useRef(null);

  // Initialize theme, configuration parameters, and conversations
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    setTheme(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
    document.documentElement.setAttribute('data-bs-theme', savedTheme);

    fetchConfig();
    fetchSessions();
  }, []);

  // Sync active session if none is selected
  useEffect(() => {
    if (sessions.length > 0 && !activeSessionId) {
      setActiveSessionId(sessions[0].id);
    }
  }, [sessions, activeSessionId]);

  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/config`);
      const data = await res.json();
      setConfig(data);
    } catch (e) {
      console.error("Error loading config:", e);
    }
  };

  const fetchSessions = async (selectedId = null) => {
    try {
      const res = await fetch(`${API_BASE}/sessions`);
      const data = await res.json();
      setSessions(data);
      if (selectedId) {
        setActiveSessionId(selectedId);
      }
    } catch (e) {
      console.error("Error loading sessions:", e);
    }
  };

  const handleToggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    localStorage.setItem('theme', nextTheme);
    document.documentElement.setAttribute('data-theme', nextTheme);
    document.documentElement.setAttribute('data-bs-theme', nextTheme);
  };

  const handleSaveConfig = async (newConfig) => {
    setConfig(newConfig);
    try {
      await fetch(`${API_BASE}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      });
    } catch (e) {
      console.error("Error saving config:", e);
    }
  };

  const handleCreateSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`, { method: 'POST' });
      const newSession = await res.json();
      await fetchSessions(newSession.id);
    } catch (e) {
      console.error("Error creating session:", e);
    }
  };

  const handleUpdateSession = async (sid, updates) => {
    try {
      await fetch(`${API_BASE}/sessions/${sid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      await fetchSessions(activeSessionId);
    } catch (e) {
      console.error("Error updating session:", e);
    }
  };

  const handleDeleteSession = async (sid) => {
    try {
      await fetch(`${API_BASE}/sessions/${sid}`, { method: 'DELETE' });
      if (activeSessionId === sid) {
        setActiveSessionId(null);
      }
      await fetchSessions();
    } catch (e) {
      console.error("Error deleting session:", e);
    }
  };

  const handleDuplicateSession = async (sid) => {
    try {
      const res = await fetch(`${API_BASE}/sessions/${sid}/duplicate`, { method: 'POST' });
      const newSession = await res.json();
      await fetchSessions(newSession.id);
    } catch (e) {
      console.error("Error duplicating session:", e);
    }
  };

  const handleUploadFile = async (file) => {
    if (!activeSessionId) return;
    const formData = new FormData();
    formData.append('file', file);

    try {
      await fetch(`${API_BASE}/sessions/${activeSessionId}/upload`, {
        method: 'POST',
        body: formData
      });
      await fetchSessions(activeSessionId);
    } catch (e) {
      console.error("Error uploading file:", e);
    }
  };

  const handleDeleteDocument = async (filename) => {
    if (!activeSessionId) return;
    try {
      await fetch(`${API_BASE}/sessions/${activeSessionId}/documents/${filename}`, {
        method: 'DELETE'
      });
      await fetchSessions(activeSessionId);
    } catch (e) {
      console.error("Error deleting document:", e);
    }
  };

  // --- SEND MESSAGE FLOW ---

  const handleSendMessage = async (text) => {
    if (!activeSessionId || isGenerating) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    // Instantly append empty assistant card for responsiveness
    const updatedSessions = sessions.map(s => {
      if (s.id === activeSessionId) {
        return {
          ...s,
          messages: [
            ...(s.messages || []),
            { role: 'user', content: text, timestamp: timeStr, sources: [] },
            { role: 'assistant', content: '', timestamp: timeStr, sources: [] }
          ]
        };
      }
      return s;
    });
    setSessions(updatedSessions);
    setIsGenerating(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const response = await fetch(`${API_BASE}/sessions/${activeSessionId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
        signal: abortController.signal
      });

      if (!response.body) {
        throw new Error("No response body stream");
      }

      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        updateAssistantLastMessage(data.content, data.sources);
        setIsGenerating(false);
        fetchSessions(activeSessionId);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let streamedResponse = "";
      let finalSources = [];

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        
        if (value) {
          const chunk = decoder.decode(value, { stream: !done });
          const lines = chunk.split('\n\n');
          for (const line of lines) {
            if (line.trim().startsWith('data: ')) {
              try {
                const data = JSON.parse(line.trim().slice(6));
                
                if (data.type === 'token') {
                  streamedResponse += data.content;
                  updateAssistantLastMessage(streamedResponse, []);
                } else if (data.type === 'corrected') {
                  streamedResponse = data.content;
                  updateAssistantLastMessage(streamedResponse, []);
                } else if (data.type === 'done') {
                  finalSources = data.sources || [];
                  updateAssistantLastMessage(streamedResponse, finalSources);
                } else if (data.type === 'error') {
                  streamedResponse = `Error: ${data.content}`;
                  updateAssistantLastMessage(streamedResponse, []);
                }
              } catch (e) {
                // Ignore parse errors from mid-chunk breaks
              }
            }
          }
        }
      }
      
      setIsGenerating(false);
      fetchSessions(activeSessionId);

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log("Generation stopped by user.");
      } else {
        console.error("Send message error:", error);
        updateAssistantLastMessage(`An error occurred: ${error.message}`, []);
      }
      setIsGenerating(false);
      fetchSessions(activeSessionId);
    }
  };

  const updateAssistantLastMessage = (content, sources) => {
    setSessions(prev => prev.map(s => {
      if (s.id === activeSessionId) {
        const msgs = [...(s.messages || [])];
        if (msgs.length > 0) {
          msgs[msgs.length - 1] = {
            ...msgs[msgs.length - 1],
            content: content,
            sources: sources
          };
        }
        return { ...s, messages: msgs };
      }
      return s;
    }));
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsGenerating(false);
    }
  };

  const handleRegenerateResponse = async (msgIdx) => {
    const active = sessions.find(s => s.id === activeSessionId);
    if (!active) return;
    
    let queryText = '';
    let targetMsgIdx = msgIdx - 1;
    while (targetMsgIdx >= 0) {
      if (active.messages[targetMsgIdx].role === 'user') {
        queryText = active.messages[targetMsgIdx].content;
        break;
      }
      targetMsgIdx--;
    }

    if (queryText) {
      const updatedMessages = active.messages.slice(0, targetMsgIdx);
      const nextSessions = sessions.map(s => {
        if (s.id === activeSessionId) {
          return { ...s, messages: updatedMessages };
        }
        return s;
      });
      setSessions(nextSessions);
      
      setTimeout(() => handleSendMessage(queryText), 100);
    }
  };

  const handleEditMessage = (msgIdx, newText) => {
    const active = sessions.find(s => s.id === activeSessionId);
    if (!active) return;

    const updatedMessages = active.messages.slice(0, msgIdx);
    const nextSessions = sessions.map(s => {
      if (s.id === activeSessionId) {
        return { ...s, messages: updatedMessages };
      }
      return s;
    });
    setSessions(nextSessions);

    setTimeout(() => handleSendMessage(newText), 100);
  };

  const activeSession = sessions.find(s => s.id === activeSessionId) || { messages: [], uploaded_files: [] };

  return (
    <div className="app-container">
      {/* Collapsible Sidebar */}
      <Sidebar 
        sessions={sessions}
        activeSessionId={activeSessionId}
        collapsed={sidebarCollapsed}
        onSelectSession={setActiveSessionId}
        onCreateSession={handleCreateSession}
        onUpdateSession={handleUpdateSession}
        onDeleteSession={handleDeleteSession}
        onDuplicateSession={handleDuplicateSession}
        onOpenSettings={() => setShowSettings(true)}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />

      {/* Main Chat Area */}
      <div className="chat-main">
        {/* Top Control Bar */}
        <div 
          className="d-flex align-items-center px-3 border-bottom" 
          style={{ height: '56px', backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}
        >
          <button 
            className="btn btn-sm text-secondary p-1 me-3 border-0 bg-transparent" 
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          >
            <i className={`bi ${sidebarCollapsed ? 'bi-layout-sidebar-inset' : 'bi-layout-sidebar'}`} style={{ fontSize: '1.2rem' }}></i>
          </button>
          <span className="small fw-semibold text-secondary text-truncate">{activeSession.title || 'No active chat'}</span>
        </div>

        <ChatWindow 
          session={activeSession}
          config={config}
          onSendMessage={handleSendMessage}
          onRegenerateResponse={handleRegenerateResponse}
          onEditMessage={handleEditMessage}
          onUploadFile={handleUploadFile}
          onDeleteDocument={handleDeleteDocument}
          isGenerating={isGenerating}
          onStopGeneration={handleStopGeneration}
        />
      </div>

      {/* Settings Modal */}
      <SettingsModal 
        show={showSettings}
        onClose={() => setShowSettings(false)}
        config={config}
        onSaveConfig={handleSaveConfig}
      />
    </div>
  );
}
