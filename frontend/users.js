(function () {
  if (!window.requireAuth()) return;

  var user = window.getUser();
  if (!user) return;

  var listEl = document.getElementById('listContent');
  if (user.role !== 'ROLE_ADMIN') {
    listEl.innerHTML = '<p class="error">Доступ только у директора.</p>';
    return;
  }

  var api = window.API_BASE_URL || '';
  var fetchApi = window.fetchWithAuth || fetch;
  var modal = document.getElementById('modalForm');
  var form = document.getElementById('formEdit');
  var editingId = null;

  function formatDetail(detail) {
    if (!detail) return '';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map(function (item) {
        if (!item) return '';
        if (typeof item === 'string') return item;
        var path = Array.isArray(item.loc) ? item.loc.filter(function (part) { return part !== 'body'; }).join('.') : '';
        var msg = item.msg || item.detail || '';
        return path ? (path + ': ' + msg) : msg;
      }).filter(Boolean).join('\n');
    }
    if (typeof detail === 'object') {
      return detail.detail || detail.message || JSON.stringify(detail);
    }
    return String(detail);
  }

  function extractError(response) {
    return response.json()
      .then(function (payload) {
        throw new Error(formatDetail(payload && payload.detail) || response.statusText || 'Ошибка запроса');
      })
      .catch(function (err) {
        if (err instanceof Error && err.message) throw err;
        throw new Error(response.statusText || 'Ошибка запроса');
      });
  }

  function roleLabel(role) {
    return {
      ROLE_OPERATOR: 'Оператор документов',
      ROLE_PLATE_OPERATOR: 'Оператор номеров',
      ROLE_MANAGER: 'Управляющий',
      ROLE_ADMIN: 'Директор'
    }[role] || role;
  }

  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    alert('Логин скопирован');
  }

  function copyLogin(login) {
    if (!login) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(login)
        .then(function () { alert('Логин скопирован'); })
        .catch(function () { fallbackCopy(login); });
      return;
    }
    fallbackCopy(login);
  }

  function loadList() {
    listEl.textContent = 'Загрузка…';
    fetchApi(api + '/employees?all=1')
      .then(function (r) {
        if (!r.ok) return extractError(r);
        return r.json();
      })
      .then(function (list) {
        if (!list.length) {
          listEl.innerHTML = '<p class="text-muted">Нет сотрудников.</p>';
          return;
        }
        var myId = user ? user.id : null;
        var rows = list.map(function (employee) {
          var trClass = employee.is_active ? '' : ' class="inactive"';
          var loginCell = employee.login
            ? '<span class="copy-link" data-login="' + employee.login.replace(/"/g, '&quot;') + '" title="Копировать логин">' + employee.login + '</span>'
            : '—';
          var actions = '<div class="table-actions">';
          actions += '<button type="button" class="btn btn-sm btn-edit" data-id="' + employee.id + '">Изменить</button>';
          if (employee.is_active && employee.id !== myId) {
            actions += '<button type="button" class="btn btn-sm btn-danger btn-deactivate" data-id="' + employee.id + '" data-name="' + (employee.name || '').replace(/"/g, '&quot;') + '">Деактивировать</button>';
          }
          if (!employee.is_active) {
            actions += '<button type="button" class="btn btn-sm btn-restore" data-id="' + employee.id + '">Восстановить</button>';
          }
          actions += '</div>';
          return '<tr' + trClass + '><td>' + employee.id + '</td><td>' + (employee.name || '') + '</td><td>' + loginCell + '</td><td>' + roleLabel(employee.role) + '</td><td>' + (employee.is_active ? 'Да' : 'Нет') + '</td><td>' + actions + '</td></tr>';
        }).join('');
        listEl.innerHTML = '<table class="users-table"><thead><tr><th>ID</th><th>Имя</th><th>Логин</th><th>Роль</th><th>Активен</th><th>Действия</th></tr></thead><tbody>' + rows + '</tbody></table>';

        listEl.querySelectorAll('.btn-edit').forEach(function (btn) {
          btn.addEventListener('click', function () { openEdit(Number(btn.getAttribute('data-id'))); });
        });
        listEl.querySelectorAll('.btn-deactivate').forEach(function (btn) {
          btn.addEventListener('click', function () {
            var id = Number(btn.getAttribute('data-id'));
            var name = btn.getAttribute('data-name') || '';
            if (confirm('Деактивировать «' + name + '»?')) deactivate(id);
          });
        });
        listEl.querySelectorAll('.btn-restore').forEach(function (btn) {
          btn.addEventListener('click', function () { restore(Number(btn.getAttribute('data-id'))); });
        });
        listEl.querySelectorAll('.copy-link').forEach(function (el) {
          el.addEventListener('click', function () { copyLogin(el.getAttribute('data-login')); });
        });
      })
      .catch(function (err) {
        listEl.innerHTML = '<p class="error">' + (err.message || 'Ошибка загрузки') + '</p>';
      });
  }

  function openAdd() {
    editingId = null;
    document.getElementById('modalTitle').textContent = 'Добавить сотрудника';
    document.getElementById('formId').value = '';
    document.getElementById('formName').value = '';
    document.getElementById('formLogin').value = '';
    document.getElementById('formLogin').disabled = false;
    document.getElementById('formPassword').value = '';
    document.getElementById('formPasswordHint').textContent = '';
    document.getElementById('formActiveLabel').style.display = 'none';
    modal.classList.add('show');
  }

  function openEdit(id) {
    fetchApi(api + '/employees?all=1')
      .then(function (r) {
        if (!r.ok) return extractError(r);
        return r.json();
      })
      .then(function (list) {
        var employee = list.find(function (item) { return item.id === id; });
        if (!employee) return;
        editingId = id;
        document.getElementById('modalTitle').textContent = 'Изменить сотрудника';
        document.getElementById('formId').value = id;
        document.getElementById('formName').value = employee.name || '';
        document.getElementById('formLogin').value = employee.login || '';
        document.getElementById('formLogin').disabled = true;
        document.getElementById('formPassword').value = '';
        document.getElementById('formPasswordHint').textContent = '(оставьте пустым, чтобы не менять)';
        document.getElementById('formRole').value = employee.role || 'ROLE_OPERATOR';
        document.getElementById('formActive').checked = employee.is_active !== false;
        document.getElementById('formActiveLabel').style.display = 'block';
        modal.classList.add('show');
      });
  }

  function closeModal() {
    modal.classList.remove('show');
  }

  function deactivate(id) {
    fetchApi(api + '/employees/' + id, { method: 'DELETE' })
      .then(function (r) {
        if (!r.ok) return extractError(r);
        loadList();
      })
      .catch(function (err) {
        alert(err.message);
      });
  }

  function restore(id) {
    fetchApi(api + '/employees/' + id, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: true })
    })
      .then(function (r) {
        if (!r.ok) return extractError(r);
        loadList();
      })
      .catch(function (err) {
        alert(err.message);
      });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var payload = {
      name: document.getElementById('formName').value.trim(),
      role: document.getElementById('formRole').value
    };
    if (!editingId) {
      payload.login = document.getElementById('formLogin').value.trim() || null;
      payload.password = document.getElementById('formPassword').value || null;
      if (!payload.login || !payload.password) {
        alert('Для нового сотрудника укажите логин и пароль.');
        return;
      }
    } else {
      payload.login = document.getElementById('formLogin').value.trim() || null;
      payload.is_active = document.getElementById('formActive').checked;
      var password = document.getElementById('formPassword').value;
      if (password) payload.password = password;
    }

    fetchApi(editingId ? api + '/employees/' + editingId : api + '/employees', {
      method: editingId ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (r) {
        if (!r.ok) return extractError(r);
        closeModal();
        loadList();
      })
      .catch(function (err) {
        alert(err.message || 'Ошибка сохранения');
      });
  });

  document.getElementById('btnAdd').addEventListener('click', openAdd);
  document.getElementById('btnCancel').addEventListener('click', closeModal);
  modal.addEventListener('click', function (e) {
    if (e.target === modal) closeModal();
  });

  loadList();
})();
