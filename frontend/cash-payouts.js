(function () {
  if (!window.requireAuth || !window.requireAuth()) return;

  var API = window.API_BASE_URL || '';
  var fetchApi = window.fetchWithAuth || fetch;

  var bodyEl = document.getElementById('payoutBody');
  var totalEl = document.getElementById('payoutTotal');
  var totalShortEl = document.getElementById('payoutTotalShort');
  var msgEl = document.getElementById('payoutMsg');
  var btnEl = document.getElementById('btnPayoutPay');
  var toggleEl = document.getElementById('btnPayoutToggle');
  var panelEl = document.getElementById('cashPayoutPanel');

  if (!bodyEl || !totalEl || !btnEl || !toggleEl || !panelEl) return;

  function formatMoney(n) {
    var num = Number(n || 0);
    if (!isFinite(num)) num = 0;
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(num) + ' ₽';
  }

  function setMsg(text, isErr) {
    if (!msgEl) return;
    msgEl.textContent = text || '';
    msgEl.className = 'cash-payout__msg' + (isErr ? ' cash-payout__msg--err' : '');
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
    var rows = (data && data.rows) || [];
    var total = data ? data.total || 0 : 0;

    bodyEl.innerHTML = '';
    if (!rows.length) {
      var tr = document.createElement('tr');
      tr.innerHTML = '<td colspan="3" class="cash-payout__empty">Нет денег за номера к переносу.</td>';
      bodyEl.appendChild(tr);
    } else {
      rows.forEach(function (r) {
        var tr = document.createElement('tr');
        var date = r.created_at ? r.created_at.substring(0, 10).split('-').reverse().join('.') : '';
        tr.innerHTML =
          '<td class="cash-payout__date">' + escapeHtml(date) + '</td>' +
          '<td class="cash-payout__client"><span>' + (r.client_short_name || r.client_name ? escapeHtml(r.client_short_name || r.client_name) : '—') +
          '</span><small>' + escapeHtml(r.quantity || 1) + ' шт</small></td>' +
          '<td class="cash-payout__amount">' + formatMoney(r.amount) + '</td>';
        bodyEl.appendChild(tr);
      });
    }

    var formatted = formatMoney(total);
    totalEl.textContent = formatted;
    totalShortEl.textContent = formatted;

    if (panelEl.hasAttribute('hidden')) panelEl.removeAttribute('hidden');
    btnEl.disabled = !rows.length;
  }

  function load() {
    setMsg('', false);
    bodyEl.innerHTML =
      '<tr><td colspan="3" class="cash-payout__empty">Загрузка…</td></tr>';
    fetchApi(API + '/cash/plate-payouts')
      .then(function (r) {
        if (!r.ok) {
          return r.json().then(function (j) {
            throw new Error(j.detail || r.statusText);
          });
        }
        return r.json();
      })
      .then(function (data) {
        render(data);
      })
      .catch(function (e) {
        setMsg('Ошибка загрузки: ' + (e.message || ''), true);
        bodyEl.innerHTML =
          '<tr><td colspan="3" class="cash-payout__empty">Ошибка загрузки</td></tr>';
      });
  }

  function pay() {
    if (!confirm('Перенести все деньги за номера из кассы документов в промежуточную кассу?')) return;
    setMsg('', false);
    fetchApi(API + '/cash/plate-payouts/pay', { method: 'POST' })
      .then(function (r) {
        if (!r.ok) {
          return r.json().then(function (j) {
            throw new Error(j.detail || r.statusText);
          });
        }
        return r.json();
      })
      .then(function (res) {
        setMsg('Перенесено за ' + (res.count || 0) + ' заказ(ов), сумма ' + formatMoney(res.total || 0) + '.', false);
        load();
      })
      .catch(function (e) {
        setMsg('Ошибка переноса: ' + (e.message || ''), true);
      });
  }

  btnEl.addEventListener('click', pay);
  load();
})();
