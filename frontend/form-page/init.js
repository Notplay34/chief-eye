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
