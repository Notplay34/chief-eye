(function () {
  var page = window.RegDocFormPage;
  if (!page) return;

  page.showError = function (msg) {
    alert('Ошибка: ' + msg);
  };

  page.addSelectedDocument = function () {
    if (!page.docSelect || !page.docSelect.value) return;
    var template = page.docSelect.value;
    var item = page.state.priceList.find(function (priceItem) { return priceItem.template === template; });
    if (!item) return;
    page.state.selectedDocuments.push({
      template: item.template,
      label: item.label || item.template,
      price: item.price
    });
    page.renderDocumentsList();
    page.syncFromMainForm();
  };

  page.buildOrderPayload = function () {
    var needPlate = page.inputs.needPlate && page.inputs.needPlate.checked;
    var plateQuantity = needPlate ? page.getPlateQuantity() : 1;
    var inputs = page.inputs;

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
      service_type: page.state.selectedDocuments[0] ? page.state.selectedDocuments[0].template : null,
      need_plate: needPlate,
      plate_quantity: plateQuantity,
      state_duty: page.getStateDuty(),
      extra_amount: 0,
      plate_amount: 0,
      summa_dkp: (inputs.hasSeller && inputs.hasSeller.checked && inputs.summaDkp) ? page.num(inputs.summaDkp.value) : 0,
      documents: page.state.selectedDocuments.map(function (item) {
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
      if (!resOrder.ok) {
        var err = await resOrder.json().catch(function () { return { detail: resOrder.statusText }; });
        throw new Error(err.detail || JSON.stringify(err));
      }
      var order = await resOrder.json();
      var resPay = await page.fetchApi(page.apiBaseUrl + '/orders/' + order.id + '/pay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!resPay.ok) {
        var errPay = await resPay.json().catch(function () { return { detail: resPay.statusText }; });
        throw new Error(errPay.detail || JSON.stringify(errPay));
      }
      page.orderIdDisplay.textContent = 'Заказ: ' + (order.public_id || order.id);
      page.orderIdDisplay.style.fontWeight = '600';
      page.btnAcceptCash.textContent = 'Оплата принята';
      window.lastOrderId = order.id;
      window.lastOrderDocuments = page.state.selectedDocuments.map(function (item) { return item.template; });
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
    page.setVal(inputs.clientFio, formData.client_fio);
    page.setVal(inputs.clientPassport, formData.client_passport);
    page.setVal(inputs.clientAddress, formData.client_address);
    page.setVal(inputs.clientPhone, formData.client_phone);
    page.setVal(inputs.clientIsLegal, formData.client_is_legal);
    page.setVal(inputs.clientLegalName, formData.client_legal_name);
    page.setVal(inputs.clientInn, formData.client_inn);
    page.setVal(inputs.clientOgrn, formData.client_ogrn);
    page.setVal(inputs.hasSeller, !!(formData.seller_fio || formData.seller_passport || formData.seller_address));
    page.setVal(inputs.sellerFio, formData.seller_fio);
    page.setVal(inputs.sellerPassport, formData.seller_passport);
    page.setVal(inputs.sellerAddress, formData.seller_address);
    page.setVal(inputs.hasTrustee, !!(formData.trustee_fio || formData.trustee_passport || formData.trustee_basis));
    page.setVal(inputs.trusteeFio, formData.trustee_fio);
    page.setVal(inputs.trusteePassport, formData.trustee_passport);
    page.setVal(inputs.trusteeBasis, formData.trustee_basis);
    page.setVal(inputs.vin, formData.vin);
    page.setVal(inputs.brandModel, formData.brand_model);
    page.setVal(inputs.vehicleType, formData.vehicle_type);
    page.setVal(inputs.year, formData.year);
    page.setVal(inputs.engine, formData.engine);
    page.setVal(inputs.chassis, formData.chassis);
    page.setVal(inputs.body, formData.body);
    page.setVal(inputs.color, formData.color);
    page.setVal(inputs.srts, formData.srts);
    page.setVal(inputs.plateNumber, formData.plate_number);
    page.setVal(inputs.pts, formData.pts);
    page.setVal(inputs.dkpDate, formData.dkp_date);
    page.setVal(inputs.dkpNumber, formData.dkp_number);
    page.setVal(inputs.dkpSummary, formData.dkp_summary);
    page.setVal(inputs.summaDkp, formData.summa_dkp != null ? formData.summa_dkp : '');
    page.setVal(inputs.stateDuty, formData.state_duty != null ? formData.state_duty : '');
    page.setVal(inputs.needPlate, formData.need_plate);
    page.setVal(inputs.plateQuantity, formData.plate_quantity != null ? formData.plate_quantity : 1);
    page.state.selectedDocuments = (formData.documents || []).map(function (item) {
      return { template: item.template || '', label: item.label || item.template || '', price: page.num(item.price) };
    });
    page.toggleClientType();
    var sellerBody = page.el('sellerBody');
    var trusteeBody = page.el('trusteeBody');
    if (sellerBody) sellerBody.classList.toggle('form-section__body--closed', !(inputs.hasSeller && inputs.hasSeller.checked));
    if (trusteeBody) trusteeBody.classList.toggle('form-section__body--closed', !(inputs.hasTrustee && inputs.hasTrustee.checked));
    page.renderDocumentsList();
    page.syncFromMainForm();
    page.updateDocList();
  };

  page.loadFormHistory = async function () {
    var listEl = page.el('formHistoryList');
    var loadingEl = page.el('formHistoryLoading');
    if (!listEl) return;
    if (loadingEl) loadingEl.textContent = 'Загрузка…';
    try {
      var response = await page.fetchApi(page.apiBaseUrl + '/form-history?limit=50');
      if (!response.ok) throw new Error(response.statusText);
      var items = await response.json();
      if (!Array.isArray(items)) items = [];
      if (loadingEl) loadingEl.remove();
      if (!items.length) {
        listEl.innerHTML = '<li class="form-history-list__loading">Нет записей.</li>';
        return;
      }
      listEl.innerHTML = items.map(function (item) {
        var data = item.form_data || {};
        var label = data.client_fio || data.client_legal_name || 'Без имени';
        var dt = item.created_at
          ? new Date(item.created_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
          : '';
        var dataAttr = 'data-form-data="' + JSON.stringify(item.form_data || {}).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;') + '"';
        return '<li class="form-history-list__item" ' + dataAttr + '>' + String(label).replace(/</g, '&lt;') + ' — ' + dt + '</li>';
      }).join('');
      listEl.querySelectorAll('.form-history-list__item').forEach(function (li) {
        li.addEventListener('click', function () {
          try {
            var data = this.getAttribute('data-form-data');
            if (data) page.applyFormData(JSON.parse(data));
          } catch (_) {}
        });
      });
    } catch (_) {
      listEl.innerHTML = '<li class="form-history-list__loading">Не удалось загрузить историю</li>';
    }
  };

  page.doPrint = function () {
    var orderId = window.lastOrderId;
    if (!orderId) {
      alert('Сначала примите оплату по заказу.');
      return;
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
      if (page.docSelect) {
        var options = page.state.priceList.filter(function (item) { return (item.template || '') !== 'number.docx'; });
        page.docSelect.innerHTML = '<option value="">Выберите документ из списка</option>' + options.map(function (item) {
          var price = typeof item.price === 'number' ? item.price : parseFloat(item.price);
          var label = (item.label || item.template) + ' — ' + (isNaN(price) ? '0' : price) + ' ₽';
          return '<option value="' + (item.template || '').replace(/"/g, '&quot;') + '">' + label.replace(/</g, '&lt;') + '</option>';
        }).join('');
      }
    } catch (_) {
      if (page.docSelect) page.docSelect.innerHTML = '<option value="">Не удалось загрузить прейскурант</option>';
    }
  };
})();
