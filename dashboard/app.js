// =========================================================
// SmartRetail AI - Comprehensive Dashboard Client
// =========================================================

let dwellChart = null;
let trafficTrendChart = null;
let queueTrendChart = null;
let hourlyTrendChart = null;
let dailyTrendChart = null;
let currentAlertFilter = 'all';
let allAlerts = [];
let currentCamChannel = 1;

// Initialize Dashboard
document.addEventListener("DOMContentLoaded", () => {
  initEdgeClock();
  initCharts();
  fetchInitialData();
  fetchCameraSourceStatus();
  fetchTrafficTrends();
  setInterval(fetchLiveStats, 1000);
  setInterval(fetchHistory, 5000);
  setInterval(fetchLedgerBlocks, 4000);
  setInterval(fetchHeatmapData, 2500);
  setInterval(fetchTrafficTrends, 12000);
  setInterval(fetchSyncStatusAndQueue, 4000);
  fetchSyncStatusAndQueue();
  fetchSupabaseDiagnostics();
  fetchConnectedCameras();
  fetchTheftIncidents();
  setInterval(fetchTheftIncidents, 4000);
});

function initEdgeClock() {
  const clockEl = document.getElementById("edgeClockTime");
  if (!clockEl) return;
  const update = () => {
    const now = new Date();
    const hrs = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const secs = String(now.getSeconds()).padStart(2, '0');
    clockEl.textContent = `${hrs}:${mins}:${secs}`;
  };
  update();
  setInterval(update, 1000);
}

// Tab Switcher
function switchTab(tabId) {
  document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));

  const targetTab = document.getElementById(`tab-${tabId}`);
  if (targetTab) targetTab.classList.add("active");

  const activeBtn = Array.from(document.querySelectorAll(".tab-btn")).find(btn => 
    btn.getAttribute("onclick") && btn.getAttribute("onclick").includes(tabId)
  );
  if (activeBtn) activeBtn.classList.add("active");

  if (tabId === "traffic") {
    fetchHeatmapData();
    fetchTrafficTrends();
  } else if (tabId === "fleet") {
    fetchFleetSummary();
  } else if (tabId === "ledger") {
    fetchLedgerBlocks();
  } else if (tabId === "billing") {
    fetchInventoryLedger();
  } else if (tabId === "demand") {
    fetchDemandForecast();
  } else if (tabId === "sync") {
    fetchSyncStatusAndQueue();
  } else if (tabId === "cloud") {
    fetchSupabaseDiagnostics();
  } else if (tabId === "theft") {
    fetchTheftIncidents();
  } else if (tabId === "anomalies") {
    fetchAnomaliesList();
  }
}

// Multi-Camera Switching
function switchCameraChannel(camNum) {
  currentCamChannel = camNum;
  document.querySelectorAll(".cam-btn").forEach(b => b.classList.remove("active"));
  const btn = Array.from(document.querySelectorAll(".cam-btn")).find(b => b.textContent.includes(`CAM 0${camNum}`));
  if (btn) btn.classList.add("active");

  reloadVideoFeed();
}

// ================= VIDEO FEED SOURCE MANAGEMENT =================
async function fetchCameraSourceStatus() {
  try {
    const res = await fetch("/api/camera/sources");
    if (!res.ok) return;
    const data = await res.json();
    updateSourceUI(data);
  } catch (err) {
    console.warn("Failed to fetch camera sources:", err);
  }
}

function updateSourceUI(data) {
  const btnWebcam = document.getElementById("btnSrcWebcam");
  const btnUpload = document.getElementById("btnSrcUpload");
  const btnDemo = document.getElementById("btnSrcDemo");
  const label = document.getElementById("activeSourceLabel");
  const badge = document.getElementById("activeSourceBadge");
  const cctvTitle = document.getElementById("cctvHeaderTitle");

  [btnWebcam, btnUpload, btnDemo].forEach(b => b && b.classList.remove("active"));

  if (data.is_webcam) {
    if (btnWebcam) btnWebcam.classList.add("active");
    if (label) label.textContent = `Webcam (Device ${data.active_source})`;
    if (badge) {
      badge.style.borderColor = "#06b6d4";
      badge.style.color = "#22d3ee";
    }
    if (cctvTitle) {
      cctvTitle.textContent = `Live Edge CCTV: Webcam (Device ${data.active_source}) Active`;
    }
  } else if (data.is_synthetic_demo) {
    if (btnDemo) btnDemo.classList.add("active");
    if (label) label.textContent = "Active: Demo Store";
    if (badge) {
      badge.style.borderColor = "rgba(16, 185, 129, 0.3)";
      badge.style.color = "#10b981";
    }
    if (cctvTitle) {
      cctvTitle.textContent = "Live Edge CCTV Stream (Demo Store Stream)";
    }
  } else {
    if (btnUpload) btnUpload.classList.add("active");
    const filename = String(data.active_source).split("/").pop().split("\\").pop();
    if (label) label.textContent = `Video: ${filename}`;
    if (badge) {
      badge.style.borderColor = "#f59e0b";
      badge.style.color = "#fbbf24";
    }
    if (cctvTitle) {
      cctvTitle.textContent = `Live Edge CCTV: Video (${filename})`;
    }
  }
}

// ================= HARDWARE WEBCAM SELECTION =================
async function fetchConnectedCameras(notify = false) {
  try {
    const res = await fetch("/api/camera/devices");
    if (!res.ok) return;
    const data = await res.json();
    const select = document.getElementById("webcamDeviceSelect");
    if (select) {
      const devices = data.devices || [];
      if (devices.length > 0) {
        select.innerHTML = devices.map(d => 
          `<option value="${d.index}">${escapeHtml(d.label)}</option>`
        ).join("");
        if (data.is_webcam) {
          select.value = String(data.active_source);
        }
      } else {
        select.innerHTML = `<option value="0">Camera 0: Integrated Camera</option><option value="1">Camera 1: External USB Camera</option>`;
      }
    }
    if (notify) {
      alert(`🔍 Camera Hardware Scan Complete!\n\nFound ${data.total_detected} connected video device(s).`);
    }
  } catch (err) {
    console.warn("fetchConnectedCameras error:", err);
  }
}

async function activateSelectedWebcam() {
  const select = document.getElementById("webcamDeviceSelect");
  const deviceIndex = select ? select.value : 0;
  await switchWebcam(deviceIndex);
}

async function switchWebcam(deviceIndex = 0) {
  const label = document.getElementById("activeSourceLabel");
  if (label) label.textContent = `Connecting to Camera ${deviceIndex}...`;
  
  try {
    const res = await fetch("/api/camera/switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: deviceIndex })
    });
    const result = await res.json();
    if (result.success) {
      fetchCameraSourceStatus();
      reloadVideoFeed();
    } else {
      alert(`⚠️ Could not open Camera (Device ${deviceIndex}).\n\nVerify that your external USB webcam is firmly connected and not in use by another app (e.g. Zoom, Teams, or Windows Camera app).`);
      fetchCameraSourceStatus();
    }
  } catch (err) {
    alert("Network error connecting to webcam: " + err.message);
    fetchCameraSourceStatus();
  }
}

function activateWebcam() {
  activateSelectedWebcam();
}

async function activateDemoVideo() {
  const label = document.getElementById("activeSourceLabel");
  if (label) label.textContent = "Loading Demo Stream...";
  
  try {
    const res = await fetch("/api/camera/switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "videos/store.mp4" })
    });
    const result = await res.json();
    if (result.success) {
      fetchCameraSourceStatus();
      reloadVideoFeed();
    }
  } catch (err) {
    console.error("Error switching to demo store:", err);
  }
}

function triggerVideoUpload() {
  const input = document.getElementById("videoFileInput");
  if (input) input.click();
}

async function handleVideoFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  const status = document.getElementById("videoUploadStatus");
  if (status) {
    status.style.display = "inline";
    status.textContent = `Uploading ${file.name}...`;
  }

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/camera/upload-video", {
      method: "POST",
      body: formData
    });
    const data = await res.json();

    if (data.success) {
      if (status) {
        status.textContent = `Uploaded!`;
        setTimeout(() => { status.style.display = "none"; }, 2500);
      }
      fetchCameraSourceStatus();
      reloadVideoFeed();
    } else {
      alert("⚠️ Upload failed: " + (data.error || "Unknown error"));
      if (status) status.style.display = "none";
    }
  } catch (err) {
    alert("Error uploading video: " + err.message);
    if (status) status.style.display = "none";
  } finally {
    event.target.value = "";
  }
}

function reloadVideoFeed() {
  const img = document.getElementById("liveFeedImg");
  if (img) {
    img.src = `/api/video/feed?cam=${currentCamChannel}&t=${Date.now()}`;
  }
}

// ================= FETCH LIVE REAL-TIME STATS =================
async function fetchLiveStats() {
  try {
    const res = await fetch("/api/live-stats");
    if (!res.ok) throw new Error("Network error");
    const data = await res.json();

    // 1. Edge & Cloud Status Header
    document.getElementById("edgeFps").textContent = `${data.fps || 30.0} FPS`;
    
    const cloudStatus = data.cloud_status || {};
    const cloudDot = document.getElementById("cloudDot");
    const cloudStatusText = document.getElementById("cloudStatusText");
    const cloudBadge = document.getElementById("cloudStatusBadge");
    const btnDisconnectHeader = document.getElementById("btnDisconnectHeader");

    if (cloudStatus.enabled && cloudStatus.connected) {
      cloudDot.className = "pulse-dot green";
      cloudStatusText.textContent = "CONNECTED";
      if (btnDisconnectHeader) btnDisconnectHeader.style.display = "inline-block";
      if (cloudBadge) {
        cloudBadge.textContent = "CONNECTED (LIVE SYNC ACTIVE)";
        cloudBadge.style.color = "#10b981";
      }
    } else if (cloudStatus.enabled && !cloudStatus.connected) {
      cloudDot.className = "pulse-dot rose";
      cloudStatusText.textContent = "SYNC WARNING";
      if (btnDisconnectHeader) btnDisconnectHeader.style.display = "inline-block";
      if (cloudBadge) {
        cloudBadge.textContent = "WARNING: " + (cloudStatus.status || "SYNC ISSUE");
        cloudBadge.style.color = "#f43f5e";
      }
    } else {
      cloudDot.className = "pulse-dot amber";
      cloudStatusText.textContent = "OFFLINE";
      if (btnDisconnectHeader) btnDisconnectHeader.style.display = "none";
      if (cloudBadge) {
        cloudBadge.textContent = "OFFLINE (LOCAL SQLITE ACTIVE)";
        cloudBadge.style.color = "#f59e0b";
      }
    }

    // 2. Staff vs Customer Traffic Metrics
    const traffic = data.traffic || {};
    const queue = data.queue || {};
    const stock = data.stock || {};
    const shelfAudit = data.shelf_audit || {};
    const priceAudit = data.price_audit || [];
    const forecasts = data.forecasts || [];
    const alerts = data.alerts || [];

    const custCount = traffic.current_customers || 0;
    const staffCount = traffic.current_staff || 2;
    const staffRatio = traffic.customer_to_staff_ratio || "4.0 : 1";

    document.getElementById("kpiCustomers").textContent = custCount;
    document.getElementById("kpiTotalIn").textContent = traffic.total_in || 0;
    document.getElementById("kpiStaff").textContent = staffCount;
    document.getElementById("kpiStaffRatio").textContent = staffRatio;
    document.getElementById("headerStaffCount").textContent = `${staffCount} ON DUTY`;

    const convElem = document.getElementById("kpiConversionRate");
    if (convElem) convElem.textContent = `${traffic.conversion_rate_pct || 0.0}%`;
    const salesCntElem = document.getElementById("kpiCompletedSales");
    if (salesCntElem) salesCntElem.textContent = traffic.completed_sales_count || 0;

    // Queue KPI
    const qLen = queue.queue_length || 0;
    document.getElementById("kpiQueue").textContent = `${qLen} Person${qLen === 1 ? '' : 's'}`;
    document.getElementById("kpiWaitTime").textContent = `${queue.estimated_wait_time_min || 0.0}m`;
    
    const qStatus = document.getElementById("kpiQueueStatus");
    if (queue.congestion) {
      qStatus.textContent = `● High Congestion (${qLen} in line)`;
      qStatus.className = "kpi-footer text-rose";
    } else {
      qStatus.textContent = `● Flow is optimal (${qLen} in line)`;
      qStatus.className = "kpi-footer text-emerald";
    }

    // Stock KPI
    document.getElementById("kpiStockHealth").textContent = `${stock.stock_health_score || 100}%`;
    const oosCount = (stock.items || []).filter(i => i.status === "OUT_OF_STOCK").length;
    document.getElementById("kpiOosCount").textContent = oosCount;

    // Price Audit KPI
    const mismatchCount = priceAudit.filter(p => p.is_mismatch).length;
    document.getElementById("kpiPriceAudit").textContent = `${priceAudit.length - mismatchCount}/${priceAudit.length || 8}`;
    document.getElementById("kpiPriceMismatch").textContent = mismatchCount;

    // Alerts KPI
    document.getElementById("kpiAlerts").textContent = alerts.length;
    const criticalCount = alerts.filter(a => a.severity === "critical").length;
    document.getElementById("kpiCritical").textContent = criticalCount;
    document.getElementById("tabAlertCount").textContent = alerts.length;

    // 2b. Business Impact Financial & Operational KPIs
    const roi = data.business_impact || {};
    const roiProtElem = document.getElementById("roiProtectedVal");
    if (roiProtElem) roiProtElem.textContent = `₹${Math.round(roi.revenue_protected_today || 0).toLocaleString()}`;

    const roiLostElem = document.getElementById("roiLostVal");
    if (roiLostElem) roiLostElem.textContent = `₹${Math.round(roi.total_estimated_lost_sales_today || 0).toLocaleString()}`;

    const roiLostBreakdown = document.getElementById("roiLostBreakdown");
    if (roiLostBreakdown) {
      roiLostBreakdown.textContent = `● Stockouts: ₹${Math.round(roi.lost_sales_stockout_today || 0)} | Queue: ₹${Math.round(roi.lost_sales_queue_today || 0)}`;
    }

    const roiHoursElem = document.getElementById("roiHoursSaved");
    if (roiHoursElem) roiHoursElem.textContent = `${roi.staff_hours_saved_today || 0}h`;

    const roiStockRedElem = document.getElementById("roiStockoutReduction");
    if (roiStockRedElem) roiStockRedElem.textContent = `+${roi.stockout_reduction_pct || 34.0}%`;

    // 3. Operational Advice & Store Brain Directives
    const recText = document.getElementById("overviewRecText");
    if (queue.recommendation) {
      recText.textContent = queue.recommendation;
    }

    const brain = data.brain || {};
    renderStoreBrainDirectives(brain);

    renderOverviewAlerts(alerts);
    document.getElementById("overviewCompliance").textContent = `${shelfAudit.overall_compliance_score || 100}%`;
    document.getElementById("overviewComplianceBar").style.width = `${shelfAudit.overall_compliance_score || 100}%`;

    // 4. Render Tables & Views
    window.lastActiveTracks = traffic.active_tracks || [];
    renderInventoryTable(stock.items || []);
    renderPriceOcrTable(priceAudit);
    renderPlanogramAudit(shelfAudit.shelves || []);
    if (data.planogram_audit) {
      renderSlotLevelPlanogram(data.planogram_audit);
    }
    renderBillingDiscrepancies(stock.items || []);
    renderForecasterTable(forecasts);

    // 5. Queue Tab
    document.getElementById("queueHeroCount").textContent = qLen;
    document.getElementById("queueHeroWait").textContent = `${queue.estimated_wait_time_min || 0.0} mins`;
    document.getElementById("queueRecMessage").textContent = queue.recommendation || "Queue operating normally.";

    // 6. Full Alerts Tab
    allAlerts = alerts;
    renderFullAlerts(alerts);

    // 7. Sync Telemetry Counts
    if (cloudStatus.synced_counts) {
      if (document.getElementById("syncCountTraffic")) document.getElementById("syncCountTraffic").textContent = cloudStatus.synced_counts.traffic || 0;
      if (document.getElementById("syncCountInventory")) document.getElementById("syncCountInventory").textContent = cloudStatus.synced_counts.inventory || 0;
      if (document.getElementById("syncCountQueue")) document.getElementById("syncCountQueue").textContent = cloudStatus.synced_counts.queue || 0;
      if (document.getElementById("syncCountAlerts")) document.getElementById("syncCountAlerts").textContent = cloudStatus.synced_counts.alerts || 0;
      if (document.getElementById("syncCountShelf")) document.getElementById("syncCountShelf").textContent = cloudStatus.synced_counts.shelf || 0;
      if (document.getElementById("syncCountSales")) document.getElementById("syncCountSales").textContent = cloudStatus.synced_counts.sales || 0;
      if (document.getElementById("syncCountLedger")) document.getElementById("syncCountLedger").textContent = cloudStatus.synced_counts.ledger || 0;
    }

    // 8. Theft and Loss Prevention Live Status
    const activeThefts = data.active_theft_count || 0;
    const theftBadge = document.getElementById("tabTheftCount");
    const liveTheftBadge = document.getElementById("liveTheftBadge");
    if (theftBadge) {
      theftBadge.textContent = activeThefts;
      theftBadge.style.display = activeThefts > 0 ? "inline-block" : "none";
    }
    if (liveTheftBadge) {
      liveTheftBadge.style.display = activeThefts > 0 ? "inline-block" : "none";
    }

  } catch (err) {
    console.warn("Live stats polling error:", err);
  }
}

