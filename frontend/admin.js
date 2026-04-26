(function () {
  if (!window.requireAuth()) return;

  var apiBase = window.API_BASE_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : '');
  var fetchApi = window.fetchWithAuth || fetch;
  var ordersEl = document.getElementById('ordersContent');
  var employeesEl = document.getElementById('employeesContent');
  var priceListEl = document.getElementById('priceListContent');
  var priceListMessage = document.getElementById('priceListMessage');
  var stateDutyCommissionInput = document.getElementById('stateDutyCommission');
  var stateDuty2025Input = document.getElementById('stateDuty2025CashAmount');
  var stateDutySettingsMessage = document.getElementById('stateDutySettingsMessage');
  var orderStatusFilter = document.getElementById('orderStatusFilter');
  var ordersPage = 0;
  var ordersPageSize = 30;
  var ordersHasNext = false;

  function showErr(el, msg) {
    el.innerHTML = '<span class="error">' + (msg || 'Ошибка загрузки') + '</span>';
  }

  function getOrdersUrl() {
    var status = orderStatusFilter && orderStatusFilter.value ? orderStatusFilter.value : '';
    return apiBase + '/orders?limit=' + encodeURIComponent(ordersPageSize + 1) +
      '&offset=' + encodeURIComponent(ordersPage * ordersPageSize) +
      (status ? '&status=' + encodeURIComponent(status) : '');
  }

  function renderOrdersPager(visibleCount) {
    var info = document.getElementById('ordersPageInfo');
    var prev = document.getElementById('ordersPagePrev');
    var next = document.getElementById('ordersPageNext');
    if (info) {
      var start = visibleCount ? ordersPage * ordersPageSize + 1 : 0;
      var end = ordersPage * ordersPageSize + visibleCount;
      info.textContent = start + '–' + end;
    }
    if (prev) prev.disabled = ordersPage <= 0;
    if (next) next.disabled = !ordersHasNext;
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function statusLabel(status) {
    return {
      CREATED: 'Создан',
      PENDING_PAYMENT: 'Ожидает оплаты',
      PAID: 'Оплачен',
      PLATE_IN_PROGRESS: 'Номера в работе',
      PLATE_READY: 'Номера готовы',
      COMPLETED: 'Завершён',
      PROBLEM: 'Проблема'
    }[status] || status || '—';
  }

  function roleLabel(role) {
    return {
      ROLE_OPERATOR: 'Оператор документов',
      ROLE_PLATE_OPERATOR: 'Оператор номеров',
      ROLE_MANAGER: 'Управляющий',
      ROLE_ADMIN: 'Директор'
    }[role] || role || '—';
  }

  function badgeForStatus(status) {
    var cls = status === 'PROBLEM' ? 'badge--problem' : status === 'COMPLETED' ? 'badge--ready' : status === 'PAID' ? 'badge--paid' : 'badge--progress';
    return '<span class="badge ' + cls + '">' + escapeHtml(statusLabel(status)) + '</span>';
  }

  function shortOrderId(order) {
    var id = order.public_id || String(order.id || '');
    return id.length > 14 ? id.slice(0, 8) + '...' : id;
  }

  function copyToClipboard(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { alert('Номер заказа скопирован'); });
      return;
    }
    var ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    alert('Номер заказа скопирован');
  }

  function openOrderDetail(orderId) {
    var modal = document.getElementById('orderDetailModal');
    var titleEl = document.getElementById('orderDetailTitle');
    var bodyEl = document.getElementById('orderDetailBody');
    bodyEl.innerHTML = '<p class="loading">Загрузка…</p>';
    modal.classList.add('show');
    fetchApi(apiBase + '/orders/' + orderId + '/detail')
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (data) {
        titleEl.textContent = 'Заказ ' + (data.public_id || data.id);
        var html = '<p><strong>Статус:</strong> ' + badgeForStatus(data.status) + ' <strong>Сумма:</strong> ' + Number(data.total_amount) + ' ₽</p>';
        if (data.created_by_name) html += '<p><strong>Оформил:</strong> ' + data.created_by_name + '</p>';
        html += '<p><strong>Создан:</strong> ' + (data.created_at ? new Date(data.created_at).toLocaleString('ru') : '') + '</p>';
        if (data.form_data && Object.keys(data.form_data).length) {
          html += '<h4 style="margin:1rem 0 0.5rem;">Данные заказа</h4><dl class="detail-grid">';
          var labels = {
            client_fio: 'Клиент (ФИО)',
            client_passport: 'Паспорт',
            client_address: 'Адрес',
            client_phone: 'Телефон',
            client_is_legal: 'Клиент — юр. лицо',
            client_legal_name: 'Название (юр. лицо)',
            client_inn: 'ИНН',
            client_ogrn: 'ОГРН',
            seller_fio: 'Продавец (ФИО)',
            seller_passport: 'Паспорт продавца',
            seller_address: 'Адрес продавца',
            trustee_fio: 'Доверенное лицо (ФИО)',
            trustee_passport: 'Паспорт доверенного',
            trustee_basis: 'По доверенности от',
            vin: 'VIN',
            brand_model: 'Марка/модель',
            year: 'Год',
            color: 'Цвет',
            power: 'Мощность',
            mass: 'Масса',
            dkp_date: 'Дата договора ДКП',
            dkp_number: 'Номер договора ДКП',
            dkp_summary: 'ДКП (вручную)',
            summa_dkp: 'Сумма ДКП',
            plate_quantity: 'Кол-во номеров',
            service_type: 'Услуга',
            documents: 'Документы'
          };
          for (var key in data.form_data) {
            var value = data.form_data[key];
            if (value == null || value === '') continue;
            if (key === 'documents' && Array.isArray(value)) {
              var docStr = value.map(function (x) {
                return (x.label || x.template) + (x.price != null ? ' — ' + Number(x.price) + ' ₽' : '');
              }).join(', ');
              if (docStr) html += '<dt>Документы</dt><dd>' + escapeHtml(docStr) + '</dd>';
            } else {
              html += '<dt>' + escapeHtml(labels[key] || key) + '</dt><dd>' + escapeHtml(String(value)) + '</dd>';
            }
          }
          html += '</dl>';
        }
        bodyEl.innerHTML = html;
      })
      .catch(function (e) {
        bodyEl.innerHTML = '<p class="error">' + (e.message || 'Ошибка загрузки') + '</p>';
      });
  }

  function loadOrders() {
    fetchApi(getOrdersUrl())
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (list) {
        ordersHasNext = list.length > ordersPageSize;
        if (ordersHasNext) list = list.slice(0, ordersPageSize);
        if (!list.length) {
          ordersEl.innerHTML = '<p class="text-muted">Заказов пока нет.</p>';
          renderOrdersPager(0);
          return;
        }
        var rows = list.map(function (order) {
          var id = order.public_id || '';
          return '<tr><td class="order-id-copy admin-order-id" data-id="' + escapeHtml(id) + '" title="Копировать полный номер"><strong>' + escapeHtml(shortOrderId(order)) + '</strong><span>' + escapeHtml(id) + '</span></td><td>' + badgeForStatus(order.status) + '</td><td>' + Number(order.total_amount) + ' ₽</td><td>' + (order.need_plate ? '<span class="badge badge--ready">Да</span>' : '—') + '</td><td>' + escapeHtml(order.service_type || '—') + '</td><td>' + (order.created_at ? new Date(order.created_at).toLocaleString('ru') : '') + '</td><td><button type="button" class="btn btn-sm btn-detail" data-order-id="' + order.id + '">Детали</button></td></tr>';
        });
        ordersEl.innerHTML = '<table><thead><tr><th>Номер</th><th>Статус</th><th>Сумма</th><th>Номер</th><th>Услуга</th><th>Создан</th><th></th></tr></thead><tbody>' + rows.join('') + '</tbody></table>';
        ordersEl.querySelectorAll('.order-id-copy').forEach(function (el) {
          el.addEventListener('click', function () { copyToClipboard(el.getAttribute('data-id')); });
        });
        ordersEl.querySelectorAll('.btn-detail').forEach(function (btn) {
          btn.addEventListener('click', function () { openOrderDetail(Number(btn.getAttribute('data-order-id'))); });
        });
        renderOrdersPager(list.length);
      })
      .catch(function (e) {
        ordersHasNext = false;
        renderOrdersPager(0);
        showErr(ordersEl, e.message);
      });
  }

  function loadEmployees() {
    fetchApi(apiBase + '/employees')
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (list) {
        if (!list.length) {
          employeesEl.innerHTML = '<p class="text-muted">Сотрудников нет.</p>';
          return;
        }
        var rows = list.map(function (employee) {
          return '<tr><td>' + employee.id + '</td><td>' + escapeHtml(employee.name || '') + '</td><td><span class="badge badge--neutral">' + escapeHtml(roleLabel(employee.role)) + '</span></td><td>' + escapeHtml(employee.login || '—') + '</td><td>' + (employee.is_active ? '<span class="badge badge--ready">Активен</span>' : '<span class="badge badge--problem">Отключён</span>') + '</td></tr>';
        });
        employeesEl.innerHTML = '<table><thead><tr><th>ID</th><th>Имя</th><th>Роль</th><th>Логин</th><th>Активен</th></tr></thead><tbody>' + rows.join('') + '</tbody></table>';
      })
      .catch(function (e) {
        showErr(employeesEl, e.message);
      });
  }

  function priceListRowHtml(item) {
    var template = (item.template || '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
    var label = (item.label || '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
    var price = item.price != null ? Number(item.price) : 0;
    return '<tr><td><input type="text" value="' + template + '" data-field="template" placeholder="file.docx"></td><td><input type="text" value="' + label + '" data-field="label" placeholder="Название"></td><td><input type="number" min="0" step="1" value="' + price + '" data-field="price" placeholder="0"></td><td><button type="button" class="btn btn-sm price-list-remove">Удалить</button></td></tr>';
  }

  function bindPriceListEvents() {
    if (!priceListEl) return;
    priceListEl.querySelectorAll('.price-list-remove').forEach(function (btn) {
      btn.onclick = function () {
        var tr = btn.closest('tr');
        if (tr) tr.remove();
      };
    });
  }

  function renderPriceListTable(list) {
    if (!priceListEl) return;
    var rows = Array.isArray(list) ? list.map(priceListRowHtml).join('') : '';
    priceListEl.innerHTML = '<table class="price-list-table"><thead><tr><th>Шаблон</th><th>Название</th><th>Цена, ₽</th><th></th></tr></thead><tbody>' + rows + '</tbody></table>';
    bindPriceListEvents();
  }

  function addPriceRow() {
    if (!priceListEl) return;
    var tbody = priceListEl.querySelector('tbody');
    if (!tbody) {
      renderPriceListTable([]);
      tbody = priceListEl.querySelector('tbody');
    }
    var tr = document.createElement('tr');
    tr.innerHTML = '<td><input type="text" data-field="template" placeholder="file.docx"></td><td><input type="text" data-field="label" placeholder="Название"></td><td><input type="number" min="0" step="1" value="0" data-field="price"></td><td><button type="button" class="btn btn-sm price-list-remove">Удалить</button></td>';
    tbody.appendChild(tr);
    bindPriceListEvents();
  }

  function loadPriceList() {
    if (!priceListEl) return;
    fetchApi(apiBase + '/price-list')
      .then(function (r) { return r.text().then(function (text) { return { ok: r.ok, text: text, statusText: r.statusText }; }); })
      .then(function (result) {
        var text = result.text || '';
        if (text.trim().charAt(0) === '<') {
          priceListEl.innerHTML = '<p class="error">Сервер вернул HTML вместо JSON.</p><table class="price-list-table"><thead><tr><th>Шаблон</th><th>Название</th><th>Цена, ₽</th><th></th></tr></thead><tbody></tbody></table>';
          bindPriceListEvents();
          return;
        }
        if (!result.ok) throw new Error(result.statusText);
        var list = JSON.parse(text || '[]');
        renderPriceListTable(Array.isArray(list) ? list : []);
      })
      .catch(function (e) {
        priceListEl.innerHTML = '<p class="error">' + (e.message || 'Ошибка загрузки') + '</p><table class="price-list-table"><thead><tr><th>Шаблон</th><th>Название</th><th>Цена, ₽</th><th></th></tr></thead><tbody></tbody></table>';
        bindPriceListEvents();
      });
  }

  function savePriceList() {
    var rows = priceListEl && priceListEl.querySelectorAll('tbody tr');
    if (!rows || !rows.length) {
      alert('Добавьте хотя бы одну позицию.');
      return;
    }
    var items = [];
    for (var i = 0; i < rows.length; i += 1) {
      var row = rows[i];
      var template = row.querySelector('input[data-field="template"]');
      var label = row.querySelector('input[data-field="label"]');
      var price = row.querySelector('input[data-field="price"]');
      if (!template || !label || !price) continue;
      var templateValue = template.value.trim();
      if (!templateValue) continue;
      items.push({
        template: templateValue,
        label: label.value.trim(),
        price: Math.max(0, parseFloat(price.value) || 0),
        sort_order: items.length
      });
    }
    if (!items.length) {
      alert('Заполните шаблон у каждой позиции.');
      return;
    }
    if (priceListMessage) priceListMessage.textContent = 'Сохранение…';
    fetchApi(apiBase + '/price-list', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(items)
    })
      .then(function (r) { return r.text().then(function (text) { return { ok: r.ok, text: text, statusText: r.statusText, status: r.status }; }); })
      .then(function (result) {
        if (!result.ok) {
          var err = {};
          if (result.text.trim().charAt(0) === '{') {
            try { err = JSON.parse(result.text); } catch (_) {}
          }
          if (result.status === 403) throw new Error('Только для администратора');
          throw new Error(err.detail || result.statusText);
        }
        if (priceListMessage) priceListMessage.textContent = 'Сохранено.';
        setTimeout(function () {
          if (priceListMessage) priceListMessage.textContent = '';
        }, 3000);
        loadPriceList();
      })
      .catch(function (e) {
        if (priceListMessage) priceListMessage.textContent = '';
        alert('Ошибка: ' + (e.message || 'Не удалось сохранить'));
      });
  }

  function loadStateDutySettings() {
    if (!stateDutyCommissionInput || !stateDuty2025Input) return;
    fetchApi(apiBase + '/settings/state-duty')
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (settings) {
        stateDutyCommissionInput.value = Number(settings.commission || 0);
        stateDuty2025Input.value = Number(settings.special_2025_cash_amount || 2200);
      })
      .catch(function (e) {
        if (stateDutySettingsMessage) stateDutySettingsMessage.textContent = e.message || 'Ошибка загрузки';
      });
  }

  function saveStateDutySettings() {
    if (!stateDutyCommissionInput || !stateDuty2025Input) return;
    var payload = {
      commission: Math.max(0, parseFloat(stateDutyCommissionInput.value) || 0),
      special_2025_cash_amount: Math.max(2025, parseFloat(stateDuty2025Input.value) || 2025)
    };
    if (stateDutySettingsMessage) stateDutySettingsMessage.textContent = 'Сохранение…';
    fetchApi(apiBase + '/settings/state-duty', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (r) {
        return r.json().then(function (json) {
          if (!r.ok) throw new Error(json.detail || r.statusText);
          return json;
        });
      })
      .then(function (settings) {
        stateDutyCommissionInput.value = Number(settings.commission || 0);
        stateDuty2025Input.value = Number(settings.special_2025_cash_amount || 2200);
        if (stateDutySettingsMessage) stateDutySettingsMessage.textContent = 'Сохранено.';
        setTimeout(function () {
          if (stateDutySettingsMessage) stateDutySettingsMessage.textContent = '';
        }, 3000);
      })
      .catch(function (e) {
        if (stateDutySettingsMessage) stateDutySettingsMessage.textContent = '';
        alert('Ошибка: ' + (e.message || 'Не удалось сохранить комиссию'));
      });
  }

  function refresh() {
    ordersEl.textContent = 'Загрузка…';
    employeesEl.textContent = 'Загрузка…';
    if (priceListEl) priceListEl.textContent = 'Загрузка…';
    loadOrders();
    loadEmployees();
    loadStateDutySettings();
    loadPriceList();
  }

  if (orderStatusFilter) orderStatusFilter.addEventListener('change', function () {
    ordersPage = 0;
    loadOrders();
  });
  var ordersPageSizeSelect = document.getElementById('ordersPageSize');
  if (ordersPageSizeSelect) {
    ordersPageSize = parseInt(ordersPageSizeSelect.value, 10) || ordersPageSize;
    ordersPageSizeSelect.addEventListener('change', function () {
      ordersPageSize = parseInt(this.value, 10) || 30;
      ordersPage = 0;
      loadOrders();
    });
  }
  var ordersPrev = document.getElementById('ordersPagePrev');
  if (ordersPrev) ordersPrev.addEventListener('click', function () {
    if (ordersPage <= 0) return;
    ordersPage -= 1;
    loadOrders();
  });
  var ordersNext = document.getElementById('ordersPageNext');
  if (ordersNext) ordersNext.addEventListener('click', function () {
    if (!ordersHasNext) return;
    ordersPage += 1;
    loadOrders();
  });
  document.getElementById('orderDetailClose').addEventListener('click', function () {
    document.getElementById('orderDetailModal').classList.remove('show');
  });
  document.getElementById('orderDetailModal').addEventListener('click', function (e) {
    if (e.target.id === 'orderDetailModal') e.target.classList.remove('show');
  });
  document.getElementById('btnRefresh').addEventListener('click', refresh);
  document.getElementById('btnSavePriceList').addEventListener('click', savePriceList);
  document.getElementById('btnAddPriceRow').addEventListener('click', addPriceRow);
  document.getElementById('btnSaveStateDutySettings').addEventListener('click', saveStateDutySettings);

  refresh();
})();
