function localToday() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

const state = {
  categories: { receita: [], despesa: [] },
  transactions: [],
  goals: [],
  month: localToday().slice(0, 7),
  view: "dashboard",
};

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const shortMonth = new Intl.DateTimeFormat("pt-BR", { month: "short" });
const fullMonth = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" });
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function formatMoney(value) {
  return money.format(Number(value) || 0);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function localDate(value) {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatDate(value) {
  const date = localDate(value);
  return date ? new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric" }).format(date) : "—";
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(" ")
      : detail || "Não foi possível concluir a operação.";
    throw new Error(message);
  }
  return payload;
}

function showToast(message, isError = false) {
  const toast = document.createElement("div");
  toast.className = `toast${isError ? " is-error" : ""}`;
  toast.textContent = message;
  $("#toast-region").append(toast);
  window.setTimeout(() => toast.remove(), 3600);
}

function currentMonthLabel() {
  const [year, month] = state.month.split("-").map(Number);
  return fullMonth.format(new Date(year, month - 1, 1));
}

function setView(view) {
  state.view = view;
  const labels = {
    dashboard: "Visão geral",
    transactions: "Transações",
    goals: "Minhas metas",
  };
  $$(".view-section").forEach((section) => {
    const active = section.id === `view-${view}`;
    section.hidden = !active;
    section.classList.toggle("is-visible", active);
  });
  $$(".nav-link").forEach((link) => link.classList.toggle("is-active", link.dataset.view === view));
  $("#page-crumb").textContent = labels[view];
  $("#sidebar").classList.remove("is-open");
  if (view === "transactions") loadTransactions().catch(showAppError);
  if (view === "goals") loadGoals().catch(showAppError);
}

function transactionRow(transaction, withActions = false) {
  const isIncome = transaction.tipo === "receita";
  const symbol = isIncome ? "↓" : "↑";
  const amountClass = isIncome ? "transaction-income" : "transaction-expense";
  const sign = isIncome ? "+" : "−";
  return `
    <tr>
      <td><span class="transaction-description"><span class="transaction-icon${isIncome ? "" : " is-expense"}">${symbol}</span>${escapeHtml(transaction.descricao)}</span></td>
      <td><span class="category-pill">${escapeHtml(transaction.categoria)}</span></td>
      <td>${formatDate(transaction.data)}</td>
      <td class="amount-column ${amountClass}">${sign} ${formatMoney(transaction.valor)}</td>
      ${withActions ? `<td class="actions-column"><span class="row-actions">
        <button class="row-action" type="button" data-edit="${transaction.id}" aria-label="Editar ${escapeHtml(transaction.descricao)}" title="Editar">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 5 4 4M4 20l4-.8L19 8a2.1 2.1 0 0 0-3-3L5 16l-1 4Z"/></svg>
        </button>
        <button class="row-action delete" type="button" data-delete="${transaction.id}" aria-label="Excluir ${escapeHtml(transaction.descricao)}" title="Excluir">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M5 7l1 14h12l1-14M9 7V4h6v3"/></svg>
        </button>
      </span></td>` : ""}
    </tr>`;
}

function renderRecentTransactions(transactions) {
  const body = $("#recent-transactions");
  if (!transactions.length) {
    body.innerHTML = '<tr><td class="empty-row" colspan="4">Nenhuma transação neste mês. Adicione a primeira para ver seu resumo.</td></tr>';
    return;
  }
  body.innerHTML = transactions.slice(0, 5).map((transaction) => transactionRow(transaction)).join("");
}

function renderTransactions(transactions) {
  const search = $("#search-filter").value.trim().toLocaleLowerCase("pt-BR");
  const type = $("#type-filter").value;
  const category = $("#category-filter").value;
  const filtered = transactions.filter((transaction) => {
    const matchesSearch = !search || `${transaction.descricao} ${transaction.categoria}`.toLocaleLowerCase("pt-BR").includes(search);
    return matchesSearch && (!type || transaction.tipo === type) && (!category || transaction.categoria === category);
  });
  const body = $("#all-transactions");
  body.innerHTML = filtered.length
    ? filtered.map((transaction) => transactionRow(transaction, true)).join("")
    : '<tr><td class="empty-row" colspan="5">Nenhuma transação encontrada para este filtro.</td></tr>';
  $("#transaction-count").textContent = `${filtered.length} ${filtered.length === 1 ? "transação encontrada" : "transações encontradas"}`;
}

function renderCategories(items) {
  const container = $("#category-chart");
  if (!items.length) {
    container.innerHTML = '<div class="empty-inline">Suas despesas por categoria<br>aparecerão aqui.</div>';
    return;
  }
  const total = items.reduce((sum, item) => sum + item.total_centavos, 0);
  container.innerHTML = items.map((item) => {
    const percent = total ? Math.max(3, Math.round(item.total_centavos / total * 100)) : 0;
    return `<div class="category-item">
      <div class="category-item-head"><span>${escapeHtml(item.categoria)}</span><strong>${formatMoney(item.total_centavos / 100)}</strong></div>
      <div class="category-track"><div class="category-fill" style="width:${percent}%"></div></div>
    </div>`;
  }).join("");
}

function renderEvolution(items) {
  const container = $("#evolution-chart");
  if (!items.length) {
    container.innerHTML = '<div class="empty-inline">Seu histórico financeiro aparecerá aqui.</div>';
    return;
  }

  const width = 660;
  const height = 174;
  const pad = { top: 12, right: 12, bottom: 25, left: 44 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const maxValue = Math.max(1, ...items.flatMap((item) => [item.receitas_centavos, item.despesas_centavos]));
  const niceMax = Math.ceil(maxValue / 100000) * 100000 || 100000;
  const x = (index) => pad.left + (items.length === 1 ? plotWidth / 2 : index * plotWidth / (items.length - 1));
  const y = (value) => pad.top + plotHeight - value / niceMax * plotHeight;
  const lineFor = (key) => items.map((item, index) => `${index ? "L" : "M"} ${x(index)} ${y(item[key])}`).join(" ");
  const areaFor = (key) => `${lineFor(key)} L ${x(items.length - 1)} ${pad.top + plotHeight} L ${x(0)} ${pad.top + plotHeight} Z`;
  const grid = [0, .5, 1].map((fraction) => {
    const position = pad.top + plotHeight * fraction;
    const label = niceMax * (1 - fraction) / 100;
    const labelText = label >= 1000 ? `${(label / 1000).toLocaleString("pt-BR")} mil` : `${Math.round(label)}`;
    return `<line class="chart-grid-line" x1="${pad.left}" y1="${position}" x2="${width - pad.right}" y2="${position}"></line>
      <text class="chart-label" x="${pad.left - 8}" y="${position + 3}" text-anchor="end">${labelText}</text>`;
  }).join("");
  const monthLabels = items.map((item, index) => {
    const [year, month] = item.mes.split("-").map(Number);
    return `<text class="chart-label" x="${x(index)}" y="${height - 5}" text-anchor="middle">${shortMonth.format(new Date(year, month - 1, 1)).replace(".", "")}</text>`;
  }).join("");
  const dots = (key, className) => items.map((item, index) => (
    `<circle class="${className}" cx="${x(index)}" cy="${y(item[key])}" r="3.3"><title>${formatMoney(item[key] / 100)}</title></circle>`
  )).join("");

  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
    <defs>
      <linearGradient id="incomeFade" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#28c6a4" stop-opacity=".16"/><stop offset="1" stop-color="#28c6a4" stop-opacity="0"/></linearGradient>
      <linearGradient id="expenseFade" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#8da3e9" stop-opacity=".13"/><stop offset="1" stop-color="#8da3e9" stop-opacity="0"/></linearGradient>
    </defs>
    ${grid}
    <path class="chart-income-area" d="${areaFor("receitas_centavos")}"></path>
    <path class="chart-expense-area" d="${areaFor("despesas_centavos")}"></path>
    <path class="chart-income-line" d="${lineFor("receitas_centavos")}"></path>
    <path class="chart-expense-line" d="${lineFor("despesas_centavos")}"></path>
    ${dots("receitas_centavos", "chart-dot-income")}${dots("despesas_centavos", "chart-dot-expense")}
    ${monthLabels}
  </svg>`;
}

function renderDashboard(summary, transactions) {
  const summaryCards = $$(".summary-card");
  const values = [
    { value: formatMoney(summary.saldo_centavos / 100), foot: "Receitas menos despesas", tone: summary.saldo_centavos < 0 ? "is-negative" : "" },
    { value: formatMoney(summary.receitas_centavos / 100), foot: "Entradas em " + currentMonthLabel() },
    { value: formatMoney(summary.despesas_centavos / 100), foot: "Saídas em " + currentMonthLabel() },
    { value: String(summary.quantidade_transacoes), foot: "Movimentações no período" },
  ];
  summaryCards.forEach((card, index) => {
    card.classList.remove("skeleton");
    const value = $(".summary-value", card);
    value.textContent = values[index].value;
    value.classList.toggle("is-negative", values[index].tone === "is-negative");
    $(".card-foot", card).textContent = values[index].foot;
  });
  renderEvolution(summary.evolucao);
  renderCategories(summary.maiores_despesas);
  renderRecentTransactions(transactions);
}

async function loadDashboard() {
  $("#today-label").textContent = `RESUMO DE ${currentMonthLabel().toLocaleUpperCase("pt-BR")}`;
  const query = `?mes=${encodeURIComponent(state.month)}`;
  const [summary, transactionResult] = await Promise.all([
    request(`/api/dashboard${query}`),
    request(`/transacoes/lista${query}`),
  ]);
  state.transactions = transactionResult.transacoes;
  renderDashboard(summary, state.transactions);
  if (state.view === "transactions") renderTransactions(state.transactions);
}

async function loadTransactions() {
  const query = `?mes=${encodeURIComponent(state.month)}`;
  const result = await request(`/transacoes/lista${query}`);
  state.transactions = result.transacoes;
  renderTransactions(state.transactions);
}

function fillCategories(type, selected = "") {
  const select = $("#transaction-category");
  const options = state.categories[type] || [];
  select.innerHTML = options.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join("");
  if (selected && options.includes(selected)) select.value = selected;
}

function openTransactionModal(transaction = null) {
  const form = $("#transaction-form");
  form.reset();
  $("#transaction-error").textContent = "";
  $("#transaction-id").value = transaction?.id || "";
  $("#transaction-modal-title").textContent = transaction ? "Editar transação" : "Nova transação";
  $("#transaction-submit").textContent = transaction ? "Salvar alterações" : "Salvar transação";
  const type = transaction?.tipo || "receita";
  $(`input[name="tipo"][value="${type}"]`).checked = true;
  $("#transaction-description").value = transaction?.descricao || "";
  $("#transaction-amount").value = transaction?.valor ?? "";
  $("#transaction-date").value = transaction?.data || localToday();
  fillCategories(type, transaction?.categoria || "");
  $("#transaction-modal").showModal();
  $("#transaction-description").focus();
}

async function submitTransaction(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const id = $("#transaction-id").value;
  const data = Object.fromEntries(new FormData(form));
  data.valor = Number(data.valor);
  $("#transaction-error").textContent = "";
  const submit = $("#transaction-submit");
  submit.disabled = true;
  try {
    await request(id ? `/transacoes/${id}` : "/transacoes/nova", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(data),
    });
    $("#transaction-modal").close();
    showToast(id ? "Transação atualizada." : "Transação cadastrada.");
    await loadDashboard();
  } catch (error) {
    $("#transaction-error").textContent = error.message;
  } finally {
    submit.disabled = false;
  }
}

async function removeTransaction(id) {
  const transaction = state.transactions.find((item) => item.id === Number(id));
  if (!transaction || !window.confirm(`Excluir "${transaction.descricao}"? Esta ação não pode ser desfeita.`)) return;
  try {
    await request(`/transacoes/${id}`, { method: "DELETE" });
    showToast("Transação excluída.");
    await loadDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderGoals(goals) {
  const container = $("#goals-grid");
  if (!goals.length) {
    container.innerHTML = '<div class="goal-empty">Você ainda não criou uma meta.<br>Que tal começar com um plano que seja importante para você?</div>';
    return;
  }
  container.innerHTML = goals.map((goal) => {
    const percent = goal.valor_alvo > 0 ? Math.min(100, Math.round(goal.valor_atual / goal.valor_alvo * 100)) : 0;
    const deadline = goal.prazo ? `Prazo: ${formatDate(goal.prazo)}` : "Sem prazo definido";
    return `<article class="goal-card">
      <div class="goal-card-top">
        <div style="display:flex;align-items:center;gap:11px"><span class="goal-mark" aria-hidden="true">✦</span><div><h2>${escapeHtml(goal.nome)}</h2><p class="goal-deadline">${deadline}</p></div></div>
        <button class="goal-menu" data-delete-goal="${goal.id}" type="button" aria-label="Excluir meta ${escapeHtml(goal.nome)}" title="Excluir meta">···</button>
      </div>
      <div class="goal-amounts"><strong class="goal-current">${formatMoney(goal.valor_atual)}</strong><span class="goal-target">de ${formatMoney(goal.valor_alvo)}</span></div>
      <div class="goal-track" role="progressbar" aria-label="Progresso da meta ${escapeHtml(goal.nome)}" aria-valuenow="${percent}" aria-valuemin="0" aria-valuemax="100"><div class="goal-fill" style="width:${percent}%"></div></div>
      <div class="goal-progress-head"><span>Progresso</span><strong>${percent}%</strong></div>
      <form class="goal-progress-form" data-goal-form="${goal.id}">
        <label>Atualizar valor guardado (R$)<input type="number" name="valor_atual" min="0" step="0.01" value="${Number(goal.valor_atual).toFixed(2)}" required></label>
        <button class="button button-secondary" type="submit">Atualizar</button>
      </form>
    </article>`;
  }).join("");
}

async function loadGoals() {
  const result = await request("/api/metas");
  state.goals = result.metas;
  renderGoals(state.goals);
}

async function submitGoal(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  data.valor_alvo = Number(data.valor_alvo);
  if (!data.prazo) delete data.prazo;
  $("#goal-error").textContent = "";
  try {
    await request("/api/metas", { method: "POST", body: JSON.stringify(data) });
    $("#goal-modal").close();
    form.reset();
    showToast("Meta criada. Um passo de cada vez!");
    await loadGoals();
  } catch (error) {
    $("#goal-error").textContent = error.message;
  }
}

async function updateGoalProgress(event) {
  event.preventDefault();
  const form = event.target.closest("[data-goal-form]");
  if (!form) return;
  const input = $('input[name="valor_atual"]', form);
  try {
    await request(`/api/metas/${form.dataset.goalForm}/progresso`, {
      method: "PUT",
      body: JSON.stringify({ valor_atual: Number(input.value) }),
    });
    showToast("Progresso da meta atualizado.");
    await loadGoals();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function removeGoal(id) {
  const goal = state.goals.find((item) => item.id === Number(id));
  if (!goal || !window.confirm(`Excluir a meta "${goal.nome}"?`)) return;
  try {
    await request(`/api/metas/${id}`, { method: "DELETE" });
    showToast("Meta excluída.");
    await loadGoals();
  } catch (error) {
    showToast(error.message, true);
  }
}

function updateCategoryFilter() {
  const select = $("#category-filter");
  const current = select.value;
  const options = [...new Set([...state.categories.receita, ...state.categories.despesa])].sort((a, b) => a.localeCompare(b, "pt-BR"));
  select.innerHTML = '<option value="">Todas as categorias</option>' + options
    .map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join("");
  if (options.includes(current)) select.value = current;
}

function showAppError(error) {
  showToast(error.message || "Não foi possível carregar o sistema.", true);
  console.error(error);
}

async function initialize() {
  $("#month-filter").value = state.month;
  try {
    const categories = await request("/api/categorias");
    state.categories = categories.categorias;
    updateCategoryFilter();
    fillCategories("receita");
    await loadDashboard();
  } catch (error) {
    showAppError(error);
  }

  $$(".nav-link").forEach((link) => link.addEventListener("click", () => setView(link.dataset.view)));
  $$("[data-go-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.goView)));
  $("#mobile-menu").addEventListener("click", () => $("#sidebar").classList.toggle("is-open"));
  $("#quick-add").addEventListener("click", () => openTransactionModal());
  $("#dashboard-add").addEventListener("click", () => openTransactionModal());
  $("#transactions-add").addEventListener("click", () => openTransactionModal());
  $("#goal-add").addEventListener("click", () => {
    $("#goal-error").textContent = "";
    $("#goal-modal").showModal();
    $("#goal-name").focus();
  });
  $("#transaction-form").addEventListener("submit", submitTransaction);
  $("#goal-form").addEventListener("submit", submitGoal);
  $$("[data-close-modal]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
  $$(".modal").forEach((dialog) => dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  }));
  $$('input[name="tipo"]').forEach((radio) => radio.addEventListener("change", (event) => fillCategories(event.target.value)));
  $("#month-filter").addEventListener("change", async (event) => {
    if (!event.target.value) return;
    state.month = event.target.value;
    try {
      await loadDashboard();
    } catch (error) {
      showAppError(error);
    }
  });
  $("#search-filter").addEventListener("input", () => renderTransactions(state.transactions));
  $("#type-filter").addEventListener("change", () => renderTransactions(state.transactions));
  $("#category-filter").addEventListener("change", () => renderTransactions(state.transactions));
  $("#all-transactions").addEventListener("click", (event) => {
    const editButton = event.target.closest("[data-edit]");
    const deleteButton = event.target.closest("[data-delete]");
    if (editButton) {
      const transaction = state.transactions.find((item) => item.id === Number(editButton.dataset.edit));
      if (transaction) openTransactionModal(transaction);
    }
    if (deleteButton) removeTransaction(deleteButton.dataset.delete);
  });
  $("#goals-grid").addEventListener("submit", updateGoalProgress);
  $("#goals-grid").addEventListener("click", (event) => {
    const button = event.target.closest("[data-delete-goal]");
    if (button) removeGoal(button.dataset.deleteGoal);
  });
}

document.addEventListener("DOMContentLoaded", initialize);
