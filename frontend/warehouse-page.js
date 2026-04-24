(function () {
  var api = window.API_BASE_URL || '';
  var fetchApi = window.fetchWithAuth || fetch;
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
        setTimeout(function () { msg(''); }, 3000);
      })
      .catch(function (e) {
        msg('Ошибка: ' + (e.message || ''), true);
      });
  });

  load();
})();
