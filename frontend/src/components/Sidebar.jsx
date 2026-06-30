import React, { useState } from 'react';

export default function Sidebar({
  sessions,
  activeSessionId,
  collapsed,
  onSelectSession,
  onCreateSession,
  onUpdateSession,
  onDeleteSession,
  onDuplicateSession,
  onOpenSettings,
  theme,
  onToggleTheme
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [renameId, setRenameId] = useState(null);
  const [renameTitle, setRenameTitle] = useState('');

  // Grouping helper
  const groupSessionsByDate = (sessionsList) => {
    const groups = {
      pinned: [],
      today: [],
      yesterday: [],
      last7Days: [],
      older: []
    };

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    const yesterdayStart = new Date(todayStart);
    yesterdayStart.setDate(yesterdayStart.getDate() - 1);
    
    const sevenDaysAgo = new Date(todayStart);
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    // Apply search filter (Search in title, uploaded file names, or message content)
    const query = searchQuery.trim().toLowerCase();
    const filtered = sessionsList.filter(s => {
      if (!query) return true;
      if (s.title.toLowerCase().includes(query)) return true;
      if (s.uploaded_files && s.uploaded_files.some(f => f.name.toLowerCase().includes(query))) return true;
      if (s.messages && s.messages.some(m => m.content.toLowerCase().includes(query))) return true;
      return false;
    });

    filtered.forEach(session => {
      if (session.pinned) {
        groups.pinned.push(session);
        return;
      }
      
      try {
        const parts = session.timestamp.split(' ');
        const dateParts = parts[0].split('-');
        const sessionDate = new Date(dateParts[0], dateParts[1] - 1, dateParts[2]);

        if (sessionDate >= todayStart) {
          groups.today.push(session);
        } else if (sessionDate >= yesterdayStart) {
          groups.yesterday.push(session);
        } else if (sessionDate >= sevenDaysAgo) {
          groups.last7Days.push(session);
        } else {
          groups.older.push(session);
        }
      } catch (e) {
        groups.older.push(session);
      }
    });

    return groups;
  };

  const groups = groupSessionsByDate(sessions);

  const startRename = (session) => {
    setRenameId(session.id);
    setRenameTitle(session.title);
  };

  const saveRename = (e) => {
    e.preventDefault();
    if (renameTitle.trim()) {
      onUpdateSession(renameId, { title: renameTitle.trim() });
    }
    setRenameId(null);
  };

  const handleExport = (session) => {
    const exportData = {
      title: session.title,
      timestamp: session.timestamp,
      files: session.uploaded_files ? session.uploaded_files.map(f => f.name) : [],
      messages: session.messages || []
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat_export_${session.title.replace(/\s+/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const renderSessionItem = (session) => {
    const isActive = session.id === activeSessionId;
    const isRenaming = session.id === renameId;

    if (isRenaming) {
      return (
        <form onSubmit={saveRename} className="p-1 d-flex gap-1 align-items-center" key={session.id}>
          <input 
            type="text" 
            className="form-control form-control-sm py-1 px-2"
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            autoFocus
            style={{ fontSize: '0.85rem' }}
          />
          <button type="submit" className="btn btn-sm btn-primary p-1" style={{ width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <i className="bi bi-check-lg"></i>
          </button>
          <button type="button" className="btn btn-sm btn-outline-secondary p-1" onClick={() => setRenameId(null)} style={{ width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <i className="bi bi-x-lg"></i>
          </button>
        </form>
      );
    }

    return (
      <div 
        key={session.id}
        className={`sidebar-history-item ${isActive ? 'active' : ''}`}
        onClick={() => onSelectSession(session.id)}
      >
        <div className="d-flex align-items-center overflow-hidden flex-grow-1">
          <i className={`bi ${session.uploaded_files?.length > 0 ? 'bi-file-earmark-text' : 'bi-chat-left'} me-2 flex-shrink-0`} style={{ fontSize: '0.95rem' }}></i>
          <span className="text-truncate">{session.title}</span>
        </div>
        
        {/* Bootstrap Dropdown context menu */}
        <div className="dropdown" onClick={(e) => e.stopPropagation()}>
          <button 
            className="btn btn-link btn-sm text-secondary p-0 dots-dropdown-toggle" 
            type="button" 
            data-bs-toggle="dropdown" 
            aria-expanded="false"
          >
            <i className="bi bi-three-dots"></i>
          </button>
          <ul className="dropdown-menu dropdown-menu-end shadow-sm">
            <li>
              <button className="dropdown-item d-flex align-items-center gap-2" onClick={() => onUpdateSession(session.id, { pinned: !session.pinned })}>
                <i className={`bi ${session.pinned ? 'bi-pin-fill' : 'bi-pin'}`}></i>
                {session.pinned ? 'Unpin Chat' : 'Pin Chat'}
              </button>
            </li>
            <li>
              <button className="dropdown-item d-flex align-items-center gap-2" onClick={() => startRename(session)}>
                <i className="bi bi-pencil"></i>
                Rename
              </button>
            </li>
            <li>
              <button className="dropdown-item d-flex align-items-center gap-2" onClick={() => onDuplicateSession(session.id)}>
                <i className="bi bi-files"></i>
                Duplicate
              </button>
            </li>
            <li>
              <button className="dropdown-item d-flex align-items-center gap-2" onClick={() => handleExport(session)}>
                <i className="bi bi-download"></i>
                Export Chat
              </button>
            </li>
            <li><hr className="dropdown-divider" /></li>
            <li>
              <button className="dropdown-item text-danger d-flex align-items-center gap-2" onClick={() => onDeleteSession(session.id)}>
                <i className="bi bi-trash"></i>
                Delete Chat
              </button>
            </li>
          </ul>
        </div>
      </div>
    );
  };

  return (
    <div className={`sidebar-container ${collapsed ? 'collapsed' : ''}`}>
      {/* Brand Header */}
      <div className="p-3 d-flex align-items-center justify-content-between border-bottom" style={{ borderColor: 'var(--border-color)', height: '56px' }}>
        <div className="d-flex align-items-center gap-2">
          <i className="bi bi-chat-square-text-fill fs-5" style={{ background: 'var(--gradient-accent)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}></i>
          <span className="fw-bold fs-6" style={{ background: 'var(--gradient-accent)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>RAG Chatbot</span>
        </div>
      </div>

      {/* Control Buttons */}
      <div className="p-3 pb-2 d-flex flex-column gap-2">
        <button 
          className="btn btn-primary fw-bold w-100 py-2 d-flex align-items-center justify-content-center gap-2"
          onClick={onCreateSession}
        >
          <i className="bi bi-plus-lg"></i> New Chat
        </button>

        {/* Search Input Box */}
        <div className="position-relative mt-1">
          <span className="position-absolute top-50 start-0 translate-middle-y ps-3 text-muted small" style={{ zIndex: 10 }}>
            <i className="bi bi-search"></i>
          </span>
          <input 
            type="text" 
            className="form-control form-control-sm ps-5 py-2" 
            placeholder="Search chats..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ fontSize: '0.85rem' }}
          />
          {searchQuery && (
            <button 
              className="btn btn-link btn-sm text-secondary position-absolute end-0 top-50 translate-middle-y pe-2 p-0"
              onClick={() => setSearchQuery('')}
              style={{ zIndex: 10 }}
            >
              <i className="bi bi-x-circle-fill"></i>
            </button>
          )}
        </div>
      </div>

      {/* Chat History List */}
      <div className="flex-grow-1 overflow-y-auto px-3 py-2">
        {/* Pinned Chats */}
        {groups.pinned.length > 0 && (
          <div className="mb-3">
            <div className="sidebar-date-header">📌 Pinned</div>
            {groups.pinned.map(renderSessionItem)}
          </div>
        )}

        {/* Today */}
        {groups.today.length > 0 && (
          <div className="mb-3">
            <div className="sidebar-date-header">Today</div>
            {groups.today.map(renderSessionItem)}
          </div>
        )}

        {/* Yesterday */}
        {groups.yesterday.length > 0 && (
          <div className="mb-3">
            <div className="sidebar-date-header">Yesterday</div>
            {groups.yesterday.map(renderSessionItem)}
          </div>
        )}

        {/* Last 7 Days */}
        {groups.last7Days.length > 0 && (
          <div className="mb-3">
            <div className="sidebar-date-header">Previous 7 Days</div>
            {groups.last7Days.map(renderSessionItem)}
          </div>
        )}

        {/* Older */}
        {groups.older.length > 0 && (
          <div className="mb-3">
            <div className="sidebar-date-header">Older</div>
            {groups.older.map(renderSessionItem)}
          </div>
        )}

        {/* Empty Placeholder */}
        {sessions.length === 0 && (
          <div className="text-center text-muted small py-4">No active conversations.</div>
        )}
      </div>

      {/* Footer controls */}
      <div className="p-3 border-top d-flex flex-column gap-2" style={{ borderColor: 'var(--border-color)' }}>
        <button 
          className="sidebar-btn-action" 
          onClick={onToggleTheme}
        >
          <i className={`bi ${theme === 'dark' ? 'bi-sun-fill text-warning' : 'bi-moon-stars-fill text-primary'}`}></i>
          {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
        </button>
        <button 
          className="sidebar-btn-action" 
          onClick={onOpenSettings}
        >
          <i className="bi bi-gear-fill"></i> Settings
        </button>
      </div>
    </div>
  );
}
