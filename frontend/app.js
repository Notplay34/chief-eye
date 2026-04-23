/**
 * Павильон 1 — веб-форма операторов.
 * Документы выбираются из прейскуранта и добавляются в список; сумма считается автоматически.
 */

(function () {
  var API_BASE_URL = window.API_BASE_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : '');
  var fetchApi = window.fetchWithAuth || fetch;
  if (window.getToken && !window.getToken()) return;

  var priceList = [];
  var selectedDocuments = [];

  var el = function (id) { return document.getElementById(id); };

  var inputs = {
    clientFio: el('clientFio'),
    clientPassport: el('clientPassport'),
    clientAddress: el('clientAddress'),
    clientPhone: el('clientPhone'),
    clientIsLegal: el('clientIsLegal'),
    clientLegalName: el('clientLegalName'),
    clientInn: el('clientInn'),
    clientOgrn: el('clientOgrn'),
    hasSeller: el('hasSeller'),
    sellerFio: el('sellerFio'),
    sellerPassport: el('sellerPassport'),
    sellerAddress: el('sellerAddress'),
    hasTrustee: el('hasTrustee'),
    trusteeFio: el('trusteeFio'),
    trusteePassport: el('trusteePassport'),
    trusteeBasis: el('trusteeBasis'),
    vin: el('vin'),
    brandModel: el('brandModel'),
    vehicleType: el('vehicleType'),
    year: el('year'),
    engine: el('engine'),
    chassis: el('chassis'),
    body: el('body'),
    color: el('color'),
    srts: el('srts'),
    plateNumber: el('plateNumber'),
    pts: el('pts'),
    dkpDate: el('dkpDate'),
    summaDkp: el('summaDkp'),
    dkpNumber: el('dkpNumber'),
    dkpSummary: el('dkpSummary'),
    stateDuty: el('stateDuty'),
    needPlate: el('needPlate'),
    plateQuantity: el('plateQuantity')
  };

  var docSelect = el('docSelect');
  var btnAddDoc = el('btnAddDoc');
  var documentsList = el('documentsList');
  var documentsEmpty = el('documentsEmpty');
  var docList = el('docList');
  var summary = {
    sumStateDuty: el('sumStateDuty'),
    sumIncome: el('sumIncome'),
    sumTotal: el('sumTotal')
  };
  var preview = {
    previewFio: el('previewFio'),
    previewPassport: el('previewPassport'),
    previewAddress: el('previewAddress'),
    previewPhone: el('previewPhone'),
    previewSeller: el('previewSeller'),
    previewTrustee: el('previewTrustee'),
    previewVehicle: el('previewVehicle'),
    previewDkp: el('previewDkp'),
    previewService: el('previewService'),
    previewTotal: el('previewTotal')
  };
  var btnAcceptCash = el('btnAcceptCash');
  var btnPrint = el('btnPrint');
  var orderIdDisplay = el('orderIdDisplay');
  var currentTime = el('currentTime');

  function num(val) {
    if (val === null || val === undefined || val === '') return 0;
    var s = String(val).replace(/\s/g, '').replace(',', '.');
    var n = parseFloat(s);
    return isNaN(n) ? 0 : n;
  }

  function getStateDuty() {
    return num(inputs.stateDuty && inputs.stateDuty.value);
  }

  function getDocumentsTotal() {
    return selectedDocuments.reduce(function (sum, d) { return sum + num(d.price); }, 0);
  }

  function getTotal() {
    return getStateDuty() + getDocumentsTotal();
  }

  function formatMoney(value) {
    return new Intl.NumberFormat('ru-RU', { style: 'decimal', minimumFractionDigits: 0 }).format(value) + ' ₽';
  }

  function renderDocumentsList() {
    var forPayment = selectedDocuments.filter(function (d) { return !isPlateZaiavlenie(d); });
    if (documentsEmpty) documentsEmpty.style.display = forPayment.length ? 'none' : 'block';
    if (!documentsList) return;
    documentsList.innerHTML = selectedDocuments.map(function (d, i) {
      if (isPlateZaiavlenie(d)) return '';
      return '<li class="documents-to-print__item">' +
        '<span class="documents-to-print__item-info">' +
          '<span>' + (d.label || d.template) + '</span>' +
          '<span class="documents-to-print__item-price">' + formatMoney(num(d.price)) + '</span>' +
        '</span>' +
        '<button type="button" class="documents-to-print__item-remove" data-index="' + i + '">Удалить</button>' +
      '</li>';
    }).filter(Boolean).join('');
    documentsList.querySelectorAll('.documents-to-print__item-remove').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.getAttribute('data-index'), 10);
        selectedDocuments.splice(idx, 1);
        renderDocumentsList();
        syncFromMainForm();
      });
    });
  }

  function updateSummary() {
    var duty = getStateDuty();
    var income = getDocumentsTotal();
    var total = getTotal();
    if (summary.sumStateDuty) summary.sumStateDuty.textContent = formatMoney(duty);
    if (summary.sumIncome) summary.sumIncome.textContent = formatMoney(income);
    if (summary.sumTotal) summary.sumTotal.textContent = formatMoney(total);
    var isLegal = inputs.clientIsLegal && inputs.clientIsLegal.checked;
    var clientFilled = isLegal
      ? (inputs.clientLegalName && inputs.clientLegalName.value.trim())
      : (inputs.clientFio && inputs.clientFio.value.trim());
    var canPay = total > 0 && clientFilled && selectedDocuments.length > 0;
    if (btnAcceptCash) btnAcceptCash.disabled = !canPay;
    if (btnPrint) btnPrint.disabled = !canPay;
  }

  function updatePreview() {
    var isLegal = inputs.clientIsLegal && inputs.clientIsLegal.checked;
    var fio = isLegal ? '—' : ((inputs.clientFio && inputs.clientFio.value.trim()) || '—');
    var passport = isLegal ? '—' : ((inputs.clientPassport && inputs.clientPassport.value.trim()) || '—');
    var address = (inputs.clientAddress && inputs.clientAddress.value.trim()) || '—';
    var phone = (inputs.clientPhone && inputs.clientPhone.value.trim()) || '—';
    var seller = '—';
    if (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerFio && inputs.sellerFio.value.trim()) {
      seller = [inputs.sellerFio.value.trim(), inputs.sellerPassport && inputs.sellerPassport.value.trim(), inputs.sellerAddress && inputs.sellerAddress.value.trim()].filter(Boolean).join(', ');
    }
    var trustee = '—';
    if (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteeFio && inputs.trusteeFio.value.trim()) {
      trustee = [inputs.trusteeFio.value.trim(), inputs.trusteePassport && inputs.trusteePassport.value.trim(), inputs.trusteeBasis && inputs.trusteeBasis.value.trim()].filter(Boolean).join(' · ');
    }
    var vehicle = (inputs.vin && inputs.vin.value.trim()) || (inputs.brandModel && inputs.brandModel.value.trim()) ? [inputs.vin && inputs.vin.value.trim(), inputs.brandModel && inputs.brandModel.value.trim()].filter(Boolean).join(' · ') : '—';
    var dkpParts = [];
    if (inputs.dkpDate && inputs.dkpDate.value.trim()) dkpParts.push(inputs.dkpDate.value.trim());
    if (inputs.summaDkp && num(inputs.summaDkp.value) > 0) dkpParts.push(formatMoney(num(inputs.summaDkp.value)));
    if (inputs.dkpNumber && inputs.dkpNumber.value.trim()) dkpParts.push('№ ' + inputs.dkpNumber.value.trim());
    var dkpStr = dkpParts.length ? dkpParts.join(', ') : '—';
    var pullDkp = inputs.hasSeller && inputs.hasSeller.checked && dkpStr !== '—';
    if (inputs.dkpSummary) {
      inputs.dkpSummary.readOnly = !!pullDkp;
      inputs.dkpSummary.classList.toggle('field__input--readonly', !!pullDkp);
      if (pullDkp) inputs.dkpSummary.value = dkpStr;
    }
    if (preview.previewDkp) preview.previewDkp.textContent = pullDkp ? dkpStr : (inputs.dkpSummary && inputs.dkpSummary.value.trim()) || '—';
    var docLabels = selectedDocuments.length ? selectedDocuments.map(function (d) { return d.label || d.template; }).join(', ') : '—';
    if (preview.previewFio) preview.previewFio.textContent = isLegal ? ((inputs.clientLegalName && inputs.clientLegalName.value.trim()) || '—') : fio;
    if (preview.previewPassport) preview.previewPassport.textContent = isLegal ? ('ИНН ' + ((inputs.clientInn && inputs.clientInn.value.trim()) || '—') + (inputs.clientOgrn && inputs.clientOgrn.value.trim() ? ', ОГРН ' + inputs.clientOgrn.value.trim() : '')) : passport;
    if (preview.previewAddress) preview.previewAddress.textContent = address;
    if (preview.previewPhone) preview.previewPhone.textContent = phone;
    if (preview.previewSeller) preview.previewSeller.textContent = seller;
    if (preview.previewTrustee) preview.previewTrustee.textContent = trustee;
    if (preview.previewVehicle) preview.previewVehicle.textContent = vehicle;
    if (preview.previewService) preview.previewService.textContent = docLabels;
    if (preview.previewTotal) preview.previewTotal.textContent = formatMoney(getTotal());
  }

  function updateDocList() {
    if (!docList) return;
    if (!selectedDocuments.length) {
      docList.innerHTML = '<li class="doc-list__item doc-list__item--placeholder">Добавьте документы выше — здесь будет тот же список</li>';
      return;
    }
    docList.innerHTML = selectedDocuments.map(function (d) {
      return '<li class="doc-list__item">' + (d.label || d.template) + '</li>';
    }).join('');
  }

  function syncFromMainForm() {
    updateSummary();
    updatePreview();
    updateDocList();
  }

  function addSelectedDocument() {
    if (!docSelect || !docSelect.value) return;
    var template = docSelect.value;
    var item = priceList.find(function (p) { return p.template === template; });
    if (!item) return;
    selectedDocuments.push({
      template: item.template,
      label: item.label || item.template,
      price: item.price
    });
    renderDocumentsList();
    syncFromMainForm();
  }

  function buildOrderPayload() {
    var user = window.getUser();
    var employeeId = user && user.id ? user.id : null;
    var needPlate = inputs.needPlate && inputs.needPlate.checked;
    var plateQuantity = needPlate ? getPlateQuantity() : 1;
    return {
      client_fio: (inputs.clientFio && inputs.clientFio.value.trim()) || null,
      client_passport: (inputs.clientPassport && inputs.clientPassport.value.trim()) || null,
      client_address: (inputs.clientAddress && inputs.clientAddress.value.trim()) || null,
      client_phone: (inputs.clientPhone && inputs.clientPhone.value.trim()) || null,
      client_comment: null,
      client_is_legal: !!(inputs.clientIsLegal && inputs.clientIsLegal.checked),
      client_legal_name: (inputs.clientLegalName && inputs.clientLegalName.value.trim()) || null,
      client_inn: (inputs.clientInn && inputs.clientInn.value.trim()) || null,
      client_ogrn: (inputs.clientOgrn && inputs.clientOgrn.value.trim()) || null,
      seller_fio: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerFio && inputs.sellerFio.value.trim()) ? inputs.sellerFio.value.trim() : null,
      seller_passport: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerPassport && inputs.sellerPassport.value.trim()) ? inputs.sellerPassport.value.trim() : null,
      seller_address: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerAddress && inputs.sellerAddress.value.trim()) ? inputs.sellerAddress.value.trim() : null,
      trustee_fio: (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteeFio && inputs.trusteeFio.value.trim()) ? inputs.trusteeFio.value.trim() : null,
      trustee_passport: (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteePassport && inputs.trusteePassport.value.trim()) ? inputs.trusteePassport.value.trim() : null,
      trustee_basis: (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteeBasis && inputs.trusteeBasis.value.trim()) ? inputs.trusteeBasis.value.trim() : null,
      vin: (inputs.vin && inputs.vin.value.trim()) || null,
      brand_model: (inputs.brandModel && inputs.brandModel.value.trim()) || null,
      vehicle_type: (inputs.vehicleType && inputs.vehicleType.value.trim()) || null,
      year: (inputs.year && inputs.year.value.trim()) || null,
      engine: (inputs.engine && inputs.engine.value.trim()) || null,
      chassis: (inputs.chassis && inputs.chassis.value.trim()) || null,
      body: (inputs.body && inputs.body.value.trim()) || null,
      color: (inputs.color && inputs.color.value.trim()) || null,
      srts: (inputs.srts && inputs.srts.value.trim()) || null,
      plate_number: (inputs.plateNumber && inputs.plateNumber.value.trim()) || null,
      pts: (inputs.pts && inputs.pts.value.trim()) || null,
      dkp_date: (inputs.hasSeller && inputs.hasSeller.checked && inputs.dkpDate && inputs.dkpDate.value.trim()) ? inputs.dkpDate.value.trim() : null,
      dkp_number: (inputs.hasSeller && inputs.hasSeller.checked && inputs.dkpNumber && inputs.dkpNumber.value.trim()) ? inputs.dkpNumber.value.trim() : null,
      dkp_summary: (!inputs.hasSeller || !inputs.hasSeller.checked) && inputs.dkpSummary && inputs.dkpSummary.value.trim() ? inputs.dkpSummary.value.trim() : null,
      service_type: selectedDocuments[0] ? selectedDocuments[0].template : null,
      need_plate: needPlate,
      plate_quantity: plateQuantity,
      state_duty: getStateDuty(),
      extra_amount: 0,
      plate_amount: 0,
      summa_dkp: (inputs.hasSeller && inputs.hasSeller.checked && inputs.summaDkp) ? num(inputs.summaDkp.value) : 0,
      employee_id: employeeId || null,
      documents: selectedDocuments.map(function (d) {
        return { template: d.template, price: num(d.price), label: d.label || d.template };
      })
    };
  }

  function showError(msg) {
    alert('Ошибка: ' + msg);
  }

  async function acceptCash() {
    var total = getTotal();
    if (total <= 0) return;
    btnAcceptCash.disabled = true;
    btnAcceptCash.textContent = 'Отправка…';
    try {
      var resOrder = await fetchApi(API_BASE_URL + '/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildOrderPayload())
      });
      if (!resOrder.ok) {
        var err = await resOrder.json().catch(function () { return { detail: resOrder.statusText }; });
        throw new Error(err.detail || JSON.stringify(err));
      }
      var order = await resOrder.json();
      var resPay = await fetchApi(API_BASE_URL + '/orders/' + order.id + '/pay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!resPay.ok) {
        var errPay = await resPay.json().catch(function () { return { detail: resPay.statusText }; });
        throw new Error(errPay.detail || JSON.stringify(errPay));
      }
      orderIdDisplay.textContent = 'Заказ: ' + (order.public_id || order.id);
      orderIdDisplay.style.fontWeight = '600';
      btnAcceptCash.textContent = 'Оплата принята';
      window.lastOrderId = order.id;
      window.lastOrderDocuments = selectedDocuments.map(function (d) { return d.template; });
      if (typeof loadFormHistory === 'function') loadFormHistory();
    } catch (e) {
      btnAcceptCash.disabled = false;
      btnAcceptCash.textContent = 'Принять наличные';
      showError(e.message || 'Не удалось создать заказ');
    }
  }

  function setVal(inp, val) {
    if (!inp) return;
    if (inp.type === 'checkbox') inp.checked = !!val;
    else inp.value = val != null ? String(val) : '';
  }

  function applyFormData(fd) {
    if (!fd) return;
    setVal(inputs.clientFio, fd.client_fio);
    setVal(inputs.clientPassport, fd.client_passport);
    setVal(inputs.clientAddress, fd.client_address);
    setVal(inputs.clientPhone, fd.client_phone);
    setVal(inputs.clientIsLegal, fd.client_is_legal);
    setVal(inputs.clientLegalName, fd.client_legal_name);
    setVal(inputs.clientInn, fd.client_inn);
    setVal(inputs.clientOgrn, fd.client_ogrn);
    setVal(inputs.hasSeller, !!(fd.seller_fio || fd.seller_passport || fd.seller_address));
    setVal(inputs.sellerFio, fd.seller_fio);
    setVal(inputs.sellerPassport, fd.seller_passport);
    setVal(inputs.sellerAddress, fd.seller_address);
    setVal(inputs.hasTrustee, !!(fd.trustee_fio || fd.trustee_passport || fd.trustee_basis));
    setVal(inputs.trusteeFio, fd.trustee_fio);
    setVal(inputs.trusteePassport, fd.trustee_passport);
    setVal(inputs.trusteeBasis, fd.trustee_basis);
    setVal(inputs.vin, fd.vin);
    setVal(inputs.brandModel, fd.brand_model);
    setVal(inputs.vehicleType, fd.vehicle_type);
    setVal(inputs.year, fd.year);
    setVal(inputs.engine, fd.engine);
    setVal(inputs.chassis, fd.chassis);
    setVal(inputs.body, fd.body);
    setVal(inputs.color, fd.color);
    setVal(inputs.srts, fd.srts);
    setVal(inputs.plateNumber, fd.plate_number);
    setVal(inputs.pts, fd.pts);
    setVal(inputs.dkpDate, fd.dkp_date);
    setVal(inputs.dkpNumber, fd.dkp_number);
    setVal(inputs.dkpSummary, fd.dkp_summary);
    setVal(inputs.summaDkp, fd.summa_dkp != null ? fd.summa_dkp : '');
    setVal(inputs.stateDuty, fd.state_duty != null ? fd.state_duty : '');
    setVal(inputs.needPlate, fd.need_plate);
    setVal(inputs.plateQuantity, fd.plate_quantity != null ? fd.plate_quantity : 1);
    var docs = fd.documents || [];
    selectedDocuments = docs.map(function (d) {
      return { template: d.template || '', label: d.label || d.template || '', price: num(d.price) };
    });
    toggleClientType();
    var sellerBody = el('sellerBody');
    var trusteeBody = el('trusteeBody');
    if (sellerBody) sellerBody.classList.toggle('form-section__body--closed', !(inputs.hasSeller && inputs.hasSeller.checked));
    if (trusteeBody) trusteeBody.classList.toggle('form-section__body--closed', !(inputs.hasTrustee && inputs.hasTrustee.checked));
    renderDocumentsList();
    syncFromMainForm();
    updateDocList();
  }

  async function loadFormHistory() {
    var listEl = el('formHistoryList');
    var loadingEl = el('formHistoryLoading');
    if (!listEl) return;
    if (loadingEl) loadingEl.textContent = 'Загрузка…';
    try {
      var r = await fetchApi(API_BASE_URL + '/form-history?limit=50');
      if (!r.ok) throw new Error(r.statusText);
      var items = await r.json();
      if (!Array.isArray(items)) items = [];
      if (loadingEl) loadingEl.remove();
      if (items.length === 0) {
        listEl.innerHTML = '<li class="form-history-list__loading">Нет записей. Записи появляются после нажатия «Принять наличные».</li>';
        return;
      }
      listEl.innerHTML = items.map(function (item) {
        var fd = item.form_data || {};
        var label = fd.client_fio || fd.client_legal_name || 'Без имени';
        var dt = item.created_at ? new Date(item.created_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
        var dataAttr = 'data-form-data="' + (JSON.stringify(item.form_data || {}).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')) + '"';
        return '<li class="form-history-list__item" ' + dataAttr + '>' + (String(label).replace(/</g, '&lt;')) + ' — ' + dt + '</li>';
      }).join('');
      listEl.querySelectorAll('.form-history-list__item').forEach(function (li) {
        li.addEventListener('click', function () {
          try {
            var data = this.getAttribute('data-form-data');
            if (data) applyFormData(JSON.parse(data));
          } catch (e) { }
        });
      });
    } catch (e) {
      if (listEl) listEl.innerHTML = '<li class="form-history-list__loading">Не удалось загрузить историю</li>';
    }
  }

  function doPrint() {
    var orderId = window.lastOrderId;
    if (!orderId) {
      alert('Сначала примите оплату по заказу (кнопка «Принять наличные»).');
      return;
    }
    var templates = window.lastOrderDocuments || [];
    if (!templates.length) {
      alert('Нет списка документов по последнему заказу.');
      return;
    }
    templates.forEach(function (template) {
      var url = API_BASE_URL + '/orders/' + orderId + '/documents/' + encodeURIComponent(template);
      fetchApi(url).then(function (r) { return r.blob(); }).then(function (blob) {
        var u = URL.createObjectURL(blob);
        window.open(u, '_blank', 'noopener');
      });
    });
  }

  function updateTime() {
    if (currentTime) {
      currentTime.textContent = new Date().toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    }
  }

  function toggleClientType() {
    var isLegal = inputs.clientIsLegal && inputs.clientIsLegal.checked;
    var ind = el('clientIndividual');
    var leg = el('clientLegal');
    if (ind) ind.style.display = isLegal ? 'none' : '';
    if (leg) leg.style.display = isLegal ? '' : 'none';
  }

  function bindInputs() {
    if (inputs.clientIsLegal) {
      inputs.clientIsLegal.addEventListener('change', function () {
        toggleClientType();
        syncFromMainForm();
      });
      toggleClientType();
    }
    Object.keys(inputs).forEach(function (key) {
      var node = inputs[key];
      if (!node) return;
      node.addEventListener('input', syncFromMainForm);
      node.addEventListener('change', syncFromMainForm);
    });
  }

  async function loadPriceList() {
    try {
      var r = await fetchApi(API_BASE_URL + '/price-list');
      if (!r.ok) throw new Error(r.statusText);
      priceList = await r.json();
      if (!Array.isArray(priceList)) priceList = [];
      if (docSelect) {
        var options = priceList.filter(function (p) { return (p.template || '') !== 'number.docx'; });
        docSelect.innerHTML = '<option value="">Выберите документ из списка</option>' +
          options.map(function (p) {
            var price = typeof p.price === 'number' ? p.price : parseFloat(p.price);
            var label = (p.label || p.template) + ' — ' + (isNaN(price) ? '0' : price) + ' ₽';
            return '<option value="' + (p.template || '').replace(/"/g, '&quot;') + '">' + (label.replace(/</g, '&lt;')) + '</option>';
          }).join('');
      }
    } catch (e) {
      if (docSelect) docSelect.innerHTML = '<option value="">Не удалось загрузить прейскурант</option>';
    }
  }

  var PLATE_PRICE_PER_UNIT = 1500;
  function getPlateQuantity() {
    return inputs.plateQuantity ? Math.max(1, parseInt(inputs.plateQuantity.value, 10) || 1) : 1;
  }
  function isPlateZaiavlenie(d) {
    return d.template === 'zaiavlenie.docx' && (d.price === 0 || num(d.price) === 0) && (d.label === 'Заявление на номера' || !d.label);
  }
  function syncPlateToDocuments() {
    var need = inputs.needPlate && inputs.needPlate.checked;
    var qty = getPlateQuantity();
    selectedDocuments = selectedDocuments.filter(function (d) {
      if (d.template === 'number.docx') return false;
      if (isPlateZaiavlenie(d)) return false;
      return true;
    });
    if (need) {
      selectedDocuments.push({ template: 'number.docx', label: 'Изготовление номера', price: PLATE_PRICE_PER_UNIT * qty });
      selectedDocuments.push({ template: 'zaiavlenie.docx', label: 'Заявление на номера', price: 0 });
    }
    if (inputs.plateQuantity) inputs.plateQuantity.disabled = !need;
    renderDocumentsList();
    updateSummary();
    updatePreview();
    updateDocList();
  }
  function setupPlateCheckbox() {
    if (inputs.needPlate) {
      inputs.needPlate.addEventListener('change', syncPlateToDocuments);
    }
    if (inputs.plateQuantity) {
      inputs.plateQuantity.addEventListener('change', syncPlateToDocuments);
      inputs.plateQuantity.disabled = !(inputs.needPlate && inputs.needPlate.checked);
    }
  }

  function setupTogglableSections() {
    var sellerBody = el('sellerBody');
    var trusteeBody = el('trusteeBody');
    if (inputs.hasSeller && sellerBody) {
      sellerBody.classList.toggle('form-section__body--closed', !inputs.hasSeller.checked);
      inputs.hasSeller.addEventListener('change', function () {
        sellerBody.classList.toggle('form-section__body--closed', !inputs.hasSeller.checked);
      });
    }
    if (inputs.hasTrustee && trusteeBody) {
      trusteeBody.classList.toggle('form-section__body--closed', !inputs.hasTrustee.checked);
      inputs.hasTrustee.addEventListener('change', function () {
        trusteeBody.classList.toggle('form-section__body--closed', !inputs.hasTrustee.checked);
      });
    }
  }

  async function init() {
    await loadPriceList();
    bindInputs();
    setupPlateCheckbox();
    setupTogglableSections();
    syncPlateToDocuments();
    renderDocumentsList();
    syncFromMainForm();
    updateTime();
    setInterval(updateTime, 60000);
    if (btnAddDoc) btnAddDoc.addEventListener('click', addSelectedDocument);
    if (docSelect) docSelect.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); addSelectedDocument(); } });
    if (btnAcceptCash) btnAcceptCash.addEventListener('click', acceptCash);
    if (btnPrint) btnPrint.addEventListener('click', doPrint);
    loadFormHistory();
  }

  init();
})();