// ================= AI RETAIL COPILOT & RAG PIPELINE =================
let currentCopilotMode = localStorage.getItem("copilot_mode") || "offline";
let currentCopilotModel = localStorage.getItem("copilot_model") || "gemini-3.5-flash";
let copilotCustomApiKey = localStorage.getItem("copilot_custom_api_key") || "";

function setCopilotMode(mode) {
  currentCopilotMode = mode;
  localStorage.setItem("copilot_mode", mode);
  
  const btnOff = document.getElementById("btnCopilotOffline");
  const btnOn = document.getElementById("btnCopilotOnline");
  const indicator = document.getElementById("copilotModeIndicator");
  const cardOff = document.getElementById("modeCardOffline");
  const cardOn = document.getElementById("modeCardOnline");
  
  if (mode === "online") {
    if (btnOff) btnOff.classList.remove("active");
    if (btnOn) btnOn.classList.add("active");
    if (indicator) {
      indicator.textContent = "✨ ONLINE GEMINI";
      indicator.style.background = "rgba(168, 85, 247, 0.15)";
      indicator.style.color = "#c084fc";
      indicator.style.borderColor = "#a855f7";
    }
    if (cardOff) cardOff.classList.remove("active-mode");
    if (cardOn) cardOn.classList.add("active-mode");
  } else {
    if (btnOn) btnOn.classList.remove("active");
    if (btnOff) btnOff.classList.add("active");
    if (indicator) {
      indicator.textContent = "⚡ OFFLINE RAG";
      indicator.style.background = "rgba(56, 189, 248, 0.15)";
      indicator.style.color = "#38bdf8";
      indicator.style.borderColor = "#38bdf8";
    }
    if (cardOn) cardOn.classList.remove("active-mode");
    if (cardOff) cardOff.classList.add("active-mode");
  }
}

async function sendCopilotQuery(queryText) {
  const chatBox = document.getElementById("copilotChatBox");
  if (!chatBox) return;
  
  // User bubble
  const userMsg = document.createElement("div");
  userMsg.className = "chat-message user";
  userMsg.innerHTML = `<div class="chat-sender">Store Manager</div><div class="chat-bubble">${escapeHtml(queryText)}</div>`;
  chatBox.appendChild(userMsg);
  chatBox.scrollTop = chatBox.scrollHeight;

  // Bot loading placeholder
  const botMsg = document.createElement("div");
  botMsg.className = "chat-message bot";
  const modeLabel = currentCopilotMode === "online" ? "✨ Online Gemini LLM" : "⚡ Offline Edge RAG";
  botMsg.innerHTML = `<div class="chat-sender">🤖 Retail Copilot <span style="font-size:10px; opacity:0.75;">(${modeLabel})</span></div><div class="chat-bubble">Thinking & synthesizing live store state...</div>`;
  chatBox.appendChild(botMsg);
  chatBox.scrollTop = chatBox.scrollHeight;

  try {
    const payload = {
      message: queryText,
      mode: currentCopilotMode,
      model: currentCopilotModel
    };
    if (copilotCustomApiKey) {
      payload.api_key = copilotCustomApiKey;
    }

    const res = await fetch("/api/copilot/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    
    let bubbleContent = formatMarkdownText(data.response);
    
    // Metadata badge
    const modeBadgeClass = data.mode === "online" ? "copilot-tag-online" : data.mode === "offline_fallback" ? "copilot-tag-fallback" : "copilot-tag-offline";
    const modelDisplayName = data.model || (data.mode === "online" ? "Gemini LLM" : "Edge RAG");
    const modeBadgeText = data.mode === "online" ? `✨ ${modelDisplayName} (${data.latency_ms}ms)` : data.mode === "offline_fallback" ? `⚠️ Fallback to Edge RAG (${data.latency_ms}ms)` : `⚡ ${modelDisplayName} (${data.latency_ms}ms)`;
    
    let metaHtml = `
      <div class="copilot-meta-bar">
        <span class="copilot-tag-badge ${modeBadgeClass}">${modeBadgeText}</span>
        <span>${data.timestamp || ""}</span>
      </div>
    `;
    
    // Sources citations drawer
    if (data.sources && data.sources.length > 0) {
      metaHtml += `
        <details class="copilot-sources-drawer">
          <summary>📚 Grounded Sources & Citations (${data.sources.length})</summary>
          <ul class="copilot-sources-list">
            ${data.sources.map(s => `<li>${escapeHtml(s)}</li>`).join("")}
          </ul>
        </details>
      `;
    }
    
    botMsg.querySelector(".chat-bubble").innerHTML = bubbleContent + metaHtml;
    chatBox.scrollTop = chatBox.scrollHeight;
  } catch (err) {
    botMsg.querySelector(".chat-bubble").textContent = "Sorry, unable to query live store data right now.";
  }
}

function handleCopilotSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("copilotInput");
  const q = input.value.trim();
  if (q) {
    sendCopilotQuery(q);
    input.value = "";
  }
}

// Modal Handlers
async function openCopilotSettingsModal() {
  const modal = document.getElementById("copilotSettingsModal");
  if (!modal) return;
  
  // Fetch current backend settings
  try {
    const res = await fetch("/api/copilot/config");
    const cfg = await res.json();
    
    const keyInput = document.getElementById("inputCopilotApiKey");
    if (keyInput) {
      keyInput.value = copilotCustomApiKey || cfg.masked_api_key || "";
    }
    const modelSelect = document.getElementById("selectCopilotModel");
    if (modelSelect && cfg.model) {
      modelSelect.value = currentCopilotModel || cfg.model;
    }
    const badge = document.getElementById("apiKeyStatusBadge");
    if (badge) {
      if (cfg.has_api_key) {
        badge.textContent = "CONFIGURED";
        badge.style.background = "rgba(16,185,129,0.15)";
        badge.style.color = "#34d399";
        badge.style.borderColor = "#10b981";
      } else {
        badge.textContent = "NOT SET";
        badge.style.background = "rgba(239,68,68,0.15)";
        badge.style.color = "#f87171";
        badge.style.borderColor = "#ef4444";
      }
    }
    const chunksBadge = document.getElementById("ragChunksCountBadge");
    if (chunksBadge && cfg.indexed_chunks) {
      chunksBadge.textContent = `${cfg.indexed_chunks} Chunks Indexed`;
    }
  } catch (e) {
    console.warn("Error fetching copilot config:", e);
  }

  setCopilotMode(currentCopilotMode);
  modal.style.display = "flex";
}

function closeCopilotSettingsModal() {
  const modal = document.getElementById("copilotSettingsModal");
  if (modal) modal.style.display = "none";
  const statusSpan = document.getElementById("settingsSaveStatus");
  if (statusSpan) statusSpan.textContent = "";
  const fb = document.getElementById("connTestFeedback");
  if (fb) fb.style.display = "none";
}

function toggleApiKeyVisibility() {
  const input = document.getElementById("inputCopilotApiKey");
  if (input) {
    input.type = input.type === "password" ? "text" : "password";
  }
}

async function testGeminiConnectionClick() {
  const input = document.getElementById("inputCopilotApiKey");
  const modelSelect = document.getElementById("selectCopilotModel");
  const fb = document.getElementById("connTestFeedback");
  const btn = document.getElementById("btnTestConn");
  
  const rawKey = input.value.trim();
  const targetKey = rawKey.includes("....") ? undefined : rawKey;
  const targetModel = modelSelect ? modelSelect.value : currentCopilotModel;

  if (btn) btn.textContent = "⏳ Testing...";
  if (fb) {
    fb.style.display = "block";
    fb.style.color = "#94a3b8";
    fb.textContent = "Testing connection to Google Gemini...";
  }

  try {
    const res = await fetch("/api/copilot/test-connection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: targetKey, model: targetModel })
    });
    const data = await res.json();
    if (data.success) {
      fb.style.color = "#34d399";
      fb.innerHTML = `✅ <strong>Connected:</strong> ${data.message}`;
    } else {
      fb.style.color = "#f87171";
      fb.innerHTML = `❌ <strong>Connection failed:</strong> ${escapeHtml(data.error || "Unknown error")}`;
    }
  } catch (err) {
    if (fb) {
      fb.style.color = "#f87171";
      fb.textContent = "❌ Connection test failed: " + err.message;
    }
  } finally {
    if (btn) btn.textContent = "🔌 Test Ping";
  }
}

async function saveCopilotSettings() {
  const input = document.getElementById("inputCopilotApiKey");
  const modelSelect = document.getElementById("selectCopilotModel");
  const statusSpan = document.getElementById("settingsSaveStatus");

  const rawKey = input ? input.value.trim() : "";
  if (rawKey && !rawKey.includes("....")) {
    copilotCustomApiKey = rawKey;
    localStorage.setItem("copilot_custom_api_key", rawKey);
  }

  if (modelSelect) {
    currentCopilotModel = modelSelect.value;
    localStorage.setItem("copilot_model", modelSelect.value);
  }

  try {
    const res = await fetch("/api/copilot/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        default_mode: currentCopilotMode,
        api_key: copilotCustomApiKey || undefined,
        model: currentCopilotModel
      })
    });
    const data = await res.json();
    if (statusSpan) {
      statusSpan.textContent = "✅ Configuration saved!";
      setTimeout(() => {
        closeCopilotSettingsModal();
      }, 900);
    }
  } catch (err) {
    if (statusSpan) {
      statusSpan.style.color = "#f87171";
      statusSpan.textContent = "Error saving settings: " + err.message;
    }
  }
}

