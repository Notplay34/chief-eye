(function () {
  var page = window.RegDocFormPage;
  if (!page) return;

  page.renderDocumentsList = function () {
    var documentsList = page.documentsList;
    var documentsEmpty = page.documentsEmpty;
    var selectedDocuments = page.state.selectedDocuments;
    if (documentsEmpty) {
      documentsEmpty.hidden = true;
      documentsEmpty.style.display = 'none';
    }
    if (!documentsList) return;

    var html = selectedDocuments.map(function (item, index) {
      if (page.isPlateZaiavlenie(item) || item.template === 'number.docx') return '';
      return '<li class="documents-to-print__item">' +
        '<span class="documents-to-print__item-info">' +
          '<span>' + (item.label || item.template) + '</span>' +
          '<span class="documents-to-print__item-price">' + page.formatMoney(page.num(item.price)) + '</span>' +
        '</span>' +
        '<button type="button" class="documents-to-print__item-remove" data-index="' + index + '">Удалить</button>' +
      '</li>';
    }).filter(Boolean).join('');
    documentsList.innerHTML = html;
    var documentsWrap = page.el('documentsToPrint');
    if (documentsWrap) documentsWrap.hidden = !html;

    documentsList.querySelectorAll('.documents-to-print__item-remove').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var index = parseInt(btn.getAttribute('data-index'), 10);
        page.state.selectedDocuments.splice(index, 1);
        page.renderDocumentsList();
        if (page.renderDocumentChecklist) page.renderDocumentChecklist();
        page.syncFromMainForm();
      });
    });
  };

  page.renderDocumentChecklist = function () {
    if (!page.docSelect) return;
    var selected = {};
    page.state.selectedDocuments.forEach(function (item) {
      if (!item.paymentOnly) selected[item.template] = true;
    });
    var options = (page.state.priceList || []).filter(function (item) {
      return (item.template || '') !== 'number.docx';
    });
    if (!options.length) {
      page.docSelect.innerHTML = '<span class="document-checklist__loading">Нет документов в прейскуранте</span>';
      return;
    }
    page.docSelect.innerHTML = options.map(function (item) {
      var template = String(item.template || '');
      var safeTemplate = template.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
      var label = String(item.label || item.template || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
      var price = page.num(item.price);
      var isSelected = !!selected[template];
      return '<label class="document-checklist__item' + (isSelected ? ' document-checklist__item--selected' : '') + '">' +
        '<input type="checkbox" value="' + safeTemplate + '"' + (isSelected ? ' checked disabled' : '') + '>' +
        '<span class="document-checklist__box"></span>' +
        '<span class="document-checklist__name">' + label + '</span>' +
        '<span class="document-checklist__price">' + page.formatMoney(price) + '</span>' +
      '</label>';
    }).join('');
  };

  page.updateSummary = function () {
    var dutyCalc = page.getStateDutyCalculation();
    var duty = dutyCalc.cashAmount;
    var selectedDocuments = page.state.selectedDocuments;
    var plate = selectedDocuments.reduce(function (sum, item) {
      return item.template === 'number.docx' ? sum + page.num(item.price) : sum;
    }, 0);
    var plateQuantity = page.inputs.needPlate && page.inputs.needPlate.checked ? page.getPlateQuantity() : 0;
    var income = selectedDocuments.reduce(function (sum, item) {
      if (page.isPlateZaiavlenie(item) || item.template === 'number.docx') return sum;
      return sum + page.num(item.price);
    }, 0);
    var total = page.getTotal();
    if (page.summary.sumStateDuty) page.summary.sumStateDuty.textContent = page.formatMoney(duty);
    if (page.summary.sumStateDutyRow) page.summary.sumStateDutyRow.hidden = duty <= 0;
    if (page.summary.sumStateDutyBase) page.summary.sumStateDutyBase.textContent = page.formatMoney(dutyCalc.base);
    if (page.summary.sumStateDutyBaseRow) page.summary.sumStateDutyBaseRow.hidden = dutyCalc.base <= 0;
    if (page.summary.sumStateDutyCommission) page.summary.sumStateDutyCommission.textContent = page.formatMoney(dutyCalc.commission);
    if (page.summary.sumStateDutyCommissionRow) page.summary.sumStateDutyCommissionRow.hidden = dutyCalc.commission <= 0;
    if (page.stateDutyNote) page.stateDutyNote.hidden = dutyCalc.base <= 0;
    if (page.stateDutyBaseHint) page.stateDutyBaseHint.textContent = page.formatMoney(dutyCalc.base);
    if (page.stateDutyCashHint) page.stateDutyCashHint.textContent = page.formatMoney(dutyCalc.cashAmount);
    if (page.stateDutyCommissionHint) page.stateDutyCommissionHint.textContent = page.formatMoney(dutyCalc.commission);
    if (page.summary.sumIncome) page.summary.sumIncome.textContent = page.formatMoney(income);
    if (page.summary.sumPlate) page.summary.sumPlate.textContent = page.formatMoney(plate);
    if (page.summary.sumPlateLabel) page.summary.sumPlateLabel.textContent = plateQuantity > 0 ? ('Номера, ' + plateQuantity + ' шт') : 'Номера';
    if (page.summary.sumPlateRow) page.summary.sumPlateRow.hidden = plate <= 0;
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
    var birth = (inputs.clientBirthDate && inputs.clientBirthDate.value.trim()) || '';
    var birthPlace = (inputs.clientBirthPlace && inputs.clientBirthPlace.value.trim()) || '';
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
        : [fio, birth, birthPlace].filter(Boolean).join(', ');
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
      page.state.selectedDocuments.push({ template: 'number.docx', label: 'Изготовление номера', price: page.PLATE_PRICE_PER_UNIT * quantity, paymentOnly: true });
    }
    if (page.inputs.plateQuantity) page.inputs.plateQuantity.disabled = !need;
    page.renderDocumentsList();
    if (page.renderDocumentChecklist) page.renderDocumentChecklist();
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
