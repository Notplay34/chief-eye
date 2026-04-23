/**
 * Касса павильона 1.
 * По образу «Кассы номеров», но с колонками:
 * ФИО, Заявление, Госпошлина, ДКП, Страховка, Номера, Итого.
 * Источник строк:
 *  - автоматически: при «Принять наличные» по заказу (backend пишет в cash_rows);
 *  - вручную: кнопка «Добавить строку» + редактирование;
 *  - поддерживаются отрицательные суммы (расходы, изъятие из кассы).
 */
(function () {
  var API = window.API_BASE_URL || '';
  var fetchApi = window.fetchWithAuth || fetch;
  if (!window.getToken || !window.getToken()) return;

  var user = window.getUser();
  if (user) {
    var u = document.getElementById('userName');
    if (u) u.textContent = user.name || '';
  }

  var rows = [];

  function msg(text, type) {
    var el = document.getElementById('cashMsg');
    if (!el) return;
    el.textContent = text || '';
    el.className = 'cash-crm__msg' + (type === 'err' ? ' err' : type === 'ok' ? ' ok' : '');
  }

  /** Парсим сумму: пробелы, запятая, минус. */
  function parseAmount(raw) {
    if (raw === null || raw === undefined) return 0;
    var s = String(raw).trim();
    if (!s) return 0;
    s = s.replace(/\s/g, '').replace(',', '.');
    var n = parseFloat(s);
    return isNaN(n) ? 0 : n;
  }

  function toInputValue(n) {
    var num = Number(n);
    if (!isFinite(num)) return '';
    // Для 0 отображаем пустоту (чтобы не захламлять таблицу)
    if (num === 0) return '';
    return num.toFixed(2);
  }

  function totalFromRow(row) {
    if (!row) return 0;
    var t = row.total;
    if (t === null || t === undefined) return 0;
    var n = Number(t);
    return isNaN(n) ? 0 : n;
  }

  function formatNumOnly(n) {
    var num = Number(n);
    if (isNaN(num)) num = 0;
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num).replace(/\u00a0/g, ' ');
  }

  function rowTotalClass(total) {
    if (total === 0) return 'cash-crm__row-total--zero';
    if (total < 0) return 'cash-crm__row-total--negative';
    return 'cash-crm__row-total--positive';
  }

  function patchRow(id, payload) {
    return fetchApi(API + '/cash/rows/' + id, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(function (r) {
      if (!r.ok) {
        return r.json().then(function (j) {
          throw new Error(j.detail || r.statusText);
        });
      }
      return r.json();
    });
  }

  function replaceRow(id, updated) {
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].id === id) {
        rows[i] = updated;
        return;
      }
    }
  }

  function recomputeTotal(row) {
    if (!row) return 0;
    var sum =
      parseAmount(row.application) +
      parseAmount(row.state_duty) +
      parseAmount(row.dkp) +
      parseAmount(row.insurance) +
      parseAmount(row.plates);
    row.total = sum;
    return sum;
  }

  function dayKey(row) {
    var s = row.created_at;
    if (!s) return '';
    var d = new Date(s);
    if (isNaN(d.getTime())) return '';
    var y = d.getFullYear();
    var m = d.getMonth() + 1;
    var day = d.getDate();
    return y + '-' + (m < 10 ? '0' : '') + m + '-' + (day < 10 ? '0' : '') + day;
  }

  function dayLabel(key) {
    if (!key) return '';
    var parts = key.split('-');
    if (parts.length !== 3) return key;
    return parts[2] + '.' + parts[1] + '.' + parts[0];
  }

  /** Поле Итого: редактируемое, допускает минус. */
  function buildTotalCell(row) {
    var id = row.id;
    var total = totalFromRow(row);
    var wrap = document.createElement('span');
    wrap.className = 'cash-crm__row-total ' + rowTotalClass(total);

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'cash-crm__input cash-crm__input--num cash-crm__input--total';
    input.dataset.rowId = String(id);
    input.value = total === 0 ? '' : toInputValue(total);
    input.setAttribute('inputmode', 'decimal');

    input.addEventListener('blur', function () {
      var raw = this.value;
      var v = parseAmount(raw);
      var row = rows.find(function (r) { return r.id === id; });
      if (!row) return;

      // Обновляем локально и отправляем только total
      row.total = v;
      this.value = raw.trim() === '' ? '' : toInputValue(v);

      patchRow(id, { total: v })
        .then(function (updated) {
          replaceRow(id, updated);
          var t = totalFromRow(updated);
          input.value = t === 0 ? '' : toInputValue(t);
          wrap.className = 'cash-crm__row-total ' + rowTotalClass(t);
          renderTotal();
          msg('Сохранено', 'ok');
        })
        .catch(function (e) {
          msg('Ошибка: ' + (e.message || 'не удалось сохранить'), 'err');
        });
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') this.blur();
    });

    wrap.appendChild(input);
    var currency = document.createElement('span');
    currency.className = 'cash-crm__amount-currency';
    currency.textContent = ' ₽';
    wrap.appendChild(currency);
    return wrap;
  }

  /** Общее поле ввода: ФИО или сумма. Суммы — text + ручной парсинг, чтобы поддерживать запятую и минус. */
  function buildCellInput(row, key, isNumber) {
    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'cash-crm__input' + (isNumber ? ' cash-crm__input--num' : '');
    input.dataset.key = key;
    input.dataset.rowId = String(row.id);
    if (!isNumber && key === 'client_name') {
      input.placeholder = 'Фамилия и инициалы';
    }
    if (isNumber) {
      input.setAttribute('inputmode', 'decimal');
      input.value = toInputValue(row[key]);
    } else {
      input.value = row[key] || '';
    }

    input.addEventListener('blur', function () {
      var id = parseInt(this.dataset.rowId, 10);
      if (isNaN(id)) return;
      var field = this.dataset.key;
      var currentRow = rows.find(function (r) { return r.id === id; });
      if (!currentRow) return;

      var raw = this.value;
      var newValue = isNumber ? parseAmount(raw) : raw.trim();

      if (isNumber) {
        // Нормализуем отображение
        this.value = raw.trim() === '' ? '' : toInputValue(newValue);
      }

      var prevVal = currentRow[field];
      if (!isNumber && String(prevVal || '') === String(newValue || '')) {
        return;
      }
      if (isNumber && Number(prevVal) === newValue) {
        return;
      }

      var payload = {};
      if (isNumber) {
        currentRow[field] = newValue;
        var sum = recomputeTotal(currentRow);
        payload[field] = newValue;
        payload.total = sum;
      } else {
        payload[field] = newValue;
      }

      patchRow(id, payload)
        .then(function (updated) {
          replaceRow(id, updated);
          // Обновляем «Итого» в строке и общий итог
          var rowEl = document.querySelector('.cash-crm__grid-row[data-row-id="' + id + '"]');
          if (rowEl) {
            var totalWrap = rowEl.querySelector('.cash-crm__row-total');
            var totalInput = totalWrap && totalWrap.querySelector('.cash-crm__input--total');
            var t = totalFromRow(updated);
            if (totalWrap) totalWrap.className = 'cash-crm__row-total ' + rowTotalClass(t);
            if (totalInput) totalInput.value = t === 0 ? '' : toInputValue(t);
          }
          renderTotal();
          msg('Сохранено', 'ok');
        })
        .catch(function (e) {
          msg('Ошибка: ' + (e.message || 'не удалось сохранить'), 'err');
        });
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') this.blur();
    });

    return input;
  }

  function renderTotal() {
    var total = rows.reduce(function (sum, r) {
      return sum + totalFromRow(r);
    }, 0);
    var wrap = document.getElementById('cashTotalCell');
    if (!wrap) return;
    var numSpan = wrap.querySelector('.cash-crm__amount-num');
    if (numSpan) numSpan.textContent = formatNumOnly(total);
    wrap.classList.remove('cash-crm__total-value--negative', 'cash-crm__total-value--positive');
    if (total < 0) wrap.classList.add('cash-crm__total-value--negative');
    else if (total > 0) wrap.classList.add('cash-crm__total-value--positive');
  }

  function renderRow(row) {
    var rowEl = document.createElement('div');
    rowEl.className = 'cash-crm__grid-row';
    rowEl.dataset.rowId = String(row.id);

    var cellName = document.createElement('div');
    cellName.className = 'cash-crm__grid-cell cash-crm__grid-cell--name';
    cellName.appendChild(buildCellInput(row, 'client_name', false));
    rowEl.appendChild(cellName);

    ['application', 'state_duty', 'dkp', 'insurance', 'plates'].forEach(function (key) {
      var cell = document.createElement('div');
      cell.className = 'cash-crm__grid-cell cash-crm__grid-cell--num';
      cell.appendChild(buildCellInput(row, key, true));
      rowEl.appendChild(cell);
    });

    var cellTotal = document.createElement('div');
    cellTotal.className = 'cash-crm__grid-cell cash-crm__grid-cell--num';
    cellTotal.appendChild(buildTotalCell(row));
    rowEl.appendChild(cellTotal);

    var cellDel = document.createElement('div');
    cellDel.className = 'cash-crm__grid-cell cash-crm__grid-cell--del';
    var btnDel = document.createElement('button');
    btnDel.type = 'button';
    btnDel.className = 'cash-crm__btn-del';
    btnDel.title = 'Удалить строку';
    btnDel.innerHTML = '🗑';
    btnDel.onclick = function () {
      if (!confirm('Удалить строку из кассы?')) return;
      fetchApi(API + '/cash/rows/' + row.id, { method: 'DELETE' })
        .then(function (r) {
          if (r.status === 204 || r.ok) {
            rows = rows.filter(function (x) { return x.id !== row.id; });
            render();
            msg('Строка удалена', 'ok');
          } else {
            return r.json().then(function (j) { throw new Error(j.detail || r.statusText); });
          }
        })
        .catch(function (e) {
          msg('Ошибка: ' + (e.message || 'не удалось удалить'), 'err');
        });
    };
    cellDel.appendChild(btnDel);
    rowEl.appendChild(cellDel);

    return rowEl;
  }

  function render() {
    var bodyEl = document.getElementById('cashBody');
    if (!bodyEl) return;
    bodyEl.innerHTML = '';

    if (!rows.length) {
      var placeholderRow = document.createElement('div');
      placeholderRow.className = 'cash-crm__grid-row cash-crm__grid-row--placeholder';
      placeholderRow.innerHTML =
        '<div class="cash-crm__grid-cell cash-crm__placeholder">Нет строк. ' +
        'Строки добавляются автоматически при оплате заказов павильона 1 или вручную кнопкой «Добавить строку». ' +
        'Суммы могут быть отрицательными — расходы из кассы.</div>';
      bodyEl.appendChild(placeholderRow);
      renderTotal();
      return;
    }

    var lastDay = null;
    rows.forEach(function (row) {
      var d = dayKey(row);
      if (d && d !== lastDay) {
        lastDay = d;
        var sep = document.createElement('div');
        sep.className = 'cash-crm__grid-row-day';
        var sepCell = document.createElement('div');
        sepCell.className = 'cash-crm__grid-cell';
        sepCell.textContent = dayLabel(d);
        sep.appendChild(sepCell);
        bodyEl.appendChild(sep);
      }
      bodyEl.appendChild(renderRow(row));
    });

    renderTotal();
  }

  function loadRows() {
    var hint = ' Проверьте, что бэкенд запущен (systemctl restart eye_w).';
    fetchApi(API + '/cash/rows')
      .then(function (r) {
        return r.text().then(function (text) {
          var t = (text || '').trim();
          if (t.indexOf('<') === 0) {
            throw new Error('Сервер вернул HTML вместо данных.' + hint);
          }
          if (!t) {
            throw new Error('Пустой ответ от сервера.' + hint);
          }
          if (!r.ok) {
            try {
              var j = JSON.parse(t);
              throw new Error(j.detail || r.statusText);
            } catch (e) {
              if (e.message && e.message !== r.statusText) throw e;
            }
            throw new Error(r.statusText || 'Ошибка ' + r.status);
          }
          try {
            return JSON.parse(t);
          } catch (_) {
            throw new Error('Ответ не JSON (возможно, nginx отдаёт страницу).' + hint);
          }
        });
      })
      .then(function (data) {
        rows = Array.isArray(data) ? data : [];
        render();
      })
      .catch(function (e) {
        var bodyEl = document.getElementById('cashBody');
        if (bodyEl) {
          bodyEl.innerHTML =
            '<div class="cash-crm__grid-row cash-crm__grid-row--placeholder"><div class="cash-crm__grid-cell cash-crm__placeholder">Ошибка загрузки: ' +
            (e.message || '') +
            '</div></div>';
        }
        msg('Ошибка загрузки', 'err');
      });
  }

  function addRow() {
    fetchApi(API + '/cash/rows', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_name: '',
        application: 0,
        state_duty: 0,
        dkp: 0,
        insurance: 0,
        plates: 0,
        total: 0,
      }),
    })
      .then(function (r) {
        if (!r.ok) {
          return r.json().then(function (j) {
            throw new Error(j.detail || r.statusText);
          });
        }
        return r.json();
      })
      .then(function (newRow) {
        rows.unshift(newRow);
        render();
        msg('Строка добавлена. Можно ввести отрицательные суммы — расходы из кассы.', 'ok');
      })
      .catch(function (e) {
        msg('Ошибка: ' + (e.message || 'не удалось добавить'), 'err');
      });
  }

  function init() {
    loadRows();
    var btn = document.getElementById('btnAddRow');
    if (btn) btn.onclick = addRow;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