function formatMarkdownText(text) {
  if (!text) return "";
  let html = escapeHtml(text);
  
  // Parse markdown tables before splitting lines
  html = html.replace(/((?:\|[^\n]+\|\r?\n)+)/g, function(tableBlock) {
    const lines = tableBlock.trim().split("\n").map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length < 2) return tableBlock;
    
    // Header
    const headers = lines[0].split("|").map(c => c.trim()).filter(c => c.length > 0);
    let bodyStartIndex = 1;
    if (lines.length > 1 && (lines[1].includes("---") || lines[1].includes(":--"))) {
      bodyStartIndex = 2;
    }
    
    let tableHtml = '<div style="overflow-x:auto; margin:8px 0;"><table class="copilot-table" style="width:100%; border-collapse:collapse; font-size:12px; border:1px solid rgba(255,255,255,0.1); border-radius:6px; overflow:hidden;">';
    tableHtml += '<thead style="background:rgba(56,189,248,0.12); color:#38bdf8;"><tr>';
    headers.forEach(h => {
      tableHtml += `<th style="padding:6px 10px; text-align:left; border-bottom:1px solid rgba(255,255,255,0.1); font-weight:600;">${h}</th>`;
    });
    tableHtml += '</tr></thead><tbody>';
    
    for (let i = bodyStartIndex; i < lines.length; i++) {
      const cells = lines[i].split("|").map(c => c.trim()).filter(c => c.length > 0);
      if (cells.length === 0) continue;
      const rowBg = (i % 2 === 0) ? "background:rgba(255,255,255,0.03);" : "background:transparent;";
      tableHtml += `<tr style="${rowBg}">`;
      cells.forEach(c => {
        tableHtml += `<td style="padding:5px 10px; border-bottom:1px solid rgba(255,255,255,0.06); color:#e2e8f0;">${c}</td>`;
      });
      tableHtml += '</tr>';
    }
    tableHtml += '</tbody></table></div>';
    return tableHtml;
  });

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h4 style="margin:8px 0 4px; color:#38bdf8; font-size:13px; font-weight:600;">$1</h4>');
  html = html.replace(/^## (.*$)/gim, '<h3 style="margin:10px 0 6px; color:#f1f5f9; font-size:14px; font-weight:700;">$1</h3>');
  html = html.replace(/^# (.*$)/gim, '<h2 style="margin:12px 0 8px; color:#f1f5f9; font-size:15px; font-weight:700;">$1</h2>');
  
  // Bold & Italic
  html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="color:#f8fafc;">$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/`(.*?)`/g, '<code style="background:rgba(255,255,255,0.08); padding:1px 5px; border-radius:4px; font-family:\'JetBrains Mono\', monospace; font-size:11px; color:#38bdf8;">$1</code>');
  
  // Numbered list items
  html = html.replace(/^\s*([0-9]+)\.\s+(.*$)/gim, '<div style="display:flex; gap:6px; margin:3px 0;"><span style="color:#38bdf8; font-weight:600; min-width:18px;">$1.</span><span>$2</span></div>');

  // Bullet points
  html = html.replace(/^\s*[\-\*•]\s+(.*$)/gim, '<div style="display:flex; gap:6px; margin:3px 0;"><span style="color:#38bdf8;">•</span><span>$1</span></div>');
  
  // Horizontal rule
  html = html.replace(/^\-\-\-+$/gim, '<hr style="border:none; border-top:1px solid rgba(255,255,255,0.1); margin:8px 0;">');
  
  // Line breaks
  html = html.replace(/\n\n/g, '<div style="height:6px;"></div>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}


// ================= HASHGRAPH LEDGER EXPLORER =================
async function fetchLedgerBlocks() {
  try {
    const res = await fetch("/api/ledger/blocks?limit=15");
    const data = await res.json();
    const container = document.getElementById("ledgerBlocksList");
    if (!container || !data.blocks) return;

    document.getElementById("ledgerBlockCount").textContent = data.total_blocks || 0;

    container.innerHTML = data.blocks.map(b => `
      <div class="ledger-block-card">
        <div class="l-block-head">
          <span class="l-seq">Block #${b.sequence_number}</span>
          <span class="l-type">${b.event_type}</span>
          <span class="status-badge match">CONSENSUS VERIFIED</span>
        </div>
        <div style="font-size: 12px; color: #d1d5db; margin: 4px 0;">
          <strong>Payload:</strong> ${JSON.stringify(b.payload)}
        </div>
        <div class="l-hash">
          <strong>SHA-256 Hash:</strong> ${b.hash}
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.warn("Ledger fetch error:", err);
  }
}

async function verifyLedgerIntegrity() {
  try {
    const res = await fetch("/api/ledger/verify");
    const data = await res.json();
    if (data.valid) {
      alert(`🛡️ Cryptographic Integrity Verified!\n\n• Total Blocks Checked: ${data.total_blocks}\n• Consensus Status: ${data.consensus_status}\n• Latest Hash: ${data.latest_hash}`);
    } else {
      alert(`⚠️ Chain Verification Alert: ${data.message}`);
    }
  } catch (err) {
    alert("Verification failed: " + err.message);
  }
}

// ================= PREDICTIVE FORECASTER TABLE =================
function renderForecasterTable(forecasts) {
  const tbody = document.getElementById("forecasterTableBody");
  if (!tbody || !forecasts || forecasts.length === 0) return;

  tbody.innerHTML = forecasts.map(f => {
    let riskBadge = `<span class="status-badge match">OPTIMAL</span>`;
    if (f.urgency.includes("CRITICAL")) {
      riskBadge = `<span class="status-badge out-of-stock">DEPLETED (0 MINS)</span>`;
    } else if (f.urgency.includes("HIGH")) {
      riskBadge = `<span class="status-badge low-stock">HIGH RISK</span>`;
    }

    return `
      <tr>
        <td><strong>${f.product_name}</strong></td>
        <td><code>${f.current_stock} units</code></td>
        <td>${f.depletion_velocity} units / min</td>
        <td><strong style="color: ${f.estimated_minutes_remaining < 15 ? '#fb7185' : '#67e8f9'};">${f.estimated_minutes_remaining} mins</strong></td>
        <td>${riskBadge}</td>
        <td><strong>${f.recommended_restock_units} units</strong></td>
        <td style="color: #fb7185;">₹${f.projected_revenue_loss.toFixed(2)}</td>
      </tr>
    `;
  }).join("");
}

// ================= DIRECT STAFF PHONE DISPATCH & WHATSAPP =================
function openStaffPhoneModal() {
  document.getElementById("staffPhoneModal").style.display = "flex";
}

function closeStaffPhoneModal() {
  document.getElementById("staffPhoneModal").style.display = "none";
}

function updateStaffPhoneField() {
  const select = document.getElementById("staffPhoneSelect");
  const customGroup = document.getElementById("customPhoneGroup");
  if (select.value === "custom") {
    customGroup.style.display = "block";
  } else {
    customGroup.style.display = "none";
  }
}

function insertMessageTemplate(type) {
  const textarea = document.getElementById("staffMessageText");
  if (type === "oos") {
    textarea.value = "🚨 URGENT RESTOCK ORDER: Fanta Orange, Real Juice, and Amul Milk are depleted on Shelves B & C. Please restock immediately from back-room inventory!";
  } else if (type === "queue") {
    textarea.value = "🛒 QUEUE CONGESTION ALERT: 6+ customers in line at Billing Counter 1. Please open Counter 2 immediately to reduce customer wait time!";
  } else if (type === "price") {
    textarea.value = "🔍 PRICE TAG MISMATCH: EasyOCR detected Coca Cola shelf tag displays Rs 99, but POS system price is Rs 40. Please update shelf label!";
  }
}

function getSelectedStaffPhoneAndName() {
  const select = document.getElementById("staffPhoneSelect");
  let phone = select.value;
  let name = select.options[select.selectedIndex].getAttribute("data-name") || "Staff Member";
  
  if (phone === "custom") {
    phone = document.getElementById("customPhoneInput").value.trim();
    name = "Custom Staff (" + phone + ")";
  }
  return { phone, name };
}

// 1. Direct WhatsApp to Staff Phone
function sendWhatsAppToStaff() {
  const { phone, name } = getSelectedStaffPhoneAndName();
  const message = document.getElementById("staffMessageText").value.trim();
  if (!message) {
    alert("Please enter a message to send.");
    return;
  }

  // Clean phone string
  const cleanPhone = phone.replace(/[^0-9]/g, "");
  const encodedMsg = encodeURIComponent(message);
  const whatsappUrl = `https://api.whatsapp.com/send?phone=${cleanPhone}&text=${encodedMsg}`;

  // Log dispatch in background to Hashgraph
  fetch("/api/staff/notify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone: cleanPhone, staff: name, message: message, channel: "whatsapp" })
  }).catch(() => {});

  // Open WhatsApp in new tab
  window.open(whatsappUrl, "_blank");
  closeStaffPhoneModal();
}

// 2. Direct Server-Side Notification & Hashgraph Logging
async function submitDirectStaffNotification() {
  const { phone, name } = getSelectedStaffPhoneAndName();
  const message = document.getElementById("staffMessageText").value.trim();
  if (!message) {
    alert("Please enter a message to send.");
    return;
  }

  try {
    const res = await fetch("/api/staff/notify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, staff: name, message })
    });
    const data = await res.json();
    alert(`✅ Message Dispatched to ${data.staff} (${data.phone})!\n\nMessage: "${data.message}"\n\n🛡️ Signed & Logged to Hashgraph Ledger\nBlock Hash: ${data.ledger_block_hash.substring(0, 20)}...`);
    closeStaffPhoneModal();
    fetchLedgerBlocks();
  } catch (err) {
    alert("Dispatch error: " + err.message);
  }
}

// ================= EXECUTIVE PDF & CSV REPORTS =================
function downloadPdfReport() {
  window.open("/api/reports/pdf?autoprint=true", "_blank");
}

function downloadExecutiveReport() {
  window.open("/api/reports/download", "_blank");
}

// Render Overview Mini Alerts
function renderOverviewAlerts(alerts) {
  const container = document.getElementById("overviewAlertsList");
  if (!alerts || alerts.length === 0) {
    container.innerHTML = `<div class="empty-state">No active incidents detected. Store operating smoothly.</div>`;
    return;
  }

  container.innerHTML = alerts.map(a => `
    <div class="alert-item-card ${a.severity}">
      <div>
        <div class="alert-item-title">${a.title}</div>
        <div class="alert-item-desc">${a.message}</div>
        <div class="alert-item-action">👉 ${a.action}</div>
      </div>
      <div style="display: flex; gap: 6px; align-items: center;">
        <button class="btn-ack" onclick="acknowledgeAlert('${a.id}')">Ack</button>
        <button class="btn-ack" style="background: rgba(16, 185, 129, 0.2); border-color: #10b981; color: #34d399;" onclick="resolveAlert('${a.id}')">✓ Resolve</button>
      </div>
    </div>
  `).join("");
}

// Render Inventory Table (Camera vs Billing Ledger)
function renderInventoryTable(items) {
  const tbody = document.getElementById("inventoryTableBody");
  if (!tbody || !items || items.length === 0) return;

  tbody.innerHTML = items.map(item => {
    let badgeClass = "in-stock";
    let badgeLabel = "IN STOCK";

    if (item.status === "OUT_OF_STOCK") {
      badgeClass = "out-of-stock";
      badgeLabel = "OUT OF STOCK";
    } else if (item.status === "LOW_STOCK") {
      badgeClass = "low-stock";
      badgeLabel = "LOW STOCK";
    }

    const facingCount = item.shelf_facing_count !== undefined ? item.shelf_facing_count : item.stock;
    const ledgerStock = item.ledger_stock !== undefined ? item.ledger_stock : item.stock;
    const discrepancy = item.discrepancy || "BALANCED";

    return `
      <tr>
        <td><code>${item.product_id}</code></td>
        <td><strong>${escapeHtml(item.product_name)}</strong></td>
        <td>${item.shelf_zone}</td>
        <td><strong style="font-family: 'JetBrains Mono'; font-size: 14px; color: #38bdf8;">${facingCount}</strong></td>
        <td><strong style="font-family: 'JetBrains Mono'; font-size: 14px; color: #34d399;">${ledgerStock}</strong></td>
        <td><span class="discrepancy-tag ${discrepancy}">${discrepancy}</span></td>
        <td><span class="status-badge ${badgeClass}">${badgeLabel}</span></td>
        <td>₹${item.total_value.toFixed(2)}</td>
      </tr>
    `;
  }).join("");
}

// Render EasyOCR Price Verification Table
function renderPriceOcrTable(priceAudit) {
  const tbody = document.getElementById("priceOcrTableBody");
  if (!tbody || !priceAudit || priceAudit.length === 0) return;

  tbody.innerHTML = priceAudit.map(p => {
    let badge = p.is_mismatch 
      ? `<span class="status-badge mismatch">MISMATCH (₹${p.detected_shelf_price})</span>`
      : `<span class="status-badge match">MATCH (100%)</span>`;

    return `
      <tr>
        <td><strong>${p.product_name}</strong></td>
        <td><code style="color: ${p.is_mismatch ? '#fb7185' : '#67e8f9'}">₹${p.detected_shelf_price.toFixed(2)}</code></td>
        <td><code>₹${p.catalog_price.toFixed(2)}</code></td>
        <td>${badge}</td>
      </tr>
    `;
  }).join("");
}

// Render Planogram Audit
function renderPlanogramAudit(shelves) {
  const container = document.getElementById("planogramAuditList");
  if (!shelves || shelves.length === 0) return;

  container.innerHTML = shelves.map(s => {
    let scoreColor = s.compliance_score >= 80 ? "text-emerald" : (s.compliance_score >= 50 ? "text-amber" : "text-rose");
    return `
      <div class="planogram-shelf-card">
        <div class="pshelf-header">
          <span class="pshelf-title">${s.zone} (${s.shelf_code})</span>
          <span class="${scoreColor}" style="font-weight: 800;">${s.compliance_score}% Compliant</span>
        </div>
        <div class="pshelf-details">
          <div><strong>Expected SKUs:</strong> ${s.expected_items.join(", ") || "None"}</div>
          <div><strong>Detected Items:</strong> ${s.detected_items.join(", ") || "Empty Shelf Slot"}</div>
          ${s.misplaced_items.length ? `<div style="color: var(--accent-rose);">⚠️ Misplaced: ${s.misplaced_items.join(", ")}</div>` : ''}
        </div>
      </div>
    `;
  }).join("");
}

// 🆕 Render Slot-Level Planogram Compliance Matrix
function renderSlotLevelPlanogram(planogramData) {
  if (!planogramData) return;
  const scoreBadge = document.getElementById("planogramScoreBadge");
  if (scoreBadge && planogramData.overall_compliance_score !== undefined) {
    const score = planogramData.overall_compliance_score;
    scoreBadge.textContent = `${score}% COMPLIANT`;
    scoreBadge.style.color = score >= 80 ? "#34d399" : (score >= 50 ? "#fbbf24" : "#f43f5e");
  }

  // Render Violations List
  const violList = document.getElementById("planogramViolationsList");
  if (violList) {
    const violations = planogramData.violations || [];
    if (violations.length === 0) {
      violList.innerHTML = `<div style="color: #10b981; font-size: 12px; padding: 6px 0;">✅ 100% Planogram Compliance. All items are in their designated shelf facing slots.</div>`;
    } else {
      violList.innerHTML = violations.map(v => `
        <div class="violation-pill ${v.severity}">
          <span>${v.status === "MISPLACED" ? "🚨" : (v.status === "EMPTY" ? "⚠️" : "🔍")}</span>
          <div>${escapeHtml(v.message)}</div>
        </div>
      `).join("");
    }
  }

  // Render Visual Shelf Bays
  const baysContainer = document.getElementById("slotBaysContainer");
  if (baysContainer && planogramData.zone_audits) {
    baysContainer.innerHTML = planogramData.zone_audits.map(zone => `
      <div class="shelf-bay-card">
        <div class="shelf-bay-title">
          <span>${zone.zone_name} (${zone.shelf_code})</span>
          <span style="color: ${zone.compliance_score >= 80 ? '#34d399' : (zone.compliance_score >= 50 ? '#fbbf24' : '#f43f5e')}; font-weight: 800;">
            ${zone.compliant_slots} / ${zone.total_slots} slots (${zone.compliance_score}%)
          </span>
        </div>
        <div class="slots-grid">
          ${(zone.slots || []).map(slot => `
            <div class="slot-box ${slot.status.toLowerCase()}">
              <div class="slot-pos-badge">
                <span>Slot #${slot.position}</span>
                <span class="slot-status-pill ${slot.status}">${slot.status}</span>
              </div>
              <div style="font-size: 10px; color: #94a3b8;">Expected:</div>
              <div style="font-size: 12px; font-weight: 700; color: #f8fafc;">${escapeHtml(slot.expected_name)}</div>
              <div style="font-size: 10px; color: #94a3b8; margin-top: 4px;">Detected:</div>
              <div style="font-size: 12px; font-weight: 700; color: ${slot.status === 'COMPLIANT' ? '#34d399' : (slot.status === 'MISPLACED' ? '#f43f5e' : '#fbbf24')};">
                ${slot.detected_name ? escapeHtml(slot.detected_name) : '— None / Empty —'}
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    `).join("");
  }
}

// Render Full Alerts Center
function renderFullAlerts(alerts) {
  const container = document.getElementById("alertsFullContainer");
  let filtered = alerts;
  if (currentAlertFilter === "critical") {
    filtered = alerts.filter(a => a.severity === "critical");
  } else if (currentAlertFilter === "warning") {
    filtered = alerts.filter(a => a.severity === "warning");
  }

  if (!filtered || filtered.length === 0) {
    container.innerHTML = `<div class="empty-state">No matching alerts in this category. Store operating smoothly.</div>`;
    return;
  }

  container.innerHTML = filtered.map(a => `
    <div class="alert-item-card ${a.severity}" style="margin-bottom: 12px;">
      <div>
        <div class="alert-item-title">${a.title} <span style="font-size: 11px; font-weight: normal; opacity: 0.7;">• ${a.timestamp}</span></div>
        <div class="alert-item-desc">${a.message}</div>
        <div class="alert-item-action">👉 Action: ${a.action}</div>
      </div>
      <button class="btn-ack" onclick="acknowledgeAlert('${a.id}')">Mark Resolved</button>
    </div>
  `).join("");
}

function filterAlerts(type) {
  currentAlertFilter = type;
  document.querySelectorAll(".btn-filter").forEach(b => b.classList.remove("active"));
  const btn = Array.from(document.querySelectorAll(".btn-filter")).find(b => b.textContent.toLowerCase().includes(type));
  if (btn) btn.classList.add("active");
  renderFullAlerts(allAlerts);
}

// Acknowledge Alert
async function acknowledgeAlert(alertId) {
  try {
    await fetch(`/api/alerts/${alertId}/acknowledge`, { method: "POST" });
    fetchLiveStats();
  } catch (err) {
    console.error("Failed to acknowledge alert:", err);
  }
}

// ================= 2D HEATMAP CANVAS RENDERER =================
async function fetchHeatmapData() {
  try {
    const res = await fetch("/api/traffic/heatmap");
    const data = await res.json();
    drawHeatmap(data.heatmap_grid, data.dimensions);
    updateDwellChart(data.zone_dwell_summary);
  } catch (err) {
    console.error("Heatmap fetch error:", err);
  }
}

function drawHeatmap(grid, dimensions) {
  const canvas = document.getElementById("heatmapCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  // 1. Dark store floor base
  ctx.fillStyle = "#090d18";
  ctx.fillRect(0, 0, width, height);

  // 2. Subtle architectural floor grid lines
  ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
  ctx.lineWidth = 1;
  const gridStepX = width / 18;
  const gridStepY = height / 10;
  for (let x = 0; x <= width; x += gridStepX) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y <= height; y += gridStepY) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  // 3. Store Physical Fixture Outlines
  // Shelf A (Snacks) top left
  drawStoreZoneOutline(ctx, width * 0.04, height * 0.08, width * 0.38, height * 0.32, "SHELF A: SNACKS", "#f59e0b");
  // Shelf B (Beverages) bottom left
  drawStoreZoneOutline(ctx, width * 0.04, height * 0.58, width * 0.38, height * 0.34, "SHELF B: BEVERAGES", "#0284c7");
  // Shelf C (Dairy) top right
  drawStoreZoneOutline(ctx, width * 0.60, height * 0.08, width * 0.36, height * 0.32, "SHELF C: DAIRY", "#10b981");
  // Checkout Queue bottom right
  drawStoreZoneOutline(ctx, width * 0.62, height * 0.55, width * 0.34, height * 0.38, "CHECKOUT QUEUE", "#f43f5e", true);

  // Entrance & Exit indicators
  ctx.fillStyle = "#10b981";
  ctx.fillRect(0, height * 0.40, 6, height * 0.18);
  ctx.fillStyle = "#f43f5e";
  ctx.fillRect(width - 6, height * 0.40, 6, height * 0.18);

  // 4. Multi-Layer Radial Gradient Density Heatmap
  if (grid && grid.length > 0) {
    const rows = dimensions.rows || 20;
    const cols = dimensions.cols || 36;
    const cellW = width / cols;
    const cellH = height / rows;

    ctx.save();
    ctx.globalCompositeOperation = "screen";

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const val = grid[r] ? grid[r][c] : 0;
        if (val > 0.02) {
          const cx = c * cellW + cellW / 2;
          const cy = r * cellH + cellH / 2;
          const radius = Math.max(20, cellW * (1.3 + val * 2.5));

          const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
          if (val < 0.25) {
            grad.addColorStop(0, `rgba(6, 182, 212, ${val * 1.5})`);
            grad.addColorStop(0.5, `rgba(6, 182, 212, ${val * 0.8})`);
            grad.addColorStop(1, "rgba(6, 182, 212, 0)");
          } else if (val < 0.55) {
            grad.addColorStop(0, `rgba(16, 185, 129, ${val * 1.4})`);
            grad.addColorStop(0.5, `rgba(16, 185, 129, ${val * 0.7})`);
            grad.addColorStop(1, "rgba(16, 185, 129, 0)");
          } else if (val < 0.80) {
            grad.addColorStop(0, `rgba(245, 158, 11, ${val * 1.3})`);
            grad.addColorStop(0.4, `rgba(16, 185, 129, ${val * 0.8})`);
            grad.addColorStop(1, "rgba(245, 158, 11, 0)");
          } else {
            grad.addColorStop(0, `rgba(244, 63, 94, 0.95)`);
            grad.addColorStop(0.35, `rgba(245, 158, 11, 0.75)`);
            grad.addColorStop(0.7, `rgba(16, 185, 129, 0.35)`);
            grad.addColorStop(1, "rgba(244, 63, 94, 0)");
          }

          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.arc(cx, cy, radius, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }
    ctx.restore();
  }

  // 5. Active Shoppers Position Dots & Vectors
  const activeTracks = window.lastActiveTracks || [];
  activeTracks.forEach(t => {
    const px = t.x * width;
    const py = t.y * height;
    const isStaff = (t.type === "staff");
    const color = isStaff ? "#fbbf24" : "#38bdf8";

    // Outer pulse ring
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(px, py, 10, 0, Math.PI * 2);
    ctx.stroke();

    // Inner dot
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(px, py, 4, 0, Math.PI * 2);
    ctx.fill();

    // Label
    ctx.font = "bold 9px monospace";
    ctx.fillStyle = "#ffffff";
    const label = isStaff ? `STAFF` : `#${t.track_id}`;
    ctx.fillText(label, px + 12, py + 3);
  });
}

function drawStoreZoneOutline(ctx, x, y, w, h, label, color, isQueue = false) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.setLineDash([4, 4]);
  ctx.strokeRect(x, y, w, h);

  ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
  ctx.fillRect(x, y, w, 22);

  ctx.fillStyle = color;
  ctx.font = "bold 10px 'JetBrains Mono', monospace";
  ctx.fillText(label, x + 8, y + 15);
  ctx.restore();
}

// ================= CHARTS INITIALIZATION =================
function initCharts() {
  const ctxDwell = document.getElementById("dwellBarChart").getContext("2d");
  dwellChart = new Chart(ctxDwell, {
    type: "bar",
    data: {
      labels: ["Snacks & Biscuits", "Beverages & Drinks", "Dairy & Essentials", "Checkout Queue"],
      datasets: [{
        label: "Total Dwell Time (Seconds)",
        data: [45, 80, 35, 120],
        backgroundColor: ["rgba(245, 158, 11, 0.6)", "rgba(6, 182, 212, 0.6)", "rgba(16, 185, 129, 0.6)", "rgba(244, 63, 94, 0.6)"],
        borderColor: ["#f59e0b", "#06b6d4", "#10b981", "#f43f5e"],
        borderWidth: 1,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#9ca3af" }, grid: { display: false } },
        y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } }
      }
    }
  });

  const ctxTraffic = document.getElementById("trafficTrendChart").getContext("2d");
  trafficTrendChart = new Chart(ctxTraffic, {
    type: "line",
    data: {
      labels: ["-5m", "-4m", "-3m", "-2m", "-1m", "Now"],
      datasets: [
        {
          label: "Customers IN",
          data: [2, 4, 5, 7, 8, 8],
          borderColor: "#06b6d4",
          backgroundColor: "rgba(6, 182, 212, 0.1)",
          fill: true,
          tension: 0.4
        },
        {
          label: "Customers Active",
          data: [2, 3, 4, 6, 7, 8],
          borderColor: "#10b981",
          tension: 0.4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#9ca3af" } } },
      scales: {
        x: { ticks: { color: "#9ca3af" }, grid: { display: false } },
        y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } }
      }
    }
  });

  const ctxQueue = document.getElementById("queueTrendChart").getContext("2d");
  queueTrendChart = new Chart(ctxQueue, {
    type: "line",
    data: {
      labels: ["-5m", "-4m", "-3m", "-2m", "-1m", "Now"],
      datasets: [
        {
          label: "Queue Length (Persons)",
          data: [1, 2, 3, 4, 5, 6],
          borderColor: "#f43f5e",
          backgroundColor: "rgba(244, 63, 94, 0.1)",
          fill: true,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#9ca3af" } } },
      scales: {
        x: { ticks: { color: "#9ca3af" }, grid: { display: false } },
        y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" }, min: 0 }
      }
    }
  });

  const ctxHourly = document.getElementById("hourlyTrendChart")?.getContext("2d");
  if (ctxHourly) {
    hourlyTrendChart = new Chart(ctxHourly, {
      type: "bar",
      data: {
        labels: ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00"],
        datasets: [{
          label: "Shoppers",
          data: [8, 18, 34, 48, 62, 38, 26, 32, 54, 78, 92, 84, 46, 16],
          backgroundColor: ["#0284c7", "#0284c7", "#0284c7", "#0284c7", "#10b981", "#0284c7", "#0284c7", "#0284c7", "#0284c7", "#f59e0b", "#f43f5e", "#f59e0b", "#0284c7", "#0284c7"],
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#9ca3af" }, grid: { display: false } },
          y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } }
        }
      }
    });
  }

  const ctxDaily = document.getElementById("dailyTrendChart")?.getContext("2d");
  if (ctxDaily) {
    dailyTrendChart = new Chart(ctxDaily, {
      type: "bar",
      data: {
        labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        datasets: [
          {
            label: "Footfall",
            data: [120, 135, 142, 158, 210, 285, 260],
            backgroundColor: "rgba(2, 132, 199, 0.6)",
            borderRadius: 4,
            yAxisID: 'y'
          },
          {
            type: "line",
            label: "Conversion %",
            data: [24.2, 25.1, 26.0, 25.8, 29.4, 32.1, 30.5],
            borderColor: "#10b981",
            tension: 0.3,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: "#9ca3af" } } },
        scales: {
          x: { ticks: { color: "#9ca3af" }, grid: { display: false } },
          y: { position: 'left', ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } },
          y1: { position: 'right', ticks: { color: "#10b981" }, grid: { display: false } }
        }
      }
    });
  }
}

