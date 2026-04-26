(function () {
  var api = window.API_BASE_URL || '';
  var fetchApi = window.fetchWithAuth || fetch;
  if (!window.getToken || !window.getToken()) return;

  var rows = [];
  var bodyEl = document.getElementById('plateTransferBody');
  var totalEl = document.getElementById('plateTransferTotal');
  var metaEl = document.getElementById('plateTransferMeta');
  var btnPay = document.getElementById('btnPlateTransferPay');
  var msgEl = document.getElementById('plateTransferMsg');
  var formEl = document.getElementById('plateTransferForm');
  var nameEl = document.getElementById('plateTransferName');
  var quantityEl = document.getElementById('plateTransferQuantity');
  var amountEl = document.getElementById('plateTransferAmount');

  function money(value) {
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(Number(value || 0)) + ' ₽';
  }

  function setMsg(text, isErr) {
    if (!msgEl) return;
    msgEl.textContent = text || '';
    msgEl.className = 'plate-cash-msg' + (isErr ? ' err' : '');
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function statusLabel(row) {
    if (row.row_type === 'manual') return '<small>ручная строка</small>';
    if (row.ready_to_pay) return '<small>к выдаче</small>';
    return '<small>в промежуточной, ждёт выдачи номера</small>';
  }

  function render(data) {
    rows = (data && data.rows) || [];
    var total = Number(data && data.total || 0);
    var quantity = Number(data && data.quantity || 0);
    var readyCount = Number(data && data.ready_count || 0);
    var readyTotal = Number(data && data.ready_total || 0);

    totalEl.textContent = money(total);
    metaEl.textContent = rows.length + ' строк · ' + quantity + ' шт · к выдаче ' + readyCount + ' на ' + money(readyTotal);
    btnPay.disabled = readyCount <= 0;
    bodyEl.innerHTML = '';

    if (!rows.length) {
      bodyEl.innerHTML = '<tr><td colspan="4" class="plate-cash-msg">Промежуточная касса пустая. Строки появятся после переноса денег из кассы документов или ручного добавления.</td></tr>';
      return;
    }

    rows.forEach(function (row) {
      var tr = document.createElement('tr');
      if (row.ready_to_pay) tr.className = 'plate-transfer-table__ready';
      tr.innerHTML =
        '<td class="col-name"><strong>' + escapeHtml(row.client_short_name || row.client_name || '—') + '</strong>' + statusLabel(row) + '</td>' +
        '<td class="col-quantity">' + escapeHtml(row.quantity || 0) + '</td>' +
        '<td class="col-amount col-amount--positive">' + money(row.amount) + '</td>' +
        '<td class="col-del"><button type="button" data-row-key="' + escapeHtml(row.row_key || '') + '" title="Удалить">×</button></td>';
      bodyEl.appendChild(tr);
    });
  }

  function load() {
    setMsg('');
    bodyEl.innerHTML = '<tr><td colspan="4" class="plate-cash-msg">Загрузка…</td></tr>';
    fetchApi(api + '/cash/plate-transfers')
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
        return r.json();
      })
      .then(render)
      .catch(function (e) {
        setMsg('Ошибка загрузки: ' + (e.message || ''), true);
        bodyEl.innerHTML = '<tr><td colspan="4" class="plate-cash-msg err">Ошибка загрузки</td></tr>';
      });
  }

  function addManualRow(event) {
    event.preventDefault();
    var amount = Number(amountEl && amountEl.value || 0);
    var quantity = Math.max(0, parseInt(quantityEl && quantityEl.value || '0', 10) || 0);
    if (!amount || amount <= 0) {
      setMsg('Введите сумму больше нуля.', true);
      return;
    }
    setMsg('');
    fetchApi(api + '/cash/plate-transfers/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_name: nameEl ? nameEl.value : '',
        quantity: quantity,
        amount: amount
      })
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
        return r.json();
      })
      .then(function () {
        if (nameEl) nameEl.value = '';
        if (quantityEl) quantityEl.value = '0';
        if (amountEl) amountEl.value = '';
        setMsg('Строка добавлена в промежуточную кассу.');
        load();
      })
      .catch(function (e) {
        setMsg('Ошибка добавления: ' + (e.message || ''), true);
      });
  }

  function deleteRow(rowKey) {
    if (!rowKey) return;
    if (!confirm('Удалить строку из промежуточной кассы?')) return;
    setMsg('');
    fetchApi(api + '/cash/plate-transfers/' + encodeURIComponent(rowKey), { method: 'DELETE' })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
      })
      .then(function () {
        setMsg('Строка удалена из промежуточной кассы.');
        load();
      })
      .catch(function (e) {
        setMsg('Ошибка удаления: ' + (e.message || ''), true);
      });
  }

  if (formEl) formEl.addEventListener('submit', addManualRow);
  bodyEl.addEventListener('click', function (event) {
    var target = event.target;
    if (!target || !target.getAttribute) return;
    var rowKey = target.getAttribute('data-row-key');
    if (rowKey) deleteRow(rowKey);
  });

  btnPay.addEventListener('click', function () {
    var readyRows = rows.filter(function (row) { return row.ready_to_pay; });
    if (!readyRows.length) return;
    if (!confirm('Выдать деньги в кассу номеров по строкам «к выдаче»? Остальные останутся в промежуточной кассе.')) return;
    setMsg('');
    fetchApi(api + '/cash/plate-transfers/pay', { method: 'POST' })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
        return r.json();
      })
      .then(function (res) {
        setMsg('Выдано в кассу номеров: ' + (res.count || 0) + ' строк, ' + money(res.total || 0) + '.');
        load();
      })
      .catch(function (e) {
        setMsg('Ошибка передачи: ' + (e.message || ''), true);
      });
  });

  load();
})();
