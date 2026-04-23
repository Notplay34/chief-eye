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

  function render(data) {
    var rows = (data && data.rows) || [];
    var total = data ? data.total || 0 : 0;

    bodyEl.innerHTML = '';
    if (!rows.length) {
      var tr = document.createElement('tr');
      tr.innerHTML = '<td colspan="3" class="cash-payout__empty">Нет номеров к выдаче.</td>';
      bodyEl.appendChild(tr);
    } else {
      rows.forEach(function (r) {
        var tr = document.createElement('tr');
        var date = r.created_at ? r.created_at.substring(0, 10).split('-').reverse().join('.') : '';
        tr.innerHTML =
          '<td>' + date + '</td>' +
          '<td>' + (r.client_name || '—') + '</td>' +
          '<td class="cash-payout__amount">' + formatMoney(r.amount) + '</td>';
        bodyEl.appendChild(tr);
      });
    }

    var formatted = formatMoney(total);
    totalEl.textContent = formatted;
    totalShortEl.textContent = formatted;

    // Если нечего выдавать — делаем чип бледным и панель по умолчанию закрытой
    toggleEl.disabled = !rows.length;
    if (!rows.length && !panelEl.hasAttribute('hidden')) {
      panelEl.setAttribute('hidden', 'hidden');
    }
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
    if (!confirm('Выдать деньги оператору номеров за все невыплаченные номера?')) return;
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
        setMsg('Выдано за ' + (res.count || 0) + ' заказ(ов), сумма ' + formatMoney(res.total || 0) + '.', false);
        load();
      })
      .catch(function (e) {
        setMsg('Ошибка выдачи: ' + (e.message || ''), true);
      });
  }

  btnEl.addEventListener('click', pay);

  toggleEl.addEventListener('click', function () {
    var isHidden = panelEl.hasAttribute('hidden');
    if (isHidden) {
      panelEl.removeAttribute('hidden');
    } else {
      panelEl.setAttribute('hidden', 'hidden');
    }
  });
  load();
})();