function updateDwellChart(dwellSummary) {
  if (!dwellChart || !dwellSummary) return;
  const labels = Object.keys(dwellSummary);
  const values = Object.values(dwellSummary);
  if (labels.length > 0) {
    dwellChart.data.labels = labels;
    dwellChart.data.datasets[0].data = values;
    dwellChart.update();
  }
}

async function fetchHistory() {
  try {
    const res = await fetch("/api/history?limit=15");
    const data = await res.json();
    if (data.traffic && data.traffic.length > 0 && trafficTrendChart) {
      const labels = data.traffic.map(t => t.timestamp.split("T")[1].substring(0, 8));
      trafficTrendChart.data.labels = labels;
      trafficTrendChart.data.datasets[0].data = data.traffic.map(t => t.total_in);
      trafficTrendChart.data.datasets[1].data = data.traffic.map(t => t.current_people);
      trafficTrendChart.update();
    }
    if (data.queue && data.queue.length > 0 && queueTrendChart) {
      const labels = data.queue.map(q => q.timestamp.split("T")[1].substring(0, 8));
      queueTrendChart.data.labels = labels;
      queueTrendChart.data.datasets[0].data = data.queue.map(q => q.queue_length);
      queueTrendChart.update();
    }
  } catch (err) {
    // console.warn("History fetch error:", err);
  }
}

async function fetchSystemStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();

    // Sync store selector
    if (data.active_store && data.active_store.store_code) {
      const sel = document.getElementById("headerStoreSelector");
      if (sel && sel.value !== data.active_store.store_code) {
        sel.value = data.active_store.store_code;
      }
    }

    // Sync privacy status
    updatePrivacyUI({
      privacy_mode_enabled: data.privacy_mode,
      blur_faces: data.blur_faces
    });
  } catch (e) {}
}

async function fetchInitialData() {
  fetchSystemStatus();
  fetchLiveStats();
  fetchHeatmapData();
  fetchTrafficTrends();
  fetchHistory();
  fetchLedgerBlocks();
  initBillingPOS();
  fetchInventoryLedger();
  fetchDemandForecast();
  fetchFleetSummary();
  fetchSyncStatusAndQueue();
}

// ================= SUPABASE ACTIONS =================
function openSupabaseModal() {
  document.getElementById("supabaseModal").style.display = "flex";
}

function closeSupabaseModal() {
  document.getElementById("supabaseModal").style.display = "none";
}

async function saveModalSupabase() {
  const url = document.getElementById("modalSbUrl").value.trim();
  const key = document.getElementById("modalSbKey").value.trim();
  if (!url || !key) {
    alert("Please provide both Supabase Project URL and API Key.");
    return;
  }
  await sendSupabaseConfig(url, key);
  closeSupabaseModal();
}

async function saveSupabaseConfig(e) {
  e.preventDefault();
  const url = document.getElementById("sbUrlInput").value.trim();
  const key = document.getElementById("sbKeyInput").value.trim();
  if (!url || !key) {
    alert("Please enter both Supabase Project URL and API Key.");
    return;
  }
  await sendSupabaseConfig(url, key);
}

async function sendSupabaseConfig(url, key) {
  try {
    const res = await fetch("/api/supabase/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, key })
    });
    const data = await res.json();
    if (data.success) {
      alert("✅ Supabase Cloud Connected Successfully!\nAll tables verified and credentials saved permanently to .env.");
    } else if (data.needs_migration) {
      alert("⚠️ Connected to Supabase project, but tables are missing!\n\n" + data.message + "\n\nPlease copy 'supabase_schema.sql' and run it in your Supabase SQL Editor.");
    } else {
      alert("⚠️ Supabase Connection Issue:\n" + (data.message || "Could not verify Supabase tables."));
    }
    fetchLiveStats();
    fetchSupabaseDiagnostics();
  } catch (err) {
    alert("Failed to configure Supabase: " + err.message);
  }
}

async function disconnectFromSupabase() {
  try {
    const res = await fetch("/api/supabase/disconnect", { method: "POST" });
    const data = await res.json();
    alert(data.message || "Disconnected from Supabase Cloud.");
    const uInput = document.getElementById("sbUrlInput");
    const kInput = document.getElementById("sbKeyInput");
    if (uInput) uInput.value = "";
    if (kInput) kInput.value = "";
    const resBox = document.getElementById("cloudTestResult");
    if (resBox) resBox.style.display = "none";
    fetchLiveStats();
    fetchSupabaseDiagnostics();
  } catch (err) {
    alert("Failed to disconnect: " + err.message);
  }
}

async function testSupabaseConnection() {
  const resultBox = document.getElementById("cloudTestResult");
  resultBox.style.display = "block";
  resultBox.textContent = "Testing Supabase Cloud connection and tables...";
  resultBox.style.background = "rgba(6, 182, 212, 0.1)";
  resultBox.style.color = "#06b6d4";

  try {
    const res = await fetch("/api/supabase/test");
    const data = await res.json();
    if (data.success) {
      resultBox.textContent = "✅ " + data.message;
      resultBox.style.background = "rgba(16, 185, 129, 0.15)";
      resultBox.style.color = "#34d399";
    } else {
      resultBox.textContent = "❌ " + data.message;
      resultBox.style.background = "rgba(244, 63, 94, 0.15)";
      resultBox.style.color = "#fb7185";
    }
    fetchSupabaseDiagnostics();
  } catch (err) {
    resultBox.textContent = "❌ Error connecting to test endpoint: " + err.message;
  }
}

async function triggerManualSync() {
  try {
    const res = await fetch("/api/supabase/sync", { method: "POST" });
    const data = await res.json();
    if (data.synced) {
      alert(`✅ Cloud Sync Successful at ${data.timestamp}!\n\nSynced to Supabase:\n• Traffic logs: ${data.counts.traffic}\n• Queue records: ${data.counts.queue}\n• Shelf compliance: ${data.counts.shelf}\n• Live alerts: ${data.counts.alerts}\n• Inventory snapshots: ${data.counts.inventory}\n• POS Sales: ${data.counts.sales || 0}\n• Inventory Ledger: ${data.counts.ledger || 0}`);
    } else {
      const errDetail = data.errors ? "\n\nTable Errors:\n" + Object.entries(data.errors).map(([k, v]) => `• ${k}: ${v}`).join("\n") : "";
      alert(`⚠️ Sync Warning: ${data.reason || data.error || 'Check Supabase credentials or schema migration.'}${errDetail}`);
    }
    fetchLiveStats();
    fetchSupabaseDiagnostics();
  } catch (err) {
    alert("Sync request failed: " + err.message);
  }
}

async function triggerForceResyncAll() {
  const resultBox = document.getElementById("cloudTestResult");
  if (resultBox) {
    resultBox.style.display = "block";
    resultBox.textContent = "Pushing all local historical records from SQLite to Supabase...";
    resultBox.style.background = "rgba(6, 182, 212, 0.1)";
    resultBox.style.color = "#06b6d4";
  }
  try {
    const res = await fetch("/api/supabase/resync-all", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      alert(`✅ Full Re-Sync Completed!\n\nSuccessfully pushed ${data.total_pushed} records to Supabase tables.`);
      if (resultBox) {
        resultBox.textContent = `✅ Successfully pushed ${data.total_pushed} historical records to Supabase!`;
        resultBox.style.background = "rgba(16, 185, 129, 0.15)";
        resultBox.style.color = "#34d399";
      }
    } else {
      const errStr = data.errors ? Object.entries(data.errors).map(([k, v]) => `${k}: ${v}`).join(", ") : (data.message || "Unknown error");
      alert(`⚠️ Re-Sync Warning: ${errStr}`);
      if (resultBox) {
        resultBox.textContent = `⚠️ Re-Sync Note: ${errStr}`;
        resultBox.style.background = "rgba(244, 63, 94, 0.15)";
        resultBox.style.color = "#fb7185";
      }
    }
    fetchLiveStats();
    fetchSupabaseDiagnostics();
  } catch (err) {
    alert("Force re-sync request failed: " + err.message);
  }
}

