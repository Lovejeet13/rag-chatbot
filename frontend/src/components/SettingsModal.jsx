import React from 'react';

export default function SettingsModal({ show, onClose, config, onSaveConfig }) {
  if (!show) return null;

  const handleToggle = (key) => {
    onSaveConfig({ ...config, [key]: !config[key] });
  };

  const handleSliderChange = (key, value) => {
    onSaveConfig({ ...config, [key]: Number(value) });
  };

  return (
    <div className="modal show d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.65)', zIndex: 1050 }}>
      <div className="modal-dialog modal-dialog-centered">
        <div className="modal-content">
          <div className="modal-header border-0 pb-0">
            <h6 className="modal-title fw-bold d-flex align-items-center gap-2">
              <i className="bi bi-sliders text-primary"></i> Chatbot Configuration
            </h6>
            <button type="button" className="btn-close" onClick={onClose} aria-label="Close"></button>
          </div>
          <div className="modal-body py-3">
            
            {/* Toggles */}
            <div className="form-check form-switch mb-3">
              <input 
                className="form-check-input" 
                type="checkbox" 
                role="switch"
                id="toggleStreaming" 
                checked={config.streaming}
                onChange={() => handleToggle('streaming')}
              />
              <label className="form-check-label fw-medium small" htmlFor="toggleStreaming">Enable Response Streaming</label>
            </div>

            <div className="form-check form-switch mb-3">
              <input 
                className="form-check-input" 
                type="checkbox" 
                role="switch"
                id="toggleOCR" 
                checked={config.enable_ocr}
                onChange={() => handleToggle('enable_ocr')}
              />
              <label className="form-check-label fw-medium small" htmlFor="toggleOCR">Enable OCR (Scanned PDFs & Images)</label>
            </div>

            <div className="form-check form-switch mb-4">
              <input 
                className="form-check-input" 
                type="checkbox" 
                role="switch"
                id="toggleSources" 
                checked={config.show_sources}
                onChange={() => handleToggle('show_sources')}
              />
              <label className="form-check-label fw-medium small" htmlFor="toggleSources">Show Source Citations</label>
            </div>

            <hr className="my-3" style={{ borderColor: 'var(--border-color)' }} />

            {/* Sliders */}
            <div className="mb-3">
              <div className="d-flex justify-content-between mb-1">
                <label className="fw-medium small" style={{ color: 'var(--text-secondary)' }}>Chunk Size (characters)</label>
                <span className="text-primary small fw-bold">{config.chunk_size}</span>
              </div>
              <input 
                type="range" 
                className="form-range" 
                min="200" 
                max="2000" 
                step="50"
                value={config.chunk_size}
                onChange={(e) => handleSliderChange('chunk_size', e.target.value)}
              />
              <div className="d-flex justify-content-between text-muted" style={{ fontSize: '0.7rem' }}>
                <span>200</span>
                <span>2000</span>
              </div>
            </div>

            <div className="mb-3">
              <div className="d-flex justify-content-between mb-1">
                <label className="fw-medium small" style={{ color: 'var(--text-secondary)' }}>Chunk Overlap</label>
                <span className="text-primary small fw-bold">{config.chunk_overlap}</span>
              </div>
              <input 
                type="range" 
                className="form-range" 
                min="20" 
                max="500" 
                step="10"
                value={config.chunk_overlap}
                onChange={(e) => handleSliderChange('chunk_overlap', e.target.value)}
              />
              <div className="d-flex justify-content-between text-muted" style={{ fontSize: '0.7rem' }}>
                <span>20</span>
                <span>500</span>
              </div>
            </div>

            <div className="mb-3">
              <div className="d-flex justify-content-between mb-1">
                <label className="fw-medium small" style={{ color: 'var(--text-secondary)' }}>Top-k Retrieval</label>
                <span className="text-primary small fw-bold">{config.retrieval_k}</span>
              </div>
              <input 
                type="range" 
                className="form-range" 
                min="2" 
                max="15" 
                step="1"
                value={config.retrieval_k}
                onChange={(e) => handleSliderChange('retrieval_k', e.target.value)}
              />
              <div className="d-flex justify-content-between text-muted" style={{ fontSize: '0.7rem' }}>
                <span>2</span>
                <span>15</span>
              </div>
            </div>

            <div className="mb-2">
              <div className="d-flex justify-content-between mb-1">
                <label className="fw-medium small" style={{ color: 'var(--text-secondary)' }}>Confidence Threshold (L2 distance)</label>
                <span className="text-primary small fw-bold">{config.confidence_threshold}</span>
              </div>
              <input 
                type="range" 
                className="form-range" 
                min="0.5" 
                max="2.0" 
                step="0.05"
                value={config.confidence_threshold}
                onChange={(e) => handleSliderChange('confidence_threshold', e.target.value)}
              />
              <div className="d-flex justify-content-between text-muted" style={{ fontSize: '0.7rem' }}>
                <span>0.5 (Strict)</span>
                <span>2.0 (Loose)</span>
              </div>
            </div>

          </div>
          <div className="modal-footer border-0 pt-0">
            <button type="button" className="btn btn-primary w-100 fw-semibold py-2" onClick={onClose}>Done</button>
          </div>
        </div>
      </div>
    </div>
  );
}
