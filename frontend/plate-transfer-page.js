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

  function render(data) {
    rows = (data && data.rows) || [];
    var total = Number(data && data.total || 0);
    var quantity = Number(data && data.quantity || 0);

    totalEl.textContent = money(total);
    metaEl.textContent = rows.length + ' человек · ' + quantity + ' шт';
    btnPay.disabled = !rows.length;
    bodyEl.innerHTML = '';

    if (!rows.length) {
      bodyEl.innerHTML = '<tr><td colspan="3" class="plate-cash-msg">Нет выданных номеров к передаче. Строки появятся после кнопки «Выдано клиенту» у оператора номеров.</td></tr>';
      return;
    }

    rows.forEach(function (row) {
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td class="col-name"><strong>' + escapeHtml(row.client_short_name || row.client_name || '—') + '</strong></td>' +
        '<td class="col-quantity">' + escapeHtml(row.quantity || 1) + '</td>' +
        '<td class="col-amount col-amount--positive">' + money(row.amount) + '</td>';
      bodyEl.appendChild(tr);
    });
  }

  function load() {
    setMsg('');
    bodyEl.innerHTML = '<tr><td colspan="3" class="plate-cash-msg">Загрузка…</td></tr>';
    fetchApi(api + '/cash/plate-transfers')
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
        return r.json();
      })
      .then(render)
      .catch(function (e) {
        setMsg('Ошибка загрузки: ' + (e.message || ''), true);
        bodyEl.innerHTML = '<tr><td colspan="3" class="plate-cash-msg err">Ошибка загрузки</td></tr>';
      });
  }

  btnPay.addEventListener('click', function () {
    if (!rows.length) return;
    if (!confirm('Выдать деньги в кассу номеров по выданным клиентам? После этого строки появятся в кассе номеров.')) return;
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