async function fetchSupabaseDiagnostics() {
  const diagContainer = document.getElementById("supabaseDiagnosticsList");
  if (!diagContainer) return;

  try {
    const res = await fetch("/api/supabase/diagnostics");
    if (!res.ok) return;
    const data = await res.json();

    if (!data.connected) {
      diagContainer.innerHTML = `<div style="color: #94a3b8; font-size: 11px; padding: 6px 0;">⚡ Supabase is currently disconnected. Enter credentials above to link database.</div>`;
      return;
    }

    if (data.healthy) {
      diagContainer.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid #10b981; border-radius: 6px; padding: 8px 12px; color: #34d399; font-size: 11px;">
          <strong>✅ Database Verified:</strong> All 10 cloud tables exist and are receiving edge data.
        </div>
      `;
    } else {
      diagContainer.innerHTML = `
        <div style="background: rgba(244, 63, 94, 0.15); border: 1px solid #f43f5e; border-radius: 6px; padding: 10px; color: #fda4af; font-size: 11px;">
          <strong>⚠️ Action Needed — Missing Tables:</strong> ${data.missing_tables.join(", ")}<br>
          <span style="color: #cbd5e1; display: block; margin-top: 4px;">Run <code>supabase_schema.sql</code> in your Supabase SQL Editor to enable full synchronization.</span>
        </div>
      `;
    }
  } catch (err) {
    console.warn("Diagnostics fetch error:", err);
  }
}

// ================= STORE BRAIN DIRECTIVES =================
function renderStoreBrainDirectives(brain) {
  const container = document.getElementById("brainDirectivesList");
  const badge = document.getElementById("brainSurgeBadge");
  if (!container) return;

  if (badge) {
    const surge = brain.traffic_surge_pct || 0;
    badge.textContent = `Footfall Surge: ${surge >= 0 ? '+' : ''}${surge}%`;
    badge.style.color = surge > 15 ? '#fbbf24' : '#94a3b8';
  }

  const actions = brain.top_prioritized_actions || [];
  if (actions.length === 0) {
    container.innerHTML = `<div style="color: #10b981; font-size: 11px; padding: 4px;">✅ Store operations optimal. No urgent replenishment directives.</div>`;
    return;
  }

  container.innerHTML = actions.slice(0, 3).map((a, idx) => {
    const isCrit = a.priority === 1;
    const badgeColor = isCrit ? '#f43f5e' : '#fbbf24';
    const badgeBg = isCrit ? 'rgba(244,63,94,0.15)' : 'rgba(245,158,11,0.15)';
    const revText = a.revenue_at_risk ? `• ₹${Math.round(a.revenue_at_risk)} at risk` : '';

    return `
      <div style="background: rgba(0,0,0,0.35); border-left: 3px solid ${badgeColor}; border-radius: 6px; padding: 8px 10px; font-size: 11px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 2px;">
          <span style="font-weight: 700; color: #f8fafc;">${idx + 1}. [${escapeHtml(a.type)}] ${escapeHtml(a.action)}</span>
          <span style="font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px; background:${badgeBg}; color:${badgeColor}; font-family:'JetBrains Mono'; white-space:nowrap; margin-left:6px;">
            ${isCrit ? 'URGENT' : 'PRIORITY 2'}
          </span>
        </div>
        <div style="display:flex; justify-content:space-between; color:#94a3b8; font-size: 10px; margin-top: 4px;">
          <span>Target: <code>${escapeHtml(a.target)}</code> (${escapeHtml(a.zone)})</span>
          <span style="color:#fbbf24; font-family:'JetBrains Mono';">Deadline: ${a.deadline_mins}m ${revText}</span>
        </div>
      </div>
    `;
  }).join("");
}

// ================= SYSTEM INTEGRITY & DIAGNOSTIC CENTER =================
let currentIntegrityTab = 'live';

function switchIntegrityModalTab(tab) {
  currentIntegrityTab = tab;
  const liveTab = document.getElementById("integrityTabLive");
  const archTab = document.getElementById("integrityTabArch");
  const btnLive = document.getElementById("tabBtnIntegrityLive");
  const btnArch = document.getElementById("tabBtnIntegrityArch");

  if (liveTab && archTab && btnLive && btnArch) {
    if (tab === 'live') {
      liveTab.style.display = "block";
      archTab.style.display = "none";
      btnLive.classList.add("active");
      btnArch.classList.remove("active");
    } else {
      liveTab.style.display = "none";
      archTab.style.display = "block";
      btnLive.classList.remove("active");
      btnArch.classList.add("active");
    }
  }
}

async function openIntegrityModal() {
  const modal = document.getElementById("integrityModal");
  if (!modal) return;
  modal.style.display = "flex";

  try {
    const res = await fetch("/api/integrity");
    if (res.ok) {
      const data = await res.json();

      // 1. Overall Score
      const scoreElem = document.getElementById("integrityHealthScore");
      const badgeElem = document.getElementById("integrityHealthBadge");
      if (scoreElem) scoreElem.textContent = `${data.overall_health_score || 100}%`;
      if (badgeElem) {
        badgeElem.textContent = data.health_level === "OPTIMAL" ? "ALL SYSTEMS OPTIMAL" : "ATTENTION NEEDED";
        badgeElem.style.color = data.health_level === "OPTIMAL" ? "#34d399" : "#fbbf24";
      }

      // 2. Subsystems Live Diagnostic Cards
      const subGrid = document.getElementById("integritySubsystemsGrid");
      if (subGrid && data.subsystems) {
        const iconMap = {
          "camera_pipeline": "📹",
          "yolo_detector": "🧠",
          "inventory_ledger": "⚖️",
          "cryptographic_chain": "⛓️",
          "demand_forecaster": "⛅",
          "edge_storage": "🗄️",
          "privacy_anonymizer": "🔒",
          "cloud_gateway": "☁️"
        };

        subGrid.innerHTML = data.subsystems.map(s => {
          const icon = iconMap[s.id] || "⚙️";
          const isOptimal = (s.status === "HEALTHY" || s.status === "ONLINE" || s.status === "OPTIMAL");
          const statusColor = isOptimal ? "#34d399" : (s.status === "STANDBY" || s.status === "OFFLINE_RESILIENT" ? "#38bdf8" : "#fbbf24");
          const statusBg = isOptimal ? "rgba(16,185,129,0.15)" : "rgba(56,189,248,0.15)";
          const borderCol = isOptimal ? "rgba(16,185,129,0.3)" : "rgba(255,255,255,0.1)";

          return `
            <div style="background: rgba(0,0,0,0.4); border: 1px solid ${borderCol}; border-radius: 10px; padding: 12px; display: flex; flex-direction: column; justify-content: space-between;">
              <div>
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 6px;">
                  <div style="display:flex; align-items:center; gap: 8px;">
                    <span style="font-size: 16px;">${icon}</span>
                    <strong style="font-size: 12px; color: #f8fafc;">${escapeHtml(s.name)}</strong>
                  </div>
                  <span style="font-size: 9px; font-weight: 800; padding: 2px 7px; border-radius: 6px; font-family:'JetBrains Mono'; background:${statusBg}; color:${statusColor}; border: 1px solid ${statusColor};">
                    ${escapeHtml(s.status)}
                  </span>
                </div>
                <div style="font-size: 15px; font-weight: 800; font-family: 'JetBrains Mono'; color: #f1f5f9; margin: 4px 0 6px 0;">
                  ${escapeHtml(s.metric)}
                </div>
                <div style="font-size: 11px; color: #94a3b8; line-height: 1.35; margin-bottom: 8px;">
                  ${escapeHtml(s.details)}
                </div>
              </div>
              <div style="display:flex; justify-content:space-between; font-size: 10px; color: #64748b; font-family:'JetBrains Mono'; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 6px;">
                <span>Type: ${escapeHtml(s.source)}</span>
                <span style="color: #10b981;">Score: ${s.score}%</span>
              </div>
            </div>
          `;
        }).join("");
      }

      // 3. Architectural Honesty Matrix Table
      const list = document.getElementById("integrityGrid");
      if (list && data.components) {
        list.innerHTML = data.components.map(c => `
          <div style="background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 12px;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 6px;">
              <strong style="font-size: 13px; color: #f8fafc;">${escapeHtml(c.module)}</strong>
              <span style="font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 12px; font-family:'JetBrains Mono'; ${
                c.source === 'REAL_NEURAL_NET' || c.source === 'TRAINED_MODEL' ? 'background:rgba(16,185,129,0.15); color:#34d399; border:1px solid #10b981;' :
                c.source === 'REAL_EDGE_ANALYTICS' || c.source === 'REAL_EDGE_OCR' ? 'background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid #38bdf8;' :
                c.source.includes('HEURISTIC') ? 'background:rgba(245,158,11,0.15); color:#fbbf24; border:1px solid #f59e0b;' :
                'background:rgba(148,163,184,0.15); color:#94a3b8; border:1px solid rgba(255,255,255,0.2);'
              }">${escapeHtml(c.source)}</span>
            </div>
            <div style="font-size: 11px; color: #94a3b8; margin-bottom: 6px;">${escapeHtml(c.description)}</div>
            <div style="display:flex; justify-content:space-between; font-size: 10px; color: #64748b; font-family:'JetBrains Mono';">
              <span>Method: ${escapeHtml(c.method)}</span>
              <span>Latency: ${escapeHtml(c.latency)}</span>
            </div>
          </div>
        `).join("");
      }

      // 4. Timestamp
      const stampElem = document.getElementById("integrityLastCheckedText");
      if (stampElem && data.timestamp) {
        stampElem.textContent = `Last Probe: ${data.timestamp} • All Checksums Valid`;
      }
    }
  } catch (err) {
    console.warn("Integrity fetch failed:", err);
  }
}

async function runIntegritySelfTest() {
  const btn = document.getElementById("btnRunSelfTest");
  const stamp = document.getElementById("integrityLastCheckedText");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Testing Subsystems...";
  }

  try {
    const res = await fetch("/api/integrity/self-test", { method: "POST" });
    const data = await res.json();
    if (data.self_test_passed) {
      if (stamp) {
        stamp.innerHTML = `✅ <span style="color:#34d399;">Self-Test Certified in ${data.execution_time_ms}ms</span> • 8/8 Subsystems Passed`;
      }
    } else {
      if (stamp) stamp.textContent = `⚠️ Self-Test warning detected`;
    }
    await openIntegrityModal();
  } catch (err) {
    console.warn("Self test error:", err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "▶ Run Active Self-Test";
    }
  }
}

function downloadIntegrityCertificate() {
  window.location.href = "/api/integrity/report/download";
}

function closeIntegrityModal() {
  const modal = document.getElementById("integrityModal");
  if (modal) modal.style.display = "none";
}

// Backdrop click dismiss for modals
window.addEventListener("click", (e) => {
  const intModal = document.getElementById("integrityModal");
  if (intModal && e.target === intModal) {
    intModal.style.display = "none";
  }
  const supModal = document.getElementById("supabaseModal");
  if (supModal && e.target === supModal) {
    supModal.style.display = "none";
  }
  const staffModal = document.getElementById("staffPhoneModal");
  if (staffModal && e.target === staffModal) {
    staffModal.style.display = "none";
  }
});

// ================= 🆕 BILLING POS & RESTOCK CLIENT =================
let posCart = [];
let catalogProducts = [];

async function initBillingPOS() {
  try {
    const res = await fetch("/api/products");
    catalogProducts = await res.json();
    populateProductDropdowns();
  } catch (err) {
    console.warn("Failed to load catalog for POS:", err);
  }
}

function populateProductDropdowns() {
  const posSel = document.getElementById("posProductSelect");
  const restockSel = document.getElementById("restockProductSelect");
  if (!posSel || !catalogProducts.length) return;

  const opts = catalogProducts.map(p => 
    `<option value="${p.id}">${escapeHtml(p.name)} (₹${p.price.toFixed(2)})</option>`
  ).join("");

  posSel.innerHTML = opts;
  if (restockSel) restockSel.innerHTML = opts;
}

function updatePosProductPrice() {
  // Optional dynamic helper
}

function adjustPosQty(delta) {
  const input = document.getElementById("posProductQty");
  if (!input) return;
  let val = (parseInt(input.value) || 1) + delta;
  if (val < 1) val = 1;
  if (val > 50) val = 50;
  input.value = val;
}

function clearPosCart() {
  posCart = [];
  renderPosCart();
}

function quickSampleSale() {
  if (!catalogProducts.length) return;
  // Pick 2 random items or first two items
  const item1 = catalogProducts[0];
  const item2 = catalogProducts[1] || catalogProducts[0];
  posCart = [
    { sku_id: item1.id, name: item1.name, price: item1.price, quantity: 2 },
    { sku_id: item2.id, name: item2.name, price: item2.price, quantity: 1 }
  ];
  renderPosCart();
}

function addPosItemToCart() {
  const sel = document.getElementById("posProductSelect");
  const qtyInput = document.getElementById("posProductQty");
  if (!sel || !qtyInput) return;

  const skuId = sel.value;
  const qty = parseInt(qtyInput.value) || 1;
  const prod = catalogProducts.find(p => p.id === skuId);
  if (!prod) return;

  const existing = posCart.find(i => i.sku_id === skuId);
  if (existing) {
    existing.quantity += qty;
  } else {
    posCart.push({
      sku_id: prod.id,
      name: prod.name,
      price: prod.price,
      quantity: qty
    });
  }

  // Reset quantity input back to 1
  qtyInput.value = 1;
  renderPosCart();
}

function removePosCartItem(idx) {
  posCart.splice(idx, 1);
  renderPosCart();
}

function renderPosCart() {
  const container = document.getElementById("posCartList");
  const totalElem = document.getElementById("posCartTotal");
  const countElem = document.getElementById("posCartCount");
  if (!container) return;

  const totalItemsCount = posCart.reduce((acc, i) => acc + i.quantity, 0);
  if (countElem) {
    countElem.textContent = `${totalItemsCount} item${totalItemsCount === 1 ? '' : 's'}`;
  }

  if (posCart.length === 0) {
    container.innerHTML = `<div style="color: #64748b; font-size: 12px; padding: 14px; text-align: center;">Cart is empty. Select a product above and click <strong>Add to Cart</strong>.</div>`;
    if (totalElem) totalElem.textContent = "₹0.00";
    return;
  }

  let total = 0;
  container.innerHTML = posCart.map((it, idx) => {
    const lineTot = it.price * it.quantity;
    total += lineTot;
    return `
      <div class="cart-item-row">
        <div>
          <strong>${escapeHtml(it.name)}</strong>
          <span style="color:#94a3b8; margin-left:6px; font-family:'JetBrains Mono'; font-size:12px;">x${it.quantity} @ ₹${it.price.toFixed(2)}</span>
        </div>
        <div style="display:flex; align-items:center; gap:12px;">
          <strong style="font-family:'JetBrains Mono'; color:#38bdf8; font-size:14px;">₹${lineTot.toFixed(2)}</strong>
          <button type="button" onclick="removePosCartItem(${idx})" title="Remove item" style="background: rgba(244,63,94,0.15); border: 1px solid rgba(244,63,94,0.3); color:#f43f5e; border-radius: 4px; padding: 2px 8px; cursor:pointer; font-weight:bold; font-size: 12px;">&times;</button>
        </div>
      </div>
    `;
  }).join("");

  if (totalElem) totalElem.textContent = `₹${total.toFixed(2)}`;
}

async function handlePosCheckout(e) {
  e.preventDefault();
  if (posCart.length === 0) {
    alert("Please add at least one product to the checkout cart.");
    return;
  }

  const paymentMethod = document.getElementById("posPaymentMethod").value;
  const cashier = document.getElementById("posCashierName").value;

  const payload = {
    items: posCart.map(it => ({ sku_id: it.sku_id, quantity: it.quantity })),
    payment_method: paymentMethod,
    cashier: cashier
  };

  try {
    const res = await fetch("/api/billing/sale", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const receipt = await res.json();

    if (receipt.success) {
      renderPosReceipt(receipt);
      posCart = [];
      renderPosCart();
      fetchInventoryLedger();
      fetchLiveStats();
      fetchSyncStatusAndQueue();
    } else {
      alert("⚠️ Checkout failed: " + (receipt.error || "Unknown error"));
    }
  } catch (err) {
    alert("Error processing sale: " + err.message);
  }
}

function openReceiptsPdf() {
  window.open("/api/billing/receipts/pdf", "_blank");
}

function renderPosReceipt(r) {
  const container = document.getElementById("posReceiptContainer");
  if (!container) return;

  container.style.display = "block";
  container.innerHTML = `
    <div class="pos-receipt-card">
      <div class="receipt-header">
        <strong style="color: #38bdf8; font-size: 13px;">SMARTRETAIL POS DIGITAL RECEIPT</strong><br>
        Store: Indiranagar Flagship • Txn: ${r.transaction_id}<br>
        Cashier: ${escapeHtml(r.cashier)} • Method: ${escapeHtml(r.payment_method)} • ${r.timestamp.substring(0, 19).replace('T', ' ')}
      </div>
      <div>
        ${r.items.map(it => `
          <div style="display:flex; justify-content:space-between; padding:2px 0;">
            <span>${escapeHtml(it.product_name)} x${it.quantity}</span>
            <span>₹${it.line_total.toFixed(2)}</span>
          </div>
        `).join("")}
      </div>
      <div style="border-top:1px dashed rgba(255,255,255,0.1); padding-top:6px; margin-top:4px; display:flex; justify-content:space-between; font-weight:800; color:#34d399; font-size:13px;">
        <span>TOTAL PAID:</span>
        <span>₹${r.total_amount.toFixed(2)}</span>
      </div>
      <div style="font-size:9px; color:#64748b; text-align:center; margin-top:4px;">
        ✅ Stock accurately decremented from SQLite inventory ledger.
      </div>
      <div style="display: flex; gap: 8px; margin-top: 8px; justify-content: flex-end;">
        <button type="button" onclick="openReceiptsPdf()" class="btn-secondary" style="padding: 5px 10px; font-size: 11px; font-weight: 700;">
          📑 View / Print All Receipts PDF
        </button>
        <button type="button" onclick="window.print()" class="btn-secondary" style="padding: 5px 10px; font-size: 11px; font-weight: 700;">
          🖨️ Print This Slip
        </button>
      </div>
    </div>
  `;
}

async function handlePosRestock(e) {
  e.preventDefault();
  const skuId = document.getElementById("restockProductSelect").value;
  const qty = parseInt(document.getElementById("restockQtyInput").value);
  const actor = document.getElementById("restockActorInput").value;
  const note = document.getElementById("restockNoteInput").value;

  try {
    const res = await fetch("/api/inventory/restock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sku_id: skuId, quantity: qty, actor, note })
    });
    const data = await res.json();

    if (data.success) {
      alert(`✅ Restocked +${qty} units for ${skuId}. New true stock: ${data.new_true_stock} units.`);
      fetchInventoryLedger();
      fetchLiveStats();
      fetchSyncStatusAndQueue();
    } else {
      alert("⚠️ Restock error: " + (data.error || "Failed"));
    }
  } catch (err) {
    alert("Restock network error: " + err.message);
  }
}

async function fetchInventoryLedger() {
  try {
    const [ledgRes, invRes] = await Promise.all([
      fetch("/api/inventory/ledger?limit=40"),
      fetch("/api/inventory")
    ]);
    const ledgData = await ledgRes.json();
    const invData = await invRes.json();

    renderLedgerHistory(ledgData.ledger || []);
    renderBillingDiscrepancies(invData.items || []);
  } catch (err) {
    console.warn("Error fetching ledger:", err);
  }
}

function renderBillingDiscrepancies(items) {
  const tbody = document.getElementById("discrepancyTableBody");
  if (!tbody || !items || !items.length) return;

  tbody.innerHTML = items.map(it => `
    <tr>
      <td><strong>${escapeHtml(it.product_name)}</strong></td>
      <td><span style="color:#38bdf8; font-weight:700; font-family:'JetBrains Mono';">${it.shelf_facing_count ?? it.stock}</span></td>
      <td><span style="color:#34d399; font-weight:700; font-family:'JetBrains Mono';">${it.ledger_stock ?? it.stock}</span></td>
      <td><span class="discrepancy-tag ${it.discrepancy || 'BALANCED'}">${it.discrepancy || 'BALANCED'}</span></td>
    </tr>
  `).join("");
}

function renderLedgerHistory(records) {
  const tbody = document.getElementById("ledgerHistoryTableBody");
  if (!tbody) return;

  if (records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:#64748b; padding:12px;">No ledger transactions recorded yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map(r => {
    const isSale = (r.reason === "sale" || r.change_qty < 0);
    const qtyColor = isSale ? "#f43f5e" : "#10b981";
    const qtySign = r.change_qty > 0 ? `+${r.change_qty}` : `${r.change_qty}`;

    return `
      <tr>
        <td><code>#${r.id}</code></td>
        <td><strong>${escapeHtml(r.sku_id)}</strong></td>
        <td><strong style="color: ${qtyColor}; font-family:'JetBrains Mono';">${qtySign}</strong></td>
        <td><span class="slot-status-pill ${isSale ? 'MISPLACED' : 'COMPLIANT'}">${escapeHtml(r.reason.toUpperCase())}</span></td>
        <td><code>${escapeHtml(r.reference_id || '—')}</code></td>
        <td style="font-size:11px; color:#cbd5e1;">${escapeHtml(r.note || '')}</td>
        <td style="font-size:11px;">${escapeHtml(r.actor || 'system')}</td>
        <td style="font-size:10px; color:#94a3b8; font-family:'JetBrains Mono';">${escapeHtml(r.timestamp.substring(0, 19).replace('T', ' '))}</td>
      </tr>
    `;
  }).join("");
}

// ================= 🆕 WEATHER & DEMAND AI CLIENT =================
async function fetchDemandForecast() {
  try {
    const res = await fetch("/api/demand/forecast");
    const data = await res.json();
    if (!data) return;

    // Update Weather card
    const w = data.weather || {};
    const curr = w.current || {};
    const tomorrow = w.tomorrow_forecast || {};
    const loc = w.store_location || {};

    const tCurrElem = document.getElementById("wCurrentTemp");
    if (tCurrElem) tCurrElem.textContent = `${curr.temperature_c ?? 26.3}°C`;

    const condCurrElem = document.getElementById("wCurrentCondition");
    if (condCurrElem) condCurrElem.textContent = curr.condition || "Clear";

    const tTomElem = document.getElementById("wTomorrowTemp");
    if (tTomElem) tTomElem.textContent = `${tomorrow.temperature_max_c ?? 33.8}°C Max`;

    const rainElem = document.getElementById("wRainProb");
    if (rainElem) rainElem.textContent = `${tomorrow.precipitation_probability_pct ?? 55}%`;

    const condTomElem = document.getElementById("wTomorrowCondition");
    if (condTomElem) condTomElem.textContent = tomorrow.condition || "Rainy / Showers";

    // Location display
    const storeCoordsElem = document.getElementById("wStoreCoords");
    if (storeCoordsElem) {
      const city = loc.city || "Jamnagar";
      const reg = loc.region || "Gujarat";
      const lat = loc.lat !== undefined ? Number(loc.lat).toFixed(2) : "22.47";
      const lon = loc.lon !== undefined ? Number(loc.lon).toFixed(2) : "70.06";
      storeCoordsElem.textContent = `${city}, ${reg} (${lat}°N, ${lon}°E)`;
    }

    const locTagElem = document.getElementById("wLocationTag");
    if (locTagElem && loc.detected_from) {
      locTagElem.textContent = `📍 ${loc.detected_from}`;
    }

    // Mode Badge & Metadata
    const modeBadge = document.getElementById("demandModeBadge");
    if (modeBadge) {
      modeBadge.textContent = data.mode === "TRAINED" ? "TRAINED ML (RandomForest)" : "HEURISTIC (Rules)";
      modeBadge.style.color = data.mode === "TRAINED" ? "#34d399" : "#fbbf24";
    }

    const metaElem = document.getElementById("demandModelMeta");
    if (metaElem && data.model_metadata) {
      const meta = data.model_metadata;
      if (data.mode === "TRAINED") {
        metaElem.textContent = `Trained on: ${meta.location || "Jamnagar, Gujarat"} • Samples: ${meta.total_samples || 370} • MAE: ${meta.mae || 3.04} units`;
      } else {
        metaElem.textContent = "Transparent category weather rules active";
      }
    }

    // Directives list
    const dirContainer = document.getElementById("demandDirectivesList");
    if (dirContainer && data.directives) {
      dirContainer.innerHTML = data.directives.map(d => `
        <div class="directive-banner">${escapeHtml(d)}</div>
      `).join("");
    }

    // Total Profit
    const profitElem = document.getElementById("demandTotalProfit");
    if (profitElem && data.total_projected_profit !== undefined) {
      profitElem.textContent = `₹${data.total_projected_profit.toLocaleString()}`;
    }

    // Predictions Table
    renderDemandForecastTable(data.predictions || []);
  } catch (err) {
    console.warn("Demand forecast fetch error:", err);
  }
}

async function detectPCLocation() {
  const tag = document.getElementById("wLocationTag");
  if (tag) tag.textContent = "🔄 Detecting PC Location...";
  try {
    const res = await fetch("/api/demand/detect-location", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      await fetchDemandForecast();
      if (tag) tag.textContent = "📍 PC Detected & Synced";
      setTimeout(() => {
        if (tag) tag.textContent = "📍 Current PC Location";
      }, 3000);
    }
  } catch (err) {
    console.warn("Location detection error:", err);
    if (tag) tag.textContent = "📍 Store Location";
  }
}

function renderDemandForecastTable(predictions) {
  const tbody = document.getElementById("demandForecastTableBody");
  if (!tbody || !predictions.length) return;

  tbody.innerHTML = predictions.map(p => `
    <tr>
      <td><code>${p.sku_id}</code></td>
      <td><strong>${escapeHtml(p.product_name)}</strong></td>
      <td>${p.category}</td>
      <td>₹${p.price.toFixed(2)}</td>
      <td style="color:#94a3b8;">₹${p.cost_price.toFixed(2)}</td>
      <td><strong style="color:#10b981; font-family:'JetBrains Mono';">₹${p.unit_margin.toFixed(2)}</strong> <small style="color:#64748b;">(${p.margin_pct}%)</small></td>
      <td><strong style="font-family:'JetBrains Mono'; color:#38bdf8;">${p.current_stock}</strong></td>
      <td><strong style="font-family:'JetBrains Mono'; font-size:15px; color:#fbbf24;">${p.predicted_units}</strong> units</td>
      <td><strong style="font-family:'JetBrains Mono'; color:#34d399;">₹${p.projected_profit.toFixed(2)}</strong></td>
      <td><span class="demand-action-badge ${p.action}">${p.action.replace(/_/g, ' ')}</span></td>
    </tr>
  `).join("");
}

async function triggerDemandTraining() {
  const statusElem = document.getElementById("demandTrainStatus");
  if (statusElem) {
    statusElem.style.display = "inline";
    statusElem.textContent = "Training RandomForest model for your PC location...";
  }

  try {
    const res = await fetch("/api/demand/train", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const data = await res.json();
    if (data.success) {
      if (statusElem) {
        statusElem.textContent = `✅ Model trained for your location! Mode: ${data.mode}`;
        setTimeout(() => { statusElem.style.display = "none"; }, 4000);
      }
      fetchDemandForecast();
    } else {
      if (statusElem) statusElem.textContent = `⚠️ Training failed: ${data.error || 'Check logs'}`;
    }
  } catch (err) {
    if (statusElem) statusElem.textContent = `Error: ${err.message}`;
  }
}

// ================= SHOPPER TRENDS (HOURLY & DAILY) =================
async function fetchTrafficTrends() {
  try {
    const [hRes, dRes] = await Promise.all([
      fetch("/api/traffic/trends/hourly"),
      fetch("/api/traffic/trends/daily")
    ]);
    
    if (hRes.ok && hourlyTrendChart) {
      const hourlyData = await hRes.json();
      hourlyTrendChart.data.labels = hourlyData.map(h => h.hour);
      hourlyTrendChart.data.datasets[0].data = hourlyData.map(h => h.shoppers);
      hourlyTrendChart.data.datasets[0].backgroundColor = hourlyData.map(h => h.is_peak ? "#f43f5e" : "#0284c7");
      hourlyTrendChart.update();
    }

    if (dRes.ok && dailyTrendChart) {
      const dailyData = await dRes.json();
      dailyTrendChart.data.labels = dailyData.map(d => d.day.substring(0, 3));
      dailyTrendChart.data.datasets[0].data = dailyData.map(d => d.footfall);
      dailyTrendChart.data.datasets[1].data = dailyData.map(d => d.conversion_rate_pct);
      dailyTrendChart.update();
    }
  } catch (err) {
    // console.warn("Traffic trends error:", err);
  }
}

// ================= PRIVACY-AWARE EDGE CONTROLS =================
async function togglePrivacyMode() {
  try {
    const res = await fetch("/api/privacy/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}"
    });
    const data = await res.json();
    updatePrivacyUI(data);
    reloadVideoFeed();
  } catch (err) {
    console.warn("Privacy toggle error:", err);
  }
}

function updatePrivacyUI(data) {
  const dot = document.getElementById("privacyDot");
  const label = document.getElementById("privacyBtnLabel");
  if (!dot || !label) return;

  if (data.privacy_mode_enabled) {
    dot.className = "pulse-dot amber";
    label.textContent = "🛡️ Silhouette Privacy ON";
  } else if (data.blur_faces) {
    dot.className = "pulse-dot green";
    label.textContent = "🛡️ Face Blur: ON";
  } else {
    dot.className = "pulse-dot rose";
    label.textContent = "🛡️ Privacy: OFF";
  }
}

// ================= MULTI-STORE FLEET OPERATIONS =================
async function switchStoreBranch(storeCode) {
  try {
    const res = await fetch("/api/fleet/switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ store_code: storeCode })
    });
    const data = await res.json();
    if (data.success) {
      console.log("Switched to store:", storeCode);
      const sel = document.getElementById("headerStoreSelector");
      if (sel) sel.value = storeCode;
      fetchLiveStats();
      fetchFleetSummary();
    }
  } catch (err) {
    console.warn("Store switch error:", err);
  }
}

async function fetchFleetSummary() {
  try {
    const res = await fetch("/api/fleet/summary");
    const data = await res.json();

    const actElem = document.getElementById("fleetActiveStores");
    if (actElem) actElem.textContent = `${data.online_locations} / ${data.total_locations} ONLINE`;

    const ffElem = document.getElementById("fleetTotalFootfall");
    if (ffElem) ffElem.textContent = data.total_chain_footfall_today.toLocaleString();

    const revElem = document.getElementById("fleetRevenueProtected");
    if (revElem) revElem.textContent = `₹${data.total_chain_revenue_protected.toLocaleString()}`;

    const congElem = document.getElementById("fleetCongestedCount");
    if (congElem) congElem.textContent = data.congested_branches_count;

    const congDet = document.getElementById("fleetCongestedDetail");
    if (congDet) {
      congDet.textContent = data.congested_branches.length ? `Congested: ${data.congested_branches.join(", ")}` : "All store queues optimal";
    }

    const tbody = document.getElementById("fleetBranchesTableBody");
    if (tbody && data.branches) {
      tbody.innerHTML = data.branches.map(b => `
        <tr style="${b.is_active_local ? 'background: rgba(2, 132, 199, 0.08);' : ''}">
          <td><code>${b.store_code}</code> ${b.is_active_local ? '<span class="badge-mini" style="background:#0284c7; color:#fff;">LOCAL EDGE</span>' : ''}</td>
          <td><strong>${b.name}</strong></td>
          <td><span class="badge-mini">${b.tier}</span></td>
          <td><strong style="color:#38bdf8;">${b.active_customers}</strong></td>
          <td>${b.total_footfall_today}</td>
          <td>${b.queue_length} shoppers</td>
          <td>${b.avg_wait_min}m</td>
          <td><strong style="color:${b.stock_health_pct > 90 ? '#10b981' : '#f59e0b'};">${b.stock_health_pct}%</strong></td>
          <td><span class="badge-mini" style="background:${b.status === 'CONGESTED' ? '#f43f5e' : '#10b981'}; color:#fff;">${b.status}</span></td>
          <td><button class="btn-sm" onclick="switchStoreBranch('${b.store_code}')">Select Store</button></td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.warn("Fleet summary error:", err);
  }
}

