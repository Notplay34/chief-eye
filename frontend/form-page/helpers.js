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

  page.getStateDutyCalculation = function () {
    var base = page.getStateDuty();
    if (base <= 0) {
      return { base: 0, commission: 0, cashAmount: 0 };
    }
    var settings = page.state.stateDutySettings || {};
    var commission = Math.max(0, page.num(settings.commission != null ? settings.commission : 150));
    var special = Math.max(2025, page.num(settings.special_2025_cash_amount != null ? settings.special_2025_cash_amount : 2200));
    var cashAmount = base === 2025 ? special : base + commission;
    return {
      base: base,
      commission: Math.max(0, cashAmount - base),
      cashAmount: cashAmount
    };
  };

  page.getDocumentsTotal = function () {
    return page.state.selectedDocuments.reduce(function (sum, item) {
      return sum + page.num(item.price);
    }, 0);
  };

  page.getTotal = function () {
    return page.getStateDutyCalculation().cashAmount + page.getDocumentsTotal();
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

  page.isDateInput = function (input) {
    return !!(input && input.classList && input.classList.contains('field__input--date'));
  };

  page.normalizeRuDateInput = function (value) {
    return page.formatDateDigits(value);
  };

  page.isValidRuDate = function (value) {
    var raw = String(value || '').trim();
    var match = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (!match) return false;
    var day = parseInt(match[1], 10);
    var month = parseInt(match[2], 10);
    var year = parseInt(match[3], 10);
    if (year < 1900 || year > 2199) return false;
    var parsed = new Date(year, month - 1, day);
    return parsed.getFullYear() === year &&
      parsed.getMonth() === month - 1 &&
      parsed.getDate() === day;
  };

  page.validateDateInput = function (input, report) {
    if (!page.isDateInput(input)) return true;
    if (!page.dateInputApplies(input)) {
      input.setCustomValidity('');
      return true;
    }
    var value = String(input.value || '').trim();
    var valid = !value || page.isValidRuDate(value);
    input.setCustomValidity(valid ? '' : 'Введите дату в формате ДД.ММ.ГГГГ');
    if (!valid && report && input.reportValidity) input.reportValidity();
    return valid;
  };

  page.dateInputApplies = function (input) {
    if (!input) return false;
    if (page.inputs.clientIsLegal && page.inputs.clientIsLegal.checked && input.closest('#clientIndividual')) return false;
    if (page.inputs.hasSeller && !page.inputs.hasSeller.checked && input.closest('#sellerBody')) return false;
    if (page.inputs.hasTrustee && !page.inputs.hasTrustee.checked && input.closest('#trusteeBody')) return false;
    return true;
  };

  page.hasInvalidDates = function (report) {
    var invalid = false;
    Array.prototype.slice.call(document.querySelectorAll('.field__input--date')).forEach(function (input) {
      if (!page.validateDateInput(input, report && !invalid)) invalid = true;
    });
    return invalid;
  };

  page.ruToIsoDate = function (value) {
    var raw = String(value || '').trim();
    if (!raw) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
    var match = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    return match ? (match[3] + '-' + match[2] + '-' + match[1]) : '';
  };

  page.isoToRuDate = function (value) {
    var raw = String(value || '').trim();
    if (!raw) return '';
    if (/^\d{2}\.\d{2}\.\d{4}$/.test(raw)) return raw;
    var match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return match ? (match[3] + '.' + match[2] + '.' + match[1]) : '';
  };

  page.dateValue = function (input) {
    if (!input || !input.value) return null;
    var value = page.isDateInput(input) ? page.normalizeRuDateInput(input.value) : page.isoToRuDate(input.value);
    return page.isValidRuDate(value) ? value : null;
  };

  page.dateDisplay = function (input) {
    if (!input || !input.value) return '';
    var value = page.isDateInput(input) ? page.normalizeRuDateInput(input.value) : page.isoToRuDate(input.value);
    return page.isValidRuDate(value) ? value : '';
  };

  page.todayRu = function () {
    var now = new Date();
    var dd = String(now.getDate()).padStart(2, '0');
    var mm = String(now.getMonth() + 1).padStart(2, '0');
    var yyyy = String(now.getFullYear());
    return dd + '.' + mm + '.' + yyyy;
  };

  page.todayIso = function () {
    return page.ruToIsoDate(page.todayRu());
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
    var rawNumber = number ? String(number.value || '').replace(/\s+/g, '').toUpperCase() : '';
    var n = prefix === 'pts' ? rawNumber : rawNumber.slice(0, 6);
    if (prefix === 'pts' && !s && n) return n;
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
      number: normalized.slice(4)
    };
  };

  page.isPrintableDocument = function (documentItem) {
    return documentItem && !documentItem.paymentOnly && documentItem.printable !== false;
  };

  page.isPlateZaiavlenie = function (documentItem) {
    return documentItem.template === 'zaiavlenie.docx' &&
      (documentItem.price === 0 || page.num(documentItem.price) === 0) &&
      (documentItem.label === 'Заявление на номера' || !documentItem.label);
  };

  page.setVal = function (input, value) {
    if (!input) return;
    if (input.type === 'checkbox') input.checked = !!value;
    else if (page.isDateInput(input)) {
      input.value = page.normalizeRuDateInput(page.isoToRuDate(value) || value);
      page.validateDateInput(input);
    }
    else if (input.type === 'date') input.value = page.ruToIsoDate(value);
    else input.value = value != null ? String(value) : '';
  };

  page.clearInputs = function (keys, defaults) {
    defaults = defaults || {};
    keys.forEach(function (key) {
      var input = page.inputs[key];
      if (!input) return;
      if (Object.prototype.hasOwnProperty.call(defaults, key)) page.setVal(input, defaults[key]);
      else if (input.type === 'checkbox') page.setVal(input, false);
      else page.setVal(input, '');
      input.setCustomValidity('');
    });
  };
})();
