(function () {
  var page = window.RegDocFormPage;
  if (!page) return;

  page.PLATE_PRICE_PER_UNIT = 1500;

  page.num = function (val) {
    if (val === null || val === undefined || val === '') return 0;
    var normalized = String(val).replace(/\s/g, '').replace(',', '.');
    var parsed = parseFloat(normalized);
    return isNaN(parsed) ? 0 : parsed;
  };

  page.getStateDuty = function () {
    return page.num(page.inputs.stateDuty && page.inputs.stateDuty.value);
  };

  page.getDocumentsTotal = function () {
    return page.state.selectedDocuments.reduce(function (sum, item) {
      return sum + page.num(item.price);
    }, 0);
  };

  page.getTotal = function () {
    return page.getStateDuty() + page.getDocumentsTotal();
  };

  page.formatMoney = function (value) {
    return new Intl.NumberFormat('ru-RU', {
      style: 'decimal',
      minimumFractionDigits: 0
    }).format(value) + ' ₽';
  };

  page.getPlateQuantity = function () {
    return page.inputs.plateQuantity ? Math.max(1, parseInt(page.inputs.plateQuantity.value, 10) || 1) : 1;
  };

  page.isPlateZaiavlenie = function (documentItem) {
    return documentItem.template === 'zaiavlenie.docx' &&
      (documentItem.price === 0 || page.num(documentItem.price) === 0) &&
      (documentItem.label === 'Заявление на номера' || !documentItem.label);
  };

  page.setVal = function (input, value) {
    if (!input) return;
    if (input.type === 'checkbox') input.checked = !!value;
    else input.value = value != null ? String(value) : '';
  };
})();
