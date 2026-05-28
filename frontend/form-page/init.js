(function () {
  var page = window.RegDocFormPage;
  if (!page) return;

  page.updateTime = function () {
    if (page.currentTime) {
      page.currentTime.textContent = new Date().toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    }
  };

  page.bindInputs = function () {
    if (page.inputs.clientIsLegal) {
      page.inputs.clientIsLegal.addEventListener('change', function () {
        page.toggleClientType();
        page.syncFromMainForm();
      });
      page.toggleClientType();
    }
    Object.keys(page.inputs).forEach(function (key) {
      var node = page.inputs[key];
      if (!node) return;
      node.addEventListener('input', page.syncFromMainForm);
      node.addEventListener('change', page.syncFromMainForm);
    });
  };

  page.bindInputMasks = function () {
    Array.prototype.slice.call(document.querySelectorAll('.field__input--date')).forEach(function (input) {
      input.addEventListener('keydown', function (event) {
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        if (['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].indexOf(event.key) !== -1) return;
        if (!/^[0-9.]$/.test(event.key)) event.preventDefault();
      });
      input.addEventListener('input', function () {
        input.value = page.normalizeRuDateInput(input.value);
        page.validateDateInput(input);
      });
      input.addEventListener('blur', function () {
        input.value = page.normalizeRuDateInput(input.value);
        page.validateDateInput(input, true);
      });
    });
    ['client', 'seller', 'trustee'].forEach(function (prefix) {
      var series = page.inputs[prefix + 'PassportSeries'];
      var number = page.inputs[prefix + 'PassportNumber'];
      var code = page.inputs[prefix + 'PassportDivisionCode'];
      if (series) series.addEventListener('input', function () { page.limitDigits(series, 4); });
      if (number) number.addEventListener('input', function () { page.limitDigits(number, 6); });
      if (code) code.addEventListener('input', function () { code.value = page.formatDivisionCode(code.value); });
    });
    if (page.inputs.clientPhone) {
      page.inputs.clientPhone.addEventListener('focus', function () {
        if (!page.inputs.clientPhone.value.trim()) page.inputs.clientPhone.value = page.formatPhone('');
      });
      page.inputs.clientPhone.addEventListener('input', function () {
        page.inputs.clientPhone.value = page.formatPhone(page.inputs.clientPhone.value);
      });
    }
    if (page.inputs.vin) {
      page.inputs.vin.addEventListener('input', function () {
        page.inputs.vin.value = page.inputs.vin.value.toUpperCase();
      });
    }
    ['srts', 'pts'].forEach(function (prefix) {
      var series = page.inputs[prefix + 'Series'];
      var number = page.inputs[prefix + 'Number'];
      if (series) series.addEventListener('input', function () { series.value = series.value.replace(/\s+/g, '').toUpperCase().slice(0, 4); });
      if (number) number.addEventListener('input', function () {
        var normalized = number.value.replace(/\s+/g, '').toUpperCase();
        number.value = prefix === 'pts' ? normalized : normalized.slice(0, 6);
      });
    });
  };

  page.setupPlateCheckbox = function () {
    if (page.inputs.needPlate) {
      page.inputs.needPlate.addEventListener('change', page.syncPlateToDocuments);
    }
    if (page.inputs.plateQuantity) {
      page.inputs.plateQuantity.addEventListener('change', page.syncPlateToDocuments);
      page.inputs.plateQuantity.disabled = !(page.inputs.needPlate && page.inputs.needPlate.checked);
    }
  };

  page.clearClientBlock = function () {
    page.clearInputs([
      'clientFio',
      'clientBirthDate',
      'clientBirthPlace',
      'clientPassportSeries',
      'clientPassportNumber',
      'clientPassportIssuedBy',
      'clientPassportIssuedDate',
      'clientPassportDivisionCode',
      'clientAddress',
      'clientPhone',
      'clientIsLegal',
      'clientLegalName',
      'clientInn',
      'clientOgrn'
    ], { clientPhone: page.formatPhone('') });
    page.toggleClientType();
    page.syncFromMainForm();
  };

  page.clearSellerBlock = function () {
    page.clearInputs([
      'hasSeller',
      'sellerFio',
      'sellerBirthDate',
      'sellerPassportSeries',
      'sellerPassportNumber',
      'sellerPassportIssuedBy',
      'sellerPassportIssuedDate',
      'sellerPassportDivisionCode',
      'sellerAddress',
      'dkpDate',
      'summaDkp',
      'dkpNumber'
    ], { summaDkp: '0' });
    var sellerBody = page.el('sellerBody');
    if (sellerBody) sellerBody.classList.add('form-section__body--closed');
    if (page.inputs.dkpSummary && page.inputs.dkpSummary.dataset.autoDkp === '1') {
      page.inputs.dkpSummary.value = '';
      page.inputs.dkpSummary.dataset.autoDkp = '';
    }
    page.syncFromMainForm();
  };

  page.clearVehicleBlock = function () {
    page.clearInputs([
      'vin',
      'brandModel',
      'vehicleType',
      'year',
      'engine',
      'chassis',
      'power',
      'mass',
      'body',
      'color',
      'plateNumber',
      'srtsSeries',
      'srtsNumber',
      'srtsIssuedDate',
      'srtsIssuedBy',
      'ptsSeries',
      'ptsNumber',
      'ptsIssuedDate',
      'ptsIssuedBy',
      'dkpSummary'
    ]);
    if (page.inputs.dkpSummary) page.inputs.dkpSummary.dataset.autoDkp = '';
    page.syncFromMainForm();
  };

  page.swapClientSeller = function () {
    var inputs = page.inputs;
    var pairs = [
      ['clientFio', 'sellerFio'],
      ['clientBirthDate', 'sellerBirthDate'],
      ['clientPassportSeries', 'sellerPassportSeries'],
      ['clientPassportNumber', 'sellerPassportNumber'],
      ['clientPassportIssuedBy', 'sellerPassportIssuedBy'],
      ['clientPassportIssuedDate', 'sellerPassportIssuedDate'],
      ['clientPassportDivisionCode', 'sellerPassportDivisionCode'],
      ['clientAddress', 'sellerAddress']
    ];
    var values = {};
    pairs.forEach(function (pair) {
      values[pair[0]] = inputs[pair[0]] ? inputs[pair[0]].value : '';
      values[pair[1]] = inputs[pair[1]] ? inputs[pair[1]].value : '';
    });
    if (inputs.clientIsLegal) inputs.clientIsLegal.checked = false;
    if (inputs.hasSeller) inputs.hasSeller.checked = true;
    pairs.forEach(function (pair) {
      page.setVal(inputs[pair[0]], values[pair[1]]);
      page.setVal(inputs[pair[1]], values[pair[0]]);
    });
    page.clearInputs(['clientLegalName', 'clientInn', 'clientOgrn']);
    page.toggleClientType();
    var sellerBody = page.el('sellerBody');
    if (sellerBody) sellerBody.classList.remove('form-section__body--closed');
    page.syncFromMainForm();
  };

  page.bindBlockClearButtons = function () {
    [
      { button: page.clearClientBlockBtn, action: page.clearClientBlock },
      { button: page.clearSellerBlockBtn, action: page.clearSellerBlock },
      { button: page.clearVehicleBlockBtn, action: page.clearVehicleBlock },
      { button: page.swapClientSellerBtn, action: page.swapClientSeller }
    ].forEach(function (item) {
      if (!item.button) return;
      item.button.addEventListener('click', function (event) {
        event.preventDefault();
        event.stopPropagation();
        item.action();
      });
    });
  };

  page.openHistoryPopover = function () {
    if (!page.historyPopover || !page.historyTrigger) return;
    page.historyPopover.hidden = false;
    page.historyTrigger.setAttribute('aria-expanded', 'true');
  };

  page.closeHistoryPopover = function () {
    if (!page.historyPopover || !page.historyTrigger) return;
    page.historyPopover.hidden = true;
    page.historyTrigger.setAttribute('aria-expanded', 'false');
  };

  page.toggleHistoryPopover = function () {
    if (!page.historyPopover) return;
    if (page.historyPopover.hidden) page.openHistoryPopover();
    else page.closeHistoryPopover();
  };

  page.bindHistoryMenu = function () {
    if (page.historyTrigger) {
      page.historyTrigger.addEventListener('click', function (e) {
        e.stopPropagation();
        page.toggleHistoryPopover();
      });
    }
    if (page.historyPrev) {
      page.historyPrev.addEventListener('click', function (e) {
        e.stopPropagation();
        page.state.historyPage -= 1;
        page.renderHistoryPage();
      });
    }
    if (page.historyNext) {
      page.historyNext.addEventListener('click', function (e) {
        e.stopPropagation();
        page.state.historyPage += 1;
        page.renderHistoryPage();
      });
    }
    if (page.historyDateFilter) {
      page.historyDateFilter.addEventListener('click', function (e) { e.stopPropagation(); });
      page.historyDateFilter.addEventListener('change', function () {
        page.state.historyPage = 0;
        page.loadFormHistory();
      });
    }
    if (page.historyDateClear) {
      page.historyDateClear.addEventListener('click', function (e) {
        e.stopPropagation();
        if (page.historyDateFilter) page.historyDateFilter.value = '';
        page.state.historyPage = 0;
        page.loadFormHistory();
      });
    }
    if (page.historySearch) {
      page.historySearch.addEventListener('click', function (e) { e.stopPropagation(); });
      page.historySearch.addEventListener('input', function () {
        page.state.historySearch = this.value || '';
        page.state.historyPage = 0;
        page.renderHistoryPage();
      });
      page.historySearch.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
          e.stopPropagation();
          this.value = '';
          page.state.historySearch = '';
          page.state.historyPage = 0;
          page.renderHistoryPage();
        }
      });
    }
    document.addEventListener('click', function (e) {
      if (!page.historyPopover || page.historyPopover.hidden) return;
      if (e.target.closest('#historyMenu')) return;
      page.closeHistoryPopover();
    });
  };

  page.init = async function () {
    await Promise.all([page.loadPriceList(), page.loadStateDutySettings()]);
    page.bindInputMasks();
    page.bindInputs();
    page.setupPlateCheckbox();
    page.bindBlockClearButtons();
    page.setupTogglableSections();
    page.bindHistoryMenu();
    page.syncPlateToDocuments();
    if (page.renderDocumentChecklist) page.renderDocumentChecklist();
    page.renderDocumentsList();
    page.syncFromMainForm();
    page.updateTime();
    setInterval(page.updateTime, 60000);

    if (page.docSelect) page.docSelect.addEventListener('change', page.syncSelectedDocumentsFromChecklist);
    if (page.btnAcceptCash) page.btnAcceptCash.addEventListener('click', page.acceptCash);
    if (page.btnPrint) page.btnPrint.addEventListener('click', page.doPrint);
    page.loadFormHistory();
  };
})();
