/**
 * VeriCite AI - Frontend Reactive Application Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // Navigation & Tab state
  const tabs = document.querySelectorAll('.nav-tab');
  const panes = document.querySelectorAll('.tab-pane');
  
  // Research Form elements
  const researchForm = document.getElementById('research-form');
  const queryInput = document.getElementById('query-input');
  const topKSelect = document.getElementById('top-k-select');
  const topKVal = document.getElementById('top-k-val');
  const strictToggle = document.getElementById('strict-citations-toggle');
  const btnSubmit = document.getElementById('btn-submit-query');
  
  // Stepper & Result elements
  const stepperCard = document.getElementById('stepper-card');
  const stepperTimeline = document.getElementById('stepper-timeline');
  const execTimer = document.getElementById('exec-total-timer');
  const resultPlaceholder = document.getElementById('result-placeholder');
  const resultContent = document.getElementById('result-content-container');
  const resultStatusTag = document.getElementById('result-status-tag');
  const meterFill = document.getElementById('meter-fill');
  const meterVal = document.getElementById('meter-val');
  const citationsCountTag = document.getElementById('citations-count-tag');
  const answerBody = document.getElementById('answer-body');
  const citationsList = document.getElementById('citations-list');
  const claimsSummaryBadge = document.getElementById('claims-summary-badge');
  const claimsTableBody = document.getElementById('claims-table-body');
  
  // Modals
  const chunkModal = document.getElementById('chunk-modal');
  const modalCloseBtn = document.getElementById('modal-close-btn');
  const modalChunkId = document.getElementById('modal-chunk-id');
  const modalDocTitle = document.getElementById('modal-doc-title');
  const modalSectionName = document.getElementById('modal-section-name');
  const modalQuoteText = document.getElementById('modal-quote-text');
  const modalFullText = document.getElementById('modal-full-text');
  
  const uploadModal = document.getElementById('upload-modal');
  const btnOpenUpload = document.getElementById('btn-open-upload-modal');
  const uploadModalClose = document.getElementById('upload-modal-close-btn');
  const uploadForm = document.getElementById('upload-form');

  // Corpus & Benchmark Containers
  const documentsGrid = document.getElementById('documents-grid');
  const benchmarkTableBody = document.getElementById('benchmark-table-body');
  const btnRunBenchmark = document.getElementById('btn-run-all-benchmark');
  const benchmarkMetricsRow = document.getElementById('benchmark-metrics-row');

  // Active result cache
  let currentResult = null;

  // -------------------------------------------------------------
  // Initialization & System Health
  // -------------------------------------------------------------
  fetchHealth();
  fetchDocuments();
  fetchBenchmarkQuestions();

  // Update Top-K Range Display
  topKSelect.addEventListener('input', (e) => {
    topKVal.textContent = e.target.value;
  });

  // Tab Navigation Handling
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      panes.forEach(p => {
        p.classList.remove('active');
        p.style.display = 'none';
      });

      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      const targetPane = document.getElementById(tab.dataset.tab);
      if (targetPane) {
        targetPane.classList.add('active');
        targetPane.style.display = 'block';
      }

      if (tab.dataset.tab === 'tab-corpus') {
        fetchDocuments();
      }
    });
  });

  // Preset Query Pills
  document.querySelectorAll('.preset-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      queryInput.value = pill.dataset.query;
      queryInput.focus();
    });
  });

  // -------------------------------------------------------------
  // Research Query Submission
  // -------------------------------------------------------------
  researchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    // UI Loading State
    btnSubmit.disabled = true;
    btnSubmit.innerHTML = `<span>Synthesizing & Verifying...</span>`;
    stepperCard.style.display = 'block';
    renderInitialStepper();

    resultPlaceholder.style.display = 'none';
    resultContent.style.display = 'none';

    try {
      const payload = {
        query: query,
        top_k: parseInt(topKSelect.value, 10),
        strict_citations: strictToggle.checked
      };

      const resp = await fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!resp.ok) {
        throw new Error(`Server returned ${resp.status}: ${resp.statusText}`);
      }

      const data = await resp.json();
      currentResult = data;
      renderResearchResult(data);

    } catch (err) {
      console.error(err);
      alert(`Research Agent Error: ${err.message}`);
    } finally {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <span>Execute Agentic Research</span>
      `;
    }
  });

  // -------------------------------------------------------------
  // Render Research Result & Citations
  // -------------------------------------------------------------
  function renderResearchResult(data) {
    execTimer.textContent = `${data.total_time_ms.toFixed(1)}ms`;
    
    // Render Execution Steps
    stepperTimeline.innerHTML = '';
    data.execution_steps.forEach(step => {
      const stepEl = document.createElement('div');
      stepEl.className = 'step-item';
      const iconChar = step.status === 'completed' ? '✓' : (step.status === 'fallback' ? '!' : 'ℹ');
      stepEl.innerHTML = `
        <div class="step-icon ${step.status}">${iconChar}</div>
        <div class="step-content">
          <div class="step-title-line">
            <span>${step.step_name}</span>
            <span class="step-duration">${step.duration_ms}ms</span>
          </div>
          <div class="step-detail">${step.detail}</div>
        </div>
      `;
      stepperTimeline.appendChild(stepEl);
    });

    // Result Banner Status & Confidence
    if (data.is_fallback) {
      resultStatusTag.textContent = 'Insufficient Evidence';
      resultStatusTag.className = 'status-tag fallback';
      meterFill.style.width = '0%';
      meterFill.style.backgroundColor = 'var(--accent-warn)';
      meterVal.textContent = '0%';
      citationsCountTag.textContent = '0 Sources';
    } else {
      const isFull = data.verification_report && data.verification_report.is_fully_grounded;
      resultStatusTag.textContent = isFull ? 'Verified Grounded' : 'Partially Grounded';
      resultStatusTag.className = isFull ? 'status-tag' : 'status-tag fallback';
      
      const confPct = Math.round(data.confidence * 100);
      meterFill.style.width = `${confPct}%`;
      meterFill.style.backgroundColor = isFull ? 'var(--accent-primary)' : 'var(--accent-warn)';
      meterVal.textContent = `${confPct}%`;
      citationsCountTag.textContent = `${data.citations.length} Source(s) Cited`;
    }

    // Render Formatted Answer with Interactive Citation Anchors
    answerBody.innerHTML = formatMarkdownWithCitations(data.answer, data.citations);

    // Attach click listeners to citation links
    answerBody.querySelectorAll('.citation-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const cid = link.dataset.cid;
        openChunkModal(cid, data);
      });
    });

    // Render Citations Tray
    citationsList.innerHTML = '';
    if (data.citations && data.citations.length > 0) {
      data.citations.forEach(cit => {
        const item = document.createElement('div');
        item.className = 'citation-card-item';
        item.innerHTML = `
          <div class="citation-card-header">
            <span class="citation-marker-tag">${cit.citation_id}</span>
            <span class="citation-score-badge">Match: ${(cit.relevance_score * 100).toFixed(1)}%</span>
          </div>
          <div class="citation-card-title">${cit.document_title} — ${cit.section}</div>
          <div class="citation-card-quote">"${cit.quote}"</div>
        `;
        item.addEventListener('click', () => openChunkModal(cit.chunk_id, data));
        citationsList.appendChild(item);
      });
      document.getElementById('citations-tray').style.display = 'block';
    } else {
      document.getElementById('citations-tray').style.display = 'none';
    }

    // Render Anti-Hallucination Claim Breakdown
    const vReport = data.verification_report;
    if (vReport && vReport.total_claims > 0) {
      claimsSummaryBadge.textContent = `${vReport.verified_claims}/${vReport.total_claims} Claims Grounded (${(vReport.grounding_score * 100).toFixed(0)}%)`;
      claimsTableBody.innerHTML = '';
      vReport.claim_details.forEach(claim => {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td><strong>#${claim.claim_id}</strong></td>
          <td>${claim.claim_text}</td>
          <td><code>${claim.cited_marker || 'None'}</code></td>
          <td>
            <span class="claim-status-pill ${claim.is_grounded ? 'verified' : 'unverified'}">
              ${claim.is_grounded ? 'Verified' : 'Unverified'}
            </span>
          </td>
          <td>${claim.rationale}</td>
        `;
        claimsTableBody.appendChild(row);
      });
      document.getElementById('verification-drawer').style.display = 'block';
    } else {
      document.getElementById('verification-drawer').style.display = 'none';
    }

    resultContent.style.display = 'block';
  }

  function renderInitialStepper() {
    stepperTimeline.innerHTML = `
      <div class="step-item">
        <div class="step-icon completed">⏳</div>
        <div class="step-content">
          <div class="step-title-line"><span>Agent Pipeline Initializing</span></div>
          <div class="step-detail">Analyzing inquiry and decomposing search queries...</div>
        </div>
      </div>
    `;
  }

  // -------------------------------------------------------------
  // Markdown & Citation Anchor Formatter
  // -------------------------------------------------------------
  function formatMarkdownWithCitations(text, citations) {
    if (!text) return '';
    let html = text
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^- (.*$)/gim, '<li>$1</li>')
      .replace(/\n\n/g, '<p></p>');

    // Wrap li elements
    html = html.replace(/(<li>.*?<\/li>)/g, '<ul>$1</ul>');

    // Replace [^chunk_id] or [^1] with interactive pill links
    html = html.replace(/\[\^([a-zA-Z0-9_#-]+)\]/g, (match, p1) => {
      return `<button type="button" class="citation-link" data-cid="${p1}">[^${p1}]</button>`;
    });

    return html;
  }

  // -------------------------------------------------------------
  // Chunk Evidence Inspector Modal
  // -------------------------------------------------------------
  function openChunkModal(chunkId, resultData) {
    let targetScored = null;
    if (resultData && resultData.retrieved_sources) {
      targetScored = resultData.retrieved_sources.find(sc => sc.chunk.chunk_id === chunkId);
    }
    
    let targetCit = null;
    if (resultData && resultData.citations) {
      targetCit = resultData.citations.find(cit => cit.chunk_id === chunkId);
    }

    if (targetScored) {
      const c = targetScored.chunk;
      modalChunkId.textContent = c.chunk_id;
      modalDocTitle.textContent = c.title;
      modalSectionName.textContent = `Section: ${c.section} (Match Score: ${(targetScored.score * 100).toFixed(1)}%)`;
      modalQuoteText.textContent = targetCit ? targetCit.quote : c.text.slice(0, 160) + '...';
      modalFullText.textContent = c.text;
      chunkModal.style.display = 'flex';
    } else {
      modalChunkId.textContent = chunkId;
      modalDocTitle.textContent = "Referenced Passage";
      modalSectionName.textContent = "Cited Evidence";
      modalQuoteText.textContent = targetCit ? targetCit.quote : "Referenced source chunk.";
      modalFullText.textContent = `Source chunk ID: ${chunkId}`;
      chunkModal.style.display = 'flex';
    }
  }

  modalCloseBtn.addEventListener('click', () => {
    chunkModal.style.display = 'none';
  });

  // -------------------------------------------------------------
  // Corpus Document Browser
  // -------------------------------------------------------------
  async function fetchDocuments() {
    try {
      const resp = await fetch('/api/documents');
      const data = await resp.json();
      document.getElementById('header-doc-count').textContent = data.total;

      documentsGrid.innerHTML = '';
      data.documents.forEach(doc => {
        const card = document.createElement('div');
        card.className = 'document-card';
        card.innerHTML = `
          <div class="doc-card-header">
            <span class="doc-type-badge">${doc.source_type}</span>
            <span style="font-size:0.75rem; color:var(--text-muted); font-family:var(--font-mono);">${doc.doc_id}</span>
          </div>
          <div class="doc-card-title">${doc.title}</div>
          <div class="doc-card-stats">
            <span>${doc.chunk_count} Chunks</span>
            <span>${doc.word_count} Words</span>
          </div>
        `;
        documentsGrid.appendChild(card);
      });
    } catch (err) {
      console.error('Error fetching documents:', err);
    }
  }

  // Upload Modal Handling
  btnOpenUpload.addEventListener('click', () => {
    uploadModal.style.display = 'flex';
  });

  uploadModalClose.addEventListener('click', () => {
    uploadModal.style.display = 'none';
  });

  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('upload-file');
    const titleInput = document.getElementById('upload-title');
    if (!fileInput.files[0]) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    if (titleInput.value) {
      formData.append('title', titleInput.value);
    }

    try {
      const resp = await fetch('/api/documents/upload', {
        method: 'POST',
        body: formData
      });
      const res = await resp.json();
      if (resp.ok) {
        alert(res.message);
        uploadModal.style.display = 'none';
        uploadForm.reset();
        fetchDocuments();
        fetchHealth();
      } else {
        alert(`Upload error: ${res.detail}`);
      }
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    }
  });

  // -------------------------------------------------------------
  // Benchmark Evaluation Suite Runner
  // -------------------------------------------------------------
  async function fetchBenchmarkQuestions() {
    try {
      const resp = await fetch('/api/benchmark/questions');
      const data = await resp.json();
      benchmarkTableBody.innerHTML = '';
      data.forEach(q => {
        const row = document.createElement('tr');
        row.id = `bench-row-${q.id}`;
        const catBadge = q.category === 'unanswerable' ? 'Fallback Refusal' : q.category.replace('_', ' ').toUpperCase();
        row.innerHTML = `
          <td><strong>${q.id}</strong></td>
          <td><span class="doc-type-badge">${catBadge}</span></td>
          <td>${q.question}</td>
          <td><small style="color:var(--text-secondary);">${q.description}</small></td>
          <td id="bench-status-${q.id}"><span class="test-status-pill" style="background:var(--bg-surface-raised); color:var(--text-muted);">Pending</span></td>
          <td id="bench-grounding-${q.id}">-</td>
          <td id="bench-latency-${q.id}">-</td>
        `;
        benchmarkTableBody.appendChild(row);
      });
    } catch (err) {
      console.error('Error fetching questions:', err);
    }
  }

  btnRunBenchmark.addEventListener('click', async () => {
    btnRunBenchmark.disabled = true;
    btnRunBenchmark.innerHTML = `<span>Running 10 Test Cases...</span>`;

    try {
      const resp = await fetch('/api/benchmark/run', { method: 'POST' });
      if (!resp.ok) throw new Error('Benchmark run failed');
      const report = await resp.json();

      // Display Summary Row
      document.getElementById('metric-pass-rate').textContent = `${(report.pass_rate * 100).toFixed(0)}%`;
      document.getElementById('metric-pass-sub').textContent = `${report.passed_cases} / ${report.total_cases} test cases`;
      document.getElementById('metric-grounding').textContent = `${(report.avg_grounding_score * 100).toFixed(1)}%`;
      document.getElementById('metric-citation-validity').textContent = `${(report.avg_citation_validity * 100).toFixed(0)}%`;
      document.getElementById('metric-fallback-rate').textContent = `${(report.unanswerable_detection_rate * 100).toFixed(0)}%`;
      document.getElementById('metric-avg-latency').textContent = `${report.avg_latency_ms.toFixed(1)}ms`;
      benchmarkMetricsRow.style.display = 'grid';

      // Update Individual Rows
      report.evaluations.forEach(ev => {
        const statusCell = document.getElementById(`bench-status-${ev.question_id}`);
        const groundingCell = document.getElementById(`bench-grounding-${ev.question_id}`);
        const latencyCell = document.getElementById(`bench-latency-${ev.question_id}`);

        if (statusCell) {
          statusCell.innerHTML = `
            <span class="test-status-pill ${ev.passed ? 'passed' : 'failed'}">
              ${ev.passed ? 'PASSED' : 'FAILED'}
            </span>
          `;
        }
        if (groundingCell) {
          groundingCell.innerHTML = `<span style="font-family:var(--font-mono); font-weight:600;">${(ev.grounding_score * 100).toFixed(0)}%</span>`;
        }
        if (latencyCell) {
          latencyCell.innerHTML = `<span style="font-family:var(--font-mono); color:var(--text-secondary);">${ev.latency_ms.toFixed(1)}ms</span>`;
        }
      });

    } catch (err) {
      alert(`Benchmark error: ${err.message}`);
    } finally {
      btnRunBenchmark.disabled = false;
      btnRunBenchmark.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        <span>Execute 10-Case Benchmark</span>
      `;
    }
  });

  // -------------------------------------------------------------
  // System Health
  // -------------------------------------------------------------
  async function fetchHealth() {
    try {
      const resp = await fetch('/api/health');
      const data = await resp.json();
      const provName = data.llm_provider.toUpperCase();
      document.getElementById('provider-name-display').textContent = `Brain: ${provName} (${data.model_name})`;
      document.getElementById('arch-llm-provider').textContent = `${provName} (${data.model_name})`;
    } catch (err) {
      document.getElementById('provider-name-display').textContent = `Offline Engine`;
    }
  }

  // Close modals when clicking outside
  window.addEventListener('click', (e) => {
    if (e.target === chunkModal) chunkModal.style.display = 'none';
    if (e.target === uploadModal) uploadModal.style.display = 'none';
  });
});