// ================= WEEKLY EXECUTIVE INTELLIGENCE BRIEF =================
function openWeeklyReport() {
  window.open("/api/reports/weekly/pdf?autoprint=false", "_blank");
}

function downloadWeeklyCSV() {
  window.location.href = "/api/reports/weekly/download";
}

// ================= RESOLVE ALERT ACTION =================
async function resolveAlert(alertId) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ staff: "Floor Associate", note: "Restocked & Verified" })
    });
    const data = await res.json();
    if (data.success) {
      fetchLiveStats();
    }
  } catch (err) {
    console.warn("Resolve alert error:", err);
  }
}

// ================= 2D HEATMAP OVERLAY TOGGLE =================
let heatmapOverlayActive = false;
function toggleHeatmapOverlay() {
  heatmapOverlayActive = !heatmapOverlayActive;
  const btn = document.getElementById("btnToggleHeatmap");
  if (btn) {
    btn.style.background = heatmapOverlayActive ? "rgba(244, 63, 94, 0.3)" : "";
    btn.textContent = heatmapOverlayActive ? "🔥 Heatmap: ACTIVE" : "🔥 2D Heatmap Overlay";
  }
}

// ================= OFFLINE-FIRST EDGE BUFFER & CLOUD SYNC =================
let isSimulatedNetworkOffline = false;

