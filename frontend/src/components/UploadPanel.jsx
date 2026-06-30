import React, { useRef, useState } from 'react';

export default function UploadPanel({ session, onUploadFile, onDeleteDocument }) {
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await uploadFiles(e.dataTransfer.files);
    }
  };

  const handleFileChange = async (e) => {
    if (e.target.files && e.target.files[0]) {
      await uploadFiles(e.target.files);
    }
  };

  const uploadFiles = async (files) => {
    setIsUploading(true);
    for (let i = 0; i < files.length; i++) {
      await onUploadFile(files[i]);
    }
    setIsUploading(false);
  };

  const getFileIcon = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    switch (ext) {
      case 'pdf': return 'bi-file-pdf-fill text-danger';
      case 'docx': return 'bi-file-word-fill text-primary';
      case 'txt': return 'bi-file-text-fill text-secondary';
      case 'png':
      case 'jpg':
      case 'jpeg': return 'bi-file-image-fill text-success';
      default: return 'bi-file-earmark-fill text-muted';
    }
  };

  return (
    <div className="mb-4">
      {/* Dashed Drag/Drop Box */}
      <div 
        className={`upload-card-dashed p-4 ${dragActive ? 'border-primary' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{ borderStyle: 'dashed' }}
      >
        <input 
          type="file" 
          ref={fileInputRef}
          style={{ display: 'none' }}
          multiple
          onChange={handleFileChange}
          accept=".pdf,.txt,.docx,.png,.jpg,.jpeg"
        />
        <i className="bi bi-cloud-upload fs-2 text-muted mb-2 d-block"></i>
        <span className="fw-semibold d-block text-primary small">Upload Knowledge Base Documents</span>
        <span className="text-muted small" style={{ fontSize: '0.8rem' }}>PDF, DOCX, TXT, PNG, JPG, or JPEG</span>
      </div>

      {/* Uploading progress spinner */}
      {isUploading && (
        <div className="d-flex align-items-center justify-content-center my-3 text-primary">
          <div className="spinner-border spinner-border-sm me-2" role="status"></div>
          <span className="small fw-semibold">Ingesting files and indexing...</span>
        </div>
      )}

      {/* Active Document Cards Grid */}
      {session.uploaded_files && session.uploaded_files.length > 0 && (
        <div className="mt-3">
          <p className="small fw-bold text-muted mb-2 text-uppercase" style={{ fontSize: '0.725rem', letterSpacing: '0.04rem' }}>Knowledge Base</p>
          <div className="row g-2">
            {session.uploaded_files.map((doc, idx) => (
              <div className="col-12 col-md-6" key={idx}>
                <div className="doc-card-badge d-flex justify-content-between align-items-center">
                  <div className="d-flex align-items-center overflow-hidden">
                    <i className={`bi ${getFileIcon(doc.name)} doc-badge-icon fs-5 me-2`}></i>
                    <div className="overflow-hidden">
                      <div className="fw-semibold text-truncate small" title={doc.name} style={{ color: 'var(--text-primary)' }}>{doc.name}</div>
                      <div className="text-muted small" style={{ fontSize: '0.75rem' }}>
                        {doc.size} {doc.pages ? `• ${doc.pages} pgs` : ''}
                      </div>
                    </div>
                  </div>
                  <button 
                    className="btn btn-sm btn-link text-danger p-1 border-0 bg-transparent"
                    title="Remove Document"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteDocument(doc.name);
                    }}
                  >
                    <i className="bi bi-trash"></i>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
