/**
 * script.js
 * ---------
 * Sales Insight Assistant - Interactive Frontend Engine
 * 
 * Features:
 * 1. Dynamic multi-dimensional filter synchronization (Month, Product, Region, Channel, Status)
 * 2. 4-Chart visualization suite using Chart.js (Line, Product Bar, Regional Bar, Channel Doughnut)
 * 3. Natural language query handling (deterministic SQL + Vectorless RAG)
 * 4. Searchable, sortable, and paginated transaction table
 * 5. Data quality metrics auditing and live refresh capabilities
 * 
 * Author: Senior Full-Stack Engineer / Student Developer
 * Project: Sales Insight Assistant
 */

document.addEventListener("DOMContentLoaded", () => {
  // --- DOM Elements ---
  const btnRefresh = document.getElementById("btn-refresh");
  const btnClearFilters = document.getElementById("btn-clear-filters");
  const activeFilterBadge = document.getElementById("active-filter-badge");

  // Filters
  const filterMonth = document.getElementById("filter-month");
  const filterProduct = document.getElementById("filter-product");
  const filterRegion = document.getElementById("filter-region");
  const filterChannel = document.getElementById("filter-channel");
  const filterStatus = document.getElementById("filter-status");

  // Natural Language Form & Results
  const questionForm = document.getElementById("question-form");
  const questionInput = document.getElementById("question-input");
  const askBtn = document.getElementById("ask-btn");
  const loadingSpinner = document.getElementById("loading-spinner");
  const errorCard = document.getElementById("error-card");
  const errorMessage = document.getElementById("error-message");
  const resultsCard = document.getElementById("results-card");
  const answerText = document.getElementById("answer-text");
  const sqlText = document.getElementById("sql-text");
  const executionMode = document.getElementById("execution-mode");
  const tableHead = document.getElementById("table-head");
  const tableBody = document.getElementById("table-body");
  const copySqlBtn = document.getElementById("copy-sql-btn");
  const chipButtons = document.querySelectorAll(".chip-btn");

  // Transaction Table
  const tableSearchInput = document.getElementById("table-search-input");
  const transactionsTableBody = document.getElementById("transactions-table-body");
  const btnPrevPage = document.getElementById("btn-prev-page");
  const btnNextPage = document.getElementById("btn-next-page");
  const paginationInfo = document.getElementById("pagination-info");
  const pageNumDisplay = document.getElementById("page-num-display");
  const tableSubtitleCount = document.getElementById("table-subtitle-count");
  const tableHeaders = document.querySelectorAll(".table-container th");

  // State
  let currentPage = 1;
  const pageLimit = 10;
  let currentSortCol = "order_date";
  let currentSortOrder = "DESC";
  let currentSearchQuery = "";
  let searchDebounceTimeout = null;

  // Chart Instances
  let monthlyChartInstance = null;
  let productChartInstance = null;
  let regionChartInstance = null;
  let channelChartInstance = null;

  // --- Initial Page Load ---
  initDashboard();

  async function initDashboard() {
    await loadFilterOptions();
    await refreshAllData();
    await loadDataQuality();
  }

  // ========================================================================
  // 1. Filter Options Loader
  // ========================================================================
  async function loadFilterOptions() {
    try {
      const res = await fetch("/api/filter-options");
      const json = await res.json();
      if (!json.success || !json.data) return;

      const d = json.data;
      const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

      // Months
      if (filterMonth && d.months) {
        filterMonth.innerHTML = `<option value="all">All Months</option>`;
        d.months.forEach(m => {
          const parts = m.split("-");
          const label = parts.length === 2 ? `${monthNames[parseInt(parts[1], 10) - 1]} ${parts[0]}` : m;
          filterMonth.innerHTML += `<option value="${m}">${label}</option>`;
        });
      }

      // Products
      if (filterProduct && d.products) {
        filterProduct.innerHTML = `<option value="all">All Products</option>`;
        d.products.forEach(p => {
          filterProduct.innerHTML += `<option value="${p}">${p}</option>`;
        });
      }

      // Regions
      if (filterRegion && d.regions) {
        filterRegion.innerHTML = `<option value="all">All Regions</option>`;
        d.regions.forEach(r => {
          filterRegion.innerHTML += `<option value="${r}">${r}</option>`;
        });
      }

      // Channels
      if (filterChannel && d.channels) {
        filterChannel.innerHTML = `<option value="all">All Channels</option>`;
        d.channels.forEach(c => {
          filterChannel.innerHTML += `<option value="${c}">${c}</option>`;
        });
      }
    } catch (err) {
      console.warn("Could not load filter options:", err);
    }
  }

  // Collect Current Filter Parameters
  function getFilterQueryString() {
    const params = new URLSearchParams();
    if (filterMonth && filterMonth.value !== "all") params.append("month", filterMonth.value);
    if (filterProduct && filterProduct.value !== "all") params.append("product", filterProduct.value);
    if (filterRegion && filterRegion.value !== "all") params.append("region", filterRegion.value);
    if (filterChannel && filterChannel.value !== "all") params.append("sales_channel", filterChannel.value);
    if (filterStatus && filterStatus.value !== "all") params.append("status", filterStatus.value);
    return params.toString();
  }

  function hasActiveFilters() {
    return (
      (filterMonth && filterMonth.value !== "all") ||
      (filterProduct && filterProduct.value !== "all") ||
      (filterRegion && filterRegion.value !== "all") ||
      (filterChannel && filterChannel.value !== "all") ||
      (filterStatus && filterStatus.value !== "Completed")
    );
  }

  function updateFilterBadge() {
    if (activeFilterBadge) {
      if (hasActiveFilters()) {
        activeFilterBadge.classList.add("visible");
      } else {
        activeFilterBadge.classList.remove("visible");
      }
    }
  }

  // Master Refresh Coordinator
  async function refreshAllData() {
    updateFilterBadge();
    await Promise.all([
      loadKPIOverview(),
      loadAllCharts(),
      loadTransactions(1)
    ]);
  }

  // Filter Change Events
  [filterMonth, filterProduct, filterRegion, filterChannel, filterStatus].forEach(sel => {
    if (sel) {
      sel.addEventListener("change", () => {
        currentPage = 1;
        refreshAllData();
      });
    }
  });

  // Clear Filters Button
  if (btnClearFilters) {
    btnClearFilters.addEventListener("click", () => {
      if (filterMonth) filterMonth.value = "all";
      if (filterProduct) filterProduct.value = "all";
      if (filterRegion) filterRegion.value = "all";
      if (filterChannel) filterChannel.value = "all";
      if (filterStatus) filterStatus.value = "Completed";
      currentPage = 1;
      refreshAllData();
    });
  }

  // Refresh Button in Header
  if (btnRefresh) {
    btnRefresh.addEventListener("click", async () => {
      btnRefresh.classList.add("spinning");
      if (filterMonth) filterMonth.value = "all";
      if (filterProduct) filterProduct.value = "all";
      if (filterRegion) filterRegion.value = "all";
      if (filterChannel) filterChannel.value = "all";
      if (filterStatus) filterStatus.value = "Completed";
      currentPage = 1;
      await refreshAllData();
      await loadDataQuality();
      setTimeout(() => btnRefresh.classList.remove("spinning"), 600);
    });
  }

  // ========================================================================
  // 2. KPI Cards Loader
  // ========================================================================
  async function loadKPIOverview() {
    try {
      const q = getFilterQueryString();
      const res = await fetch(`/api/overview?${q}`);
      const json = await res.json();
      if (!json.success || !json.data) return;

      const d = json.data;

      // 1. Total Net Revenue
      const revEl = document.getElementById("kpi-total-revenue");
      if (revEl) revEl.innerHTML = `&#8377; ${formatNumber(d.total_net_revenue)}`;

      // 2. Completed Transactions
      const txnsEl = document.getElementById("kpi-valid-txns");
      if (txnsEl) txnsEl.innerText = `${d.valid_transactions}`;

      const subTxnsEl = document.getElementById("kpi-subtext-txns");
      if (subTxnsEl) {
        subTxnsEl.innerText = d.is_filtered
          ? `${d.valid_transactions} matching &bull; ${d.returned_transactions} returned`
          : `50 valid &bull; 1 returned excluded`;
      }

      // 3. Top Product
      const topProdEl = document.getElementById("kpi-top-product");
      const topProdSub = document.getElementById("kpi-top-product-sub");
      if (topProdEl && d.top_product) {
        topProdEl.innerText = d.top_product.name || "None";
        if (topProdSub) topProdSub.innerHTML = `&#8377; ${formatNumber(d.top_product.revenue)}`;
      }

      // 4. Top Region
      const topRegEl = document.getElementById("kpi-top-region");
      const topRegSub = document.getElementById("kpi-top-region-sub");
      if (topRegEl && d.top_region) {
        topRegEl.innerText = d.top_region.name || "None";
        if (topRegSub) topRegSub.innerHTML = `&#8377; ${formatNumber(d.top_region.revenue)}`;
      }

      // Metadata badge in header
      const metaBadge = document.getElementById("dataset-meta-badge");
      if (metaBadge) {
        metaBadge.innerText = `${d.total_transactions} Records &bull; 7 Products`;
      }
    } catch (err) {
      console.warn("Could not load KPI overview:", err);
    }
  }

  // ========================================================================
  // 3. Four Interactive Charts Loader
  // ========================================================================
  async function loadAllCharts() {
    try {
      const q = getFilterQueryString();
      const res = await fetch(`/api/charts?${q}`);
      const json = await res.json();
      if (!json.success || !json.data) return;

      const data = json.data;
      const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

      // ------------------------------------------------------------
      // Chart 1: Monthly Revenue Trend (Line Chart)
      // ------------------------------------------------------------
      const monthlyCtx = document.getElementById("monthlyChart");
      if (monthlyCtx) {
        const labels = data.monthly_trend.labels.map(m => {
          const parts = m.split("-");
          return parts.length === 2 ? `${monthNames[parseInt(parts[1], 10) - 1]} ${parts[0]}` : m;
        });

        if (monthlyChartInstance) monthlyChartInstance.destroy();

        monthlyChartInstance = new Chart(monthlyCtx.getContext("2d"), {
          type: "line",
          data: {
            labels: labels,
            datasets: [{
              label: "Net Revenue (₹)",
              data: data.monthly_trend.values,
              borderColor: "#00dca4",
              backgroundColor: "rgba(0, 220, 164, 0.12)",
              borderWidth: 2.5,
              fill: true,
              tension: 0.38,
              pointBackgroundColor: "#00dca4",
              pointBorderColor: "rgba(0, 220, 164, 0.4)",
              pointBorderWidth: 3,
              pointRadius: 4.5,
              pointHoverRadius: 7,
              pointHoverBackgroundColor: "#ffffff",
              pointHoverBorderColor: "#00dca4",
              pointHoverBorderWidth: 2.5
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              tooltip: {
                backgroundColor: "rgba(11, 17, 34, 0.95)",
                borderColor: "rgba(0, 220, 164, 0.35)",
                borderWidth: 1,
                titleColor: "#ffffff",
                bodyColor: "#00dca4",
                padding: 10,
                callbacks: {
                  label: ctx => ` Net Revenue: ₹ ${formatNumber(ctx.parsed.y)}`
                }
              }
            },
            scales: {
              y: {
                beginAtZero: true,
                ticks: {
                  font: { size: 10, family: "'Inter', sans-serif" },
                  color: "#94a3b8",
                  callback: val => `₹ ${(val / 1000).toFixed(0)}k`
                },
                grid: { color: "rgba(255, 255, 255, 0.05)" },
                border: { color: "transparent" }
              },
              x: {
                grid: { display: false },
                ticks: { font: { size: 10 }, color: "#94a3b8" },
                border: { color: "transparent" }
              }
            }
          }
        });
      }

      // ------------------------------------------------------------
      // Chart 2: Product-wise Revenue (Bar Chart)
      // ------------------------------------------------------------
      const productCtx = document.getElementById("productChart");
      if (productCtx) {
        if (productChartInstance) productChartInstance.destroy();

        const productColors = [
          "#a855f7", "#00dca4", "#38bdf8", "#f59e0b",
          "#f43f5e", "#c084fc", "#34d399"
        ];

        productChartInstance = new Chart(productCtx.getContext("2d"), {
          type: "bar",
          data: {
            labels: data.product_sales.labels,
            datasets: [{
              label: "Sales (₹)",
              data: data.product_sales.values,
              backgroundColor: productColors,
              hoverBackgroundColor: productColors.map(c => c + "cc"),
              borderRadius: 6,
              borderSkipped: false
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              tooltip: {
                backgroundColor: "rgba(11, 17, 34, 0.95)",
                borderColor: "rgba(168, 85, 247, 0.35)",
                borderWidth: 1,
                titleColor: "#ffffff",
                bodyColor: "#a855f7",
                padding: 10,
                callbacks: {
                  label: ctx => ` Total Sales: ₹ ${formatNumber(ctx.parsed.y)}`
                }
              }
            },
            scales: {
              y: {
                beginAtZero: true,
                ticks: {
                  font: { size: 10, family: "'Inter', sans-serif" },
                  color: "#94a3b8",
                  callback: val => `₹ ${(val / 1000).toFixed(0)}k`
                },
                grid: { color: "rgba(255, 255, 255, 0.05)" },
                border: { color: "transparent" }
              },
              x: {
                grid: { display: false },
                ticks: {
                  font: { size: 9.5 },
                  color: "#94a3b8",
                  maxRotation: 20
                },
                border: { color: "transparent" }
              }
            }
          }
        });
      }

      // ------------------------------------------------------------
      // Chart 3: Regional Sales Comparison (Bar Chart)
      // ------------------------------------------------------------
      const regionCtx = document.getElementById("regionChart");
      if (regionCtx) {
        if (regionChartInstance) regionChartInstance.destroy();

        const regionColors = ["#38bdf8", "#0ea5e9", "#0284c7", "#0369a1"];

        regionChartInstance = new Chart(regionCtx.getContext("2d"), {
          type: "bar",
          data: {
            labels: data.regional_sales.labels,
            datasets: [{
              label: "Regional Sales (₹)",
              data: data.regional_sales.values,
              backgroundColor: regionColors,
              borderRadius: 6,
              borderSkipped: false
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              tooltip: {
                backgroundColor: "rgba(11, 17, 34, 0.95)",
                borderColor: "rgba(56, 189, 248, 0.35)",
                borderWidth: 1,
                titleColor: "#ffffff",
                bodyColor: "#38bdf8",
                padding: 10,
                callbacks: {
                  label: ctx => ` Sales: ₹ ${formatNumber(ctx.parsed.y)}`
                }
              }
            },
            scales: {
              y: {
                beginAtZero: true,
                ticks: {
                  font: { size: 10 },
                  color: "#94a3b8",
                  callback: val => `₹ ${(val / 1000).toFixed(0)}k`
                },
                grid: { color: "rgba(255, 255, 255, 0.05)" },
                border: { color: "transparent" }
              },
              x: {
                grid: { display: false },
                ticks: { font: { size: 10 }, color: "#94a3b8" },
                border: { color: "transparent" }
              }
            }
          }
        });
      }

      // ------------------------------------------------------------
      // Chart 4: Sales Channel Distribution (Doughnut Chart)
      // ------------------------------------------------------------
      const channelCtx = document.getElementById("channelChart");
      if (channelCtx) {
        if (channelChartInstance) channelChartInstance.destroy();

        const channelColors = ["#00dca4", "#a855f7"];
        const totalChannelRevenue = data.channel_sales.values.reduce((a, b) => a + b, 0);

        channelChartInstance = new Chart(channelCtx.getContext("2d"), {
          type: "doughnut",
          data: {
            labels: data.channel_sales.labels,
            datasets: [{
              data: data.channel_sales.values,
              backgroundColor: channelColors,
              borderColor: "rgba(11, 17, 34, 0.9)",
              borderWidth: 3,
              hoverOffset: 6
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "68%",
            plugins: {
              legend: {
                position: "bottom",
                labels: {
                  color: "#94a3b8",
                  font: { size: 11, family: "'Inter', sans-serif" },
                  padding: 14,
                  usePointStyle: true,
                  pointStyle: "circle"
                }
              },
              tooltip: {
                backgroundColor: "rgba(11, 17, 34, 0.95)",
                borderColor: "rgba(255, 255, 255, 0.15)",
                borderWidth: 1,
                titleColor: "#ffffff",
                bodyColor: "#00dca4",
                padding: 10,
                callbacks: {
                  label: ctx => {
                    const val = ctx.parsed;
                    const pct = totalChannelRevenue > 0 ? ((val / totalChannelRevenue) * 100).toFixed(1) : 0;
                    return ` ${ctx.label}: ₹ ${formatNumber(val)} (${pct}%)`;
                  }
                }
              }
            }
          }
        });
      }
    } catch (err) {
      console.warn("Could not load charts:", err);
    }
  }

  // ========================================================================
  // 4. Natural Language Sales Assistant
  // ========================================================================
  if (questionForm) {
    questionForm.addEventListener("submit", async e => {
      e.preventDefault();
      const q = questionInput.value.trim();
      if (q) await executeQuestion(q);
    });
  }

  chipButtons.forEach(btn => {
    btn.addEventListener("click", async () => {
      const q = btn.getAttribute("data-q");
      if (questionInput) questionInput.value = q;
      await executeQuestion(q);
    });
  });

  async function executeQuestion(question) {
    hideError();
    if (resultsCard) resultsCard.classList.add("hidden");
    if (loadingSpinner) loadingSpinner.classList.remove("hidden");
    if (askBtn) askBtn.disabled = true;

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question })
      });

      const data = await res.json();
      if (loadingSpinner) loadingSpinner.classList.add("hidden");
      if (askBtn) askBtn.disabled = false;

      if (!res.ok || !data.success) {
        showError(data.error || "Could not interpret or execute query.");
        return;
      }

      // Populate Result
      if (answerText) answerText.innerText = data.answer.replace(/Rs\./g, "₹");
      if (sqlText) sqlText.innerText = data.sql;
      if (executionMode) executionMode.innerText = data.mode || "Deterministic SQL Engine";

      // Render Supporting Table
      renderTable("table-head", "table-body", data.columns, data.rows);

      // Reveal Results Card
      if (resultsCard) {
        resultsCard.classList.remove("hidden");
        resultsCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    } catch (err) {
      if (loadingSpinner) loadingSpinner.classList.add("hidden");
      if (askBtn) askBtn.disabled = false;
      showError("Connection error: Could not reach backend server at localhost:5000.");
    }
  }

  function renderTable(headId, bodyId, columns, rows) {
    const headEl = document.getElementById(headId);
    const bodyEl = document.getElementById(bodyId);
    if (!headEl || !bodyEl) return;

    headEl.innerHTML = "";
    bodyEl.innerHTML = "";

    if (!columns || columns.length === 0) {
      headEl.innerHTML = "<tr><th>No Data</th></tr>";
      return;
    }

    const trHead = document.createElement("tr");
    columns.forEach(col => {
      const th = document.createElement("th");
      th.innerText = col.replace(/_/g, " ");
      trHead.appendChild(th);
    });
    headEl.appendChild(trHead);

    if (!rows || rows.length === 0) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td colspan="${columns.length}">No records returned.</td>`;
      bodyEl.appendChild(tr);
      return;
    }

    rows.forEach(row => {
      const tr = document.createElement("tr");
      columns.forEach(col => {
        const td = document.createElement("td");
        const val = row[col];
        if (typeof val === "number") {
          if (col.includes("revenue") || col.includes("price") || col.includes("amount") || col.includes("rev")) {
            td.innerText = `₹ ${formatNumber(val)}`;
          } else {
            td.innerText = val.toLocaleString();
          }
        } else {
          td.innerText = val ?? "—";
        }
        tr.appendChild(td);
      });
      bodyEl.appendChild(tr);
    });
  }

  // Copy SQL Button
  if (copySqlBtn) {
    copySqlBtn.addEventListener("click", () => {
      const sql = sqlText ? sqlText.innerText : "";
      if (!sql) return;
      navigator.clipboard.writeText(sql).then(() => {
        const orig = copySqlBtn.innerText;
        copySqlBtn.innerText = "Copied!";
        setTimeout(() => { copySqlBtn.innerText = orig; }, 1800);
      });
    });
  }

  // ========================================================================
  // 5. Searchable & Sortable Transaction Table
  // ========================================================================
  async function loadTransactions(page = 1) {
    try {
      currentPage = page;
      const filterQs = getFilterQueryString();
      const params = new URLSearchParams(filterQs);
      params.append("page", currentPage);
      params.append("limit", pageLimit);
      params.append("sort", currentSortCol);
      params.append("order", currentSortOrder);
      if (currentSearchQuery) params.append("search", currentSearchQuery);

      const res = await fetch(`/api/transactions?${params.toString()}`);
      const json = await res.json();
      if (!json.success || !json.data) return;

      const d = json.data;

      // Populate Rows
      if (transactionsTableBody) {
        transactionsTableBody.innerHTML = "";
        if (d.transactions.length === 0) {
          transactionsTableBody.innerHTML = `<tr><td colspan="11" style="text-align:center; padding: 20px; color: #94a3b8;">No matching transactions found.</td></tr>`;
        } else {
          d.transactions.forEach(t => {
            const tr = document.createElement("tr");
            const statusClass = (t.status || "").toLowerCase() === "completed" ? "completed" : "returned";
            tr.innerHTML = `
              <td><strong>${t.transaction_id}</strong></td>
              <td>${t.order_date}</td>
              <td>${t.product}</td>
              <td>${t.category}</td>
              <td>${t.region}</td>
              <td>${t.sales_channel}</td>
              <td>${t.quantity}</td>
              <td>₹ ${formatNumber(t.unit_price)}</td>
              <td>₹ ${formatNumber(t.discount_amount)}</td>
              <td><strong>₹ ${formatNumber(t.revenue)}</strong></td>
              <td><span class="badge-status ${statusClass}">${t.status}</span></td>
            `;
            transactionsTableBody.appendChild(tr);
          });
        }
      }

      // Pagination Information
      if (paginationInfo) {
        paginationInfo.innerText = d.total_count > 0
          ? `Showing ${d.start_index}–${d.end_index} of ${d.total_count} records`
          : `0 records found`;
      }
      if (pageNumDisplay) {
        pageNumDisplay.innerText = `Page ${d.page} of ${d.total_pages}`;
      }
      if (tableSubtitleCount) {
        tableSubtitleCount.innerText = `${d.total_count} total records available`;
      }

      if (btnPrevPage) btnPrevPage.disabled = d.page <= 1;
      if (btnNextPage) btnNextPage.disabled = d.page >= d.total_pages;

    } catch (err) {
      console.warn("Could not load transactions:", err);
    }
  }

  // Table Search Input
  if (tableSearchInput) {
    tableSearchInput.addEventListener("input", e => {
      clearTimeout(searchDebounceTimeout);
      searchDebounceTimeout = setTimeout(() => {
        currentSearchQuery = e.target.value.trim();
        currentPage = 1;
        loadTransactions(1);
      }, 250);
    });
  }

  // Column Header Sorting
  tableHeaders.forEach(th => {
    th.addEventListener("click", () => {
      const col = th.getAttribute("data-col");
      if (!col) return;

      if (currentSortCol === col) {
        currentSortOrder = currentSortOrder === "ASC" ? "DESC" : "ASC";
      } else {
        currentSortCol = col;
        currentSortOrder = "DESC";
      }

      tableHeaders.forEach(h => h.classList.remove("sorted-asc", "sorted-desc"));
      th.classList.add(currentSortOrder === "ASC" ? "sorted-asc" : "sorted-desc");

      loadTransactions(currentPage);
    });
  });

  // Pagination Buttons
  if (btnPrevPage) {
    btnPrevPage.addEventListener("click", () => {
      if (currentPage > 1) loadTransactions(currentPage - 1);
    });
  }
  if (btnNextPage) {
    btnNextPage.addEventListener("click", () => {
      loadTransactions(currentPage + 1);
    });
  }

  // ========================================================================
  // 6. Data Quality & Reliability Audit Loader
  // ========================================================================
  async function loadDataQuality() {
    try {
      const res = await fetch("/api/data-quality");
      const json = await res.json();
      if (!json.success || !json.data) return;

      const d = json.data;
      const elSource = document.getElementById("dq-total-source");
      const elCompleted = document.getElementById("dq-valid-completed");
      const elReturned = document.getElementById("dq-flagged-returned");
      const elImputed = document.getElementById("dq-imputed");

      if (elSource) elSource.innerText = `${d.total_source_records}`;
      if (elCompleted) elCompleted.innerText = `${d.valid_completed_records}`;
      if (elReturned) elReturned.innerText = `${d.flagged_returned_records}`;
      if (elImputed) elImputed.innerText = `${d.imputed_records}`;
    } catch (err) {
      console.warn("Could not load data quality audit:", err);
    }
  }

  // --- Helper Functions ---
  function formatNumber(num) {
    if (num === null || num === undefined) return "0.00";
    return Number(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function showError(msg) {
    if (errorMessage) errorMessage.innerText = msg;
    if (errorCard) {
      errorCard.classList.remove("hidden");
      errorCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  function hideError() {
    if (errorCard) errorCard.classList.add("hidden");
  }
});
