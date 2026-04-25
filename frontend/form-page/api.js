(function () {
  var page = window.RegDocFormPage;
  if (!page) return;

  function formatDetail(detail) {
    if (!detail) return '';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map(function (item) {
        if (!item) return '';
        if (typeof item === 'string') return item;
        var path = Array.isArray(item.loc) ? item.loc.filter(function (part) { return part !== 'body'; }).join('.') : '';
        var msg = item.msg || item.detail || '';
        return path ? (path + ': ' + msg) : msg;
      }).filter(Boolean).join('\n');
    }
    if (typeof detail === 'object') {
      return detail.detail || detail.message || JSON.stringify(detail);
    }
    return String(detail);
  }

  page.showError = function (msg) {
    alert('Ошибка: ' + formatDetail(msg));
  };

  page.extractError = async function (response) {
    var payload = await response.json().catch(function () { return { detail: response.statusText }; });
    throw new Error(formatDetail(payload && payload.detail) || response.statusText || 'Ошибка запроса');
  };

  page.addSelectedDocument = function () {
    if (!page.docSelect) return;
    var checked = Array.prototype.slice.call(page.docSelect.querySelectorAll('input[type="checkbox"]:checked:not(:disabled)'));
    if (!checked.length) return;
    var existing = {};
    page.state.selectedDocuments.forEach(function (item) {
      existing[item.template] = true;
    });
    checked.forEach(function (input) {
      var template = input.value;
      if (!template || existing[template]) return;
      var item = page.state.priceList.find(function (priceItem) { return priceItem.template === template; });
      if (!item) return;
      page.state.selectedDocuments.push({
        template: item.template,
        label: item.label || item.template,
        price: item.price
      });
      existing[template] = true;
    });
    page.renderDocumentsList();
    if (page.renderDocumentChecklist) page.renderDocumentChecklist();
    page.syncFromMainForm();
  };

  page.buildOrderPayload = function () {
    var needPlate = page.inputs.needPlate && page.inputs.needPlate.checked;
    var plateQuantity = needPlate ? page.getPlateQuantity() : 1;
    var platePrice = needPlate ? page.PLATE_PRICE_PER_UNIT * plateQuantity : 0;
    var inputs = page.inputs;
    var clientPassport = page.composePassport('client');
    var sellerPassport = page.composePassport('seller');
    var trusteePassport = page.composePassport('trustee');
    var srts = page.composeVehicleDoc('srts');
    var pts = page.composeVehicleDoc('pts');

    return {
      client_fio: (inputs.clientFio && inputs.clientFio.value.trim()) || null,
      client_birth_date: (inputs.clientBirthDate && inputs.clientBirthDate.value.trim()) || null,
      client_birth_place: (inputs.clientBirthPlace && inputs.clientBirthPlace.value.trim()) || null,
      client_passport: clientPassport,
      client_passport_series: (inputs.clientPassportSeries && inputs.clientPassportSeries.value.trim()) || null,
      client_passport_number: (inputs.clientPassportNumber && inputs.clientPassportNumber.value.trim()) || null,
      client_passport_issued_by: (inputs.clientPassportIssuedBy && inputs.clientPassportIssuedBy.value.trim()) || null,
      client_passport_issued_date: (inputs.clientPassportIssuedDate && inputs.clientPassportIssuedDate.value.trim()) || null,
      client_passport_division_code: (inputs.clientPassportDivisionCode && inputs.clientPassportDivisionCode.value.trim()) || null,
      client_address: (inputs.clientAddress && inputs.clientAddress.value.trim()) || null,
      client_phone: page.composePhone(),
      client_comment: null,
      client_is_legal: !!(inputs.clientIsLegal && inputs.clientIsLegal.checked),
      client_legal_name: (inputs.clientLegalName && inputs.clientLegalName.value.trim()) || null,
      client_inn: (inputs.clientInn && inputs.clientInn.value.trim()) || null,
      client_ogrn: (inputs.clientOgrn && inputs.clientOgrn.value.trim()) || null,
      seller_fio: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerFio && inputs.sellerFio.value.trim()) ? inputs.sellerFio.value.trim() : null,
      seller_birth_date: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerBirthDate && inputs.sellerBirthDate.value.trim()) ? inputs.sellerBirthDate.value.trim() : null,
      seller_passport: (inputs.hasSeller && inputs.hasSeller.checked) ? sellerPassport : null,
      seller_passport_series: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerPassportSeries && inputs.sellerPassportSeries.value.trim()) ? inputs.sellerPassportSeries.value.trim() : null,
      seller_passport_number: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerPassportNumber && inputs.sellerPassportNumber.value.trim()) ? inputs.sellerPassportNumber.value.trim() : null,
      seller_passport_issued_by: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerPassportIssuedBy && inputs.sellerPassportIssuedBy.value.trim()) ? inputs.sellerPassportIssuedBy.value.trim() : null,
      seller_passport_issued_date: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerPassportIssuedDate && inputs.sellerPassportIssuedDate.value.trim()) ? inputs.sellerPassportIssuedDate.value.trim() : null,
      seller_passport_division_code: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerPassportDivisionCode && inputs.sellerPassportDivisionCode.value.trim()) ? inputs.sellerPassportDivisionCode.value.trim() : null,
      seller_address: (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerAddress && inputs.sellerAddress.value.trim()) ? inputs.sellerAddress.value.trim() : null,
      trustee_fio: (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteeFio && inputs.trusteeFio.value.trim()) ? inputs.trusteeFio.value.trim() : null,
      trustee_birth_date: (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteeBirthDate && inputs.trusteeBirthDate.value.trim()) ? inputs.trusteeBirthDate.value.trim() : null,
      trustee_passport: (inputs.hasTrustee && inputs.hasTrustee.checked) ? trusteePassport : null,
      trustee_passport_series: (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteePassportSeries && inputs.trusteePassportSeries.value.trim()) ? inputs.trusteePassportSeries.value.trim() : null,
      trustee_passport_number: (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteePassportNumber && inputs.trusteePassportNumber.value.trim()) ? inputs.trusteePassportNumber.value.trim() : null,
      trustee_passport_issued_by: (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteePassportIssuedBy && inputs.trusteePassportIssuedBy.value.trim()) ? inputs.trusteePassportIssuedBy.value.trim() : null,
      trustee_passport_issued_date: (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteePassportIssuedDate && inputs.trusteePassportIssuedDate.value.trim()) ? inputs.trusteePassportIssuedDate.value.trim() : null,
      trustee_passport_division_code: (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteePassportDivisionCode && inputs.trusteePassportDivisionCode.value.trim()) ? inputs.trusteePassportDivisionCode.value.trim() : null,
      trustee_basis: null,
      vin: (inputs.vin && inputs.vin.value.trim()) || null,
      brand_model: (inputs.brandModel && inputs.brandModel.value.trim()) || null,
      vehicle_type: (inputs.vehicleType && inputs.vehicleType.value.trim()) || null,
      year: (inputs.year && inputs.year.value.trim()) || null,
      engine: (inputs.engine && inputs.engine.value.trim()) || null,
      chassis: (inputs.chassis && inputs.chassis.value.trim()) || null,
      power: (inputs.power && inputs.power.value.trim()) || null,
      mass: (inputs.mass && inputs.mass.value.trim()) || null,
      body: (inputs.body && inputs.body.value.trim()) || null,
      color: (inputs.color && inputs.color.value.trim()) || null,
      srts: srts,
      srts_series: (inputs.srtsSeries && inputs.srtsSeries.value.trim()) || null,
      srts_number: (inputs.srtsNumber && inputs.srtsNumber.value.trim()) || null,
      srts_issued_by: (inputs.srtsIssuedBy && inputs.srtsIssuedBy.value.trim()) || null,
      srts_issued_date: (inputs.srtsIssuedDate && inputs.srtsIssuedDate.value.trim()) || null,
      plate_number: (inputs.plateNumber && inputs.plateNumber.value.trim()) || null,
      pts: pts,
      pts_series: (inputs.ptsSeries && inputs.ptsSeries.value.trim()) || null,
      pts_number: (inputs.ptsNumber && inputs.ptsNumber.value.trim()) || null,
      pts_issued_by: (inputs.ptsIssuedBy && inputs.ptsIssuedBy.value.trim()) || null,
      pts_issued_date: (inputs.ptsIssuedDate && inputs.ptsIssuedDate.value.trim()) || null,
      dkp_date: (inputs.hasSeller && inputs.hasSeller.checked && inputs.dkpDate && inputs.dkpDate.value.trim()) ? inputs.dkpDate.value.trim() : null,
      dkp_number: (inputs.hasSeller && inputs.hasSeller.checked && inputs.dkpNumber && inputs.dkpNumber.value.trim()) ? inputs.dkpNumber.value.trim() : null,
      dkp_summary: (!inputs.hasSeller || !inputs.hasSeller.checked) && inputs.dkpSummary && inputs.dkpSummary.value.trim() ? inputs.dkpSummary.value.trim() : null,
      service_type: page.state.selectedDocuments[0] ? page.state.selectedDocuments[0].template : null,
      need_plate: needPlate,
      plate_quantity: plateQuantity,
      state_duty: page.getStateDuty(),
      extra_amount: 0,
      plate_amount: platePrice,
      summa_dkp: (inputs.hasSeller && inputs.hasSeller.checked && inputs.summaDkp) ? page.num(inputs.summaDkp.value) : 0,
      documents: page.state.selectedDocuments.filter(function (item) { return !item.paymentOnly; }).map(function (item) {
        return { template: item.template, price: page.num(item.price), label: item.label || item.template };
      })
    };
  };

  page.acceptCash = async function () {
    var total = page.getTotal();
    if (total <= 0) return;
    page.btnAcceptCash.disabled = true;
    page.btnAcceptCash.textContent = 'Отправка…';
    try {
      var resOrder = await page.fetchApi(page.apiBaseUrl + '/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(page.buildOrderPayload())
      });
      if (!resOrder.ok) await page.extractError(resOrder);
      var order = await resOrder.json();
      var resPay = await page.fetchApi(page.apiBaseUrl + '/orders/' + order.id + '/pay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!resPay.ok) await page.extractError(resPay);
      page.orderIdDisplay.textContent = 'Заказ: ' + (order.public_id || order.id);
      page.orderIdDisplay.style.fontWeight = '600';
      page.btnAcceptCash.textContent = 'Оплата принята';
      window.lastOrderId = order.id;
      window.lastOrderDocuments = page.state.selectedDocuments.filter(function (item) { return !item.paymentOnly; }).map(function (item) { return item.template; });
      page.state.loadedFromHistory = false;
      if (typeof page.loadFormHistory === 'function') page.loadFormHistory();
    } catch (e) {
      page.btnAcceptCash.disabled = false;
      page.btnAcceptCash.textContent = 'Принять наличные';
      page.showError(e.message || 'Не удалось создать заказ');
    }
  };

  page.applyFormData = function (formData) {
    if (!formData) return;
    var inputs = page.inputs;
    var clientPassport = page.splitPassport(formData.client_passport);
    var sellerPassport = page.splitPassport(formData.seller_passport);
    var trusteePassport = page.splitPassport(formData.trustee_passport);
    var srts = page.splitVehicleDoc(formData.srts);
    var pts = page.splitVehicleDoc(formData.pts);
    page.setVal(inputs.clientFio, formData.client_fio);
    page.setVal(inputs.clientBirthDate, formData.client_birth_date);
    page.setVal(inputs.clientBirthPlace, formData.client_birth_place);
    page.setVal(inputs.clientPassportSeries, formData.client_passport_series || clientPassport.series);
    page.setVal(inputs.clientPassportNumber, formData.client_passport_number || clientPassport.number);
    page.setVal(inputs.clientPassportIssuedBy, formData.client_passport_issued_by);
    page.setVal(inputs.clientPassportIssuedDate, formData.client_passport_issued_date);
    page.setVal(inputs.clientPassportDivisionCode, formData.client_passport_division_code);
    page.setVal(inputs.clientAddress, formData.client_address);
    page.setVal(inputs.clientPhone, formData.client_phone ? page.formatPhone(formData.client_phone) : page.formatPhone(''));
    page.setVal(inputs.clientIsLegal, formData.client_is_legal);
    page.setVal(inputs.clientLegalName, formData.client_legal_name);
    page.setVal(inputs.clientInn, formData.client_inn);
    page.setVal(inputs.clientOgrn, formData.client_ogrn);
    page.setVal(inputs.hasSeller, !!(formData.seller_fio || formData.seller_passport || formData.seller_address));
    page.setVal(inputs.sellerFio, formData.seller_fio);
    page.setVal(inputs.sellerBirthDate, formData.seller_birth_date);
    page.setVal(inputs.sellerPassportSeries, formData.seller_passport_series || sellerPassport.series);
    page.setVal(inputs.sellerPassportNumber, formData.seller_passport_number || sellerPassport.number);
    page.setVal(inputs.sellerPassportIssuedBy, formData.seller_passport_issued_by);
    page.setVal(inputs.sellerPassportIssuedDate, formData.seller_passport_issued_date);
    page.setVal(inputs.sellerPassportDivisionCode, formData.seller_passport_division_code);
    page.setVal(inputs.sellerAddress, formData.seller_address);
    page.setVal(inputs.hasTrustee, !!(formData.trustee_fio || formData.trustee_passport || formData.trustee_basis));
    page.setVal(inputs.trusteeFio, formData.trustee_fio);
    page.setVal(inputs.trusteeBirthDate, formData.trustee_birth_date);
    page.setVal(inputs.trusteePassportSeries, formData.trustee_passport_series || trusteePassport.series);
    page.setVal(inputs.trusteePassportNumber, formData.trustee_passport_number || trusteePassport.number);
    page.setVal(inputs.trusteePassportIssuedBy, formData.trustee_passport_issued_by);
    page.setVal(inputs.trusteePassportIssuedDate, formData.trustee_passport_issued_date);
    page.setVal(inputs.trusteePassportDivisionCode, formData.trustee_passport_division_code);
    page.setVal(inputs.vin, formData.vin);
    page.setVal(inputs.brandModel, formData.brand_model);
    page.setVal(inputs.vehicleType, formData.vehicle_type);
    page.setVal(inputs.year, formData.year);
    page.setVal(inputs.engine, formData.engine);
    page.setVal(inputs.chassis, formData.chassis);
    page.setVal(inputs.power, formData.power);
    page.setVal(inputs.mass, formData.mass);
    page.setVal(inputs.body, formData.body);
    page.setVal(inputs.color, formData.color);
    page.setVal(inputs.srtsSeries, formData.srts_series || srts.series);
    page.setVal(inputs.srtsNumber, formData.srts_number || srts.number);
    page.setVal(inputs.srtsIssuedBy, formData.srts_issued_by);
    page.setVal(inputs.srtsIssuedDate, formData.srts_issued_date);
    page.setVal(inputs.plateNumber, formData.plate_number);
    page.setVal(inputs.ptsSeries, formData.pts_series || pts.series);
    page.setVal(inputs.ptsNumber, formData.pts_number || pts.number);
    page.setVal(inputs.ptsIssuedBy, formData.pts_issued_by);
    page.setVal(inputs.ptsIssuedDate, formData.pts_issued_date);
    page.setVal(inputs.dkpDate, formData.dkp_date);
    page.setVal(inputs.dkpNumber, formData.dkp_number);
    page.setVal(inputs.dkpSummary, formData.dkp_summary);
    page.setVal(inputs.summaDkp, formData.summa_dkp != null ? formData.summa_dkp : '');
    page.setVal(inputs.stateDuty, formData.state_duty != null ? formData.state_duty : '');
    page.setVal(inputs.needPlate, formData.need_plate);
    page.setVal(inputs.plateQuantity, formData.plate_quantity != null ? formData.plate_quantity : 1);
    window.lastOrderId = null;
    window.lastOrderDocuments = null;
    page.state.loadedFromHistory = true;
    if (page.orderIdDisplay) page.orderIdDisplay.textContent = 'Данные из истории';
    page.state.selectedDocuments = (formData.documents || []).map(function (item) {
      return { template: item.template || '', label: item.label || item.template || '', price: page.num(item.price) };
    });
    page.toggleClientType();
    var sellerBody = page.el('sellerBody');
    var trusteeBody = page.el('trusteeBody');
    if (sellerBody) sellerBody.classList.toggle('form-section__body--closed', !(inputs.hasSeller && inputs.hasSeller.checked));
    if (trusteeBody) trusteeBody.classList.toggle('form-section__body--closed', !(inputs.hasTrustee && inputs.hasTrustee.checked));
    page.syncPlateToDocuments();
  };

  page.loadFormHistory = async function () {
    var listEl = page.formHistoryList;
    var loadingEl = page.formHistoryLoading;
    if (!listEl) return;
    if (loadingEl) loadingEl.textContent = 'Загрузка…';
    try {
      var response = await page.fetchApi(page.apiBaseUrl + '/form-history?limit=50');
      if (!response.ok) throw new Error(response.statusText);
      var items = await response.json();
      if (!Array.isArray(items)) items = [];
      page.state.historyItems = items.map(function (item) {
        var data = item.form_data || {};
        return {
          form_data: data,
          label: data.client_fio || data.client_legal_name || 'Без имени',
          created_label: item.created_at
            ? new Date(item.created_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
            : ''
        };
      });
      page.state.historyPage = 0;
      page.renderHistoryPage();
    } catch (_) {
      page.state.historyItems = [];
      page.state.historyPage = 0;
      listEl.innerHTML = '<li class="form-history-list__loading">Не удалось загрузить историю</li>';
      if (page.historyRange) page.historyRange.textContent = '0–0';
      if (page.historyPrev) page.historyPrev.disabled = true;
      if (page.historyNext) page.historyNext.disabled = true;
    }
  };

  page.createDraftOrderForPrint = async function () {
    var resOrder = await page.fetchApi(page.apiBaseUrl + '/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(page.buildOrderPayload())
    });
    if (!resOrder.ok) await page.extractError(resOrder);
    var order = await resOrder.json();
    window.lastOrderId = order.id;
    window.lastOrderDocuments = page.state.selectedDocuments.filter(function (item) { return !item.paymentOnly; }).map(function (item) { return item.template; });
    if (page.orderIdDisplay) {
      page.orderIdDisplay.textContent = 'Заказ: ' + (order.public_id || order.id);
      page.orderIdDisplay.style.fontWeight = '600';
    }
    if (typeof page.loadFormHistory === 'function') page.loadFormHistory();
    return order.id;
  };

  page.doPrint = async function () {
    var orderId = window.lastOrderId;
    if (!orderId) {
      if (!page.state.loadedFromHistory) {
        alert('Сначала примите оплату по заказу.');
        return;
      }
      try {
        orderId = await page.createDraftOrderForPrint();
      } catch (e) {
        page.showError(e.message || 'Не удалось создать заказ для печати');
        return;
      }
    }
    var templates = window.lastOrderDocuments || [];
    if (!templates.length) {
      alert('Нет списка документов по последнему заказу.');
      return;
    }
    templates.forEach(function (template) {
      var url = page.apiBaseUrl + '/orders/' + orderId + '/documents/' + encodeURIComponent(template);
      window.fetchDocumentWithAuth(url, template).catch(function (err) {
        page.showError(err.message || 'Не удалось открыть документ');
      });
    });
  };

  page.loadPriceList = async function () {
    try {
      var response = await page.fetchApi(page.apiBaseUrl + '/price-list');
      if (!response.ok) throw new Error(response.statusText);
      page.state.priceList = await response.json();
      if (!Array.isArray(page.state.priceList)) page.state.priceList = [];
      if (page.renderDocumentChecklist) page.renderDocumentChecklist();
    } catch (_) {
      if (page.docSelect) page.docSelect.innerHTML = '<span class="document-checklist__loading">Не удалось загрузить прейскурант</span>';
    }
  };

  page.loadStateDutySettings = async function () {
    try {
      var response = await page.fetchApi(page.apiBaseUrl + '/settings/state-duty');
      if (!response.ok) throw new Error(response.statusText);
      var settings = await response.json();
      page.state.stateDutySettings = {
        commission: page.num(settings.commission),
        special_2025_cash_amount: page.num(settings.special_2025_cash_amount)
      };
    } catch (_) {
      page.state.stateDutySettings = {
        commission: 150,
        special_2025_cash_amount: 2200
      };
    }
  };
})();
