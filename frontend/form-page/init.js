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
        if (!page.inputs.clientPhone.value.trim()) page.inputs.clientPhone.value = '+7 ';
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
      if (number) number.addEventListener('input', function () { number.value = number.value.replace(/\s+/g, '').toUpperCase().slice(0, 6); });
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
    document.addEventListener('click', function (e) {
      if (!page.historyPopover || page.historyPopover.hidden) return;
      if (e.target.closest('#historyMenu')) return;
      page.closeHistoryPopover();
    });
  };

  page.init = async function () {
    await page.loadPriceList();
    page.bindInputMasks();
    page.bindInputs();
    page.setupPlateCheckbox();
    page.setupTogglableSections();
    page.bindHistoryMenu();
    page.syncPlateToDocuments();
    page.renderDocumentsList();
    page.syncFromMainForm();
    page.updateTime();
    setInterval(page.updateTime, 60000);

    if (page.btnAddDoc) page.btnAddDoc.addEventListener('click', page.addSelectedDocument);
    if (page.docSelect) {
      page.docSelect.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          page.addSelectedDocument();
        }
      });
    }
    if (page.btnAcceptCash) page.btnAcceptCash.addEventListener('click', page.acceptCash);
    if (page.btnPrint) page.btnPrint.addEventListener('click', page.doPrint);
    page.loadFormHistory();
  };
})();
