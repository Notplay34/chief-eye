(function () {
  var api = window.API_BASE_URL || '';
  var fetchApi = window.fetchWithAuth || fetch;
  var state = { report: null };
  if (!window.getToken || !window.getToken()) return;

  function el(id) {
    return document.getElementById(id);
  }

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function isoDate(date) {
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate());
  }

  function num(value) {
    var parsed = Number(String(value || '').replace(/\s/g, '').replace(',', '.'));
    return isNaN(parsed) ? 0 : parsed;
  }

  function formatMoney(value) {
    return new Intl.NumberFormat('ru-RU', {
      maximumFractionDigits: 0,
      minimumFractionDigits: 0
    }).format(num(value)) + ' ₽';
  }

  function plainMoney(value) {
    return new Intl.NumberFormat('ru-RU', {
      maximumFractionDigits: 0,
      minimumFractionDigits: 0
    }).format(num(value));
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function parseJsonResponse(response) {
    return response.text().then(function (text) {
      var trimmed = (text || '').trim();
      if (!response.ok) {
        try {
          var parsed = JSON.parse(trimmed);
          throw new Error(parsed.detail || response.statusText);
        } catch (e) {
          if (e.message && e.message !== response.statusText) throw e;
        }
        throw new Error(response.statusText || ('Ошибка ' + response.status));
      }
      return trimmed ? JSON.parse(trimmed) : {};
    });
  }

  function card(label, value, hint, tone) {
    return [
      '<article class="analytics-card', tone ? ' analytics-card--' + tone : '', '">',
      '  <div class="analytics-card__label">', escapeHtml(label), '</div>',
      '  <div class="analytics-card__value">', escapeHtml(value), '</div>',
      '  <div class="analytics-card__hint">', escapeHtml(hint || ''), '</div>',
      '</article>'
    ].join('');
  }

  function moneyRow(label, value, tone) {
    return [
      '<div class="analytics-money-row', tone ? ' analytics-money-row--' + tone : '', '">',
      '  <span>', escapeHtml(label), '</span>',
      '  <strong>', escapeHtml(formatMoney(value)), '</strong>',
      '</div>'
    ].join('');
  }

  function render() {
    var root = el('plateReportApp');
    if (!root) return;
    var report = state.report;
    if (!report) {
      root.innerHTML = '<div class="analytics-empty">Загрузка отчёта…</div>';
      return;
    }

    var ownerExpenses = num(report.owner_expenses);
    var partnerExpenses = num(el('partnerExpenses') && el('partnerExpenses').value);
    var gross = num(report.gross_amount);
    var totalExpenses = ownerExpenses + partnerExpenses;
    var netProfit = gross - totalExpenses;
    var half = netProfit / 2;
    var partnerTransfer = half + partnerExpenses;

    root.innerHTML = [
      '<section class="analytics-grid analytics-grid--cards">',
      card('Сделано номеров', String(report.made_quantity || 0), 'По выданным номерам за период', 'primary'),
      card('Должно быть в кассе', formatMoney(gross), (report.made_quantity || 0) + ' × ' + formatMoney(report.unit_price || 1500), 'turnover'),
      card('Мои расходы', formatMoney(ownerExpenses), 'Отрицательные строки кассы номеров'),
      card('Остаток кассы номеров', formatMoney(report.plate_cash_balance), 'После закрытия месяца должен быть 0'),
      card('Чистая прибыль', formatMoney(netProfit), 'После вычета всех расходов'),
      '</section>',
      '<section class="analytics-grid analytics-grid--main">',
      '  <div class="analytics-stack">',
      '    <section class="analytics-panel">',
      '      <div class="analytics-panel__header">',
      '        <h2>Делёжка</h2>',
      '        <p>Чистая прибыль делится пополам; к половине партнёра добавляются его расходы.</p>',
      '      </div>',
      '      <div class="analytics-money-list">',
      moneyRow('Грязная сумма по номерам', gross),
      moneyRow('Мои расходы из кассы номеров', ownerExpenses),
      moneyRow('Расходы партнёра', partnerExpenses),
      moneyRow('Чистая прибыль', netProfit, 'total'),
      moneyRow('Моя половина', half),
      moneyRow('Половина партнёра', half),
      moneyRow('Отправить партнёру', partnerTransfer, 'total'),
      '      </div>',
      '    </section>',
      '  </div>',
      '  <div class="analytics-stack">',
      '    <section class="analytics-panel">',
      '      <div class="analytics-panel__header">',
      '        <h2>Склад на сейчас</h2>',
      '        <p>Остаток и браки для нижней части месячного отчёта.</p>',
      '      </div>',
      '      <div class="plate-report-stock">',
      '        <div><strong>', escapeHtml(report.stock_quantity || 0), '</strong><span>Всего осталось</span></div>',
      '        <div><strong>', escapeHtml(report.available_quantity || 0), '</strong><span>Доступно</span></div>',
      '        <div><strong>', escapeHtml(report.reserved_quantity || 0), '</strong><span>Зарезервировано</span></div>',
      '        <div><strong>', escapeHtml(report.defects_count || 0), '</strong><span>Браков за период</span></div>',
      '      </div>',
      '    </section>',
      '  </div>',
      '</section>'
    ].join('');
  }

  function buildReportText() {
    var report = state.report;
    if (!report) return '';
    var ownerExpenses = num(report.owner_expenses);
    var partnerExpenses = num(el('partnerExpenses') && el('partnerExpenses').value);
    var gross = num(report.gross_amount);
    var totalExpenses = ownerExpenses + partnerExpenses;
    var netProfit = gross - totalExpenses;
    var half = netProfit / 2;
    var partnerTransfer = half + partnerExpenses;
    var notes = (el('partnerExpenseNotes') && el('partnerExpenseNotes').value.trim()) || '';
    var ownerRows = report.owner_expense_rows || [];
    var lines = [
      'Отчёт по номерам',
      'Период: ' + (report.period && report.period.date_from ? report.period.date_from : '') + ' — ' + (report.period && report.period.date_to ? report.period.date_to : ''),
      '',
      'Сделали: ' + (report.made_quantity || 0) + ' × ' + plainMoney(report.unit_price || 1500) + ' = ' + plainMoney(gross),
      '',
      'Мои расходы: ' + plainMoney(ownerExpenses)
    ];
    if (ownerRows.length) {
      ownerRows.forEach(function (row) {
        lines.push('- ' + (row.client_name || 'Расход') + ': ' + plainMoney(Math.abs(num(row.amount))));
      });
    }
    lines.push('');
    lines.push('Расходы партнёра: ' + plainMoney(partnerExpenses));
    if (notes) {
      notes.split(/\r?\n/).forEach(function (line) {
        if (line.trim()) lines.push('- ' + line.trim());
      });
    }
    lines.push('');
    lines.push(plainMoney(gross) + ' - ' + plainMoney(ownerExpenses) + ' - ' + plainMoney(partnerExpenses) + ' = ' + plainMoney(netProfit));
    lines.push(plainMoney(netProfit) + ' / 2 = ' + plainMoney(half));
    lines.push('Мне: ' + plainMoney(half));
    lines.push('Партнёру: ' + plainMoney(half) + ' + ' + plainMoney(partnerExpenses) + ' = ' + plainMoney(partnerTransfer));
    lines.push('');
    lines.push('Осталось номеров: ' + (report.stock_quantity || 0));
    lines.push('Брак: ' + (report.defects_count || 0));
    lines.push('Касса номеров до закрытия: ' + plainMoney(report.plate_cash_balance));
    return lines.join('\n');
  }

  function downloadReport() {
    var text = buildReportText();
    if (!text) return;
    var blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    var period = state.report && state.report.period ? state.report.period : {};
    a.href = url;
    a.download = 'plate-report-' + (period.date_from || 'from') + '-' + (period.date_to || 'to') + '.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function load() {
    var root = el('plateReportApp');
    if (root) root.innerHTML = '<div class="analytics-empty">Загрузка отчёта…</div>';
    var params = new URLSearchParams();
    params.set('period', 'month');
    if (el('reportDateFrom') && el('reportDateFrom').value) params.set('date_from', el('reportDateFrom').value);
    if (el('reportDateTo') && el('reportDateTo').value) params.set('date_to', el('reportDateTo').value);
    fetchApi(api + '/analytics/plate-report?' + params.toString())
      .then(parseJsonResponse)
      .then(function (data) {
        state.report = data;
        render();
      })
      .catch(function (error) {
        if (root) root.innerHTML = '<div class="analytics-empty analytics-empty--error">Ошибка: ' + escapeHtml(error.message || '') + '</div>';
      });
  }

  function closeMonth() {
    var from = el('reportDateFrom') && el('reportDateFrom').value;
    var to = el('reportDateTo') && el('reportDateTo').value;
    if (!from || !to) return;
    if (!confirm('Создать отрицательную операцию в кассе номеров на весь остаток выбранного периода?')) return;
    var params = new URLSearchParams();
    params.set('period', 'month');
    params.set('date_from', from);
    params.set('date_to', to);
    fetchApi(api + '/analytics/plate-report/close?' + params.toString(), { method: 'POST' })
      .then(parseJsonResponse)
      .then(function (data) {
        state.report = data.report || data;
        render();
      })
      .catch(function (error) {
        var root = el('plateReportApp');
        if (root) root.innerHTML = '<div class="analytics-empty analytics-empty--error">Ошибка закрытия: ' + escapeHtml(error.message || '') + '</div>';
      });
  }

  function initDates() {
    var now = new Date();
    var start = new Date(now.getFullYear(), now.getMonth(), 1);
    if (el('reportDateFrom')) el('reportDateFrom').value = isoDate(start);
    if (el('reportDateTo')) el('reportDateTo').value = isoDate(now);
  }

  function init() {
    initDates();
    ['partnerExpenses', 'partnerExpenseNotes'].forEach(function (id) {
      var input = el(id);
      if (input) input.addEventListener('input', render);
    });
    if (el('btnReportRefresh')) el('btnReportRefresh').addEventListener('click', load);
    if (el('btnDownloadReport')) el('btnDownloadReport').addEventListener('click', downloadReport);
    if (el('btnClosePlateMonth')) el('btnClosePlateMonth').addEventListener('click', closeMonth);
    load();
  }

  init();
})();