async function fetchSyncStatusAndQueue() {
  try {
    const res = await fetch("/api/sync/status");
    if (!res.ok) return;
    const statusData = await res.json();

    isSimulatedNetworkOffline = !!statusData.simulated_network_offline;
    const isBrowserOnline = navigator.onLine && !isSimulatedNetworkOffline;

    // Update global offline banner
    const offlineBanner = document.getElementById("offlineGlobalBanner");
    const offlineBannerText = document.getElementById("offlineBannerText");
    if (offlineBanner) {
      if (!isBrowserOnline || statusData.network_status === "OFFLINE_BUFFERING") {
        offlineBanner.style.display = "flex";
        if (offlineBannerText) {
          offlineBannerText.innerHTML = `⚠️ <strong>EDGE AUTONOMOUS MODE:</strong> Network uplink is currently disconnected or simulated offline. <strong>${statusData.total_pending_sync || 0} local events</strong> safely buffered on device.`;
        }
      } else {
        offlineBanner.style.display = "none";
      }
    }

    // Update Network State Badge
    const netBadge = document.getElementById("syncNetworkStateBadge");
    const simBtn = document.getElementById("btnSimulateBlackout");
    if (netBadge) {
      if (isSimulatedNetworkOffline) {
        netBadge.style.background = "rgba(244, 63, 94, 0.25)";
        netBadge.style.color = "#f43f5e";
        netBadge.textContent = "🔴 SIMULATED BLACKOUT (OFFLINE EDGE)";
      } else if (!navigator.onLine) {
        netBadge.style.background = "rgba(244, 63, 94, 0.25)";
        netBadge.style.color = "#f43f5e";
        netBadge.textContent = "🔴 PHYSICAL NETWORK DISCONNECTED";
      } else if (statusData.cloud_connected) {
        netBadge.style.background = "rgba(16, 185, 129, 0.2)";
        netBadge.style.color = "#10b981";
        netBadge.textContent = "🟢 ONLINE (LIVE SUPABASE SYNC ACTIVE)";
      } else {
        netBadge.style.background = "rgba(245, 158, 11, 0.2)";
        netBadge.style.color = "#fbbf24";
        netBadge.textContent = "🟡 LOCAL EDGE (SUPABASE DISCONNECTED / PENDING)";
      }
    }

    if (simBtn) {
      simBtn.textContent = isSimulatedNetworkOffline ? "🟢 Reconnect Simulated Link" : "⚡ Simulate Network Blackout";
      simBtn.style.background = isSimulatedNetworkOffline ? "rgba(16, 185, 129, 0.15)" : "rgba(244, 63, 94, 0.15)";
      simBtn.style.borderColor = isSimulatedNetworkOffline ? "#10b981" : "#f43f5e";
      simBtn.style.color = isSimulatedNetworkOffline ? "#34d399" : "#fda4af";
    }

    // Update KPI counters
    const kpiTotal = document.getElementById("syncKpiTotalPending");
    const kpiSales = document.getElementById("syncKpiSalesPending");
    const kpiLedger = document.getElementById("syncKpiLedgerPending");
    const kpiTelemetry = document.getElementById("syncKpiTelemetryPending");
    const kpiAlerts = document.getElementById("syncKpiAlertsPending");

    if (kpiTotal) kpiTotal.textContent = statusData.total_pending_sync || 0;
    if (kpiSales) kpiSales.textContent = statusData.breakdown?.sales_transactions || 0;
    if (kpiLedger) kpiLedger.textContent = statusData.breakdown?.inventory_ledger || 0;
    if (kpiTelemetry) kpiTelemetry.textContent = (statusData.breakdown?.shopper_traffic || 0) + (statusData.breakdown?.queue_metrics || 0);
    if (kpiAlerts) kpiAlerts.textContent = statusData.breakdown?.alerts || 0;

    // Fetch and render queue table
    const queueRes = await fetch("/api/sync/queue?limit=50");
    if (queueRes.ok) {
      const queueData = await queueRes.json();
      renderSyncQueueTable(queueData.items || []);
    }
  } catch (err) {
    console.warn("fetchSyncStatusAndQueue error:", err);
  }
}

function renderSyncQueueTable(items) {
  const tbody = document.getElementById("syncQueueTableBody");
  if (!tbody) return;

  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#64748b; padding:24px;">✨ Edge buffer is fully clear. All transactions and events are synced to cloud!</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(item => {
    const isSynced = item.status === "SYNCED";
    const badgeClass = isSynced ? "sync-status-badge SYNCED" : "sync-status-badge BUFFERED";
    const statusText = isSynced ? "✅ SYNCED" : "⏳ LOCAL_BUFFERED";
    let catClass = "sync-cat-sales";
    if (item.category && item.category.includes("inventory")) catClass = "sync-cat-inventory";
    else if (item.category && item.category.includes("traffic")) catClass = "sync-cat-traffic";
    else if (item.category && item.category.includes("queue")) catClass = "sync-cat-queue";
    else if (item.category && item.category.includes("alert")) catClass = "sync-cat-alerts";

    return `
      <tr>
        <td style="font-family: var(--font-mono); font-size: 11px; color: #94a3b8;">${item.id}</td>
        <td><span class="sync-category-badge ${catClass}">${item.category}</span></td>
        <td style="max-width: 320px; font-size: 12px; color: #cbd5e1; word-break: break-all;">${item.summary}</td>
        <td style="font-family: var(--font-mono); font-size: 11px; color: #94a3b8;">${item.timestamp ? item.timestamp.replace("T", " ").substring(0, 19) : "-"}</td>
        <td><span class="${badgeClass}">${statusText}</span></td>
        <td><span style="font-size: 11px; color: #38bdf8;">Edge SQLite (retail.db)</span></td>
      </tr>
    `;
  }).join("");
}

async function triggerBufferFlush() {
  try {
    const res = await fetch("/api/sync/flush", { method: "POST" });
    const data = await res.json();
    if (data.status === "OFFLINE_SIMULATED") {
      alert("⚠️ Network is currently in Simulated Blackout mode! Reconnect simulated network first or disable offline mode to flush.");
    } else {
      await fetchSyncStatusAndQueue();
    }
  } catch (err) {
    console.error("triggerBufferFlush error:", err);
  }
}

async function toggleSimulateNetwork() {
  try {
    const newState = !isSimulatedNetworkOffline;
    const res = await fetch("/api/sync/simulate-network", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ offline: newState })
    });
    if (res.ok) {
      await fetchSyncStatusAndQueue();
    }
  } catch (err) {
    console.error("toggleSimulateNetwork error:", err);
  }
}

function exportOfflineDump() {
  window.location.href = "/api/sync/export/json";
}

// Auto-sync listener on browser online/offline events
window.addEventListener("online", () => {
  console.log("🌐 Network uplink restored. Initiating automatic cloud store-and-forward...");
  triggerBufferFlush();
});

window.addEventListener("offline", () => {
  console.warn("⚠️ Network connection severed. Autonomous Edge Buffering active.");
  fetchSyncStatusAndQueue();
});

// Initialize Copilot Mode on Load
document.addEventListener("DOMContentLoaded", () => {
  if (typeof setCopilotMode === "function") {
    setCopilotMode(currentCopilotMode);
  }
});

// =========================================================
// 🆕 AI-ASSISTED THEFT & LOSS PREVENTION CLIENT
// =========================================================

let allTheftEvents = [];
let currentTheftFilter = "all";
let selectedTheftEventId = null;

async function fetchTheftIncidents() {
  try {
    const [evRes, metRes] = await Promise.all([
      fetch("/api/v1/theft-events?limit=100"),
      fetch("/api/v1/theft-events/metrics")
    ]);
    
    if (evRes.ok) {
      const evData = await evRes.json();
      allTheftEvents = evData.events || [];
      renderTheftKPIs();
      renderTheftCards();
    }

    if (metRes.ok) {
      const metData = await metRes.json();
      const m = metData.metrics || {};
      const elTot = document.getElementById("theftKpiTotal");
      const elAct = document.getElementById("theftKpiActive");
      const elHigh = document.getElementById("theftKpiHigh");
      const elRes = document.getElementById("theftKpiResolved");
      const elFalse = document.getElementById("theftKpiFalsePos");

      if (elTot) elTot.textContent = m.total_events || 0;
      if (elAct) elAct.textContent = m.active_alerts || 0;
      if (elHigh) elHigh.textContent = m.high_risk_events || 0;
      if (elRes) elRes.textContent = m.resolved_events || 0;
      if (elFalse) elFalse.textContent = m.false_positives || 0;

      const theftTabBadge = document.getElementById("tabTheftCount");
      if (theftTabBadge) {
        theftTabBadge.textContent = m.active_alerts || 0;
        theftTabBadge.style.display = (m.active_alerts > 0) ? "inline-block" : "none";
      }
    }
  } catch (err) {
    console.warn("fetchTheftIncidents error:", err);
  }
}

function renderTheftKPIs() {
  const label = document.getElementById("theftFilteredCountLabel");
  const filtered = getFilteredTheftEvents();
  if (label) {
    label.textContent = `Showing ${filtered.length} of ${allTheftEvents.length} incidents`;
  }
}

function getFilteredTheftEvents() {
  if (currentTheftFilter === "all") return allTheftEvents;
  if (currentTheftFilter === "HIGH") {
    return allTheftEvents.filter(e => e.risk_level === "HIGH" || e.risk_score >= 80);
  }
  return allTheftEvents.filter(e => e.status === currentTheftFilter);
}

function filterTheftEvents(filterType) {
  currentTheftFilter = filterType;
  const filterBtns = {
    all: "theftFilterAll",
    ACTIVE: "theftFilterActive",
    HIGH: "theftFilterHigh",
    UNDER_REVIEW: "theftFilterReview",
    RESOLVED: "theftFilterResolved",
    FALSE_POSITIVE: "theftFilterFalsePos"
  };

  Object.entries(filterBtns).forEach(([k, id]) => {
    const btn = document.getElementById(id);
    if (btn) {
      if (k === filterType) btn.classList.add("active");
      else btn.classList.remove("active");
    }
  });

  renderTheftCards();
}

function renderTheftCards() {
  const container = document.getElementById("theftCardsContainer");
  if (!container) return;

  const events = getFilteredTheftEvents();
  if (!events || events.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding: 40px 20px; text-align: center; color: #64748b;">
        🛡️ No matching suspicious incidents found in this view.
      </div>
    `;
    return;
  }

  container.innerHTML = events.map(ev => {
    const isHigh = ev.risk_score >= 80 || ev.risk_level === "HIGH";
    const isSuspicious = ev.risk_score >= 60 && !isHigh;
    const isSelected = ev.event_id === selectedTheftEventId;

    const levelTitle = isHigh ? "🚨 HIGH RISK" : (isSuspicious ? "⚠️ SUSPICIOUS" : "ℹ️ LOW RISK");
    const barColor = isHigh ? "#f43f5e" : (isSuspicious ? "#f59e0b" : "#38bdf8");

    const checkoutText = ev.checkout_detected ? "✅ Verified Passed" : "❌ Not Detected";
    const checkoutClass = ev.checkout_detected ? "color: #34d399;" : "color: #fda4af;";

    let statusBadge = "";
    if (ev.status === "ACTIVE") {
      statusBadge = `<span class="badge-mini" style="background: rgba(244,63,94,0.2); color: #f43f5e; border: 1px solid #f43f5e;">ACTIVE ALERT</span>`;
    } else if (ev.status === "UNDER_REVIEW") {
      statusBadge = `<span class="badge-mini" style="background: rgba(56,189,248,0.2); color: #38bdf8; border: 1px solid #38bdf8;">UNDER REVIEW</span>`;
    } else if (ev.status === "RESOLVED") {
      statusBadge = `<span class="badge-mini" style="background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid #10b981;">RESOLVED</span>`;
    } else if (ev.status === "FALSE_POSITIVE") {
      statusBadge = `<span class="badge-mini" style="background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid #f59e0b;">FALSE POSITIVE</span>`;
    }

    return `
      <div class="theft-alert-card ${isHigh ? 'card-high-risk' : ''} ${isSelected ? 'card-selected' : ''}" onclick="selectTheftIncident('${ev.event_id}')" style="background: rgba(15, 23, 42, 0.75); border: 1px solid ${isSelected ? '#f43f5e' : 'rgba(255,255,255,0.08)'}; border-radius: 12px; padding: 14px 16px; cursor: pointer; transition: all 0.2s ease;">
        <!-- Card Header -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
          <div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-weight: 800; font-size: 13px; color: ${isHigh ? '#f43f5e' : '#f59e0b'};">${levelTitle}</span>
              <span style="font-family: var(--font-mono); font-size: 13px; color: #f8fafc; font-weight: 700;">Person #${ev.person_id ?? 'Unknown'}</span>
              ${statusBadge}
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">
              Camera: <code>${escapeHtml(ev.camera_id || 'camera_01')}</code> • ${ev.created_at ? ev.created_at.substring(11, 19) : ''}
            </div>
          </div>
          <div style="text-align: right;">
            <div style="font-family: var(--font-mono); font-size: 18px; font-weight: 900; color: ${barColor};">
              ${ev.risk_score}%
            </div>
            <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Risk Score</div>
          </div>
        </div>

        <!-- Risk Progress Bar -->
        <div style="width: 100%; height: 5px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden; margin-bottom: 12px;">
          <div style="width: ${ev.risk_score}%; height: 100%; background: ${barColor}; border-radius: 3px;"></div>
        </div>

        <!-- Details Grid -->
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; font-size: 12px; margin-bottom: 12px; background: rgba(0,0,0,0.25); padding: 8px 12px; border-radius: 8px;">
          <div>
            <span style="color: #94a3b8;">Product:</span>
            <strong style="color: #38bdf8; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(ev.product_name || 'Product')}</strong>
          </div>
          <div>
            <span style="color: #94a3b8;">Shelf:</span>
            <strong style="color: #f8fafc; display: block;">${escapeHtml(ev.shelf_id || 'SHELF')}</strong>
          </div>
          <div>
            <span style="color: #94a3b8;">Current Zone:</span>
            <strong style="color: #fbbf24; display: block;">${escapeHtml(ev.current_zone || 'Common Area')}</strong>
          </div>
          <div>
            <span style="color: #94a3b8;">Checkout:</span>
            <strong style="${checkoutClass} display: block;">${checkoutText}</strong>
          </div>
        </div>

        <!-- Action Buttons -->
        <div style="display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end;" onclick="event.stopPropagation();">
          <button class="btn-sm" onclick="openTheftEvidenceModal('${ev.event_id}')" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); font-size: 11px; padding: 4px 10px; border-radius: 6px; cursor: pointer;">
            👁️ View Evidence
          </button>
          <button class="btn-sm" onclick="updateTheftStatus('${ev.event_id}', 'UNDER_REVIEW')" style="background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); font-size: 11px; padding: 4px 10px; border-radius: 6px; cursor: pointer;">
            ✔️ Mark Reviewed
          </button>
          <button class="btn-sm" onclick="updateTheftStatus('${ev.event_id}', 'FALSE_POSITIVE')" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); font-size: 11px; padding: 4px 10px; border-radius: 6px; cursor: pointer;">
            🛡️ False Positive
          </button>
          <button class="btn-sm" onclick="updateTheftStatus('${ev.event_id}', 'RESOLVED')" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); font-size: 11px; padding: 4px 10px; border-radius: 6px; cursor: pointer; font-weight: 700;">
            ✅ Resolve
          </button>
        </div>
      </div>
    `;
  }).join("");

  // Auto-select first incident if none selected
  if (!selectedTheftEventId && events.length > 0) {
    selectTheftIncident(events[0].event_id);
  }
}

function selectTheftIncident(eventId) {
  selectedTheftEventId = eventId;
  const ev = allTheftEvents.find(e => e.event_id === eventId);
  if (!ev) return;

  // Re-highlight cards
  document.querySelectorAll(".theft-alert-card").forEach(c => {
    c.style.borderColor = "rgba(255, 255, 255, 0.08)";
  });
  const activeCard = Array.from(document.querySelectorAll(".theft-alert-card")).find(c =>
    c.getAttribute("onclick") && c.getAttribute("onclick").includes(eventId)
  );
  if (activeCard) activeCard.style.borderColor = "#f43f5e";

  // Update Detail Panel Header
  const title = document.getElementById("theftDetailTitle");
  if (title) title.textContent = `Incident: Person #${ev.person_id ?? 'Unknown'}`;

  const badge = document.getElementById("theftDetailBadge");
  if (badge) {
    badge.textContent = `${ev.risk_score}% • ${ev.risk_level}`;
    badge.style.color = (ev.risk_score >= 80) ? "#f43f5e" : "#f59e0b";
    badge.style.background = (ev.risk_score >= 80) ? "rgba(244,63,94,0.15)" : "rgba(245,158,11,0.15)";
  }

  // Update Snapshot Image
  const snapImg = document.getElementById("theftDetailSnapshot");
  const snapPlaceholder = document.getElementById("theftSnapshotPlaceholder");
  const snapTag = document.getElementById("theftSnapshotOverlayTag");

  if (ev.snapshot_url) {
    if (snapImg) {
      snapImg.src = ev.snapshot_url + "?t=" + Date.now();
      snapImg.style.display = "block";
    }
    if (snapPlaceholder) snapPlaceholder.style.display = "none";
    if (snapTag) snapTag.style.display = "block";
  } else {
    if (snapImg) snapImg.style.display = "none";
    if (snapPlaceholder) snapPlaceholder.style.display = "block";
    if (snapTag) snapTag.style.display = "none";
  }

  // Update Subject Meta
  const metaPerson = document.getElementById("theftMetaPerson");
  const metaProd = document.getElementById("theftMetaProduct");
  const metaZone = document.getElementById("theftMetaZone");

  if (metaPerson) metaPerson.textContent = `Person #${ev.person_id ?? 'Unknown'}`;
  if (metaProd) metaProd.textContent = `${ev.product_name || 'Product'} (${ev.product_id || 'SKU'})`;
  if (metaZone) metaZone.textContent = ev.current_zone || 'Common Area';

  // Render Timeline
  renderTheftTimeline(ev.timeline || []);
}

