(function () {
  var api = window.API_BASE_URL || '';
  var fetchApi = window.fetchWithAuth || fetch;
  if (!window.getToken || !window.getToken()) return;

  var rows = [];
  var activeDate = todayKey();
  var PLATE_UNIT_PRICE = 1500;
  var page = 0;
  var pageSize = 30;
  var hasNextPage = false;

  function msg(text, isErr) {
    var el = document.getElementById('plateCashMsg');
    if (!el) return;
    el.textContent = text || '';
    el.className = 'plate-cash-msg' + (isErr ? ' err' : '');
  }

  function numVal(value) {
    var parsed = parseFloat(String(value).replace(/\s/g, '').replace('₽', '').replace(',', '.'));
    return isNaN(parsed) ? 0 : parsed;
  }

  function quantityVal(value) {
    var parsed = parseInt(String(value || '').replace(/\s/g, ''), 10);
    return isNaN(parsed) || parsed < 0 ? 0 : parsed;
  }

  function fmt(value) {
    var text = new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value) + ' ₽';
    return value < 0 ? '<span class="amount-neg">' + text + '</span>' : text;
  }

  function moneyText(value) {
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value) + ' ₽';
  }

  function patchRow(rowId, payload) {
    return fetchApi(api + '/cash/plate-rows/' + rowId, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (r) {
      if (!r.ok) {
        return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
      }
      return r.json();
    });
  }

  function updateRowInList(id, data) {
    for (var i = 0; i < rows.length; i += 1) {
      if (rows[i].id === id) {
        rows[i] = data;
        return;
      }
    }
  }

  function dayKey(row) {
    var source = row.created_at;
    if (!source) return '';
    var date = new Date(source);
    if (isNaN(date.getTime())) return '';
    var y = date.getFullYear();
    var m = date.getMonth() + 1;
    var d = date.getDate();
    return y + '-' + (m < 10 ? '0' : '') + m + '-' + (d < 10 ? '0' : '') + d;
  }

  function todayKey() {
    var date = new Date();
    var y = date.getFullYear();
    var m = date.getMonth() + 1;
    var d = date.getDate();
    return y + '-' + (m < 10 ? '0' : '') + m + '-' + (d < 10 ? '0' : '') + d;
  }

  function rowsUrl() {
    var url = api + '/cash/plate-rows';
    var params = [
      'limit=' + encodeURIComponent(pageSize + 1),
      'offset=' + encodeURIComponent(page * pageSize)
    ];
    if (activeDate) params.push('business_date=' + encodeURIComponent(activeDate));
    return url + '?' + params.join('&');
  }

  function renderPager() {
    var info = document.getElementById('plateCashPageInfo');
    var prev = document.getElementById('plateCashPagePrev');
    var next = document.getElementById('plateCashPageNext');
    if (info) {
      var start = rows.length ? page * pageSize + 1 : 0;
      var end = page * pageSize + rows.length;
      info.textContent = start + '–' + end;
    }
    if (prev) prev.disabled = page <= 0;
    if (next) next.disabled = !hasNextPage;
  }

  function dayLabel(key) {
    if (!key) return '';
    var parts = key.split('-');
    if (parts.length !== 3) return key;
    return parts[2] + '.' + parts[1] + '.' + parts[0];
  }

  function renderTotal() {
    var total = rows.reduce(function (sum, row) { return sum + numVal(row.amount); }, 0);
    document.getElementById('totalCell').innerHTML = fmt(total);
  }

  function makeInput(row, key, isNum) {
    var input = document.createElement('input');
    input.type = 'text';
    if (isNum) input.setAttribute('inputmode', 'decimal');
    if (!isNum) input.placeholder = 'Фамилия';
    input.value = isNum ? (row[key] ? moneyText(numVal(row[key])).replace(' ₽', '') : '') : (row[key] || '');
    input.dataset.key = key;
    input.dataset.rowId = String(row.id);
    input.addEventListener('blur', function () {
      var id = parseInt(this.dataset.rowId, 10);
      var field = this.dataset.key;
      var value = isNum ? numVal(this.value) : this.value.trim();
      var previous = rows.find(function (item) { return item.id === id; });
      if (!previous) return;
      if (isNum && previous[field] === value) return;
      if (!isNum && String(previous[field] || '') === String(value)) return;

      var payload = {};
      payload[field] = value;
      if (isNum) this.value = value ? moneyText(value).replace(' ₽', '') : '';
      patchRow(id, payload)
        .then(function (updated) {
          updateRowInList(id, updated);
          if (isNum) render();
          renderTotal();
          msg('Сохранено');
          setTimeout(function () { msg(''); }, 2000);
        })
        .catch(function (e) {
          msg('Ошибка: ' + (e.message || 'не удалось сохранить'), true);
        });
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') this.blur();
    });
    return input;
  }

  function makeQuantityInput(row) {
    var input = document.createElement('input');
    input.type = 'text';
    input.setAttribute('inputmode', 'numeric');
    input.placeholder = '0';
    input.value = quantityVal(row.quantity) > 0 ? String(quantityVal(row.quantity)) : '';
    input.dataset.rowId = String(row.id);
    input.addEventListener('blur', function () {
      var id = parseInt(this.dataset.rowId, 10);
      var value = quantityVal(this.value);
      var previous = rows.find(function (item) { return item.id === id; });
      if (!previous) return;
      if (quantityVal(previous.quantity) === value) return;

      var payload = { quantity: value };
      if (value > 0) payload.amount = value * PLATE_UNIT_PRICE;
      this.value = value > 0 ? String(value) : '';

      patchRow(id, payload)
        .then(function (updated) {
          updateRowInList(id, updated);
          render();
          msg(value > 0 ? 'Номера списаны со склада.' : 'Списание номеров отменено.');
          setTimeout(function () { msg(''); }, 2000);
        })
        .catch(function (e) {
          input.value = quantityVal(previous.quantity) > 0 ? String(quantityVal(previous.quantity)) : '';
          msg('Ошибка: ' + (e.message || 'не удалось сохранить'), true);
        });
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') this.blur();
    });
    return input;
  }

  function renderRow(row) {
    var tr = document.createElement('tr');
    tr.dataset.rowId = String(row.id);

    var tdName = document.createElement('td');
    tdName.className = 'col-name';
    tdName.appendChild(makeInput(row, 'client_name', false));
    tr.appendChild(tdName);

    var tdQuantity = document.createElement('td');
    tdQuantity.className = 'col-quantity';
    tdQuantity.appendChild(makeQuantityInput(row));
    tr.appendChild(tdQuantity);

    var tdAmount = document.createElement('td');
    tdAmount.className = 'col-amount ' + (numVal(row.amount) < 0 ? 'col-amount--negative' : numVal(row.amount) > 0 ? 'col-amount--positive' : 'col-amount--zero');
    tdAmount.appendChild(makeInput(row, 'amount', true));
    tr.appendChild(tdAmount);

    var tdDelete = document.createElement('td');
    tdDelete.className = 'col-del';
    var btnDelete = document.createElement('button');
    btnDelete.textContent = '×';
    btnDelete.title = 'Удалить строку';
    btnDelete.addEventListener('click', function () {
      if (!confirm('Удалить строку?')) return;
      fetchApi(api + '/cash/plate-rows/' + row.id, { method: 'DELETE' })
        .then(function (r) {
          if (r.status === 204 || r.ok) {
            rows = rows.filter(function (item) { return item.id !== row.id; });
            render();
            renderPager();
            return;
          }
          return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
        })
        .catch(function (e) {
          msg('Ошибка: ' + (e.message || 'удалить'), true);
        });
    });
    tdDelete.appendChild(btnDelete);
    tr.appendChild(tdDelete);

    return tr;
  }

  function render() {
    var tbody = document.getElementById('plateCashBody');
    tbody.innerHTML = '';
    if (!rows.length) {
      var emptyRow = document.createElement('tr');
      emptyRow.innerHTML = '<td colspan="4" class="plate-cash-msg">Нет строк. Нажмите «Добавить строку». Сумма может быть отрицательной.</td>';
      tbody.appendChild(emptyRow);
    } else {
      var lastDay = null;
      rows.forEach(function (row) {
        var currentDay = dayKey(row);
        if (currentDay && currentDay !== lastDay) {
          lastDay = currentDay;
          var separator = document.createElement('tr');
          separator.className = 'day-sep';
          separator.innerHTML = '<td colspan="4">' + dayLabel(currentDay) + '</td>';
          tbody.appendChild(separator);
        }
        tbody.appendChild(renderRow(row));
      });
    }
    renderTotal();
  }

  function load() {
    var hint = ' Проверьте, что backend запущен и nginx не отдаёт HTML.';
    fetchApi(rowsUrl())
      .then(function (r) {
        return r.text().then(function (text) {
          var trimmed = (text || '').trim();
          if (trimmed.indexOf('<') === 0) throw new Error('Сервер вернул HTML вместо данных.' + hint);
          if (!trimmed) throw new Error('Пустой ответ от сервера.' + hint);
          if (!r.ok) {
            try {
              var parsed = JSON.parse(trimmed);
              throw new Error(parsed.detail || r.statusText);
            } catch (e) {
              if (e.message && e.message !== r.statusText) throw e;
            }
            throw new Error(r.statusText || ('Ошибка ' + r.status));
          }
          try {
            return JSON.parse(trimmed);
          } catch (_) {
            throw new Error('Ответ не JSON.' + hint);
          }
        });
      })
      .then(function (data) {
        rows = data && data.rows ? data.rows : [];
        hasNextPage = rows.length > pageSize;
        if (hasNextPage) rows = rows.slice(0, pageSize);
        render();
        renderPager();
      })
      .catch(function (e) {
        document.getElementById('plateCashBody').innerHTML =
          '<tr><td colspan="4" class="plate-cash-msg err">Ошибка загрузки: ' + (e.message || '') + '</td></tr>';
        hasNextPage = false;
        renderPager();
      });
  }

  var dateFilter = document.getElementById('plateCashDateFilter');
  if (dateFilter) {
    dateFilter.value = activeDate;
    dateFilter.addEventListener('change', function () {
      activeDate = this.value || '';
      page = 0;
      load();
    });
  }
  var todayBtn = document.getElementById('btnPlateCashToday');
  if (todayBtn) todayBtn.addEventListener('click', function () {
    activeDate = todayKey();
    page = 0;
    if (dateFilter) dateFilter.value = activeDate;
    load();
  });
  var allBtn = document.getElementById('btnPlateCashAll');
  if (allBtn) allBtn.addEventListener('click', function () {
    activeDate = '';
    page = 0;
    if (dateFilter) dateFilter.value = '';
    load();
  });
  var pageSizeSelect = document.getElementById('plateCashPageSize');
  if (pageSizeSelect) {
    pageSize = parseInt(pageSizeSelect.value, 10) || pageSize;
    pageSizeSelect.addEventListener('change', function () {
      pageSize = parseInt(this.value, 10) || 30;
      page = 0;
      load();
    });
  }
  var prevBtn = document.getElementById('plateCashPagePrev');
  if (prevBtn) prevBtn.addEventListener('click', function () {
    if (page <= 0) return;
    page -= 1;
    load();
  });
  var nextBtn = document.getElementById('plateCashPageNext');
  if (nextBtn) nextBtn.addEventListener('click', function () {
    if (!hasNextPage) return;
    page += 1;
    load();
  });

  document.getElementById('btnAddRow').addEventListener('click', function () {
    fetchApi(api + '/cash/plate-rows', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_name: '', quantity: 0, amount: 0 })
    })
      .then(function (r) {
        if (!r.ok) {
          return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
        }
        return r.json();
      })
      .then(function (newRow) {
        rows.unshift(newRow);
        if (rows.length > pageSize) rows = rows.slice(0, pageSize);
        render();
        renderPager();
        msg('Строка добавлена.');
        setTimeout(function () { msg(''); }, 3000);
      })
      .catch(function (e) {
        msg('Ошибка: ' + (e.message || 'добавить'), true);
      });
  });

  load();
})();
