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

  page.onlyDigits = function (value) {
    return String(value || '').replace(/\D/g, '');
  };

  page.limitDigits = function (input, maxLength) {
    if (!input) return;
    input.value = page.onlyDigits(input.value).slice(0, maxLength);
  };

  page.formatDivisionCode = function (value) {
    var digits = page.onlyDigits(value).slice(0, 6);
    if (digits.length > 3) return digits.slice(0, 3) + '-' + digits.slice(3);
    return digits;
  };

  page.formatDateDigits = function (value) {
    var digits = page.onlyDigits(value).slice(0, 8);
    if (digits.length > 4) return digits.slice(0, 2) + '.' + digits.slice(2, 4) + '.' + digits.slice(4);
    if (digits.length > 2) return digits.slice(0, 2) + '.' + digits.slice(2);
    return digits;
  };

  page.todayRu = function () {
    var now = new Date();
    var dd = String(now.getDate()).padStart(2, '0');
    var mm = String(now.getMonth() + 1).padStart(2, '0');
    var yyyy = String(now.getFullYear());
    return dd + '.' + mm + '.' + yyyy;
  };

  page.formatPhone = function (value) {
    var digits = page.onlyDigits(value);
    if (digits.charAt(0) === '8') digits = '7' + digits.slice(1);
    if (digits.charAt(0) === '7') digits = digits.slice(1);
    digits = digits.slice(0, 10);
    var padded = (digits + '__________').slice(0, 10);
    return '+7 (' + padded.slice(0, 3) + ') ' + padded.slice(3, 6) + '-' + padded.slice(6, 8) + '-' + padded.slice(8, 10);
  };

  page.composePhone = function () {
    var input = page.inputs.clientPhone;
    if (!input) return null;
    var digits = page.onlyDigits(input.value);
    if (digits.charAt(0) === '8') digits = '7' + digits.slice(1);
    if (digits.charAt(0) === '7') digits = digits.slice(1);
    digits = digits.slice(0, 10);
    return digits.length === 10 ? ('+7' + digits) : null;
  };

  page.composePassport = function (prefix) {
    var inputs = page.inputs;
    var series = inputs[prefix + 'PassportSeries'];
    var number = inputs[prefix + 'PassportNumber'];
    var s = series ? page.onlyDigits(series.value).slice(0, 4) : '';
    var n = number ? page.onlyDigits(number.value).slice(0, 6) : '';
    return s && n ? (s + ' ' + n) : null;
  };

  page.composeVehicleDoc = function (prefix) {
    var inputs = page.inputs;
    var series = inputs[prefix + 'Series'];
    var number = inputs[prefix + 'Number'];
    var s = series ? String(series.value || '').replace(/\s+/g, '').toUpperCase().slice(0, 4) : '';
    var n = number ? String(number.value || '').replace(/\s+/g, '').toUpperCase().slice(0, 6) : '';
    return s && n ? (s + ' ' + n) : null;
  };

  page.splitPassport = function (value) {
    var digits = page.onlyDigits(value);
    return {
      series: digits.slice(0, 4),
      number: digits.slice(4, 10)
    };
  };

  page.splitVehicleDoc = function (value) {
    var normalized = String(value || '').replace(/\s+/g, '').toUpperCase();
    return {
      series: normalized.slice(0, 4),
      number: normalized.slice(4, 10)
    };
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
