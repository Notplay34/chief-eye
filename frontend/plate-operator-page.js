(function () {
  var api = window.API_BASE_URL || '';
  var fetchApi = window.fetchWithAuth || fetch;
  if (!window.getToken || !window.getToken()) return;

  var canIssue = ['PAID', 'PLATE_IN_PROGRESS', 'PLATE_READY'];
  var canDelete = ['PAID', 'PLATE_IN_PROGRESS', 'PLATE_READY'];
  var msgEl = document.getElementById('pageMsg');
  var ordersState = [];
  var searchInput = document.getElementById('plateSearch');
  var searchMeta = document.getElementById('plateSearchMeta');

  function showMessage(text, isError) {
    if (!msgEl) return;
    msgEl.textContent = text || '';
    msgEl.style.display = text ? 'block' : 'none';
    msgEl.className = 'plate-page__msg' + (isError ? ' plate-page__msg--error' : '');
  }

  function fmt(value) {
    return new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0 }).format(value) + ' ₽';
  }

  function formatDate(value) {
    if (!value) return '—';
    var parsed = new Date(value);
    if (isNaN(parsed.getTime())) return '—';
    return parsed.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function normalizeSearch(value) {
    return String(value || '').toLowerCase().replace(/\s+/g, ' ').trim();
  }

  function orderSearchText(order) {
    return normalizeSearch([
      order.client,
      order.brand_model,
      order.comment,
      formatDate(order.created_at),
      order.plate_amount,
      order.total_amount,
      order.public_id
    ].filter(Boolean).join(' '));
  }

  function filteredOrders() {
    var query = normalizeSearch(searchInput && searchInput.value);
    if (!query) return ordersState;
    return ordersState.filter(function (order) {
      return orderSearchText(order).indexOf(query) >= 0;
    });
  }

  function saveComment(input) {
    var id = parseInt(input.getAttribute('data-order-comment'), 10);
    if (!id) return Promise.resolve();
    var value = input.value || '';
    if (input.dataset.lastSaved === value) return Promise.resolve();
    input.classList.add('plate-comment-input--saving');
    return fetchApi(api + '/orders/' + id + '/plate-comment', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comment: value })
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || 'Ошибка сохранения комментария'); });
        return r.json();
      })
      .then(function (data) {
        input.dataset.lastSaved = data.comment || '';
        input.value = data.comment || '';
        input.classList.remove('plate-comment-input--error');
      })
      .catch(function (e) {
        input.classList.add('plate-comment-input--error');
        showMessage(e.message || 'Ошибка сохранения комментария', true);
      })
      .finally(function () {
        input.classList.remove('plate-comment-input--saving');
      });
  }

  function renderOrders() {
    var tbody = document.getElementById('orderBody');
    var table = document.getElementById('orderTable');
    var empty = document.getElementById('emptyMsg');
    var orders = filteredOrders();
    var hasQuery = !!normalizeSearch(searchInput && searchInput.value);
    tbody.innerHTML = '';

    if (searchMeta) {
      searchMeta.textContent = hasQuery
        ? (orders.length + ' из ' + ordersState.length)
        : (ordersState.length ? (ordersState.length + ' записей') : '');
    }

    if (!orders.length) {
      empty.textContent = hasQuery ? 'Поиск ничего не нашел.' : 'Нет заказов с номерами.';
      empty.style.display = 'block';
      table.style.display = 'none';
      return;
    }

    empty.style.display = 'none';
    table.style.display = 'table';
    orders.forEach(function (order) {
      var row = document.createElement('tr');
      var clientEscaped = escapeHtml(order.client || '');
      var clientLabel = order.client ? escapeHtml(order.client) : '—';
      var brandModelLabel = order.brand_model ? escapeHtml(order.brand_model) : '—';
      var statusValue = escapeHtml(order.status || '');
      var publicId = escapeHtml(order.public_id || order.id);
      var docTemplate = escapeHtml(order.plate_document || 'number.docx');
      var plateAmount = order.plate_amount != null ? order.plate_amount : order.total_amount;
      var createdLabel = escapeHtml(formatDate(order.created_at));
      var commentValue = escapeHtml(order.comment || '');
      var issueBtn = canIssue.indexOf(order.status) >= 0
        ? '<button type="button" class="plate-action-btn plate-action-btn--done" title="Выдано клиенту" aria-label="Выдано клиенту" data-order="' + order.id + '" data-status="COMPLETED" data-client="' + clientEscaped + '" data-amount="' + (plateAmount || 0) + '">✓</button>'
        : '';
      var deleteBtn = canDelete.indexOf(order.status) >= 0
        ? '<button type="button" class="plate-action-btn plate-action-btn--remove" title="Удалить из списка" aria-label="Удалить из списка" data-order="' + order.id + '" data-status="PROBLEM" data-delete="1">−</button>'
        : '';
      var payBtn = (order.debt || 0) > 0
        ? '<button type="button" class="plate-action-btn plate-action-btn--pay" title="Доплата" aria-label="Доплата" data-order="' + order.id + '" data-public-id="' + publicId + '" data-pay="1">₽</button>'
        : '';
      var docLink = '<a href="#" class="doc-link" title="Заявление на номера" data-order-id="' + order.id + '" data-doc="' + docTemplate + '" aria-label="Заявление на номера">&#128196;</a>';
      row.innerHTML =
        '<td data-label="Клиент">' + clientLabel + '</td>' +
        '<td data-label="Марка, модель">' + brandModelLabel + '</td>' +
        '<td data-label="Сумма">' + fmt(order.plate_amount != null ? order.plate_amount : order.total_amount) + '</td>' +
        '<td data-label="Заявление">' + docLink + '</td>' +
        '<td data-label="Дата заявки"><span class="plate-date-pill status-' + statusValue + '">' + createdLabel + '</span></td>' +
        '<td data-label="Комментарий"><input type="text" class="plate-comment-input" data-order-comment="' + order.id + '" value="' + commentValue + '" data-last-saved="' + commentValue + '" placeholder="Комментарий / дата"></td>' +
        '<td data-label="Действия" class="plate-table__actions"><div class="btn-group btn-group--row-actions">' + issueBtn + deleteBtn + payBtn + '</div></td>';
      tbody.appendChild(row);
    });
    bindActions();
  }

  function loadOrders() {
    fetchApi(api + '/orders/plate-list?limit=500')
      .then(function (r) {
        if (r.status === 401) return [];
        if (!r.ok) throw new Error('Ошибка загрузки');
        return r.json();
      })
      .then(function (orders) {
        ordersState = Array.isArray(orders) ? orders : [];
        renderOrders();
      })
      .catch(function (e) {
        var empty = document.getElementById('emptyMsg');
        empty.textContent = 'Ошибка: ' + (e.message || 'загрузка');
        empty.style.display = 'block';
      });
  }

  function bindActions() {
    document.querySelectorAll('[data-order-comment]').forEach(function (input) {
      input.addEventListener('blur', function () { saveComment(input); });
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          saveComment(input).then(function () { input.blur(); });
        }
      });
    });

    document.querySelectorAll('[data-status]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = parseInt(btn.getAttribute('data-order'), 10);
        var status = btn.getAttribute('data-status');
        var isDelete = btn.getAttribute('data-delete') === '1';
        if (isDelete && !confirm('Удалить заказ из списка? Заказ перейдёт в статус «Проблема».')) return;
        fetchApi(api + '/orders/' + id + '/status', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: status })
        })
          .then(function (r) {
            if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || 'Ошибка'); });
            loadOrders();
            if (status === 'COMPLETED') {
              showMessage('Заказ отмечен как выданный. Деньги оператору выдаются из промежуточной кассы.', false);
            }
          })
          .catch(function (e) {
            showMessage(e.message || 'Ошибка', true);
          });
      });
    });

    document.querySelectorAll('[data-pay]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = parseInt(btn.getAttribute('data-order'), 10);
        document.getElementById('modalOrderId').textContent = btn.getAttribute('data-public-id') || id;
        document.getElementById('modalAmount').value = '';
        document.getElementById('modalPay').style.display = 'flex';
        document.getElementById('modalPay').dataset.orderId = id;
      });
    });

    document.querySelectorAll('.doc-link').forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        var orderId = parseInt(link.getAttribute('data-order-id'), 10);
        var template = link.getAttribute('data-doc') || 'number.docx';
        var url = api + '/orders/' + orderId + '/documents/' + encodeURIComponent(template);
        window.fetchDocumentWithAuth(url, template)
          .catch(function (err) {
            showMessage(err.message || 'Ошибка', true);
          });
      });
    });
  }

  document.getElementById('modalSubmit').addEventListener('click', function () {
    var id = document.getElementById('modalPay').dataset.orderId;
    var amount = parseFloat(document.getElementById('modalAmount').value) || 0;
    if (amount <= 0) {
      alert('Введите сумму');
      return;
    }
    fetchApi(api + '/orders/' + id + '/pay-extra', {
      method: 'POST',
      body: JSON.stringify({ amount: amount })
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || 'Ошибка'); });
        document.getElementById('modalPay').style.display = 'none';
        loadOrders();
      })
      .catch(function (e) {
        alert(e.message || 'Ошибка');
      });
  });

  document.getElementById('modalCancel').addEventListener('click', function () {
    document.getElementById('modalPay').style.display = 'none';
  });

  if (searchInput) {
    searchInput.addEventListener('input', renderOrders);
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        this.value = '';
        renderOrders();
      }
    });
  }

  loadOrders();
})();
