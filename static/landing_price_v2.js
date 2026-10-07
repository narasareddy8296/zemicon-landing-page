const $ = (id) => document.getElementById(id);
const state = { lines: [], upload: null, lastResult: null };

function escape(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function inr(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency", currency: "INR", minimumFractionDigits: 2
  }).format(Number(value || 0));
}

function money(value, currency) {
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency, minimumFractionDigits: 2
  }).format(Number(value || 0));
}

function updateInvoiceSummary() {
  let invoiceTotal = 0;
  let convertedTotalInr = 0;
  const currency = $("invoiceCurrency").value;
  const liveRate = Number($("liveRate").value);
  const needsUsdRate = currency === "USD" &&
    (!Number.isFinite(liveRate) || liveRate <= 0);
  for (const line of state.lines) {
    const quantity = Number(line.quantity);
    const unitPrice = Number(line.unit_price);
    if (!Number.isFinite(quantity) || quantity <= 0 ||
        !Number.isFinite(unitPrice) || unitPrice < 0 || line.unit_price === "") {
      continue;
    }

    const lineSubtotal = quantity * unitPrice;
    invoiceTotal += lineSubtotal;
    if (currency === "INR") {
      convertedTotalInr += lineSubtotal;
      continue;
    }
    convertedTotalInr += Math.round(
      (lineSubtotal * liveRate * 1.02 + Number.EPSILON) * 100
    ) / 100;
  }

  const summary = $("invoiceSummary");
  summary.replaceChildren();
  if (!state.lines.some((line) => line.unit_price !== "")) {
    summary.classList.add("hidden");
    return;
  }
  summary.classList.remove("hidden");
  const title = document.createElement("h3");
  title.textContent = "Invoice totals";
  summary.appendChild(title);
  const entered = document.createElement("div");
  entered.className = "invoice-total";
  entered.innerHTML = `<span>Entered invoice total (${currency})</span><strong>${money(invoiceTotal, currency)}</strong>`;
  summary.appendChild(entered);
  const converted = document.createElement("div");
  converted.className = "invoice-total invoice-total-grand";
  converted.innerHTML = needsUsdRate
    ? "<span>Converted invoice total (INR)</span><strong>Enter the live USD/INR rate</strong>"
    : `<span>Converted invoice total (INR)</span><strong>${inr(convertedTotalInr)}</strong>`;
  summary.appendChild(converted);
}

function showError(message) {
  $("error").textContent = message;
  $("error").classList.remove("hidden");
}

function clearError() {
  $("error").textContent = "";
  $("error").classList.add("hidden");
}

function updateConversionPreview(row, line) {
  const preview = row.querySelector("[data-conversion-preview]");
  if (!line.unit_price) {
    preview.textContent = "Enter a unit price to see the INR equivalent.";
    return;
  }
  const currency = $("invoiceCurrency").value;
  if (currency === "INR") {
    preview.textContent = `Per unit in INR: ${inr(Number(line.unit_price))}`;
    return;
  }
  const liveRate = Number($("liveRate").value);
  if (!Number.isFinite(liveRate) || liveRate <= 0) {
    preview.textContent = "Enter the live interbank USD/INR rate to convert this price.";
    return;
  }
  const appliedRate = liveRate * 1.02;
  preview.textContent =
    `Live rate ${liveRate.toFixed(4)} + 2% = ${appliedRate.toFixed(4)} INR/USD; per unit ${inr(Number(line.unit_price) * appliedRate)}`;
}

function updateLineAmount(row, line) {
  const amount = lineInvoiceInr(line);
  row.querySelector('[data-label="Amount (INR)"]').textContent =
    amount === null ? "—" : inr(amount);
}

