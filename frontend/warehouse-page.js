(function () {
  var api = window.API_BASE_URL || '';
  var fetchApi = window.fetchWithAuth || fetch;
  var movementsPage = 0;
  var movementsPageSize = 30;
  var movementsHasNext = false;
  var movementsVisibleCount = 0;
  if (!window.getToken || !window.getToken()) return;

  function msg(text, isErr) {
    var el = document.getElementById('warehouseMsg');
    if (!el) return;
    el.textContent = text || '';
    el.className = 'warehouse-msg' + (isErr ? ' err' : ' ok');
  }

  function parseJsonResponse(response, hint) {
    return response.text().then(function (text) {
      var trimmed = (text || '').trim();
      if (trimmed.indexOf('<') === 0) {
        throw new Error('Сервер вернул HTML вместо данных.' + hint);
      }
      if (!response.ok) {
        try {
          var parsed = JSON.parse(trimmed);
          throw new Error(parsed.detail || response.statusText);
        } catch (e) {
          if (e.message && e.message !== response.statusText) throw e;
        }
        throw new Error(response.statusText || ('Ошибка ' + response.status));
      }
      if (!trimmed) return {};
      try {
        return JSON.parse(trimmed);
      } catch (_) {
        throw new Error('Ответ не JSON.' + hint);
      }
    });
  }

  function monthKey(date) {
    var y = date.getFullYear();
    var m = date.getMonth() + 1;
    return y + '-' + (m < 10 ? '0' : '') + m;
  }

  function addMonths(date, amount) {
    return new Date(date.getFullYear(), date.getMonth() + amount, 1);
  }

  function formatMonth(value) {
    if (!value) return '';
    var parts = value.split('-');
    if (parts.length !== 2) return value;
    return parts[1] + '.' + parts[0];
  }

  function formatDateTime(value) {
    if (!value) return '';
    var d = new Date(value);
    if (isNaN(d.getTime())) return value;
    return d.toLocaleString('ru-RU');
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function movementLabel(type) {
    var labels = {
      STOCK_IN: 'Приход',
      ORDER_COMPLETED: 'Изготовили по заказу',
      PLATE_CASH_SALE: 'Продажа в кассе номеров',
      PLATE_CASH_RETURN: 'Возврат на склад',
      DEFECT: 'Брак',
      ORDER_ROLLBACK: 'Откат заказа'
    };
    return labels[type] || type || '';
  }

  function historyQuery() {
    var from = document.getElementById('historyFrom');
    var to = document.getElementById('historyTo');
    var params = [];
    if (from && from.value) params.push('month_from=' + encodeURIComponent(from.value));
    if (to && to.value) params.push('month_to=' + encodeURIComponent(to.value));
    return params.length ? '?' + params.join('&') : '';
  }

  function movementsQuery() {
    var from = document.getElementById('historyFrom');
    var to = document.getElementById('historyTo');
    var params = [
      'limit=' + encodeURIComponent(movementsPageSize + 1),
      'offset=' + encodeURIComponent(movementsPage * movementsPageSize)
    ];
    if (from && from.value) params.push('month_from=' + encodeURIComponent(from.value));
    if (to && to.value) params.push('month_to=' + encodeURIComponent(to.value));
    return '?' + params.join('&');
  }

  function renderMovementsPager() {
    var info = document.getElementById('warehouseMovementsPageInfo');
    var prev = document.getElementById('warehouseMovementsPrev');
    var next = document.getElementById('warehouseMovementsNext');
    var pageInput = document.getElementById('warehouseMovementsPageNumber');
    var count = movementsVisibleCount;
    if (info) {
      var start = count ? movementsPage * movementsPageSize + 1 : 0;
      var end = movementsPage * movementsPageSize + count;
      info.textContent = start + '–' + end + ' записей';
    }
    if (pageInput) pageInput.value = String(movementsPage + 1);
    if (prev) prev.disabled = movementsPage <= 0;
    if (next) next.disabled = !movementsHasNext;
  }

  function loadHistory() {
    var query = historyQuery();
    fetchApi(api + '/warehouse/plate-stock/monthly' + query)
      .then(function (r) { return parseJsonResponse(r, ''); })
      .then(function (data) {
        var body = document.getElementById('warehouseMonthlyBody');
        if (!body) return;
        var rows = data.rows || [];
        if (!rows.length) {
          body.innerHTML = '<tr><td colspan="6" class="warehouse-empty">Нет данных за выбранный период.</td></tr>';
          return;
        }
        body.innerHTML = rows.map(function (row) {
          return '<tr>' +
            '<td>' + formatMonth(row.month) + '</td>' +
            '<td>' + row.opening_balance + '</td>' +
            '<td>' + row.incoming + '</td>' +
            '<td>' + row.made + '</td>' +
            '<td>' + row.defects + '</td>' +
            '<td>' + row.closing_balance + '</td>' +
            '</tr>';
        }).join('');
      })
      .catch(function (e) {
        var body = document.getElementById('warehouseMonthlyBody');
        if (body) body.innerHTML = '<tr><td colspan="6" class="warehouse-empty">Ошибка: ' + (e.message || '') + '</td></tr>';
      });

    fetchApi(api + '/warehouse/plate-stock/movements' + movementsQuery())
      .then(function (r) { return parseJsonResponse(r, ''); })
      .then(function (data) {
        var body = document.getElementById('warehouseMovementsBody');
        if (!body) return;
        var rows = data.rows || [];
        movementsHasNext = rows.length > movementsPageSize;
        if (movementsHasNext) rows = rows.slice(0, movementsPageSize);
        movementsVisibleCount = rows.length;
        if (!rows.length) {
          body.innerHTML = '<tr><td colspan="5" class="warehouse-empty">Движений за выбранный период нет.</td></tr>';
          renderMovementsPager();
          return;
        }
        body.innerHTML = rows.map(function (row) {
          var delta = Number(row.quantity_delta || 0);
          var deltaText = (delta > 0 ? '+' : '') + delta;
          return '<tr>' +
            '<td>' + formatDateTime(row.created_at) + '</td>' +
            '<td>' + escapeHtml(movementLabel(row.movement_type)) + '</td>' +
            '<td class="' + (delta < 0 ? 'warehouse-delta-neg' : 'warehouse-delta-pos') + '">' + deltaText + '</td>' +
            '<td>' + row.balance_after + '</td>' +
            '<td>' + escapeHtml(row.note || '') + '</td>' +
            '</tr>';
        }).join('');
        renderMovementsPager();
      })
      .catch(function (e) {
        var body = document.getElementById('warehouseMovementsBody');
        if (body) body.innerHTML = '<tr><td colspan="5" class="warehouse-empty">Ошибка: ' + (e.message || '') + '</td></tr>';
        movementsHasNext = false;
        movementsVisibleCount = 0;
        renderMovementsPager();
      });
  }

  function load() {
    var hint = ' Проверьте nginx: маршрут /warehouse должен проксироваться на backend.';
    fetchApi(api + '/warehouse/plate-stock')
      .then(function (r) { return parseJsonResponse(r, hint); })
      .then(function (data) {
        document.getElementById('quantity').textContent = data.quantity;
        document.getElementById('reserved').textContent = data.reserved;
        document.getElementById('available').textContent = data.available;
        document.getElementById('defectsMonth').textContent = data.defects_this_month != null ? data.defects_this_month : '—';
        var warningEl = document.getElementById('warehouseWarning');
        var stockCard = document.querySelector('.warehouse-card--stock');
        var available = Number(data.available || 0);
        var reserved = Number(data.reserved || 0);
        if (warningEl) {
          if (available <= 0 && reserved > 0) {
            warningEl.hidden = false;
            warningEl.textContent = 'Все заготовки зарезервированы. Новые заказы на номера требуют пополнения склада.';
            if (stockCard) stockCard.classList.add('warehouse-card--warning');
          } else if (available <= 0) {
            warningEl.hidden = false;
            warningEl.textContent = 'Доступных заготовок нет. Пополните склад перед новыми заказами.';
            if (stockCard) stockCard.classList.add('warehouse-card--warning');
          } else {
            warningEl.hidden = true;
            warningEl.textContent = '';
            if (stockCard) stockCard.classList.remove('warehouse-card--warning');
          }
        }

        var breakdown = data.reserved_breakdown || [];
        var breakdownEl = document.getElementById('reservedBreakdown');
        if (!breakdown.length) {
          breakdownEl.textContent = '';
          return;
        }

        var bySum = {};
        breakdown.forEach(function (item) {
          var sum = Math.round(item.total_amount);
          bySum[sum] = (bySum[sum] || 0) + item.quantity;
        });
        breakdownEl.textContent = Object.keys(bySum)
          .sort(function (a, b) { return Number(b) - Number(a); })
          .map(function (sum) { return sum + ' ₽ — ' + bySum[sum] + ' шт'; })
          .join(', ');
      })
      .catch(function (e) {
        document.getElementById('quantity').textContent = '—';
        document.getElementById('reserved').textContent = '—';
        document.getElementById('available').textContent = '—';
        document.getElementById('reservedBreakdown').textContent = '';
        document.getElementById('defectsMonth').textContent = '—';
        var warningEl = document.getElementById('warehouseWarning');
        if (warningEl) {
          warningEl.hidden = false;
          warningEl.textContent = 'Не удалось загрузить состояние склада.';
        }
        msg('Ошибка: ' + (e.message || ''), true);
      });
  }

  document.getElementById('btnAdd').addEventListener('click', function () {
    var input = document.getElementById('addAmount');
    var amount = parseInt(input.value, 10);
    if (isNaN(amount) || amount < 1) {
      msg('Введите число больше 0', true);
      return;
    }
    fetchApi(api + '/warehouse/plate-stock/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount: amount })
    })
      .then(function (r) { return parseJsonResponse(r, ''); })
      .then(function () {
        msg('Добавлено ' + amount + ' шт.');
        load();
        loadHistory();
        setTimeout(function () { msg(''); }, 3000);
      })
      .catch(function (e) {
        msg('Ошибка: ' + (e.message || ''), true);
      });
  });

  document.getElementById('btnDefect').addEventListener('click', function () {
    if (!confirm('Списать 1 шт как брак?')) return;
    fetchApi(api + '/warehouse/plate-stock/defect', { method: 'POST' })
      .then(function (r) { return parseJsonResponse(r, ''); })
      .then(function () {
        msg('Списано 1 шт (брак).');
        load();
        loadHistory();
        setTimeout(function () { msg(''); }, 3000);
      })
      .catch(function (e) {
        msg('Ошибка: ' + (e.message || ''), true);
      });
  });

  var now = new Date();
  var fromInput = document.getElementById('historyFrom');
  var toInput = document.getElementById('historyTo');
  if (fromInput) fromInput.value = monthKey(addMonths(now, -11));
  if (toInput) toInput.value = monthKey(now);
  var historyBtn = document.getElementById('btnHistoryApply');
  if (historyBtn) historyBtn.addEventListener('click', function () {
    movementsPage = 0;
    loadHistory();
  });
  var movementsPageSizeSelect = document.getElementById('warehouseMovementsPageSize');
  if (movementsPageSizeSelect) {
    movementsPageSize = parseInt(movementsPageSizeSelect.value, 10) || movementsPageSize;
    movementsPageSizeSelect.addEventListener('change', function () {
      movementsPageSize = parseInt(this.value, 10) || 30;
      movementsPage = 0;
      loadHistory();
    });
  }
  var movementsPrev = document.getElementById('warehouseMovementsPrev');
  if (movementsPrev) movementsPrev.addEventListener('click', function () {
    if (movementsPage <= 0) return;
    movementsPage -= 1;
    loadHistory();
  });
  var movementsNext = document.getElementById('warehouseMovementsNext');
  if (movementsNext) movementsNext.addEventListener('click', function () {
    if (!movementsHasNext) return;
    movementsPage += 1;
    loadHistory();
  });
  var movementsPageInput = document.getElementById('warehouseMovementsPageNumber');
  if (movementsPageInput) movementsPageInput.addEventListener('change', function () {
    var value = parseInt(this.value, 10);
    if (isNaN(value) || value < 1) value = 1;
    movementsPage = value - 1;
    loadHistory();
  });

  load();
  loadHistory();
})();
