(function () {
  if (window.RegDocFormPage) return;
  if (window.getToken && !window.getToken()) return;

  var el = function (id) { return document.getElementById(id); };

  window.RegDocFormPage = {
    apiBaseUrl: window.API_BASE_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''),
    fetchApi: window.fetchWithAuth || fetch,
    state: {
      priceList: [],
      selectedDocuments: [],
      historyItems: [],
      historyPage: 0,
      historyPageSize: 5
    },
    el: el,
    inputs: {
      clientFio: el('clientFio'),
      clientPassport: el('clientPassport'),
      clientAddress: el('clientAddress'),
      clientPhone: el('clientPhone'),
      clientIsLegal: el('clientIsLegal'),
      clientLegalName: el('clientLegalName'),
      clientInn: el('clientInn'),
      clientOgrn: el('clientOgrn'),
      hasSeller: el('hasSeller'),
      sellerFio: el('sellerFio'),
      sellerPassport: el('sellerPassport'),
      sellerAddress: el('sellerAddress'),
      hasTrustee: el('hasTrustee'),
      trusteeFio: el('trusteeFio'),
      trusteePassport: el('trusteePassport'),
      trusteeBasis: el('trusteeBasis'),
      vin: el('vin'),
      brandModel: el('brandModel'),
      vehicleType: el('vehicleType'),
      year: el('year'),
      engine: el('engine'),
      chassis: el('chassis'),
      body: el('body'),
      color: el('color'),
      srts: el('srts'),
      plateNumber: el('plateNumber'),
      pts: el('pts'),
      dkpDate: el('dkpDate'),
      summaDkp: el('summaDkp'),
      dkpNumber: el('dkpNumber'),
      dkpSummary: el('dkpSummary'),
      stateDuty: el('stateDuty'),
      needPlate: el('needPlate'),
      plateQuantity: el('plateQuantity')
    },
    docSelect: el('docSelect'),
    btnAddDoc: el('btnAddDoc'),
    documentsList: el('documentsList'),
    documentsEmpty: el('documentsEmpty'),
    historyTrigger: el('historyTrigger'),
    historyPopover: el('historyPopover'),
    historyRange: el('historyRange'),
    historyPrev: el('historyPrev'),
    historyNext: el('historyNext'),
    formHistoryList: el('formHistoryList'),
    formHistoryLoading: el('formHistoryLoading'),
    summary: {
      sumStateDuty: el('sumStateDuty'),
      sumIncome: el('sumIncome'),
      sumTotal: el('sumTotal')
    },
    preview: {
      previewFio: el('previewFio'),
      previewPassport: el('previewPassport'),
      previewAddress: el('previewAddress'),
      previewPhone: el('previewPhone'),
      previewSeller: el('previewSeller'),
      previewTrustee: el('previewTrustee'),
      previewVehicle: el('previewVehicle'),
      previewDkp: el('previewDkp'),
      previewService: el('previewService'),
      previewTotal: el('previewTotal')
    },
    btnAcceptCash: el('btnAcceptCash'),
    btnPrint: el('btnPrint'),
    orderIdDisplay: el('orderIdDisplay'),
    currentTime: el('currentTime')
  };
})();