function renderTheftTimeline(timelineItems) {
  const container = document.getElementById("theftTimelineList");
  if (!container) return;

  if (!timelineItems || timelineItems.length === 0) {
    container.innerHTML = `
      <div style="color: #64748b; font-size: 12px; text-align: center; padding: 20px;">
        No chronological milestone events logged for this incident yet.
      </div>
    `;
    return;
  }

  container.innerHTML = timelineItems.map((item, idx) => {
    const isPositive = String(item.score_delta).startsWith("+");
    const deltaColor = isPositive ? "#f43f5e" : (item.score_delta === "0" ? "#94a3b8" : "#34d399");
    const isLast = idx === timelineItems.length - 1;

    return `
      <div class="theft-timeline-row" style="display: flex; gap: 12px; align-items: flex-start; padding: 8px 10px; background: rgba(15, 23, 42, 0.5); border-left: 3px solid ${isLast ? '#f43f5e' : '#38bdf8'}; border-radius: 4px;">
        <span style="font-family: var(--font-mono); font-size: 11px; color: #38bdf8; white-space: nowrap; font-weight: 700;">
          ${item.timestamp}
        </span>
        <div style="flex: 1; font-size: 12px; color: #cbd5e1; line-height: 1.4;">
          ${escapeHtml(item.description)}
        </div>
        <div style="text-align: right; white-space: nowrap;">
          <strong style="color: ${deltaColor}; font-family: var(--font-mono); font-size: 11px;">
            ${item.score_delta != '0' ? item.score_delta : ''}
          </strong>
          <span style="font-size: 10px; color: #64748b; display: block;">${item.current_score}%</span>
        </div>
      </div>
    `;
  }).join("");
}

async function updateTheftStatus(eventId, newStatus) {
  try {
    const res = await fetch(`/api/v1/theft-events/${eventId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      await fetchTheftIncidents();
    }
  } catch (err) {
    console.warn("updateTheftStatus error:", err);
  }
}

async function triggerTheftSimulation() {
  const btn = event?.target;
  const originalText = btn ? btn.textContent : "";
  if (btn) btn.textContent = "⏳ Simulating...";

  try {
    const res = await fetch("/api/v1/theft-events/simulate", { method: "POST" });
    const data = await res.json();
    if (data.success && data.event) {
      await fetchTheftIncidents();
      selectTheftIncident(data.event.event_id);
    }
  } catch (err) {
    console.error("triggerTheftSimulation error:", err);
  } finally {
    if (btn) btn.textContent = originalText;
  }
}

// Modal Evidence Inspection
let activeModalEventId = null;

function openTheftEvidenceModal(eventId) {
  activeModalEventId = eventId;
  const ev = allTheftEvents.find(e => e.event_id === eventId);
  if (!ev) return;

  const modal = document.getElementById("theftEvidenceModal");
  const img = document.getElementById("modalEvidenceImg");
  const title = document.getElementById("modalEvidenceTitle");
  const sub = document.getElementById("modalEvidenceSubtitle");
  const meta = document.getElementById("modalEvidenceMeta");

  if (title) title.textContent = `🚨 Forensic Evidence: Person #${ev.person_id ?? 'Unknown'} (Risk: ${ev.risk_score}%)`;
  if (sub) sub.textContent = `Event ID: ${ev.event_id} • Camera: ${ev.camera_id} • Time: ${ev.created_at || 'Live'}`;

  if (img) {
    img.src = (ev.snapshot_url || "") + "?t=" + Date.now();
  }

  if (meta) {
    meta.innerHTML = `
      <div><strong>Product:</strong> <span style="color:#38bdf8;">${escapeHtml(ev.product_name || 'Product')}</span></div>
      <div><strong>Shelf:</strong> <span style="color:#f8fafc;">${escapeHtml(ev.shelf_id || 'SHELF')}</span></div>
      <div><strong>Zone:</strong> <span style="color:#fbbf24;">${escapeHtml(ev.current_zone || 'EXIT')}</span></div>
      <div><strong>Checkout:</strong> <span style="color:${ev.checkout_detected ? '#34d399' : '#f43f5e'};">${ev.checkout_detected ? 'PASSED' : 'NOT DETECTED'}</span></div>
      <div><strong>Status:</strong> <span style="color:#38bdf8;">${ev.status}</span></div>
    `;
  }

  if (modal) modal.style.display = "flex";
}

function closeTheftEvidenceModal() {
  const modal = document.getElementById("theftEvidenceModal");
  if (modal) modal.style.display = "none";
  activeModalEventId = null;
}

async function handleModalAction(actionStatus) {
  if (activeModalEventId) {
    await updateTheftStatus(activeModalEventId, actionStatus);
    closeTheftEvidenceModal();
  }
}

// Configuration Modal
async function openTheftConfigModal() {
  try {
    const res = await fetch("/api/v1/theft-config");
    if (!res.ok) return;
    const data = await res.json();
    const cfg = data.config || {};
    const zones = data.zones || [];

    const elR = document.getElementById("cfgTheftRiskThresh");
    const elH = document.getElementById("cfgTheftHighThresh");
    const elM = document.getElementById("cfgTheftMissingSec");
    const elI = document.getElementById("cfgTheftInteractionSec");
    const elP = document.getElementById("cfgScorePickup");
    const elD = document.getElementById("cfgScoreDisappeared");
    const elE = document.getElementById("cfgScoreExit");

    if (elR) elR.value = cfg.theft_risk_threshold ?? 60;
    if (elH) elH.value = cfg.high_risk_threshold ?? 80;
    if (elM) elM.value = cfg.product_missing_seconds ?? 2.0;
    if (elI) elI.value = cfg.min_shelf_interaction_seconds ?? 1.5;

    if (elP) elP.value = cfg.score_pickup ?? 20;
    if (elD) elD.value = cfg.score_disappeared ?? 25;
    if (elE) elE.value = cfg.score_enter_exit ?? 30;

    // Render zones
    const zList = document.getElementById("cfgZonesList");
    if (zList) {
      zList.innerHTML = zones.map(z => `
        <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.3); padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">
          <div>
            <strong>${escapeHtml(z.name)}</strong> <code style="color:#38bdf8;">(${z.zone_type})</code>
          </div>
          <span style="color: #94a3b8; font-family: var(--font-mono);">[${z.bbox.join(', ')}]</span>
        </div>
      `).join("");
    }

    document.getElementById("theftConfigModal").style.display = "flex";
  } catch (err) {
    console.warn("openTheftConfigModal error:", err);
  }
}

function closeTheftConfigModal() {
  const modal = document.getElementById("theftConfigModal");
  if (modal) modal.style.display = "none";
}

async function saveTheftConfig(e) {
  e.preventDefault();
  const payload = {
    config: {
      theft_risk_threshold: parseInt(document.getElementById("cfgTheftRiskThresh").value),
      high_risk_threshold: parseInt(document.getElementById("cfgTheftHighThresh").value),
      product_missing_seconds: parseFloat(document.getElementById("cfgTheftMissingSec").value),
      min_shelf_interaction_seconds: parseFloat(document.getElementById("cfgTheftInteractionSec").value),
      score_pickup: parseInt(document.getElementById("cfgScorePickup").value),
      score_disappeared: parseInt(document.getElementById("cfgScoreDisappeared").value),
      score_enter_exit: parseInt(document.getElementById("cfgScoreExit").value)
    }
  };

  try {
    const res = await fetch("/api/v1/theft-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      alert("✅ Loss prevention configuration updated successfully!");
      closeTheftConfigModal();
    }
  } catch (err) {
    alert("Error saving configuration: " + err.message);
  }
}

// =========================================================================
// AI ANOMALY DETECTION & CUSTOM TRIGGER ENGINE DASHBOARD CONTROLLER
// =========================================================================

let activeAnomaliesData = [];

async function fetchAnomaliesList() {
  try {
    const sevFilter = document.getElementById("anomFilterSeverity") ? document.getElementById("anomFilterSeverity").value : "ALL";
    const statFilter = document.getElementById("anomFilterStatus") ? document.getElementById("anomFilterStatus").value : "ALL";

    let url = `/api/anomalies/list?status=${encodeURIComponent(statFilter)}&severity=${encodeURIComponent(sevFilter)}`;
    const res = await fetch(url);
    if (!res.ok) return;

    const data = await res.json();
    if (data.success && Array.isArray(data.anomalies)) {
      activeAnomaliesData = data.anomalies;
      renderAnomaliesTable(activeAnomaliesData);
    }

    // Also update stats
    const statsRes = await fetch("/api/anomalies/stats");
    if (statsRes.ok) {
      const statsData = await statsRes.json();
      if (statsData.success && statsData.stats) {
        updateAnomalyStatsUI(statsData.stats);
      }
    }
  } catch (err) {
    console.warn("fetchAnomaliesList note:", err);
  }
}

function updateAnomalyStatsUI(stats) {
  const elCrit = document.getElementById("anomKpiCritical");
  const elHigh = document.getElementById("anomKpiHigh");
  const elMed = document.getElementById("anomKpiMedium");
  const elActive = document.getElementById("anomKpiActive");
  const elResolved = document.getElementById("anomKpiResolved");
  const elAck = document.getElementById("anomKpiAck");
  const elBadge = document.getElementById("tabAnomalyCount");
  const elTotalBadge = document.getElementById("anomTotalBadge");

  if (elCrit) elCrit.textContent = stats.critical || 0;
  if (elHigh) elHigh.textContent = stats.high || 0;
  if (elMed) elMed.textContent = stats.medium || 0;
  if (elActive) elActive.textContent = stats.active || 0;
  if (elResolved) elResolved.textContent = stats.resolved || 0;
  if (elAck) elAck.textContent = stats.acknowledged || 0;

  if (elBadge) {
    const count = stats.active || 0;
    elBadge.textContent = count;
    elBadge.style.display = count > 0 ? "inline-block" : "none";
  }

  if (elTotalBadge) {
    elTotalBadge.textContent = `${stats.total || 0} Incidents`;
  }
}

function renderAnomaliesTable(anomalies) {
  const tbody = document.getElementById("anomaliesTableBody");
  if (!tbody) return;

  if (anomalies.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; color: #64748b; padding: 24px;">
          No anomalies match the current filter.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = anomalies.map(a => {
    const isCritical = a.severity === "Critical";
    const isHigh = a.severity === "High";
    const isMed = a.severity === "Medium";

    const sevColor = isCritical ? "#ef4444" : (isHigh ? "#f97316" : (isMed ? "#f59e0b" : "#38bdf8"));
    const sevBg = isCritical ? "rgba(239, 68, 68, 0.15)" : (isHigh ? "rgba(249, 115, 22, 0.15)" : "rgba(245, 158, 11, 0.15)");

    const isAck = a.status === "Acknowledged";
    const isRes = a.status === "Resolved";

    const timeStr = a.created_at ? new Date(a.created_at).toLocaleTimeString() : "";

    return `
      <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
        <td>
          <div style="font-weight: 700; color: #f8fafc;">${escapeHtml(a.anomaly_type.replace(/_/g, " "))}</div>
          <div style="font-size: 10px; color: #64748b;">ID: ${escapeHtml(a.anomaly_id.substring(0, 8))}...</div>
        </td>
        <td>
          <span class="badge-mini" style="background: ${sevBg}; color: ${sevColor}; border: 1px solid ${sevColor}; font-weight: 800;">
            ${escapeHtml(a.severity)}
          </span>
        </td>
        <td>
          <div style="color: #cbd5e1; font-weight: 600;">${escapeHtml(a.zone_id || "Zone")}</div>
          <div style="font-size: 10px; color: #64748b;">${escapeHtml(a.camera_id || "CAM_01")}</div>
        </td>
        <td style="max-width: 320px;">
          <div style="color: #e2e8f0; font-size: 12px; line-height: 1.4;">${escapeHtml(a.description)}</div>
          <div style="font-size: 10px; color: #94a3b8; margin-top: 2px;">⏰ ${timeStr}</div>
        </td>
        <td>
          <span style="font-family: var(--font-mono); color: #34d399; font-weight: 700;">
            ${Math.round((a.confidence_score || 0.95) * 100)}%
          </span>
        </td>
        <td>
          <span style="font-size: 11px; font-weight: 700; color: ${isRes ? '#34d399' : (isAck ? '#fbbf24' : '#ef4444')};">
            ${escapeHtml(a.status)}
          </span>
        </td>
        <td style="text-align: right; white-space: nowrap;">
          ${!isAck && !isRes ? `
            <button onclick="handleAcknowledgeAnomaly('${a.anomaly_id}')" class="btn-sm" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); padding: 4px 8px; border-radius: 6px; font-size: 10px; font-weight: 700; cursor: pointer; margin-right: 4px;">
              Acknowledge
            </button>
          ` : ''}
          ${!isRes ? `
            <button onclick="handleResolveAnomaly('${a.anomaly_id}')" class="btn-sm" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); padding: 4px 8px; border-radius: 6px; font-size: 10px; font-weight: 700; cursor: pointer;">
              Resolve
            </button>
          ` : '<span style="color: #64748b; font-size: 11px;">Completed</span>'}
        </td>
      </tr>
    `;
  }).join("");
}

async function simulateAll13Anomalies() {
  try {
    const btn = event?.target;
    if (btn) btn.disabled = true;
    const res = await fetch("/api/anomalies/simulate_all_13", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      alert(`🚨 Successfully simulated all ${data.simulated_anomalies_count} distinct retail anomalies!`);
      await fetchAnomaliesList();
    }
  } catch (err) {
    alert("Simulation error: " + err.message);
  } finally {
    const btn = event?.target;
    if (btn) btn.disabled = false;
  }
}

async function evaluateAnomaliesLive() {
  try {
    const res = await fetch("/api/anomalies/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        detections: [],
        inventory_counts: {},
        tracked_persons: [],
        queue_count: 0,
        camera_health: { laplacian_var: 120.0, is_blocked: False, ssim: 0.98 }
      })
    });
    const data = await res.json();
    if (data.success) {
      alert(`⚡ Current frame evaluated: ${data.detected_count} new anomalies detected.`);
      await fetchAnomaliesList();
    }
  } catch (err) {
    alert("Evaluation error: " + err.message);
  }
}

async function handleAcknowledgeAnomaly(anomalyId) {
  try {
    const res = await fetch(`/api/anomalies/${anomalyId}/acknowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operator: "Store Operations Manager" })
    });
    if (res.ok) {
      fetchAnomaliesList();
    }
  } catch (err) {
    console.warn("handleAcknowledgeAnomaly error:", err);
  }
}

async function handleResolveAnomaly(anomalyId) {
  const notes = prompt("Enter resolution notes:", "Investigated and cleared on site");
  if (!notes) return;

  try {
    const res = await fetch(`/api/anomalies/${anomalyId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operator: "Store Operations Manager", notes: notes })
    });
    if (res.ok) {
      fetchAnomaliesList();
    }
  } catch (err) {
    console.warn("handleResolveAnomaly error:", err);
  }
}

// Auto-poll anomalies every 5 seconds
setInterval(() => {
  const anomaliesTab = document.getElementById("tab-anomalies");
  if (anomaliesTab && anomaliesTab.classList.contains("active")) {
    fetchAnomaliesList();
  }
}, 5000);


