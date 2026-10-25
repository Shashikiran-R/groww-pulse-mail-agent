/**
 * Groww App Review Pulse — Obsidian Telemetry Frontend Reactive Application Logic
 * Integrates Google Stitch Component Design with FastAPI Live Telemetry & MCP Pipeline.
 * Only verified, fully working interactive elements are included.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Global Application State
  const state = {
    pulses: [],
    activeWeek: null,
    activePulse: null,
    metrics: null,
    systemStatus: null,
    reviews: [],
    reviewsPage: 1,
    reviewsTotalPages: 1,
    currentFilterSentiment: 'all',
    currentFilterSource: 'all',
    currentSearch: '',
    pipelinePollInterval: null,
  };

  // DOM Elements
  const weekSelector = document.getElementById('week-selector');
  const breadcrumbWeek = document.getElementById('breadcrumb-week');
  const topGpRating = document.getElementById('top-gp-rating');
  const topMcpBadge = document.getElementById('top-mcp-badge');

  // KPI Elements
  const kpiTotalReviews = document.getElementById('kpi-total-reviews');
  const kpiRatingVal = document.getElementById('kpi-rating-val');
  const kpiRatingDelta = document.getElementById('kpi-rating-delta');
  const kpiRatingRing = document.getElementById('kpi-rating-ring');
  const kpiRatingPct = document.getElementById('kpi-rating-pct');
  const kpiAndroidRtg = document.getElementById('kpi-android-rtg');

  const kpiSentimentBadge = document.getElementById('kpi-sentiment-badge');
  const kpiSentimentBarPos = document.getElementById('kpi-sentiment-bar-pos');
  const kpiSentimentBarNeu = document.getElementById('kpi-sentiment-bar-neu');
  const kpiSentimentBarNeg = document.getElementById('kpi-sentiment-bar-neg');
  const kpiSentimentPosPct = document.getElementById('kpi-sentiment-pos-pct');
  const kpiSentimentNeuPct = document.getElementById('kpi-sentiment-neu-pct');
  const kpiSentimentNegPct = document.getElementById('kpi-sentiment-neg-pct');
  const kpiPolarityScore = document.getElementById('kpi-polarity-score');

  const kpiDocLink = document.getElementById('kpi-doc-link');
  const btnViewDocHub = document.getElementById('btn-view-doc-hub');
  const dashboardExecSummary = document.getElementById('dashboard-exec-summary');
  const themesListContainer = document.getElementById('themes-list-container');
  const reviewsFeedContainer = document.getElementById('reviews-feed-container');
  const trajectorySvg = document.getElementById('trajectory-svg');
  const vocTotalBadge = document.getElementById('voc-total-badge');
  const reviewsPageInfo = document.getElementById('reviews-page-info');
  const btnPrevPage = document.getElementById('btn-prev-page');
  const btnNextPage = document.getElementById('btn-next-page');

  // Operational Views Navigation (Dashboard, Customer Themes, Trend Analytics, Delivery Logs)
  const navTabButtons = document.querySelectorAll('.nav-tab-btn');

  function setActiveNavButton(target) {
    navTabButtons.forEach(btn => {
      if (btn.dataset.target === target) {
        btn.classList.add('bg-primary-container', 'text-on-primary', 'font-bold', 'shadow-[0_0_12px_rgba(5,238,168,0.25)]');
        btn.classList.remove('text-on-surface-variant');
      } else {
        btn.classList.remove('bg-primary-container', 'text-on-primary', 'font-bold', 'shadow-[0_0_12px_rgba(5,238,168,0.25)]');
        btn.classList.add('text-on-surface-variant');
      }
    });
  }

  let isProgrammaticScroll = false;

  navTabButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const target = btn.dataset.target;
      const targetSection = document.getElementById(`view-${target}`);
      if (targetSection) {
        setActiveNavButton(target);
        isProgrammaticScroll = true;
        targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setTimeout(() => {
          isProgrammaticScroll = false;
        }, 800);
      }
    });
  });

  // IntersectionObserver to sync left navigation as user scrolls through sections
  const sectionIds = ['dashboard', 'customer-themes', 'trend-analytics', 'delivery-logs'];
  const sectionObserver = new IntersectionObserver((entries) => {
    if (isProgrammaticScroll) return;
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id.replace('view-', '');
        setActiveNavButton(id);
      }
    });
  }, {
    rootMargin: '-15% 0px -65% 0px',
    threshold: 0.05
  });

  sectionIds.forEach(id => {
    const el = document.getElementById(`view-${id}`);
    if (el) sectionObserver.observe(el);
  });

  // Week Selector Change (Strict YYYY-WXX)
  if (weekSelector) {
    weekSelector.addEventListener('change', (e) => {
      selectWeek(e.target.value);
    });
  }



  // VOC Sentiment Filter Pills (All / Critical 1-2★ / Praise 5★ / Neutral 3★)
  const vocFilterPills = document.querySelectorAll('.voc-filter-pill');
  vocFilterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      vocFilterPills.forEach(p => {
        p.className = 'voc-filter-pill px-2.5 py-1 rounded bg-surface-container text-outline hover:bg-surface-container-high border border-outline-variant/30 cursor-pointer transition-colors';
      });
      pill.className = 'voc-filter-pill px-2.5 py-1 rounded bg-primary-container text-on-primary font-bold shadow-[0_0_8px_rgba(5,238,168,0.3)] cursor-pointer transition-colors';
      state.currentFilterSentiment = pill.dataset.sentiment;
      loadVoiceOfCustomerReviews(1);
    });
  });

  // Pagination Buttons
  if (btnPrevPage) {
    btnPrevPage.addEventListener('click', () => {
      if (state.reviewsPage > 1) {
        loadVoiceOfCustomerReviews(state.reviewsPage - 1);
      }
    });
  }

  if (btnNextPage) {
    btnNextPage.addEventListener('click', () => {
      if (state.reviewsPage < state.reviewsTotalPages) {
        loadVoiceOfCustomerReviews(state.reviewsPage + 1);
      }
    });
  }

  // =====================================================================
  // API Fetchers & Initializers
  // =====================================================================

  async function init() {
    await fetchSystemStatus();
    await fetchMetrics();
    await fetchPulses();
  }

  async function fetchSystemStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      state.systemStatus = data;

      const mcpText = data.mcp?.server_url ? 'Connected to MCP' : 'MCP Standby';
      if (topMcpBadge) topMcpBadge.textContent = mcpText;

      const engineVersion = document.getElementById('sidebar-engine-version');
      if (engineVersion) engineVersion.textContent = `v${data.version || '2.6.4'}-stable`;
    } catch (e) {
      console.error('Failed to fetch system status:', e);
    }
  }

  async function fetchMetrics() {
    try {
      const res = await fetch('/api/metrics');
      const data = await res.json();
      state.metrics = data;
    } catch (e) {
      console.error('Failed to fetch metrics:', e);
    }
  }

  async function fetchPulses() {
    try {
      const res = await fetch('/api/pulses');
      const data = await res.json();
      state.pulses = data.pulses || [];

      if (weekSelector) {
        weekSelector.innerHTML = '';
        state.pulses.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.week;
          opt.textContent = p.week; // Strict YYYY-WXX format
          weekSelector.appendChild(opt);
        });
      }

      if (state.pulses.length > 0) {
        selectWeek(state.pulses[0].week);
      }
    } catch (e) {
      console.error('Failed to fetch pulses:', e);
    }
  }

  async function selectWeek(week) {
    state.activeWeek = week;
    if (weekSelector) weekSelector.value = week;
    if (breadcrumbWeek) breadcrumbWeek.textContent = week;

    const rankBadge = document.getElementById('themes-week-rank-badge');
    if (rankBadge) rankBadge.textContent = `${week.replace('2026-', '')} RANKS`;

    try {
      const res = await fetch(`/api/pulses/${week}`);
      if (!res.ok) throw new Error('Pulse not found');
      const pulse = await res.json();
      state.activePulse = pulse;

      renderDashboardPulse(pulse);
      renderDetailedThemesView();
      renderTrendAnalyticsView();
      checkPipelineStatus();
      loadVoiceOfCustomerReviews(1);
      renderTrajectoryChart();
    } catch (e) {
      console.error(`Failed to load pulse ${week}:`, e);
    }
  }

  // =====================================================================
  // Renderers
  // =====================================================================

  function renderDashboardPulse(pulse) {
    const wm = pulse.metrics || (state.metrics?.weekly && state.metrics.weekly[pulse.week]) || {};

    // 1. Total Reviews
    const totalReviews = wm.total_reviews !== undefined ? wm.total_reviews : 0;
    if (kpiTotalReviews) kpiTotalReviews.textContent = totalReviews.toLocaleString();

    // 2. Store Rating & WoW Delta
    const avgRating = wm.average_rating !== undefined ? wm.average_rating.toFixed(2) : '4.30';
    if (kpiRatingVal) kpiRatingVal.textContent = `${avgRating} ★`;
    if (topGpRating) topGpRating.textContent = `Google Play ${avgRating}`;
    if (kpiAndroidRtg) kpiAndroidRtg.textContent = `${avgRating} ★`;

    if (kpiRatingDelta) {
      if (wm.wow_delta_pct !== null && wm.wow_delta_pct !== undefined) {
        const delta = wm.wow_delta_pct;
        const sign = delta > 0 ? '+' : '';
        const arrow = delta > 0 ? 'north_east' : (delta < 0 ? 'south_east' : 'east');
        const isPos = delta >= 0;
        kpiRatingDelta.className = `inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded ${isPos ? 'bg-primary-container/15 text-primary' : 'bg-error/15 text-error'} text-xs font-mono font-bold`;
        kpiRatingDelta.innerHTML = `<span class="material-symbols-outlined text-[13px]">${arrow}</span> ${sign}${delta.toFixed(1)}% WoW`;
      } else {
        kpiRatingDelta.className = 'inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-surface-container text-outline text-xs font-mono';
        kpiRatingDelta.textContent = '— WoW';
      }
    }

    // Rating ring svg percent
    if (kpiRatingPct && kpiRatingRing) {
      const pct = Math.round((parseFloat(avgRating) / 5) * 100);
      kpiRatingPct.textContent = `${pct}%`;
      kpiRatingRing.setAttribute('stroke-dasharray', `${pct}, 100`);
    }

    // 3. Dominant Sentiment
    const domSent = wm.dominant_sentiment || 'Positive';
    const domPct = wm.dominant_sentiment_pct || 64;
    if (kpiSentimentBadge) kpiSentimentBadge.textContent = `${domSent} (${domPct}%)`;

    const sDist = wm.sentiment_distribution || { positive: 64, neutral: 21, negative: 15 };
    const totalS = (sDist.positive + sDist.neutral + sDist.negative) || 100;
    const posPct = Math.round((sDist.positive / totalS) * 100);
    const neuPct = Math.round((sDist.neutral / totalS) * 100);
    const negPct = Math.max(0, 100 - posPct - neuPct);

    if (kpiSentimentBarPos) kpiSentimentBarPos.style.width = `${posPct}%`;
    if (kpiSentimentBarNeu) kpiSentimentBarNeu.style.width = `${neuPct}%`;
    if (kpiSentimentBarNeg) kpiSentimentBarNeg.style.width = `${negPct}%`;

    if (kpiSentimentPosPct) kpiSentimentPosPct.textContent = `${posPct}% Pos`;
    if (kpiSentimentNeuPct) kpiSentimentNeuPct.textContent = `${neuPct}% Neu`;
    if (kpiSentimentNegPct) kpiSentimentNegPct.textContent = `${negPct}% Neg`;

    if (kpiPolarityScore) {
      const polarity = ((posPct - negPct) / 100).toFixed(2);
      kpiPolarityScore.textContent = `${polarity > 0 ? '+' : ''}${polarity}`;
      kpiPolarityScore.className = polarity >= 0 ? 'text-primary font-bold' : 'text-error font-bold';
    }

    // 4. Live Google Doc Links
    const docUrl = pulse.doc_url || 'https://docs.google.com/document/d/18LgIvY3jE9tJthxHYguw5wVigJhG5BJmd9wvEFbsaDw/edit';
    if (kpiDocLink) kpiDocLink.href = docUrl;
    if (btnViewDocHub) btnViewDocHub.href = docUrl;

    const deliveryDocTitle = document.getElementById('delivery-doc-title');
    if (deliveryDocTitle) deliveryDocTitle.textContent = `${pulse.week} Weekly Review Pulse Brief`;

    // Executive Summary
    if (dashboardExecSummary) {
      dashboardExecSummary.textContent = pulse.summary || 'Weekly review intelligence synthesized via agent pipeline.';
    }

    // Render Top Themes
    renderThemesList(pulse.themes || [], pulse.quotes || []);
  }

  function renderThemesList(themes, quotes) {
    if (!themesListContainer) return;
    themesListContainer.innerHTML = '';

    if (themes.length === 0) {
      themesListContainer.innerHTML = '<div class="p-4 text-center text-outline font-mono text-xs">No friction themes recorded for this week.</div>';
      return;
    }

    const priorityColors = [
      { border: 'border-error/30 hover:border-error', badgeBg: 'bg-error-container text-error', text: 'text-error', dot: 'bg-error', priority: 'Priority P0', label: 'Critical Friction' },
      { border: 'border-amber-400/30 hover:border-amber-400', badgeBg: 'bg-amber-400/15 text-amber-300', text: 'text-amber-300', dot: 'bg-amber-400', priority: 'Priority P1', label: 'Latency Spill' },
      { border: 'border-outline-variant/30 hover:border-tertiary-fixed-dim/40', badgeBg: 'bg-tertiary-container/20 text-tertiary-fixed-dim', text: 'text-tertiary-fixed-dim', dot: 'bg-tertiary-fixed-dim', priority: 'Priority P2', label: 'Feature Request' },
    ];

    themes.slice(0, 3).forEach((theme, idx) => {
      const style = priorityColors[idx] || priorityColors[2];
      const matchingQuote = quotes[idx] ? `"${quotes[idx].text}"` : '"Customer feedback tracked under this category."';

      const card = document.createElement('div');
      card.className = `p-3 rounded bg-surface-container-lowest border ${style.border} transition-all`;
      card.innerHTML = `
        <div class="flex items-center justify-between">
          <span class="font-label-xs text-xs font-mono ${style.text} font-bold flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full ${style.dot}"></span>
            RANK #${theme.rank || idx + 1} · ${theme.stats || 'High Volume'}
          </span>
          <span class="px-1.5 py-0.5 rounded ${style.badgeBg} text-[10px] font-bold uppercase font-mono">${style.label}</span>
        </div>
        <h3 class="font-body-lg text-sm font-bold text-on-surface mt-1">${theme.title}</h3>
        <p class="font-body-sm text-xs text-on-surface-variant italic mt-1 bg-surface-container/50 p-2 rounded border border-outline-variant/15 leading-relaxed font-sans">
          ${matchingQuote}
        </p>
        <div class="mt-2 flex items-center justify-between font-label-xs text-[11px] text-outline font-mono">
          <span class="text-on-surface truncate max-w-[200px]">${theme.description || 'Assigned to Engineering'}</span>
          <span class="${style.text} font-bold">${style.priority}</span>
        </div>
      `;
      themesListContainer.appendChild(card);
    });
  }

  // =====================================================================
  // Trajectory Chart SVG Dynamic Rendering
  // =====================================================================

  function renderTrajectoryChart() {
    if (!trajectorySvg) return;
    const weeklyData = state.metrics?.weekly || {};
    const sortedWeeks = Object.keys(weeklyData).sort();
    if (sortedWeeks.length === 0) return;

    // Take last 8 weeks
    const weeksToPlot = sortedWeeks.slice(-8);
    const svgWidth = 700;
    const svgHeight = 220;
    const margin = { left: 40, right: 30, top: 30, bottom: 35 };
    const chartW = svgWidth - margin.left - margin.right;
    const chartH = svgHeight - margin.top - margin.bottom;

    const barWidth = 34;
    const step = chartW / weeksToPlot.length;

    let barsHtml = '';
    let ratingPoints = [];

    weeksToPlot.forEach((w, i) => {
      const data = weeklyData[w] || {};
      const sDist = data.sentiment_distribution || { positive: 60, neutral: 25, negative: 15 };
      const total = (sDist.positive + sDist.neutral + sDist.negative) || 100;
      const posRatio = sDist.positive / total;
      const neuRatio = sDist.neutral / total;
      const negRatio = sDist.negative / total;

      const totalBarH = 130;
      const posH = Math.round(posRatio * totalBarH);
      const neuH = Math.round(neuRatio * totalBarH);
      const negH = Math.round(negRatio * totalBarH);

      const x = margin.left + i * step + (step - barWidth) / 2;
      const yBottom = margin.top + chartH;

      const yNeg = yBottom - negH;
      const yNeu = yNeg - neuH;
      const yPos = yNeu - posH;

      const isCurrentWeek = w === state.activeWeek;
      const label = w.replace('2026-', '');

      // Store rating point (mapped 3.5 to 5.0 onto chart height)
      const rtg = data.average_rating || 4.2;
      const rtgNormalized = Math.min(1, Math.max(0, (rtg - 3.5) / 1.5));
      const rtgY = margin.top + chartH - (rtgNormalized * (chartH - 20));
      const rtgX = x + barWidth / 2;
      ratingPoints.push({ x: rtgX, y: rtgY, rating: rtg, week: w });

      barsHtml += `
        <g class="cursor-pointer transition-opacity hover:opacity-80" onclick="window.dispatchEvent(new CustomEvent('switch-week', {detail: '${w}'}))">
          ${isCurrentWeek ? `
            <rect x="${x - 4}" y="${margin.top - 10}" width="${barWidth + 8}" height="${chartH + 20}" rx="4" fill="#05eea8" fill-opacity="0.08" stroke="#05eea8" stroke-dasharray="2 2" stroke-width="1"></rect>
          ` : ''}
          <!-- Positive segment (top) -->
          <rect x="${x}" y="${yPos}" width="${barWidth}" height="${posH}" rx="2" fill="#05eea8"></rect>
          <!-- Neutral segment (middle) -->
          <rect x="${x}" y="${yNeu}" width="${barWidth}" height="${neuH}" rx="0" fill="#f59e0b"></rect>
          <!-- Negative segment (bottom) -->
          <rect x="${x}" y="${yNeg}" width="${barWidth}" height="${negH}" rx="2" fill="#ff3b5c"></rect>
          <!-- Week Label -->
          <text x="${x + barWidth / 2}" y="${yBottom + 20}" fill="${isCurrentWeek ? '#adffd5' : '#84958a'}" font-family="JetBrains Mono" font-size="11" font-weight="${isCurrentWeek ? 'bold' : 'normal'}" text-anchor="middle">${label}</text>
        </g>
      `;
    });

    // Spline Line path for ratings
    let linePath = '';
    if (ratingPoints.length > 0) {
      linePath = `M${ratingPoints[0].x},${ratingPoints[0].y}`;
      for (let i = 1; i < ratingPoints.length; i++) {
        linePath += ` L${ratingPoints[i].x},${ratingPoints[i].y}`;
      }
    }

    let pointsHtml = ratingPoints.map(p => {
      const isCurr = p.week === state.activeWeek;
      return `
        <circle cx="${p.x}" cy="${p.y}" r="${isCurr ? 4.5 : 3.5}" fill="${isCurr ? '#7bd0ff' : '#101416'}" stroke="#7bd0ff" stroke-width="2" class="${isCurr ? 'animate-pulse' : ''}"></circle>
      `;
    }).join('');

    trajectorySvg.innerHTML = `
      <defs>
        <linearGradient id="chartGlow" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#05eea8" stop-opacity="0.3"></stop>
          <stop offset="100%" stop-color="#05eea8" stop-opacity="0.0"></stop>
        </linearGradient>
      </defs>
      <!-- Grid Lines -->
      <line x1="${margin.left}" y1="${margin.top}" x2="${svgWidth - margin.right}" y2="${margin.top}" stroke="#3b4a41" stroke-dasharray="3 3" opacity="0.3"></line>
      <line x1="${margin.left}" y1="${margin.top + chartH / 2}" x2="${svgWidth - margin.right}" y2="${margin.top + chartH / 2}" stroke="#3b4a41" stroke-dasharray="3 3" opacity="0.3"></line>
      <line x1="${margin.left}" y1="${margin.top + chartH}" x2="${svgWidth - margin.right}" y2="${margin.top + chartH}" stroke="#3b4a41" stroke-dasharray="3 3" opacity="0.3"></line>
      
      <!-- Bars -->
      ${barsHtml}
      
      <!-- Rating Spline -->
      <path d="${linePath}" fill="none" stroke="#7bd0ff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>
      ${pointsHtml}
    `;
  }

  window.addEventListener('switch-week', (e) => {
    if (e.detail) selectWeek(e.detail);
  });

  // =====================================================================
  // Voice of Customer Feed Loader
  // =====================================================================

  async function loadVoiceOfCustomerReviews(page = 1) {
    if (!reviewsFeedContainer) return;
    state.reviewsPage = page;

    let url = `/api/reviews?page=${page}&page_size=5&week=${state.activeWeek || ''}`;
    if (state.currentFilterSentiment && state.currentFilterSentiment !== 'all') {
      url += `&sentiment=${state.currentFilterSentiment}`;
    }
    if (state.currentFilterSource && state.currentFilterSource !== 'all') {
      url += `&source=${state.currentFilterSource}`;
    }
    if (state.currentSearch) {
      url += `&search=${encodeURIComponent(state.currentSearch)}`;
    }

    try {
      const res = await fetch(url);
      const data = await res.json();
      state.reviews = data.reviews || [];
      state.reviewsTotalPages = data.total_pages || 1;

      if (vocTotalBadge) {
        vocTotalBadge.textContent = `${data.total?.toLocaleString() || 0} Total`;
      }

      if (reviewsPageInfo) {
        reviewsPageInfo.textContent = `Page ${data.page} of ${data.total_pages || 1}`;
      }
      if (btnPrevPage) btnPrevPage.disabled = data.page <= 1;
      if (btnNextPage) btnNextPage.disabled = data.page >= (data.total_pages || 1);

      renderReviewsFeed(state.reviews);
    } catch (e) {
      console.error('Failed to load reviews feed:', e);
      reviewsFeedContainer.innerHTML = '<div class="p-4 text-center text-error font-mono text-xs">Failed to load customer reviews stream.</div>';
    }
  }

  function renderReviewsFeed(reviews) {
    reviewsFeedContainer.innerHTML = '';
    if (reviews.length === 0) {
      reviewsFeedContainer.innerHTML = `
        <div class="p-8 text-center bg-surface-container-lowest rounded border border-outline-variant/20 flex flex-col items-center justify-center font-mono">
          <span class="material-symbols-outlined text-3xl text-outline mb-1">find_in_page</span>
          <p class="text-sm font-bold text-on-surface">No reviews matched query</p>
          <p class="text-xs text-outline mt-1">Try resetting the sentiment or platform filters.</p>
        </div>
      `;
      return;
    }

    reviews.forEach(r => {
      const isPos = (r.sentiment_label || '').toLowerCase().includes('pos');
      const isNeg = (r.sentiment_label || '').toLowerCase().includes('neg');
      const sentColor = isPos ? 'text-primary' : (isNeg ? 'text-error' : 'text-amber-300');
      const borderAccent = isPos ? 'border-primary-container/40' : (isNeg ? 'border-error/40' : 'border-amber-400/40');
      const barColor = isPos ? 'bg-primary-container' : (isNeg ? 'bg-error' : 'bg-amber-400');

      const stars = '★'.repeat(r.rating || 1) + '☆'.repeat(5 - (r.rating || 1));
      const sourceIcon = 'android';
      const sourceName = 'Google Play';

      const initials = (r.author || 'User').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() || 'US';

      const card = document.createElement('article');
      card.className = `p-3 rounded bg-surface-container-lowest border ${borderAccent} hover:border-primary-container/60 transition-all relative overflow-hidden group`;
      card.innerHTML = `
        <div class="absolute left-0 top-0 bottom-0 w-1 ${barColor}"></div>
        <div class="flex items-start justify-between gap-2 pl-1 font-mono">
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center justify-center w-7 h-7 rounded bg-surface-container-high text-on-surface font-bold text-xs">${initials}</span>
            <div class="flex flex-col">
              <span class="font-body-md text-xs font-bold text-on-surface">${r.author || 'Anonymous'}</span>
              <span class="font-label-xs text-[10px] text-outline flex items-center gap-1">
                <span class="material-symbols-outlined text-[13px] text-tertiary-fixed-dim">${sourceIcon}</span>
                ${sourceName} · ${r.date || 'Recent'}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded bg-surface-container text-xs font-bold ${sentColor}">
              ${r.theme || 'General Feedback'}
            </span>
            <div class="${sentColor} text-xs tracking-wider">${stars}</div>
          </div>
        </div>
        <p class="font-body-md text-xs text-on-surface mt-2 pl-1 leading-relaxed font-sans">
          ${r.text}
        </p>
        <div class="mt-2 pt-1.5 border-t border-outline-variant/15 flex items-center justify-between pl-1 font-mono text-[10px] text-outline">
          <span class="text-on-surface-variant font-mono">Theme: <strong class="text-on-surface">${r.theme || 'General'}</strong></span>
          <span>Sentiment Score: ${(r.sentiment_score || 0).toFixed(2)}</span>
        </div>
      `;
      reviewsFeedContainer.appendChild(card);
    });
  }

  // =====================================================================
  // Customer Themes Detailed View
  // =====================================================================

  function renderDetailedThemesView() {
    const grid = document.getElementById('themes-detailed-grid');
    const actionsList = document.getElementById('themes-action-items-list');
    const weekBadge = document.getElementById('themes-view-week-badge');

    if (weekBadge && state.activeWeek) weekBadge.textContent = state.activeWeek;
    if (!grid || !state.activePulse) return;

    grid.innerHTML = '';
    const themes = state.activePulse.themes || [];

    themes.forEach((t, i) => {
      const card = document.createElement('div');
      card.className = 'p-4 rounded bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between';
      card.innerHTML = `
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="font-mono text-xs text-primary font-bold">RANK #${t.rank || i + 1}</span>
            <span class="text-outline font-mono text-xs">${t.stats || ''}</span>
          </div>
          <h4 class="font-bold text-sm text-on-surface">${t.title}</h4>
          <p class="text-xs text-outline mt-2 leading-relaxed font-sans">${t.description}</p>
        </div>
        <div class="mt-4 pt-3 border-t border-outline-variant/20 flex items-center justify-between font-mono text-xs">
          <span class="text-on-surface-variant">Trend: ${t.trend || '→'}</span>
          <span class="text-primary font-bold">P${i} Active</span>
        </div>
      `;
      grid.appendChild(card);
    });

    if (actionsList) {
      actionsList.innerHTML = '';
      const actions = state.activePulse.actions || [];
      if (actions.length === 0) {
        actionsList.innerHTML = '<div class="text-outline font-mono text-xs">No active squad action items.</div>';
      } else {
        actions.forEach(a => {
          const item = document.createElement('div');
          item.className = 'p-3 rounded bg-surface-container-lowest border border-outline-variant/20 flex items-center gap-3 font-mono text-xs';
          item.innerHTML = `
            <span class="px-2 py-0.5 rounded bg-primary-container/20 text-primary font-bold">[${a.tag}]</span>
            <span class="text-on-surface font-sans">${a.description}</span>
          `;
          actionsList.appendChild(item);
        });
      }
    }
  }

  // =====================================================================
  // Trend Analytics Table View
  // =====================================================================

  function renderTrendAnalyticsView() {
    const tbody = document.getElementById('trends-table-body');
    if (!tbody || !state.metrics?.weekly) return;

    tbody.innerHTML = '';
    const weekly = state.metrics.weekly;
    const sortedWeeks = Object.keys(weekly)
      .filter(w => w >= '2026-W20')
      .sort()
      .reverse();

    sortedWeeks.forEach(w => {
      const d = weekly[w];
      const sDist = d.sentiment_distribution || { positive: 0, neutral: 0, negative: 0 };
      const totalS = (sDist.positive + sDist.neutral + sDist.negative) || 1;
      const posPct = Math.round((sDist.positive / totalS) * 100);
      const neuPct = Math.round((sDist.neutral / totalS) * 100);
      const negPct = Math.max(0, 100 - posPct - neuPct);

      const delta = d.wow_delta_pct;
      const deltaText = delta !== null && delta !== undefined ? `${delta > 0 ? '+' : ''}${delta.toFixed(1)}%` : '—';
      const deltaColor = delta > 0 ? 'text-primary font-bold' : (delta < 0 ? 'text-error font-bold' : 'text-outline');

      const tr = document.createElement('tr');
      tr.className = 'hover:bg-surface-container transition-colors';
      tr.innerHTML = `
        <td class="p-3 font-bold text-primary">${w}</td>
        <td class="p-3">${(d.total_reviews || 0).toLocaleString()}</td>
        <td class="p-3 text-tertiary-fixed-dim font-bold">${(d.average_rating || 0).toFixed(2)} ★</td>
        <td class="p-3 ${deltaColor}">${deltaText}</td>
        <td class="p-3 font-bold text-on-surface">${d.dominant_sentiment || 'Neutral'}</td>
        <td class="p-3 text-primary">${posPct}%</td>
        <td class="p-3 text-amber-300">${neuPct}%</td>
        <td class="p-3 text-error">${negPct}%</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // =====================================================================
  // Terminal Logs & Pipeline Execution (Fully Functional)
  // =====================================================================

  const btnTriggerRun = document.getElementById('btn-trigger-run');
  if (btnTriggerRun) {
    btnTriggerRun.addEventListener('click', async () => {
      btnTriggerRun.disabled = true;
      btnTriggerRun.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin">sync</span><span>Starting Pipeline...</span>';

      try {
        const res = await fetch('/api/pipeline/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ week: state.activeWeek, dry_run: false, scrape_only: false }),
        });
        await res.json();
        pollPipeline();
      } catch (e) {
        console.error(e);
      } finally {
        setTimeout(() => {
          btnTriggerRun.disabled = false;
          btnTriggerRun.innerHTML = '<span class="material-symbols-outlined text-[16px]">play_arrow</span><span>Run Pipeline Now</span>';
        }, 1500);
      }
    });
  }

  async function checkPipelineStatus() {
    try {
      const res = await fetch('/api/pipeline/status');
      const data = await res.json();
      updateTerminalLogs(data);
    } catch (e) {
      console.error(e);
    }
  }

  function updateTerminalLogs(data) {
    const terminal = document.getElementById('terminal-logs');
    const badge = document.getElementById('pipeline-status-badge');
    if (badge) {
      badge.textContent = `Status: ${data.status.toUpperCase()}`;
      badge.className = data.status === 'running' 
        ? 'px-2.5 py-1 rounded bg-amber-400/20 text-amber-300 font-mono text-xs font-bold animate-pulse'
        : (data.status === 'completed'
            ? 'px-2.5 py-1 rounded bg-primary-container/20 text-primary font-mono text-xs font-bold'
            : 'px-2.5 py-1 rounded bg-surface-container font-mono text-xs font-bold text-outline');
    }

    if (terminal && data.logs && data.logs.length > 0) {
      terminal.innerHTML = data.logs.map(line => `<div class="py-0.5 leading-relaxed">${line}</div>`).join('');
      terminal.scrollTop = terminal.scrollHeight;
    }
  }

  function pollPipeline() {
    if (state.pipelinePollInterval) clearInterval(state.pipelinePollInterval);
    state.pipelinePollInterval = setInterval(async () => {
      const res = await fetch('/api/pipeline/status');
      const data = await res.json();
      updateTerminalLogs(data);

      if (data.status !== 'running') {
        clearInterval(state.pipelinePollInterval);
        state.pipelinePollInterval = null;
        if (data.status === 'completed') {
          fetchPulses();
        }
      }
    }, 2000);
  }

  // Start initialization
  init();
});
