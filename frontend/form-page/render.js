(function () {
  var page = window.RegDocFormPage;
  if (!page) return;

  page.renderDocumentsList = function () {
    var documentsList = page.documentsList;
    var documentsEmpty = page.documentsEmpty;
    var selectedDocuments = page.state.selectedDocuments;
    var forPayment = selectedDocuments.filter(function (item) { return !page.isPlateZaiavlenie(item); });
    if (documentsEmpty) documentsEmpty.style.display = forPayment.length ? 'none' : 'block';
    if (!documentsList) return;

    documentsList.innerHTML = selectedDocuments.map(function (item, index) {
      if (page.isPlateZaiavlenie(item)) return '';
      return '<li class="documents-to-print__item">' +
        '<span class="documents-to-print__item-info">' +
          '<span>' + (item.label || item.template) + '</span>' +
          '<span class="documents-to-print__item-price">' + page.formatMoney(page.num(item.price)) + '</span>' +
        '</span>' +
        '<button type="button" class="documents-to-print__item-remove" data-index="' + index + '">Удалить</button>' +
      '</li>';
    }).filter(Boolean).join('');

    documentsList.querySelectorAll('.documents-to-print__item-remove').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var index = parseInt(btn.getAttribute('data-index'), 10);
        page.state.selectedDocuments.splice(index, 1);
        page.renderDocumentsList();
        page.syncFromMainForm();
      });
    });
  };

  page.updateSummary = function () {
    var duty = page.getStateDuty();
    var income = page.getDocumentsTotal();
    var total = page.getTotal();
    if (page.summary.sumStateDuty) page.summary.sumStateDuty.textContent = page.formatMoney(duty);
    if (page.summary.sumIncome) page.summary.sumIncome.textContent = page.formatMoney(income);
    if (page.summary.sumTotal) page.summary.sumTotal.textContent = page.formatMoney(total);

    var isLegal = page.inputs.clientIsLegal && page.inputs.clientIsLegal.checked;
    var clientFilled = isLegal
      ? (page.inputs.clientLegalName && page.inputs.clientLegalName.value.trim())
      : (page.inputs.clientFio && page.inputs.clientFio.value.trim());
    var canPay = total > 0 && clientFilled && page.state.selectedDocuments.length > 0;
    if (page.btnAcceptCash) page.btnAcceptCash.disabled = !canPay;
    if (page.btnPrint) page.btnPrint.disabled = !canPay;
  };

  page.updatePreview = function () {
    var inputs = page.inputs;
    var preview = page.preview;
    var selectedDocuments = page.state.selectedDocuments;
    var isLegal = inputs.clientIsLegal && inputs.clientIsLegal.checked;
    var fio = isLegal ? '—' : ((inputs.clientFio && inputs.clientFio.value.trim()) || '—');
    var passport = isLegal ? '—' : (page.composePassport('client') || '—');
    var address = (inputs.clientAddress && inputs.clientAddress.value.trim()) || '—';
    var phone = (inputs.clientPhone && inputs.clientPhone.value.trim()) || '—';
    var seller = '—';
    if (inputs.hasSeller && inputs.hasSeller.checked && inputs.sellerFio && inputs.sellerFio.value.trim()) {
      seller = [
        inputs.sellerFio.value.trim(),
        page.composePassport('seller'),
        inputs.sellerAddress && inputs.sellerAddress.value.trim()
      ].filter(Boolean).join(', ');
    }
    var trustee = '—';
    if (inputs.hasTrustee && inputs.hasTrustee.checked && inputs.trusteeFio && inputs.trusteeFio.value.trim()) {
      trustee = [
        inputs.trusteeFio.value.trim(),
        page.composePassport('trustee')
      ].filter(Boolean).join(' · ');
    }
    var vehicle = (inputs.vin && inputs.vin.value.trim()) || (inputs.brandModel && inputs.brandModel.value.trim())
      ? [inputs.vin && inputs.vin.value.trim(), inputs.brandModel && inputs.brandModel.value.trim()].filter(Boolean).join(' · ')
      : '—';
    var dkpParts = [];
    if (inputs.dkpDate && inputs.dkpDate.value.trim()) dkpParts.push(inputs.dkpDate.value.trim());
    if (inputs.summaDkp && page.num(inputs.summaDkp.value) > 0) dkpParts.push(page.formatMoney(page.num(inputs.summaDkp.value)));
    if (inputs.dkpNumber && inputs.dkpNumber.value.trim()) dkpParts.push('№ ' + inputs.dkpNumber.value.trim());
    var dkpStr = dkpParts.length ? dkpParts.join(', ') : '—';
    var pullDkp = inputs.hasSeller && inputs.hasSeller.checked && dkpStr !== '—';
    if (inputs.dkpSummary) {
      inputs.dkpSummary.readOnly = !!pullDkp;
      inputs.dkpSummary.classList.toggle('field__input--readonly', !!pullDkp);
      if (pullDkp) inputs.dkpSummary.value = dkpStr;
    }
    if (preview.previewDkp) preview.previewDkp.textContent = pullDkp ? dkpStr : (inputs.dkpSummary && inputs.dkpSummary.value.trim()) || '—';

    var docLabels = selectedDocuments.length
      ? selectedDocuments.map(function (item) { return item.label || item.template; }).join(', ')
      : '—';

    if (preview.previewFio) {
      preview.previewFio.textContent = isLegal
        ? ((inputs.clientLegalName && inputs.clientLegalName.value.trim()) || '—')
        : fio;
    }
    if (preview.previewPassport) {
      preview.previewPassport.textContent = isLegal
        ? ('ИНН ' + ((inputs.clientInn && inputs.clientInn.value.trim()) || '—') + (inputs.clientOgrn && inputs.clientOgrn.value.trim() ? ', ОГРН ' + inputs.clientOgrn.value.trim() : ''))
        : passport;
    }
    if (preview.previewAddress) preview.previewAddress.textContent = address;
    if (preview.previewPhone) preview.previewPhone.textContent = phone;
    if (preview.previewSeller) preview.previewSeller.textContent = seller;
    if (preview.previewTrustee) preview.previewTrustee.textContent = trustee;
    if (preview.previewVehicle) preview.previewVehicle.textContent = vehicle;
    if (preview.previewService) preview.previewService.textContent = docLabels;
    if (preview.previewTotal) preview.previewTotal.textContent = page.formatMoney(page.getTotal());
  };

  page.syncFromMainForm = function () {
    page.updateSummary();
    page.updatePreview();
  };

  page.renderHistoryPage = function () {
    var listEl = page.formHistoryList;
    var rangeEl = page.historyRange;
    var prevBtn = page.historyPrev;
    var nextBtn = page.historyNext;
    if (!listEl) return;

    var items = page.state.historyItems || [];
    var pageSize = page.state.historyPageSize || 5;
    var totalPages = Math.max(1, Math.ceil(items.length / pageSize));
    if (page.state.historyPage >= totalPages) page.state.historyPage = totalPages - 1;
    if (page.state.historyPage < 0) page.state.historyPage = 0;

    var start = page.state.historyPage * pageSize;
    var end = Math.min(start + pageSize, items.length);
    var visibleItems = items.slice(start, end);

    if (rangeEl) {
      rangeEl.textContent = items.length ? ((start + 1) + '–' + end + ' из ' + items.length) : '0–0';
    }
    if (prevBtn) prevBtn.disabled = page.state.historyPage <= 0;
    if (nextBtn) nextBtn.disabled = end >= items.length;

    if (!visibleItems.length) {
      listEl.innerHTML = '<li class="form-history-list__loading">Нет записей.</li>';
      return;
    }

    listEl.innerHTML = visibleItems.map(function (item) {
      var dataAttr = 'data-form-data="' + JSON.stringify(item.form_data || {}).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;') + '"';
      return '<li class="form-history-list__item" ' + dataAttr + '>' +
        '<span class="form-history-list__title">' + String(item.label || 'Без имени').replace(/</g, '&lt;') + '</span>' +
        '<span class="form-history-list__time">' + (item.created_label || '') + '</span>' +
      '</li>';
    }).join('');

    listEl.querySelectorAll('.form-history-list__item').forEach(function (li) {
      li.addEventListener('click', function () {
        try {
          var data = this.getAttribute('data-form-data');
          if (data) page.applyFormData(JSON.parse(data));
          page.closeHistoryPopover();
        } catch (_) {}
      });
    });
  };

  page.toggleClientType = function () {
    var isLegal = page.inputs.clientIsLegal && page.inputs.clientIsLegal.checked;
    var individual = page.el('clientIndividual');
    var legal = page.el('clientLegal');
    if (individual) individual.style.display = isLegal ? 'none' : '';
    if (legal) legal.style.display = isLegal ? '' : 'none';
  };

  page.syncPlateToDocuments = function () {
    var need = page.inputs.needPlate && page.inputs.needPlate.checked;
    var quantity = page.getPlateQuantity();
    page.state.selectedDocuments = page.state.selectedDocuments.filter(function (item) {
      if (item.template === 'number.docx') return false;
      if (page.isPlateZaiavlenie(item)) return false;
      return true;
    });
    if (need) {
      page.state.selectedDocuments.push({ template: 'number.docx', label: 'Изготовление номера', price: page.PLATE_PRICE_PER_UNIT * quantity });
      page.state.selectedDocuments.push({ template: 'zaiavlenie.docx', label: 'Заявление на номера', price: 0 });
    }
    if (page.inputs.plateQuantity) page.inputs.plateQuantity.disabled = !need;
    page.renderDocumentsList();
    page.updateSummary();
    page.updatePreview();
  };

  page.setupTogglableSections = function () {
    var sellerBody = page.el('sellerBody');
    var trusteeBody = page.el('trusteeBody');
    if (page.inputs.hasSeller && sellerBody) {
      sellerBody.classList.toggle('form-section__body--closed', !page.inputs.hasSeller.checked);
      page.inputs.hasSeller.addEventListener('change', function () {
        var enabled = page.inputs.hasSeller.checked;
        sellerBody.classList.toggle('form-section__body--closed', !enabled);
        if (page.inputs.dkpDate) page.inputs.dkpDate.value = enabled ? page.todayRu() : '';
        page.syncFromMainForm();
      });
    }
    if (page.inputs.hasTrustee && trusteeBody) {
      trusteeBody.classList.toggle('form-section__body--closed', !page.inputs.hasTrustee.checked);
      page.inputs.hasTrustee.addEventListener('change', function () {
        trusteeBody.classList.toggle('form-section__body--closed', !page.inputs.hasTrustee.checked);
      });
    }
  };
})();
