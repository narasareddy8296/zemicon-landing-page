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
  if (!line.unit_price && !line.liveQuote) {
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
    `Live rate ${liveRate.toFixed(4)} + 2% = ${appliedRate.toFixed(4)} INR/USD; per unit ${inr(Number(line.unit_price || line.liveQuote?.unit_price) * appliedRate)}`;
}

function updateLineAmount(row, line) {
  const amount = lineInvoiceInr(line);
  const amountCell = row.querySelector("[data-line-amount]");
  if (!amountCell) return;
  amountCell.textContent = amount === null ? "—" : inr(amount);
}
function updateStockWarning(row, line) {
  const warning = row.querySelector(".stock-warning");
  if (!warning) return;
  const available = line.selectedVariation?.available_quantity;
  const requested = Number(line.quantity);
  if (available != null && Number.isFinite(requested) && requested > available) {
    warning.textContent = `Insufficient DigiKey stock: ${available} available; ${requested} requested. The full quantity cannot be supplied.`;
    warning.classList.add("visible");
  } else {
    warning.textContent = "";
    warning.classList.remove("visible");
  }
}

function renderLines() {
  const body = $("productRows");
  body.replaceChildren();
  state.lines.forEach((line, index) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td data-label="MPN"><div class="mpn-search-row"><input class="mpn-input" data-field="mpn" aria-label="MPN" placeholder="Manufacturer part number" value="${escape(line.mpn || "")}"><button class="button button-secondary search-product" type="button" ${line.loading ? "disabled" : ""}>${line.loading ? '<span class="search-spinner" aria-hidden="true"></span> Searching' : "Search"}</button></div><small class="lookup-status" role="status" aria-live="polite">${escape(line.lookupMessage || "")}</small>${line.needsMatchSelection ? `<select class="match-choice" aria-label="Select DigiKey product"><option value="">Choose a DigiKey match</option>${line.productDetails.matches.map((match, choice) => `<option value="${choice}" ${String(line.selectedMatchIndex) === String(choice) ? "selected" : ""}>${escape(match.manufacturer_part_number || "Unknown MPN")} / ${escape(match.manufacturer || "Unknown manufacturer")} / ${escape(match.variations[0]?.digikey_product_number || "No DigiKey part number")}</option>`).join("")}</select>` : ""}${line.selectedProduct ? `<div class="live-product-details"><span class="live-product-label">DIGIKEY PRODUCT DETAILS</span><dl><div><dt>Manufacturer</dt><dd>${escape(line.selectedProduct.manufacturer || "Not provided")}</dd></div><div><dt>Category</dt><dd>${escape(line.master?.found ? line.master.category : "Not found in catalog")}</dd></div><div><dt>Description</dt><dd>${escape(line.selectedProduct.description || "Not provided")}</dd></div><div><dt>DigiKey part number</dt><dd>${escape(line.selectedVariation?.digikey_product_number || line.selectedProduct.digikey_part_number || "Not provided")}</dd></div></dl></div>` : ""}</td>
      <td data-label="Quantity"><input data-field="quantity" aria-label="Quantity" type="number" min="0.000001" step="any" value="${escape(line.quantity ?? 1)}"><small class="stock-warning" role="alert"></small></td>
      <td data-label="Amount (INR)" data-line-amount>â€”</td>
      <td data-label="Per unit price">
        <input data-field="unit_price" aria-label="Per unit price" type="number" min="0" step="any" value="${escape(line.unit_price ?? line.liveQuote?.unit_price ?? "")}">
        ${line.liveQuote ? `<small class="live-price">${escape(line.selectedVariation.package_type)} / MOQ ${escape(line.selectedVariation.minimum_order_quantity || 1)} / DigiKey ${escape(line.liveQuote.digikey_product_number || "")} / tier ${escape(line.liveQuote.break_quantity)} / ${line.liveQuote.requested_quantity} x ${escape(money(line.liveQuote.unit_price, line.liveQuote.currency))} = ${escape(money(line.liveQuote.extended_price, line.liveQuote.currency))} / stock ${line.liveQuote.available_quantity == null ? "unavailable" : escape(line.liveQuote.available_quantity)} / ${line.quoteCached ? "cached" : "live"} from ${escape(line.fetchedAt || "")}${line.priceSource === "digikey" ? " / Auto-filled; editable" : ""}</small>` : line.pricingMessage ? `<small class="price-unavailable">${escape(line.pricingMessage)}</small>` : ""}
        ${line.priceCurrencyMismatch ? `<small class="price-unavailable">Live price is ${escape(line.priceCurrencyMismatch.liveCurrency)}. Shipment uses ${escape(line.priceCurrencyMismatch.shipmentCurrency)}.</small>` : ""}
        <small data-conversion-preview></small>
      </td>
      <td data-label="Action"><button class="button button-secondary remove-line" type="button" aria-label="Remove line ${index + 1}">Remove</button></td>
    `;
    tr.querySelectorAll("[data-field]").forEach((input) => {
      input.addEventListener("input", () => {
        const field = input.dataset.field;
        line[field] = input.value;
        if (field === "unit_price") line.priceSource = "user";
        line.result = null;
        $("results").classList.add("hidden");
        if (field === "quantity" || field === "unit_price") {
          if (field === "quantity" && line.productDetails) {
            line.quoteCached = true;
            applyDigiKeyTier(line, false);
            const priceInput = tr.querySelector('[data-field="unit_price"]');
            if (line.priceSource === "digikey") priceInput.value = line.unit_price;
          }
          updateConversionPreview(tr, line);
          updateLineAmount(tr, line);
          updateInvoiceSummary();
          updateTariffAmounts();
        }
        if (field === "mpn") {
          if (line.priceSource === "digikey") { line.unit_price = ""; line.priceSource = ""; }
          line.productDetails = null;
          line.liveQuote = null;
          line.lookupMessage = "";
          line.master = null;
          line.category = "";
          line.bcd = "";
          line.sws = "10";
          line.result = null;
          renderTariffs();
        }
      });
    });
    tr.querySelector(".search-product").addEventListener("click", () => lookupProduct(index).catch((error) => showError(error.message)));
    tr.querySelector('[data-field="mpn"]').addEventListener("change", () => {
      if (line.mpn.trim()) lookupProduct(index).catch((error) => showError(error.message));
    });
    tr.querySelector('[data-field="quantity"]').addEventListener("change", () => {
      if (!line.productDetails) return;
      line.quoteCached = true;
      applyDigiKeyTier(line, false);
      renderLines();
    });
    tr.querySelector(".match-choice")?.addEventListener("change", (event) => {
      line.selectedMatchIndex = event.target.value === "" ? null : Number(event.target.value);
      line.selectedVariationIndex = null;
      applyDigiKeyTier(line, true);
      renderLines();
    });
    tr.querySelector(".remove-line").addEventListener("click", () => {
      state.lines.splice(index, 1);
      if (!state.lines.length) state.lines.push(newLine());
      renderLines();
      renderTariffs();
    });
    body.appendChild(tr);
    updateConversionPreview(tr, line);
    updateLineAmount(tr, line);

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
      bcdAmount === null ? "â€”" : inr(bcdAmount);
    row.querySelector("[data-sws-amount]").textContent =
      swsAmount === null ? "â€”" : inr(swsAmount);
    row.querySelector("[data-invoice-inr]").textContent =
      invoice === null ? "â€”" : inr(invoice);
    row.querySelector("[data-insurance]").textContent =
      insurance === null ? "â€”" : inr(insurance);
    row.querySelector("[data-freight]").textContent = inr(lineFreight);
    row.querySelector("[data-assessable]").textContent =
      assessable === null ? "â€”" : inr(assessable);
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
    const category = known ? line.master.category : (line.catalogCategory || line.category || "");
    const bcd = known ? line.master.bcd : (line.bcd ?? "");
    const sws = known ? line.master.sws : (line.sws ?? "10");
    const row = document.createElement("article");
    row.dataset.tariffIndex = index;
    row.className = `tariff-card ${known ? "is-found" : "is-missing"}`;
    row.innerHTML = `
      <header class="tariff-card-heading">
        <div><span class="tariff-overline">PART ${String(index + 1).padStart(2, "0")}</span><strong class="tariff-mpn">${escape(line.mpn || "MPN not entered")}</strong></div>
        <span class="master-status ${known ? "" : line.master?.found === false ? "missing" : "pending"}"><i></i>${status}</span>
      </header>
      ${line.master?.found === false
        ? '<p class="tariff-note" role="alert">This MPN is not in the local DigiKey master. Enter tariff values below for this calculation.</p>'
        : ""}
      <div class="tariff-identifiers">
        <label>Component category<input data-master="category" aria-label="Component category" placeholder="Category" value="${escape(category)}" ${known ? "readonly" : ""}></label>
        <label>HSN / CTSH<input data-master="hsn" aria-label="HSN or CTSH code" placeholder="${known ? "Not available" : "Enter HSN / CTSH"}" value="${escape(known ? line.master.hsn : (line.hsn || ""))}" ${known ? "readonly" : ""}></label>
      </div>
      <div class="tariff-metrics">
        <div><span>Invoice value</span><strong data-invoice-inr>â€”</strong></div>
        <div><span>Insurance</span><strong data-insurance>â€”</strong></div>
        <div><span>Allocated freight</span><strong data-freight>â€”</strong></div>
        <div class="assessable-metric"><span>Assessable value</span><strong data-assessable>â€”</strong></div>
      </div>
      <div class="tariff-rates">
        <section class="rate-card bcd-rate-card">
          <div class="rate-title">Basic Customs Duty <small>BCD</small></div>
          <label class="rate-entry" for="tariff-bcd-${index}"><input id="tariff-bcd-${index}" data-master="bcd" aria-label="BCD percent" type="number" min="0" max="100" step="any" placeholder="Rate" value="${escape(bcd)}" ${known ? "readonly" : ""}><b>%</b></label>
          <span class="rate-result-label">Duty amount</span><strong class="rate-result" data-bcd-amount>â€”</strong>
        </section>
        <section class="rate-card sws-rate-card">
          <div class="rate-title">Social Welfare Surcharge <small>SWS</small></div>
          <label class="rate-entry" for="tariff-sws-${index}"><input id="tariff-sws-${index}" data-master="sws" aria-label="SWS percent" type="number" min="0" max="100" step="any" placeholder="Rate" value="${escape(sws)}" ${known ? "readonly" : ""}><b>%</b></label>
          <span class="rate-result-label">Surcharge amount</span><strong class="rate-result" data-sws-amount>â€”</strong>
        </section>
      </div>
      <footer class="tariff-card-footer"><small class="catalog-source">${known ? `Source: ${escape(line.master.source || "DigiKey master catalog")}` : "Save these details to reuse them on future lookups."}</small>${line.master?.found === false ? `<button class="button save-master" type="button" ${line.savingMaster ? "disabled" : ""}>${line.savingMaster ? "Saving…" : "Save to catalog"}</button>` : ""}</footer>
    `;
    row.querySelectorAll("[data-master]").forEach((input) => {
      input.addEventListener("input", () => {
        line[input.dataset.master] = input.value;
        line.result = null;
        $("results").classList.add("hidden");
        updateTariffAmounts();
      });
    });
    row.querySelector(".save-master")?.addEventListener("click", () => saveMasterRecord(line));
    body.appendChild(row);
  });
  updateTariffAmounts();
}

async function saveMasterRecord(line) {
  if (!line.mpn?.trim()) {
    showError("Enter an MPN before saving catalog details.");
    return;
  }
  const record = {
    mpn: line.mpn.trim(),
    category: line.category || line.catalogCategory,
    hsn: line.hsn,
    bcd: line.bcd,
    sws: line.sws,
  };
  if (Object.values(record).some((value) => value == null || String(value).trim() === "")) {
    showError("Enter category, HSN / CTSH, BCD, and SWS before saving to the catalog.");
    return;
  }
  clearError();
  line.savingMaster = true;
  renderTariffs();
  try {
    const response = await fetch("/api/landing/v2/master", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: [record] }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not save catalog details.");
    const lookup = await fetch(`/api/landing/v2/product/${encodeURIComponent(line.mpn.trim())}`);
    const catalog = await lookup.json();
    if (!lookup.ok || !catalog.found) throw new Error("Saved, but the catalog record could not be reloaded.");
    line.master = { ...catalog, found: true };
    line.category = catalog.category;
    line.catalogCategory = catalog.category;
    line.hsn = catalog.hsn;
    line.bcd = catalog.bcd;
    line.sws = catalog.sws;
    line.result = null;
    $("results").classList.add("hidden");
    renderLines();
    renderTariffs();
    updateTariffAmounts();
  } catch (error) {
    showError(error.message);
  } finally {
    line.savingMaster = false;
    renderTariffs();
  }
}

function newLine(fields = {}) {
  return {
    mpn: "", quantity: 1, unit_price: "",
    sws: "10",
    master: null, productDetails: null, liveQuote: null, priceSource: "", ...fields
  };
}

function updateSelectedMatch(line) {
  line.selectedProduct = Number.isInteger(line.selectedMatchIndex)
    ? line.productDetails?.matches?.[line.selectedMatchIndex] || null : null;
  line.needsMatchSelection = Boolean(line.productDetails?.matches?.length && !line.selectedProduct);
  if (!line.selectedProduct) { line.selectedVariation = null; line.needsVariationSelection = false; return; }
  const variations = line.selectedProduct.variations
    .map((variation, variationIndex) => ({ variation, variationIndex }))
    .filter(({ variation }) => variation && typeof variation === "object");
  const selected = variations.sort((left, right) =>
    Number(left.variation.minimum_order_quantity || 0) - Number(right.variation.minimum_order_quantity || 0)
  )[0];
  line.selectedVariationIndex = selected?.variationIndex ?? null;
  line.selectedVariation = selected?.variation ?? null;
  line.needsVariationSelection = false;
  line.cutTapePackageUnavailable = variations.length === 0;
  // Preserve live DigiKey product data separately from local tariff metadata.
  line.liveCategory = line.master?.found ? line.master.category : "";
}

function applyDigiKeyTier(line, allowReplace = false) {
  updateSelectedMatch(line);
  const variation = line.selectedVariation;
  line.liveQuote = null;
  if (!line.selectedProduct) { line.pricingMessage = line.productDetails?.matches?.length ? "Select a DigiKey match." : ""; return; }
  if (!variation) {
    line.pricingMessage = line.cutTapePackageUnavailable
      ? "DigiKey package details are unavailable; price and stock are unavailable."
      : "DigiKey package details are unavailable.";
    if (line.priceSource === "digikey") { line.unit_price = ""; line.priceSource = ""; }
    return;
  }
  const quantity = Math.ceil(Number(line.quantity));
  const validTiers = (variation.pricing_tiers || []).filter((entry) =>
    Number.isInteger(Number(entry.break_quantity)) && Number(entry.break_quantity) > 0 &&
    Number.isFinite(Number(entry.unit_price)) && Number(entry.unit_price) >= 0 && Boolean(entry.currency)
  );
  const applicableTiers = validTiers.filter((entry) => Number(entry.break_quantity) <= quantity);
  const tier = applicableTiers.sort((left, right) => Number(right.break_quantity) - Number(left.break_quantity))[0]
    || validTiers.sort((left, right) => Number(left.break_quantity) - Number(right.break_quantity))[0];
  if (variation.minimum_order_quantity && quantity < variation.minimum_order_quantity) {
    line.pricingMessage = `DigiKey minimum order quantity is ${variation.minimum_order_quantity}.`;
    if (line.priceSource === "digikey") { line.unit_price = ""; line.priceSource = ""; }
    return;
  }
  if (!tier) {
    line.pricingMessage = "DigiKey returned no valid pricing tiers for this package.";
    if (line.priceSource === "digikey") { line.unit_price = ""; line.priceSource = ""; }
    return;
  }
  line.pricingMessage = "";
  const canUse = allowReplace || !line.unit_price || line.priceSource === "digikey";
  if (canUse && tier.currency !== $("invoiceCurrency").value) {
    const safe = state.lines.every((entry) => entry === line || !entry.unit_price || entry.priceSource === "digikey");
    const selector = $("invoiceCurrency");
    if (safe && [...selector.options].some((option) => option.value === tier.currency)) {
      selector.value = tier.currency;
      updatePriceSettings();
    }
  }
  line.priceCurrencyMismatch = null;
  if (canUse && tier.currency === $("invoiceCurrency").value) {
    line.unit_price = String(tier.unit_price);
    line.priceSource = "digikey";
  } else if (canUse) {
    line.priceCurrencyMismatch = { liveCurrency: tier.currency, shipmentCurrency: $("invoiceCurrency").value };
  }
  line.liveQuote = {
    digikey_product_number: variation.digikey_product_number,
    requested_quantity: quantity,
    break_quantity: tier.break_quantity,
    unit_price: tier.unit_price,
    extended_price: quantity * tier.unit_price,
    currency: tier.currency,
    available_quantity: variation.available_quantity,
  };
}

async function lookupProduct(index) {
  const line = state.lines[index];
  if (!line || !line.mpn?.trim()) return;
  const mpn = line.mpn.trim();
  const currency = $("invoiceCurrency").value;
  if (line.productDetails?.queried_mpn === mpn && line.productDetails?.query_currency === currency) {
    line.quoteCached = true;
    applyDigiKeyTier(line, true);
    renderLines();
    return;
  }
  const revision = (line.lookupRevision || 0) + 1;
  line.lookupRevision = revision;
  line.loading = true;
  line.lookupMessage = "Searching DigiKey live product data...";
  renderLines();
  try {
  const [response, liveResponse] = await Promise.all([
    fetch(`/api/landing/v2/product/${encodeURIComponent(mpn)}`),
    fetch(`/api/landing/v2/digikey-product/${encodeURIComponent(mpn)}?currency=${encodeURIComponent(currency)}`),
  ]);
  const data = await response.json();
  const liveData = await liveResponse.json();
  if (!response.ok) throw new Error(data.error || "Product lookup failed.");
  if (revision !== line.lookupRevision || line.mpn.trim() !== mpn) return;
  line.master = data.found ? { ...data, found: true } : { found: false };
  line.productDetails = liveResponse.ok && liveData.found ? liveData : { matches: [] };
  line.productDetails.queried_mpn = mpn;
  line.productDetails.query_currency = currency;
  line.selectedMatchIndex = null;
  line.selectedVariationIndex = null;
  line.fetchedAt = new Date().toLocaleTimeString();
  line.quoteCached = false;
  const matches = line.productDetails.matches || [];
  const exact = matches.map((match, matchIndex) => ({ match, matchIndex })).filter(({ match }) => match.exact_mpn_match);
  if (exact.length === 1) line.selectedMatchIndex = exact[0].matchIndex;
  else if (matches.length === 1) line.selectedMatchIndex = 0;
  updateSelectedMatch(line);
  if (data.found) {
    line.catalogCategory = data.category;
    line.bcd = data.bcd;
    line.sws = data.sws;
  } else if (line.selectedProduct) {
    line.catalogCategory = "";
    line.sws = line.sws || "10";
  }
  if (matches.length) {
    line.lookupMessage = exact.length > 1 ? "Multiple exact matches; choose one." : matches.length > 1 ? "Choose the matching DigiKey product." : "DigiKey product found.";
    applyDigiKeyTier(line, true);
  } else {
    line.lookupMessage = liveData.error || "MPN not found in DigiKey.";
    line.pricingMessage = "Price and stock unavailable.";
    if (line.priceSource === "digikey") { line.unit_price = ""; line.priceSource = ""; }
  }
  line.result = null;
  renderLines();
  renderTariffs();
  } finally {
    if (revision === line.lookupRevision) {
      line.loading = false;
      renderLines();
    }
  }
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
    `${data.items.length} line item(s) â€¢ Shipment invoice ${inr(data.totals.total_invoice_inr)}`;
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
            <dt>Category / HSN</dt><dd>${escape(item.category || "â€”")} / ${escape(item.hsn || "â€”")}</dd>
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
  button.textContent = "Calculatingâ€¦";
  try {
    for (const line of state.lines) {
      if (!line.mpn?.trim()) throw new Error("Enter an MPN for every product line.");
      if (!line.productDetails) throw new Error(`Search DigiKey for ${line.mpn} before calculating.`);
      if (line.needsMatchSelection) throw new Error(`Select the DigiKey match for ${line.mpn}.`);
      if (!line.selectedVariation) throw new Error(`${line.mpn}: DigiKey did not return a package variation.`);
      if (!line.liveQuote || line.liveQuote.requested_quantity !== Number(line.quantity) ||
          $("invoiceCurrency").value !== line.liveQuote.currency ||
          (line.priceSource !== "user" && Number(line.unit_price) !== line.liveQuote.unit_price)) {
        throw new Error(`${line.mpn}: refresh the DigiKey price for the current quantity and currency before calculating.`);
      }
      if (line.selectedVariation.minimum_order_quantity && Number(line.quantity) < line.selectedVariation.minimum_order_quantity) {
        throw new Error(`${line.mpn}: DigiKey minimum order quantity is ${line.selectedVariation.minimum_order_quantity}.`);
      }
      if (line.selectedVariation?.available_quantity != null && Number(line.quantity) > line.selectedVariation.available_quantity) {
        throw new Error(`${line.mpn}: only ${line.selectedVariation.available_quantity} in DigiKey stock; requested ${line.quantity}.`);
      }
      line.quoteCached = true;
    }
    const payload = {
      items: state.lines.map((line) => ({
        mpn: line.mpn,
        quantity: line.quantity,
        unit_price: line.unit_price,
        currency: $("invoiceCurrency").value,
        live_exchange_rate: $("liveRate").value,
        ...(!line.master?.found
          ? { category: line.liveCategory || line.category, bcd_rate: line.bcd, sws_rate: line.sws }
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
