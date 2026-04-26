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
  var btnAddRow = document.getElementById('btnAddTransferRow');
  var readyListEl = document.getElementById('plateTransferReadyList');
  var historyBodyEl = document.getElementById('plateTransferHistoryBody');
  var historyMetaEl = document.getElementById('plateTransferHistoryMeta');
  var openHistoryDay = '';

  function money(value) {
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(Number(value || 0)) + ' ₽';
  }

  function numVal(value) {
    var parsed = parseFloat(String(value || '').replace(/\s/g, '').replace('₽', '').replace(',', '.'));
    return isNaN(parsed) ? 0 : parsed;
  }

  function quantityVal(value) {
    var parsed = parseInt(String(value || '').replace(/\s/g, ''), 10);
    return isNaN(parsed) || parsed < 0 ? 0 : parsed;
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

  function patchManualRow(rowId, payload) {
    return fetchApi(api + '/cash/plate-transfers/manual/' + rowId, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (r) {
      if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
      return r.json();
    });
  }

  function updateRow(updated) {
    rows = rows.map(function (row) {
      return row.row_type === 'manual' && row.id === updated.id ? updated : row;
    });
  }

  function makeManualInput(row, field, numeric) {
    var input = document.createElement('input');
    input.type = 'text';
    if (numeric) input.setAttribute('inputmode', field === 'quantity' ? 'numeric' : 'decimal');
    input.placeholder = field === 'client_name' ? 'ФИО или причина' : '0';
    input.value = numeric ? (Number(row[field] || 0) ? String(Number(row[field] || 0)).replace('.', ',') : '') : (row[field] || '');
    input.addEventListener('blur', function () {
      var value = field === 'quantity' ? quantityVal(input.value) : numeric ? numVal(input.value) : input.value.trim();
      var previous = rows.find(function (item) { return item.row_type === 'manual' && item.id === row.id; });
      if (!previous) return;
      if (numeric && Number(previous[field] || 0) === value) return;
      if (!numeric && String(previous[field] || '') === String(value)) return;
      var payload = {};
      payload[field] = value;
      patchManualRow(row.id, payload)
        .then(function (updated) {
          updateRow(updated);
          render({ rows: rows });
          setMsg('Сохранено');
          setTimeout(function () { setMsg(''); }, 1800);
        })
        .catch(function (e) {
          setMsg('Ошибка сохранения: ' + (e.message || ''), true);
          render({ rows: rows });
        });
    });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') input.blur();
    });
    return input;
  }

  function renderReadyList(readyRows) {
    if (!readyListEl) return;
    readyListEl.innerHTML = '';
    if (!readyRows.length) {
      readyListEl.innerHTML = '<div class="plate-transfer-ready__empty">Нет строк к выдаче</div>';
      return;
    }
    readyRows.forEach(function (row) {
      var item = document.createElement('div');
      item.className = 'plate-transfer-ready__item';
      item.innerHTML =
        '<span>' + escapeHtml(row.client_short_name || row.client_name || '—') + '</span>' +
        '<strong>' + money(row.amount) + '</strong>';
      readyListEl.appendChild(item);
    });
  }

  function dateText(value) {
    if (!value) return '';
    var date = new Date(value);
    if (isNaN(date.getTime())) return '';
    return date.toLocaleDateString('ru-RU') + ' ' + date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }

  function renderHistory(data) {
    if (!historyBodyEl) return;
    var historyDays = (data && data.days) || [];
    var total = Number(data && data.total || 0);
    var quantity = Number(data && data.quantity || 0);
    if (historyMetaEl) {
      historyMetaEl.textContent = historyDays.length + ' дней · ' + quantity + ' шт · ' + money(total);
    }
    historyBodyEl.innerHTML = '';
    if (!historyDays.length) {
      historyBodyEl.innerHTML = '<div class="plate-transfer-ready__empty">Выдач из промежуточной кассы ещё не было</div>';
      return;
    }
    if (!openHistoryDay) openHistoryDay = historyDays[0].date;
    historyDays.forEach(function (day) {
      var dayEl = document.createElement('div');
      dayEl.className = 'plate-transfer-history__day' + (day.date === openHistoryDay ? ' is-open' : '');
      var rowsHtml = '';
      (day.rows || []).forEach(function (row) {
        rowsHtml +=
          '<div class="plate-transfer-history__item">' +
          '<div><strong>' + escapeHtml(row.client_short_name || row.client_name || '—') + '</strong>' +
          '<small>' + escapeHtml(dateText(row.paid_at)) + (row.quantity ? ' · ' + escapeHtml(row.quantity) + ' шт' : '') + '</small></div>' +
          '<span>' + money(row.amount) + '</span>' +
          '</div>';
      });
      dayEl.innerHTML =
        '<button type="button" class="plate-transfer-history__day-btn" data-history-day="' + escapeHtml(day.date) + '">' +
        '<span>' + escapeHtml(day.label || day.date) + '</span>' +
        '<strong>' + money(day.total) + '</strong>' +
        '<small>' + escapeHtml(day.count || 0) + ' строк · ' + escapeHtml(day.quantity || 0) + ' шт</small>' +
        '</button>' +
        '<div class="plate-transfer-history__rows">' + rowsHtml + '</div>';
      historyBodyEl.appendChild(dayEl);
    });
  }

  function loadHistory() {
    if (!historyBodyEl) return;
    fetchApi(api + '/cash/plate-transfers/history')
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
        return r.json();
      })
      .then(renderHistory)
      .catch(function (e) {
        historyBodyEl.innerHTML = '<div class="plate-transfer-ready__empty">Ошибка истории: ' + escapeHtml(e.message || '') + '</div>';
      });
  }

  function render(data) {
    if (data && data.rows) rows = data.rows;
    var total = rows.reduce(function (sum, row) { return sum + numVal(row.amount); }, 0);
    var quantity = rows.reduce(function (sum, row) { return sum + quantityVal(row.quantity); }, 0);
    var readyRows = rows.filter(function (row) { return row.ready_to_pay; });
    var readyTotal = readyRows.reduce(function (sum, row) { return sum + numVal(row.amount); }, 0);

    totalEl.textContent = money(readyTotal);
    metaEl.textContent = 'В промежуточной ' + rows.length + ' строк · ' + quantity + ' шт · всего ' + money(total);
    btnPay.disabled = readyRows.length <= 0;
    renderReadyList(readyRows);
    bodyEl.innerHTML = '';

    if (!rows.length) {
      bodyEl.innerHTML = '<tr><td colspan="4" class="plate-cash-msg">Промежуточная касса пустая. Строки появятся после переноса денег из кассы документов или ручного добавления.</td></tr>';
      return;
    }

    rows.forEach(function (row) {
      var tr = document.createElement('tr');
      if (row.ready_to_pay) tr.className = 'plate-transfer-table__ready';
      var tdName = document.createElement('td');
      tdName.className = 'col-name';
      if (row.row_type === 'manual') {
        tdName.appendChild(makeManualInput(row, 'client_name', false));
        tdName.insertAdjacentHTML('beforeend', statusLabel(row));
      } else {
        tdName.innerHTML = '<strong>' + escapeHtml(row.client_short_name || row.client_name || '—') + '</strong>' + statusLabel(row);
      }
      tr.appendChild(tdName);

      var tdQuantity = document.createElement('td');
      tdQuantity.className = 'col-quantity';
      if (row.row_type === 'manual') {
        tdQuantity.appendChild(makeManualInput(row, 'quantity', true));
      } else {
        tdQuantity.textContent = String(row.quantity || 0);
      }
      tr.appendChild(tdQuantity);

      var tdAmount = document.createElement('td');
      tdAmount.className = 'col-amount col-amount--positive';
      if (row.row_type === 'manual') {
        tdAmount.appendChild(makeManualInput(row, 'amount', true));
      } else {
        tdAmount.textContent = money(row.amount);
      }
      tr.appendChild(tdAmount);

      var tdDelete = document.createElement('td');
      tdDelete.className = 'col-del';
      tdDelete.innerHTML = '<button type="button" data-row-key="' + escapeHtml(row.row_key || '') + '" title="Удалить">×</button>';
      tr.appendChild(tdDelete);
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
      .then(loadHistory)
      .catch(function (e) {
        setMsg('Ошибка загрузки: ' + (e.message || ''), true);
        bodyEl.innerHTML = '<tr><td colspan="4" class="plate-cash-msg err">Ошибка загрузки</td></tr>';
      });
  }

  function addManualRow() {
    setMsg('');
    fetchApi(api + '/cash/plate-transfers/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_name: '', quantity: 0, amount: 0 })
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
        return r.json();
      })
      .then(function (newRow) {
        rows.unshift(newRow);
        render({ rows: rows });
        setMsg('Строка добавлена в промежуточную кассу.');
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

  if (btnAddRow) btnAddRow.addEventListener('click', addManualRow);
  if (historyBodyEl) historyBodyEl.addEventListener('click', function (event) {
    var target = event.target;
    if (!target || !target.getAttribute) target = target && target.parentNode;
    while (target && target !== historyBodyEl && !target.getAttribute('data-history-day')) {
      target = target.parentNode;
    }
    if (!target || target === historyBodyEl) return;
    var day = target.getAttribute('data-history-day');
    openHistoryDay = openHistoryDay === day ? '' : day;
    loadHistory();
  });
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
