(function () {
  var page = window.RegDocFormPage;
  if (!page) return;

  var RECIPIENT = {
    name: 'УФК по Волгоградской области (ГУ МВД России по Волгоградской области, л/с 04291356650)',
    personalAcc: '03100643000000012900',
    bankName: 'ОТДЕЛЕНИЕ ВОЛГОГРАД БАНКА РОССИИ',
    bic: '011806101',
    correspAcc: '40102810445370000021',
    inn: '3444012677',
    kpp: '344401001',
    kbk: '18810807141011000110',
    oktmo: '18520000',
    budgetPersonalAccount: '04291356650',
    docIdx: '0'
  };

  function cleanField(value) {
    return String(value || '').replace(/[|=]/g, ' ').replace(/\s+/g, ' ').trim();
  }

  function splitFio(value) {
    var parts = cleanField(value).split(' ').filter(Boolean);
    return {
      lastName: parts[0] || '',
      firstName: parts[1] || '',
      middleName: parts.slice(2).join(' ')
    };
  }

  function qrAmountKopecks() {
    return Math.round(page.getStateDuty() * 100);
  }

  function passportDigits() {
    var inputs = page.inputs || {};
    return [
      inputs.clientPassportSeries && inputs.clientPassportSeries.value,
      inputs.clientPassportNumber && inputs.clientPassportNumber.value
    ].map(page.onlyDigits).join('').slice(0, 10);
  }

  page.getStateDutyQrData = function () {
    var fio = splitFio(page.inputs.clientFio && page.inputs.clientFio.value);
    var fullName = [fio.lastName, fio.firstName, fio.middleName].filter(Boolean).join(' ');
    var amount = qrAmountKopecks();
    if (!fullName || amount <= 0) return null;

    var purpose = 'Госпошлина за ' + fullName;
    var fields = [
      ['Name', RECIPIENT.name],
      ['PersonalAcc', RECIPIENT.personalAcc],
      ['BankName', RECIPIENT.bankName],
      ['BIC', RECIPIENT.bic],
      ['CorrespAcc', RECIPIENT.correspAcc],
      ['PayeeINN', RECIPIENT.inn],
      ['KPP', RECIPIENT.kpp],
      ['CBC', RECIPIENT.kbk],
      ['OKTMO', RECIPIENT.oktmo],
      ['PersonalAccount', RECIPIENT.budgetPersonalAccount],
      ['DocIdx', RECIPIENT.docIdx],
      ['LastName', fio.lastName],
      ['FirstName', fio.firstName],
      ['MiddleName', fio.middleName],
      ['Purpose', purpose],
      ['Sum', String(amount)]
    ];

    var passport = passportDigits();
    if (passport.length === 10) {
      fields.push(['PayerIdType', '01']);
      fields.push(['PayerIdNum', passport]);
      fields.push(['PersAcc', '101000000000' + passport]);
    }

    return {
      fullName: fullName,
      amount: amount / 100,
      purpose: purpose,
      text: 'ST00012|' + fields
        .filter(function (pair) { return pair[1] !== null && pair[1] !== undefined && cleanField(pair[1]) !== ''; })
        .map(function (pair) { return pair[0] + '=' + cleanField(pair[1]); })
        .join('|')
    };
  };

  page.renderStateDutyQr = function () {
    var btn = page.btnStateDutyQr;
    var panel = page.stateDutyQrPanel;
    var code = page.stateDutyQrCode;
    var amountEl = page.stateDutyQrAmount;
    var purposeEl = page.stateDutyQrPurpose;
    var isLegal = page.inputs.clientIsLegal && page.inputs.clientIsLegal.checked;
    var data = !isLegal ? page.getStateDutyQrData() : null;

    if (btn) btn.disabled = !data;
    if (!panel || panel.hidden) return;

    if (!data || typeof window.qrcode !== 'function') {
      if (code) code.innerHTML = '';
      if (purposeEl) purposeEl.textContent = 'Заполните ФИО клиента и сумму госпошлины';
      if (amountEl) amountEl.textContent = '0 ₽';
      return;
    }

    var qr = window.qrcode(0, 'M');
    qr.addData(data.text);
    qr.make();
    if (code) code.innerHTML = qr.createSvgTag(5, 8, 'QR госпошлины', 'QR госпошлины');
    if (amountEl) amountEl.textContent = page.formatMoney(data.amount);
    if (purposeEl) purposeEl.textContent = data.purpose;
  };

  page.toggleStateDutyQr = function () {
    if (!page.stateDutyQrPanel || (page.btnStateDutyQr && page.btnStateDutyQr.disabled)) return;
    page.stateDutyQrPanel.hidden = !page.stateDutyQrPanel.hidden;
    page.renderStateDutyQr();
  };

  var previousSyncFromMainForm = page.syncFromMainForm;
  page.syncFromMainForm = function () {
    if (typeof previousSyncFromMainForm === 'function') previousSyncFromMainForm();
    page.renderStateDutyQr();
  };
})();
