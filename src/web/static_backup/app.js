/**
 * Groww App Review Pulse Agent — Frontend Reactive Application Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  const state = {
    pulses: [],
    activePulse: null,
    metrics: null,
    systemStatus: null,
    reviews: [],
    reviewsPage: 1,
    reviewsTotalPages: 1,
    pipelinePollInterval: null,
  };

  // DOM Elements
  const weekSelector = document.getElementById('week-selector');
  const metricReviews = document.getElementById('metric-total-reviews');
  const metricRating = document.getElementById('metric-avg-rating');
  const metricSentiment = document.getElementById('metric-sentiment');
  const metricPulseWeek = document.getElementById('metric-active-week');
  
  const execSummaryText = document.getElementById('exec-summary-text');
  const themesContainer = document.getElementById('themes-container');
  const quotesContainer = document.getElementById('quotes-container');
  const actionsContainer = document.getElementById('actions-container');
  
  const docLinkBtn = document.getElementById('btn-open-doc');
  const docApprovalBtn = document.getElementById('btn-approve-doc');
  const gmailApprovalBtn = document.getElementById('btn-approve-gmail');
  const approvalBanner = document.getElementById('delivery-approval-banner');

  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  const triggerModal = document.getElementById('trigger-modal');
  const btnOpenTrigger = document.getElementById('btn-open-trigger');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const formTriggerModal = document.getElementById('form-trigger-modal');
  const formTriggerController = document.getElementById('form-trigger-controller');

  const terminalBody = document.getElementById('terminal-logs');
  const pipelineStatusBadge = document.getElementById('pipeline-status-badge');

  // =====================================================================
  // Tab Switching
  // =====================================================================
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.dataset.tab;
      tabButtons.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetEl = document.getElementById(`tab-${targetTab}`);
      if (targetEl) targetEl.classList.add('active');

      if (targetTab === 'analytics') loadAnalytics();
      if (targetTab === 'reviews') loadReviews();
      if (targetTab === 'controller') checkPipelineStatus();
    });
  });

  // =====================================================================
  // API Fetchers
  // =====================================================================

  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      state.systemStatus = data;

      document.getElementById('llm-model-name').textContent = data.environment.llm_model;
      document.getElementById('mcp-status-text').textContent = data.mcp.server_url.replace('https://', '');
    } catch (e) {
      console.error('Failed fetching status:', e);
    }
  }

  function updateWeeklyMetricsCard(week) {
    if (metricPulseWeek) {
      metricPulseWeek.textContent = week;
    }

    const wm = (state.metrics?.weekly && state.metrics.weekly[week]) ||
               (state.activePulse?.metrics) ||
               null;

    if (!wm) return;

    // 1. Total Reviews This Week
    if (metricReviews && wm.total_reviews !== undefined) {
      metricReviews.textContent = wm.total_reviews.toLocaleString();
    }

    // 2. Store Rating This Week & WoW Delta
    const ratingValEl = document.getElementById('metric-rating-val');
    const ratingDeltaEl = document.getElementById('metric-rating-delta');

    if (ratingValEl) {
      ratingValEl.textContent = `${wm.average_rating !== undefined ? wm.average_rating.toFixed(2) : '—'} ★`;
    } else if (metricRating) {
      metricRating.textContent = `${wm.average_rating !== undefined ? wm.average_rating.toFixed(2) : '—'} ★`;
    }

    if (ratingDeltaEl) {
      if (wm.wow_delta_pct !== null && wm.wow_delta_pct !== undefined) {
        const delta = wm.wow_delta_pct;
        const sign = delta > 0 ? '+' : '';
        const arrow = delta > 0 ? '▲ ' : (delta < 0 ? '▼ ' : '');
        const deltaClass = delta > 0 ? 'positive' : (delta < 0 ? 'negative' : 'neutral');
        ratingDeltaEl.className = `wow-delta ${deltaClass}`;
        ratingDeltaEl.textContent = `${arrow}${sign}${delta.toFixed(1)}% WoW`;
        ratingDeltaEl.style.display = 'inline-flex';
      } else {
        ratingDeltaEl.className = 'wow-delta neutral';
        ratingDeltaEl.textContent = '— WoW';
        ratingDeltaEl.style.display = 'inline-flex';
      }
    }

    // 3. Dominant Sentiment (Positive / Negative / Neutral)
    if (metricSentiment) {
      const dom = wm.dominant_sentiment || 'Neutral';
      const pct = wm.dominant_sentiment_pct ? ` (${wm.dominant_sentiment_pct}%)` : '';
      metricSentiment.textContent = `${dom}${pct}`;
      metricSentiment.className = dom.toLowerCase();
    }
  }

  async function fetchMetrics() {
    try {
      const res = await fetch('/api/metrics');
      const data = await res.json();
      state.metrics = data;

      const activeWeek = weekSelector?.value || metricPulseWeek?.textContent;
      if (activeWeek) {
        updateWeeklyMetricsCard(activeWeek);
      }
    } catch (e) {
      console.error('Failed fetching metrics:', e);
    }
  }

  async function fetchPulses() {
    try {
      const res = await fetch('/api/pulses');
      const data = await res.json();
      state.pulses = data.pulses || [];

      weekSelector.innerHTML = '';
      if (state.pulses.length === 0) {
        weekSelector.innerHTML = '<option value="">No pulses found</option>';
        return;
      }

      state.pulses.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.week;
        opt.textContent = p.week;
        weekSelector.appendChild(opt);
      });

      const firstWeek = state.pulses[0].week;
      updateWeeklyMetricsCard(firstWeek);
      await loadPulseDetail(firstWeek);
    } catch (e) {
      console.error('Failed fetching pulses:', e);
    }
  }

  async function loadPulseDetail(week) {
    try {
      updateWeeklyMetricsCard(week);
      const res = await fetch(`/api/pulses/${week}`);
      if (!res.ok) throw new Error('Pulse not found');
      const data = await res.json();
      state.activePulse = data;

      if (data.metrics) {
        if (!state.metrics) state.metrics = { weekly: {} };
        if (!state.metrics.weekly) state.metrics.weekly = {};
        state.metrics.weekly[week] = data.metrics;
        updateWeeklyMetricsCard(week);
      }

      renderPulseView(data);
    } catch (e) {
      console.error('Failed loading pulse detail:', e);
    }
  }

  // =====================================================================
  // Pulse View Renderer
  // =====================================================================
  function renderPulseView(pulse) {
    execSummaryText.textContent = pulse.summary || 'No executive summary available.';

    // Delivery Links & Approvals
    if (pulse.doc_url) {
      docLinkBtn.href = pulse.doc_url;
      docLinkBtn.style.display = 'inline-flex';
    } else {
      docLinkBtn.style.display = 'none';
    }

    if (pulse.docs_approval_url) {
      docApprovalBtn.href = pulse.docs_approval_url;
      docApprovalBtn.style.display = 'inline-flex';
    } else {
      docApprovalBtn.style.display = 'none';
    }

    if (pulse.gmail_approval_url) {
      gmailApprovalBtn.href = pulse.gmail_approval_url;
      gmailApprovalBtn.style.display = 'inline-flex';
    } else {
      gmailApprovalBtn.style.display = 'none';
    }

    // Top Themes
    themesContainer.innerHTML = '';
    (pulse.themes || []).forEach(t => {
      const card = document.createElement('div');
      card.className = 'theme-card';

      let trendClass = 'trend-flat';
      if (t.trend === '↑') trendClass = 'trend-up';
      if (t.trend === '↓') trendClass = 'trend-down';

      card.innerHTML = `
        <div class="theme-card-header">
          <span class="theme-rank-badge">RANK #${t.rank}</span>
          <span class="theme-trend-badge ${trendClass}">${t.trend}</span>
        </div>
        <h4 class="theme-title">${escapeHtml(t.title)}</h4>
        <div class="theme-pill-stats">
          <span class="pill-stat reviews">${escapeHtml(t.stats)}</span>
        </div>
        <p class="theme-description">${escapeHtml(t.description)}</p>
      `;
      themesContainer.appendChild(card);
    });

    // User Quotes
    quotesContainer.innerHTML = '';
    (pulse.quotes || []).forEach(q => {
      const card = document.createElement('div');
      card.className = 'quote-card';
      card.innerHTML = `
        <div class="quote-stars">${'★'.repeat(q.rating)}${'☆'.repeat(5 - q.rating)}</div>
        <p class="quote-text">${escapeHtml(q.text)}</p>
        <div class="quote-attribution">
          <span>${escapeHtml(q.attribution)}</span>
          <span class="tag-badge">Verbatim</span>
        </div>
      `;
      quotesContainer.appendChild(card);
    });

    // Action Ideas
    actionsContainer.innerHTML = '';
    (pulse.actions || []).forEach(a => {
      const card = document.createElement('div');
      const tagLower = (a.tag || '').toLowerCase();
      let extraClass = '';
      if (tagLower.includes('bug') || tagLower.includes('crash')) extraClass = 'bug';
      if (tagLower.includes('upi') || tagLower.includes('payment')) extraClass = 'upi';

      card.className = `action-card ${extraClass}`;
      card.innerHTML = `
        <span class="action-tag-badge">${escapeHtml(a.tag)}</span>
        <p class="action-text">${escapeHtml(a.description)}</p>
      `;
      actionsContainer.appendChild(card);
    });

    // Raw markdown drawer
    const rawMdEl = document.getElementById('raw-markdown-text');
    if (rawMdEl) rawMdEl.textContent = pulse.markdown || '';
  }

  // =====================================================================
  // Analytics Renderer (Tab 2)
  // =====================================================================
  async function loadAnalytics() {
    if (!state.metrics) await fetchMetrics();
    const metrics = state.metrics;
    if (!metrics) return;

    // Theme bars
    const themesListEl = document.getElementById('analytics-themes-list');
    themesListEl.innerHTML = '';
    const maxThemeCount = Math.max(...metrics.top_themes.map(t => t.count), 1);

    metrics.top_themes.forEach(t => {
      const pct = Math.round((t.count / maxThemeCount) * 100);
      const row = document.createElement('div');
      row.className = 'bar-row';
      row.innerHTML = `
        <div class="bar-labels">
          <strong>${escapeHtml(t.theme)}</strong>
          <span>${t.count} reviews</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width: ${pct}%"></div>
        </div>
      `;
      themesListEl.appendChild(row);
    });

    // Sentiment Bars
    const sent = metrics.sentiment_distribution;
    const sentTotal = (sent.positive || 0) + (sent.neutral || 0) + (sent.negative || 0) || 1;
    document.getElementById('sent-pos-val').textContent = `${sent.positive} (${Math.round((sent.positive/sentTotal)*100)}%)`;
    document.getElementById('sent-neu-val').textContent = `${sent.neutral} (${Math.round((sent.neutral/sentTotal)*100)}%)`;
    document.getElementById('sent-neg-val').textContent = `${sent.negative} (${Math.round((sent.negative/sentTotal)*100)}%)`;
    
    document.getElementById('sent-pos-bar').style.width = `${Math.round((sent.positive/sentTotal)*100)}%`;
    document.getElementById('sent-neu-bar').style.width = `${Math.round((sent.neutral/sentTotal)*100)}%`;
    document.getElementById('sent-neg-bar').style.width = `${Math.round((sent.negative/sentTotal)*100)}%`;

    // Ratings Distribution
    const ratingsEl = document.getElementById('analytics-ratings-list');
    ratingsEl.innerHTML = '';
    const dist = metrics.ratings_distribution || {};
    const maxRatingCount = Math.max(...Object.values(dist), 1);

    [5, 4, 3, 2, 1].forEach(star => {
      const count = dist[star] || 0;
      const pct = Math.round((count / maxRatingCount) * 100);
      const row = document.createElement('div');
      row.className = 'bar-row';
      row.innerHTML = `
        <div class="bar-labels">
          <span>${'★'.repeat(star)} (${star} Star)</span>
          <span>${count}</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill neutral" style="width: ${pct}%"></div>
        </div>
      `;
      ratingsEl.appendChild(row);
    });
  }

  // =====================================================================
  // Reviews Explorer (Tab 3)
  // =====================================================================
  async function loadReviews() {
    const search = document.getElementById('reviews-search-input').value.trim();
    const sentiment = document.getElementById('filter-sentiment').value;
    const rating = document.getElementById('filter-rating').value;
    const theme = document.getElementById('filter-theme').value;

    const params = new URLSearchParams({
      page: state.reviewsPage,
      page_size: 15,
    });
    if (search) params.append('search', search);
    if (sentiment) params.append('sentiment', sentiment);
    if (rating) params.append('rating', rating);
    if (theme) params.append('theme', theme);

    try {
      const res = await fetch(`/api/reviews?${params.toString()}`);
      const data = await res.json();
      state.reviews = data.reviews || [];
      state.reviewsTotalPages = data.total_pages || 1;

      renderReviewsList(state.reviews);
      document.getElementById('reviews-page-indicator').textContent = `Page ${data.page} of ${data.total_pages} (${data.total} reviews)`;
    } catch (e) {
      console.error('Failed loading reviews:', e);
    }
  }

  function renderReviewsList(reviews) {
    const container = document.getElementById('reviews-list-container');
    container.innerHTML = '';

    if (reviews.length === 0) {
      container.innerHTML = '<p style="text-align:center; padding: 2rem; color: var(--text-subtle);">No reviews match your filters.</p>';
      return;
    }

    reviews.forEach(r => {
      const card = document.createElement('div');
      card.className = 'review-item-card';

      const stars = '★'.repeat(r.rating || 1);
      const sentimentTag = r.sentiment_label || 'neutral';
      const themeTag = r.theme || 'General';

      card.innerHTML = `
        <div class="review-meta-row">
          <span class="review-author">${escapeHtml(r.author || 'Anonymous')}</span>
          <span class="quote-stars">${stars}</span>
        </div>
        <p class="review-body">${escapeHtml(r.text || '')}</p>
        <div class="review-tags">
          <span class="tag-badge pill-stat ${sentimentTag}">${sentimentTag}</span>
          <span class="tag-badge">${escapeHtml(themeTag)}</span>
          <span class="tag-badge">${r.source === 'appstore' ? 'iOS App Store' : 'Google Play'}</span>
          ${r.app_version ? `<span class="tag-badge">v${escapeHtml(r.app_version)}</span>` : ''}
          ${r.is_hinglish ? '<span class="tag-badge" style="color:var(--accent-amber)">Hinglish</span>' : ''}
        </div>
      `;
      container.appendChild(card);
    });
  }

  // =====================================================================
  // Agent Controller & Terminal (Tab 4)
  // =====================================================================
  async function triggerRun(week, dryRun, scrapeOnly) {
    try {
      const res = await fetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ week, dry_run: dryRun, scrape_only: scrapeOnly }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert(`Failed: ${err.detail}`);
        return;
      }
      pollPipelineLogs();
    } catch (e) {
      alert(`Error triggering pipeline: ${e.message}`);
    }
  }

  async function checkPipelineStatus() {
    try {
      const res = await fetch('/api/pipeline/status');
      const data = await res.json();

      pipelineStatusBadge.textContent = data.status.toUpperCase();
      pipelineStatusBadge.className = `status-pill ${data.status === 'running' ? 'amber' : ''}`;

      terminalBody.innerHTML = '';
      (data.logs || []).forEach(log => {
        const p = document.createElement('div');
        p.className = 'log-entry';
        p.textContent = log;
        terminalBody.appendChild(p);
      });
      terminalBody.scrollTop = terminalBody.scrollHeight;

      if (data.status === 'running') {
        if (!state.pipelinePollInterval) {
          state.pipelinePollInterval = setInterval(checkPipelineStatus, 2000);
        }
      } else {
        if (state.pipelinePollInterval) {
          clearInterval(state.pipelinePollInterval);
          state.pipelinePollInterval = null;
        }
        // Refresh pulses if just completed
        if (data.status === 'completed') {
          fetchPulses();
        }
      }
    } catch (e) {
      console.error('Failed checking pipeline status:', e);
    }
  }

  function pollPipelineLogs() {
    checkPipelineStatus();
    if (!state.pipelinePollInterval) {
      state.pipelinePollInterval = setInterval(checkPipelineStatus, 2000);
    }
  }

  // =====================================================================
  // Event Listeners
  // =====================================================================
  weekSelector.addEventListener('change', (e) => {
    const selectedWeek = e.target.value;
    updateWeeklyMetricsCard(selectedWeek);
    loadPulseDetail(selectedWeek);
  });

  document.getElementById('btn-copy-markdown')?.addEventListener('click', () => {
    if (state.activePulse?.markdown) {
      navigator.clipboard.writeText(state.activePulse.markdown);
      alert('Weekly Pulse markdown copied to clipboard!');
    }
  });

  // Modal open / close
  btnOpenTrigger.addEventListener('click', () => triggerModal.showModal());
  btnCloseModal.addEventListener('click', () => triggerModal.close());

  formTriggerModal.addEventListener('submit', (e) => {
    e.preventDefault();
    const week = document.getElementById('modal-input-week').value.trim() || null;
    const dryRun = document.getElementById('modal-check-dryrun').checked;
    const scrapeOnly = document.getElementById('modal-check-scrapeonly').checked;
    triggerModal.close();
    
    // Switch to controller tab
    document.querySelector('[data-tab="controller"]').click();
    triggerRun(week, dryRun, scrapeOnly);
  });

  formTriggerController.addEventListener('submit', (e) => {
    e.preventDefault();
    const week = document.getElementById('ctrl-input-week').value.trim() || null;
    const dryRun = document.getElementById('ctrl-check-dryrun').checked;
    const scrapeOnly = document.getElementById('ctrl-check-scrapeonly').checked;
    triggerRun(week, dryRun, scrapeOnly);
  });

  // Review explorer filters
  document.getElementById('reviews-search-input').addEventListener('input', debounce(loadReviews, 300));
  document.getElementById('filter-sentiment').addEventListener('change', loadReviews);
  document.getElementById('filter-rating').addEventListener('change', loadReviews);
  document.getElementById('filter-theme').addEventListener('change', loadReviews);

  document.getElementById('btn-prev-page').addEventListener('click', () => {
    if (state.reviewsPage > 1) {
      state.reviewsPage--;
      loadReviews();
    }
  });

  document.getElementById('btn-next-page').addEventListener('click', () => {
    if (state.reviewsPage < state.reviewsTotalPages) {
      state.reviewsPage++;
      loadReviews();
    }
  });

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function debounce(func, wait) {
    let timeout;
    return (...args) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  // Initial Boot
  fetchStatus();
  fetchMetrics();
  fetchPulses();
});