function renderLines() {
  const body = $("productRows");
  body.replaceChildren();
  state.lines.forEach((line, index) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td data-label="MPN"><input class="mpn-input" data-field="mpn" aria-label="MPN" placeholder="Manufacturer part number" value="${escape(line.mpn || "")}"></td>
      <td data-label="Quantity"><input data-field="quantity" aria-label="Quantity" type="number" min="0.000001" step="any" value="${escape(line.quantity ?? 1)}"></td>
      <td data-label="Amount (INR)" data-line-amount>—</td>
      <td data-label="Per unit price">
        <input data-field="unit_price" aria-label="Per unit price" type="number" min="0" step="any" value="${escape(line.unit_price ?? "")}">
        <small data-conversion-preview></small>
      </td>
      <td data-label="Action"><button class="button button-secondary remove-line" type="button" aria-label="Remove line ${index + 1}">Remove</button></td>
    `;
    tr.querySelectorAll("[data-field]").forEach((input) => {
      input.addEventListener("input", () => {
        const field = input.dataset.field;
        line[field] = input.value;
        line.result = null;
        $("results").classList.add("hidden");
        if (field === "quantity" || field === "unit_price") {
          updateConversionPreview(tr, line);
          updateLineAmount(tr, line);
          updateInvoiceSummary();
          updateTariffAmounts();
        }
        if (field === "mpn") {
          line.master = null;
          line.category = "";
          line.bcd = "";
          line.sws = "10";
          line.result = null;
          renderTariffs();
        }
      });
      if (input.dataset.field === "mpn") {
        input.addEventListener("change", () => lookupProduct(index).catch((error) => showError(error.message)));
        input.addEventListener("blur", () => lookupProduct(index).catch((error) => showError(error.message)));
      }
    });
    tr.querySelector(".remove-line").addEventListener("click", () => {
      state.lines.splice(index, 1);
      if (!state.lines.length) state.lines.push(newLine());
      renderLines();
      renderTariffs();
    });
    updateConversionPreview(tr, line);
    updateLineAmount(tr, line);
    body.appendChild(tr);
  });
  updateInvoiceSummary();
  renderTariffs();
}

function updatePriceSettings() {
  const isUsd = $("invoiceCurrency").value === "USD";
  $("liveRateWrap").classList.toggle("hidden", !isUsd);
  $("inrRateNote").classList.toggle("hidden", isUsd);
  state.lines.forEach((line, index) => {
    const row = $("productRows").children[index];
    if (row) {
      updateConversionPreview(row, line);
      updateLineAmount(row, line);
    }
    line.result = null;
  });
  $("results").classList.add("hidden");
  updateInvoiceSummary();
  updateTariffAmounts();
}

function lineInvoiceInr(line) {
  const quantity = Number(line.quantity);
  const unitPrice = Number(line.unit_price);
  if (!Number.isFinite(quantity) || quantity <= 0 ||
      !Number.isFinite(unitPrice) || unitPrice < 0 || line.unit_price === "") {
    return null;
  }
  let rate = 1;
  if ($("invoiceCurrency").value !== "INR") {
    const liveRate = Number($("liveRate").value);
    if (!Number.isFinite(liveRate) || liveRate <= 0) return null;
    rate = liveRate * 1.02;
  }
  return Math.round((quantity * unitPrice * rate + Number.EPSILON) * 100) / 100;
}

function calculateAssessablePreview() {
  const invoices = state.lines.map(lineInvoiceInr);
  const validInvoices = invoices.map((amount) => amount ?? 0);
  const totalInvoice = validInvoices.reduce((sum, amount) => sum + amount, 0);
  const section = $("assessableSection");
  const complete = invoices.length > 0 && invoices.every((amount) => amount !== null);
  const freightTotal = complete && totalInvoice < Number(section.dataset.freeShippingThreshold)
    ? Number(section.dataset.internationalFreight)
    : 0;
  const weights = totalInvoice > 0
    ? validInvoices
    : state.lines.map((line) => Math.max(0, Number(line.quantity) || 0));
  const freightByLine = allocateFreight(freightTotal, weights);
  const insuranceByLine = invoices.map((invoice) =>
    invoice === null ? null : Math.round((invoice * 1.125 / 100 + Number.EPSILON) * 100) / 100
  );
  const assessableByLine = invoices.map((invoice, index) =>
    invoice === null
      ? null
      : Math.round((invoice + insuranceByLine[index] + freightByLine[index] + Number.EPSILON) * 100) / 100
  );
  return {
    invoices,
    insuranceByLine,
    freightByLine,
    assessableByLine,
    totalInvoice,
    complete,
    freightTotal,
    totalInsurance: insuranceByLine.reduce((sum, amount) => sum + (amount ?? 0), 0),
    totalAssessable: assessableByLine.reduce((sum, amount) => sum + (amount ?? 0), 0)
  };
}

function updateAssessableSummary() {
  const summary = calculateAssessablePreview();
  $("assessmentInvoice").textContent = inr(summary.totalInvoice);
  $("assessmentInsurance").textContent =
    summary.complete ? inr(summary.totalInsurance) : "Complete prices / FX rates";
  $("assessmentFreight").textContent =
    summary.complete ? inr(summary.freightTotal) : "Complete prices / FX rates";
  $("assessmentTotal").textContent =
    summary.complete ? inr(summary.totalAssessable) : "Complete prices / FX rates";
}

function allocateFreight(amount, weights) {
  if (!weights.length || amount <= 0) return weights.map(() => 0);
  let effectiveWeights = weights;
  let totalWeight = effectiveWeights.reduce((sum, weight) => sum + weight, 0);
  if (totalWeight <= 0) {
    effectiveWeights = weights.map(() => 1);
    totalWeight = effectiveWeights.length;
  }
  const cents = Math.round(amount * 100);
  const raw = effectiveWeights.map((weight) => cents * weight / totalWeight);
  const allocated = raw.map(Math.floor);
  let remainder = cents - allocated.reduce((sum, value) => sum + value, 0);
  const order = raw
    .map((value, index) => ({ value, index }))
    .map(({ value, index }) => ({ index, fraction: value - allocated[index] }))
    .sort((left, right) => right.fraction - left.fraction || left.index - right.index);
  for (const entry of order) {
    if (remainder <= 0) break;
    allocated[entry.index] += 1;
    remainder -= 1;
  }
  return allocated.map((value) => value / 100);
}

function updateTariffAmounts() {
  const preview = calculateAssessablePreview();

  state.lines.forEach((line, index) => {
    const row = $("tariffRows").querySelector(`[data-tariff-index="${index}"]`);
    if (!row) return;
    const bcdField = row.querySelector('[data-master="bcd"]');
    const swsField = row.querySelector('[data-master="sws"]');
    const bcdRate = Number(bcdField.value);
    const swsRate = Number(swsField.value);
    const invoice = line.result?.line_invoice_inr ?? preview.invoices[index];
    const insurance = line.result?.insurance ?? preview.insuranceByLine[index];
    const lineFreight = line.result?.international_freight ?? preview.freightByLine[index] ?? 0;
    const assessable = line.result?.assessable_value ?? preview.assessableByLine[index];
    const bcdAmount = line.result?.bcd_amount ??
      (assessable !== null && bcdField.value !== "" && Number.isFinite(bcdRate)
        ? Math.round(assessable * bcdRate / 100)
        : null);
    const swsAmount = line.result?.sws_amount ??
      (bcdAmount !== null && swsField.value !== "" && Number.isFinite(swsRate)
        ? Math.round((bcdAmount * swsRate / 100 + Number.EPSILON) * 100) / 100
        : null);
    row.querySelector("[data-bcd-amount]").textContent =
      bcdAmount === null ? "—" : inr(bcdAmount);
    row.querySelector("[data-sws-amount]").textContent =
      swsAmount === null ? "—" : inr(swsAmount);
    row.querySelector("[data-invoice-inr]").textContent =
      invoice === null ? "—" : inr(invoice);
    row.querySelector("[data-insurance]").textContent =
      insurance === null ? "—" : inr(insurance);
    row.querySelector("[data-freight]").textContent = inr(lineFreight);
    row.querySelector("[data-assessable]").textContent =
      assessable === null ? "—" : inr(assessable);
  });
  updateAssessableSummary();
}

function renderTariffs() {
  const body = $("tariffRows");
  body.replaceChildren();
  $("tariffEmpty").classList.toggle("hidden", state.lines.length > 0);
  state.lines.forEach((line, index) => {
    const known = Boolean(line.master?.found);
    const status = known ? "Found in DigiKey master" :
      (line.master?.found === false ? "Not found" : "Enter MPN above");
    const category = known ? line.master.category : (line.category || "");
    const bcd = known ? line.master.bcd : (line.bcd ?? "");
    const sws = known ? line.master.sws : (line.sws ?? "10");
    const row = document.createElement("tr");
    row.dataset.tariffIndex = index;
    row.innerHTML = `
      <td>${escape(line.mpn || "—")}</td>
      <td>
        <span class="master-status ${known ? "" : "missing"}">${status}</span>
        ${line.master?.found === false
          ? '<p class="master-warning" role="alert">MPN not found in DigiKey master. Enter BCD and SWS rates for this calculation.</p>'
          : ""}
      </td>
      <td><input data-master="category" aria-label="Component category" placeholder="Category" value="${escape(category)}" ${known ? "readonly" : ""}></td>
      <td data-invoice-inr>—</td>
      <td data-insurance>—</td>
      <td data-freight>—</td>
      <td data-assessable>—</td>
      <td><label class="tariff-input-label" for="tariff-bcd-${index}">BCD rate (%)</label>
        <input id="tariff-bcd-${index}" data-master="bcd" aria-label="BCD percent" type="number" min="0" max="100" step="any" placeholder="BCD %" value="${escape(bcd)}" ${known ? "readonly" : ""}>
      </td>
      <td data-bcd-amount>—</td>
      <td><label class="tariff-input-label" for="tariff-sws-${index}">SWS rate (%)</label>
        <input id="tariff-sws-${index}" data-master="sws" aria-label="SWS percent" type="number" min="0" max="100" step="any" placeholder="SWS %" value="${escape(sws)}" ${known ? "readonly" : ""}>
      </td>
      <td data-sws-amount>—</td>
    `;
    row.querySelectorAll("[data-master]").forEach((input) => {
      input.addEventListener("input", () => {
        line[input.dataset.master] = input.value;
        line.result = null;
        $("results").classList.add("hidden");
        updateTariffAmounts();
      });
    });
    body.appendChild(row);
  });
  updateTariffAmounts();
}

function newLine(fields = {}) {
  return {
    mpn: "", quantity: 1, unit_price: "",
    sws: "10",
    master: null, ...fields
  };
}

async function lookupProduct(index) {
  const line = state.lines[index];
  if (!line || !line.mpn?.trim()) return;
  const response = await fetch(`/api/landing/v2/product/${encodeURIComponent(line.mpn.trim())}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Product lookup failed.");
  line.master = data.found ? { ...data, found: true } : { found: false };
  if (data.found) {
    line.category = data.category;
    line.bcd = data.bcd;
    line.sws = data.sws;
  } else {
    line.sws = line.sws || "10";
  }
  line.result = null;
  renderTariffs();
}

function selectedColumnForm(data) {
  const choices = $("columnChoices");
  choices.replaceChildren();
  if (data.sheets?.length && !data.headers) {
    const label = document.createElement("label");
    label.className = "column-choice";
    label.textContent = "Worksheet / header";
    const select = document.createElement("select");
    select.id = "sheetChoice";
    data.sheets.forEach((entry, index) => {
      const option = document.createElement("option");
      option.value = JSON.stringify(entry);
      option.textContent = `${entry.sheet}, row ${entry.header_row}`;
      select.appendChild(option);
      if (index === 0) select.value = option.value;
    });
    label.appendChild(select);
    choices.appendChild(label);
    addChoiceButton("Inspect selected header", async () => {
      const selection = JSON.parse(select.value);
      await sendWorkbookImport(selection);
    });
    return;
  }

  const headers = data.headers || [];
  const candidates = data.candidates || {};
  const fields = [
    ["mpn_column", "MPN column", true],
    ["unit_price_column", "Per Unit Price column", true],
    ["quantity_column", "Quantity column", false],
    ["currency_column", "Currency column", false]
  ];
  fields.forEach(([key, labelText, required]) => {
    const label = document.createElement("label");
    label.className = "column-choice";
    label.textContent = labelText;
    const select = document.createElement("select");
    select.id = `choice-${key}`;
    if (!required) {
      const none = document.createElement("option");
      none.value = "";
      none.textContent = "Not present";
      select.appendChild(none);
    }
    const choicesForField = candidates[key.replace("_column", "")] || [];
    headers.forEach((header) => {
      const option = document.createElement("option");
      option.value = header.index;
      option.textContent = header.label;
      if (choicesForField.includes(header.index)) option.textContent += " (detected)";
      select.appendChild(option);
    });
    if (choicesForField.length === 1) select.value = choicesForField[0];
    label.appendChild(select);
    choices.appendChild(label);
  });
  if (!headers.length) {
    showError("No recognizable header row was found. Rename the MPN and unit price columns, then upload again.");
    return;
  }
  addChoiceButton("Import selected columns", async () => {
    const selection = {};
    for (const [key] of fields) {
      const value = $(`choice-${key}`).value;
      if (value !== "") selection[key] = value;
      else if (key === "quantity_column" || key === "currency_column") selection[key] = "";
    }
    const sheetChoice = data.sheets?.[0];
    if (sheetChoice) {
      selection.sheet = sheetChoice.sheet;
      selection.header_row = sheetChoice.header_row;
    }
    await sendWorkbookImport(selection);
  });
}

function addChoiceButton(text, callback) {
  const button = document.createElement("button");
  button.className = "button button-secondary";
  button.type = "button";
  button.textContent = text;
  button.addEventListener("click", callback);
  $("columnChoices").appendChild(button);
}

async function sendWorkbookImport(selection = {}) {
  clearError();
  const file = $("excelFile").files[0];
  if (!file) {
    showError("Choose an .xlsx workbook first.");
    return;
  }
  const form = new FormData();
  form.append("file", file);
  form.append("default_currency", "USD");
  Object.entries(selection).forEach(([key, value]) => form.append(key, value));
  try {
    const response = await fetch("/api/landing/v2/import-excel", { method: "POST", body: form });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Workbook import failed.");
    if (data.needs_selection) {
      selectedColumnForm(data);
      return;
    }
    state.upload = data;
    state.lines = data.items.map((item) => newLine({
      ...item,
      master: item.master,
      live_exchange_rate: ""
    }));
    $("columnChoices").replaceChildren();
    $("manualPanel").classList.add("hidden");
    $("excelPanel").classList.remove("hidden");
    renderLines();
  } catch (error) {
    showError(error.message);
  }
}

function renderResults(data) {
  data.items.forEach((item, index) => {
    if (state.lines[index]) state.lines[index].result = item;
  });
  renderTariffs();
  $("results").classList.remove("hidden");
  $("totals").classList.add("results-summary");
  $("resultSummary").textContent =
    `${data.items.length} line item(s) • Shipment invoice ${inr(data.totals.total_invoice_inr)}`;
  const totals = $("totals");
  totals.replaceChildren();
  const totalDuties = data.items.reduce(
    (sum, item) => sum + item.bcd_amount + item.sws_amount,
    0
  );
  const summaryRows = [
    ["Invoice total", data.totals.total_invoice_inr],
    ["Assessable value", data.totals.assessable_value],
    ["BCD + SWS", totalDuties],
    ["Total landed cost", data.totals.base_landed_cost]
  ];
  if (data.totals.margin_percent > 0) {
    summaryRows.push(
      [`Margin (${data.totals.margin_percent}%)`, data.totals.margin_amount],
      ["Selling total", data.totals.margin_inclusive_value]
    );
  }
  if (data.totals.igst_enabled) {
    summaryRows.push(
      ["Final price including IGST", data.totals.final_price_including_igst]
    );
  }
  summaryRows.forEach(([label, value]) => {
    const chip = document.createElement("div");
    chip.className = "total-chip";
    chip.innerHTML = `<span>${escape(label)}</span><strong>${inr(value)}</strong>`;
    totals.appendChild(chip);
  });

  $("resultHead").innerHTML = `<tr>
    <th>MPN</th><th>Qty</th><th>Unit price (INR)</th><th>Invoice (INR)</th><th>Assessable value</th>
    <th>BCD</th><th>SWS</th><th>Total landed cost</th><th>Landing price / unit</th>
    ${data.totals.igst_enabled ? "<th>Final price / unit incl. IGST</th>" : ""}
    <th>Details</th>
  </tr>`;
  const body = $("resultRows");
  body.replaceChildren();
  data.items.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td data-label="MPN">${escape(item.mpn)}</td>
      <td data-label="Quantity">${escape(item.quantity)}</td>
      <td data-label="Unit price (INR)">${inr(item.unit_price_inr)}</td>
      <td data-label="Invoice (INR)">${inr(item.line_invoice_inr)}</td>
      <td data-label="Assessable value">${inr(item.assessable_value)}</td>
      <td data-label="BCD">${inr(item.bcd_amount)} <small>(${escape(item.bcd_rate)}%)</small></td>
      <td data-label="SWS">${inr(item.sws_amount)} <small>(${escape(item.sws_rate)}%)</small></td>
      <td data-label="Total landed cost">${inr(item.base_landed_cost)}</td>
      <td data-label="Landing price / unit" class="result-unit-price">${inr(item.per_unit_selling_price)}</td>
      ${data.totals.igst_enabled ? `<td data-label="Final price / unit incl. IGST">${inr(item.per_unit_final_price_including_igst)}</td>` : ""}
      <td data-label="Details">
        <details class="result-details">
          <summary>More details</summary>
          <dl>
            <dt>Unit price</dt><dd>${money(item.unit_price, item.currency)}</dd>
            <dt>Invoice total (entered currency)</dt><dd>${money(item.line_invoice_currency, item.currency)}</dd>
            <dt>Exchange rate</dt><dd>${item.live_exchange_rate_inr === null ? "Not applicable" : `${item.live_exchange_rate_inr.toFixed(4)} INR/USD live`}; applied ${item.exchange_rate_inr.toFixed(4)} INR/${escape(item.currency)}</dd>
            <dt>Category / HSN</dt><dd>${escape(item.category || "—")} / ${escape(item.hsn || "—")}</dd>
            <dt>Insurance</dt><dd>${inr(item.insurance)}</dd>
            <dt>International freight</dt><dd>${inr(item.international_freight)}</dd>
            <dt>Other charges</dt><dd>${inr(item.other_charges)}</dd>
            <dt>Remittance / CHA / domestic</dt><dd>${inr(item.remittance)} / ${inr(item.cha_port_dues)} / ${inr(item.domestic_trucking)}</dd>
            <dt>Margin (${escape(item.margin_percent)}%)</dt><dd>${inr(item.margin_amount)}</dd>
            <dt>Selling value</dt><dd>${inr(item.margin_inclusive_value)}</dd>
            ${data.totals.igst_enabled ? `<dt>IGST</dt><dd>${inr(item.igst)}</dd>` : ""}
          </dl>
          <details class="trace"><summary>Calculation steps</summary><ol>${item.trace.map((step) => `<li>${escape(step)}</li>`).join("")}</ol></details>
        </details>
      </td>
    `;
    body.appendChild(row);
  });
  state.lastResult = data;
  $("results").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function calculate() {
  clearError();
  if (!state.lines.length) {
    showError("Add at least one product line.");
    return;
  }
  const button = $("calculate");
  button.disabled = true;
  button.textContent = "Calculating…";
  try {
    await Promise.all(state.lines.map((_, index) => lookupProduct(index)));
    const payload = {
      items: state.lines.map((line) => ({
        mpn: line.mpn,
        quantity: line.quantity,
        unit_price: line.unit_price,
        currency: $("invoiceCurrency").value,
        live_exchange_rate: $("liveRate").value,
        ...(!line.master?.found
          ? { category: line.category, bcd_rate: line.bcd, sws_rate: line.sws }
          : {})
      })),
      remittance_applicable: $("remittance").value,
      cha_applicable: $("cha").value,
      domestic_trucking_applicable: $("domestic").value,
      other_charges_total: $("otherChargesTotal").value,
      igst_enabled: $("igstEnabled").value,
      margin_percent: $("markup").value
    };
    const response = await fetch("/api/landing/v2/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Landing-price calculation failed.");
    renderResults(data);
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Calculate landing price";
  }
}

function setInputMethod(method) {
  const manual = method === "manual";
  $("manualPanel").classList.toggle("hidden", !manual);
  $("excelPanel").classList.toggle("hidden", manual);
  $("manualTab").classList.toggle("active", manual);
  $("excelTab").classList.toggle("active", !manual);
  $("manualTab").setAttribute("aria-selected", String(manual));
  $("excelTab").setAttribute("aria-selected", String(!manual));
  $("columnChoices").replaceChildren();
  state.lines = [];
  state.upload = null;
  $("results").classList.add("hidden");
  clearError();
  if (manual) state.lines.push(newLine());
  renderLines();
}

$("manualTab").addEventListener("click", () => setInputMethod("manual"));
$("excelTab").addEventListener("click", () => setInputMethod("excel"));
$("addLine").addEventListener("click", () => {
  state.lines.push(newLine());
  renderLines();
});
$("invoiceCurrency").addEventListener("change", updatePriceSettings);
$("vendor").addEventListener("change", () => {
  const isOtherVendor = $("vendor").value === "other";
  $("vendorNotice").classList.toggle("hidden", !isOtherVendor);
  $("results").classList.add("hidden");
});
$("liveRate").addEventListener("input", updatePriceSettings);
$("otherChargesTotal").addEventListener("input", () => {
  $("results").classList.add("hidden");
});
$("inspectExcel").addEventListener("click", () => sendWorkbookImport());
$("calculate").addEventListener("click", calculate);
$("igstEnabled").addEventListener("change", () => {
  $("results").classList.add("hidden");
});
$("markup").addEventListener("input", () => $("results").classList.add("hidden"));
setInputMethod("manual");
