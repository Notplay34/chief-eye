(function () {
  var api = window.API_BASE_URL || '';
  var fetchApi = window.fetchWithAuth || fetch;
  if (!window.getToken || !window.getToken()) return;

  var statusLabels = {
    PAID: 'Оплачен',
    PLATE_IN_PROGRESS: 'В работе',
    PLATE_READY: 'Готов',
    PROBLEM: 'Проблема',
    COMPLETED: 'Завершён'
  };
  var canIssue = ['PAID', 'PLATE_IN_PROGRESS', 'PLATE_READY'];
  var canDelete = ['PAID', 'PLATE_IN_PROGRESS', 'PLATE_READY'];
  var msgEl = document.getElementById('pageMsg');

  function showMessage(text, isError) {
    if (!msgEl) return;
    msgEl.textContent = text || '';
    msgEl.style.display = text ? 'block' : 'none';
    msgEl.className = 'plate-page__msg' + (isError ? ' plate-page__msg--error' : '');
  }

  function fmt(value) {
    return new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0 }).format(value) + ' ₽';
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function loadOrders() {
    fetchApi(api + '/orders/plate-list')
      .then(function (r) {
        if (r.status === 401) return [];
        if (!r.ok) throw new Error('Ошибка загрузки');
        return r.json();
      })
      .then(function (orders) {
        var tbody = document.getElementById('orderBody');
        var table = document.getElementById('orderTable');
        var empty = document.getElementById('emptyMsg');
        tbody.innerHTML = '';

        if (!orders || !orders.length) {
          empty.textContent = 'Нет заказов с номерами.';
          empty.style.display = 'block';
          table.style.display = 'none';
          return;
        }

        empty.style.display = 'none';
        table.style.display = 'table';
        orders.forEach(function (order, index) {
          var row = document.createElement('tr');
          var clientEscaped = escapeHtml(order.client || '');
          var clientLabel = order.client ? escapeHtml(order.client) : '—';
          var brandModelLabel = order.brand_model ? escapeHtml(order.brand_model) : '—';
          var statusValue = escapeHtml(order.status || '');
          var statusLabel = escapeHtml(statusLabels[order.status] || order.status || '');
          var publicId = escapeHtml(order.public_id || order.id);
          var docTemplate = escapeHtml(order.plate_document || 'number.docx');
          var plateAmount = order.plate_amount != null ? order.plate_amount : order.total_amount;
          var issueBtn = canIssue.indexOf(order.status) >= 0
            ? '<button type="button" class="btn btn-sm btn--primary" data-order="' + order.id + '" data-status="COMPLETED" data-client="' + clientEscaped + '" data-amount="' + (plateAmount || 0) + '">Выдано клиенту</button>'
            : '';
          var separator = (issueBtn && (canDelete.indexOf(order.status) >= 0 || (order.debt || 0) > 0))
            ? '<span class="btn-group__sep"></span>'
            : '';
          var deleteBtn = canDelete.indexOf(order.status) >= 0
            ? '<button type="button" class="btn btn-sm btn--danger-like" data-order="' + order.id + '" data-status="PROBLEM" data-delete="1">Удалить</button>'
            : '';
          var payBtn = (order.debt || 0) > 0
            ? '<button type="button" class="btn btn-sm btn--secondary" data-order="' + order.id + '" data-public-id="' + publicId + '" data-pay="1">Доплата</button>'
            : '';
          var docLink = '<a href="#" class="doc-link" title="Заявление на номера" data-order-id="' + order.id + '" data-doc="' + docTemplate + '" aria-label="Заявление на номера">&#128196;</a>';
          row.innerHTML =
            '<td data-label="№">' + (index + 1) + '</td>' +
            '<td data-label="Клиент">' + clientLabel + '</td>' +
            '<td data-label="Марка, модель">' + brandModelLabel + '</td>' +
            '<td data-label="Сумма">' + fmt(order.plate_amount != null ? order.plate_amount : order.total_amount) + '</td>' +
            '<td data-label="Заявление">' + docLink + '</td>' +
            '<td data-label="Статус"><span class="status status-' + statusValue + '">' + statusLabel + '</span></td>' +
            '<td data-label="Действия" class="plate-table__actions"><div class="btn-group btn-group--row-actions">' + issueBtn + separator + deleteBtn + payBtn + '</div></td>';
          tbody.appendChild(row);
        });
      })
      .then(bindActions)
      .catch(function (e) {
        var empty = document.getElementById('emptyMsg');
        empty.textContent = 'Ошибка: ' + (e.message || 'загрузка');
        empty.style.display = 'block';
      });
  }

  function bindActions() {
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
              showMessage('Заказ отмечен как выданный. Сумма доступна в кассе документов для выдачи в кассу номеров.', false);
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

  loadOrders();
})();
