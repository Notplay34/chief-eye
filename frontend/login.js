(function () {
  if (window.getToken && window.getToken()) {
    window.location.href = 'index.html';
    return;
  }

  var form = document.getElementById('loginForm');
  var errEl = document.getElementById('loginError');
  var btn = document.getElementById('btnSubmit');
  if (!form || !errEl || !btn) return;

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    errEl.style.display = 'none';
    errEl.textContent = '';
    btn.disabled = true;
    btn.textContent = 'Вход…';

    var formData = new FormData();
    formData.append('username', document.getElementById('login').value.trim());
    formData.append('password', document.getElementById('password').value);

    var base = window.API_BASE_URL || '';
    fetch(base + '/auth/login', { method: 'POST', body: formData })
      .then(function (res) {
        if (!res.ok) {
          return res.json()
            .then(function (j) { throw new Error(j.detail || 'Ошибка входа'); })
            .catch(function () { throw new Error('Ошибка ' + res.status); });
        }
        return res.json();
      })
      .then(function (data) {
        window.setToken(data.access_token, data.user);
        return fetch(base + '/auth/me', {
          headers: { Authorization: 'Bearer ' + data.access_token }
        }).then(function (r) {
          if (!r.ok) throw new Error('token_rejected');
          return r.json();
        });
      })
      .then(function (me) {
        if (me) {
          window.setMe(me);
          var allowed = me.allowed_pavilions || [1];
          var saved = localStorage.getItem('eye_w_pavilion');
          if (saved !== '1' && saved !== '2' && allowed.length) {
            localStorage.setItem('eye_w_pavilion', String(allowed[0]));
          }
        }
        window.location.href = 'index.html';
      })
      .catch(function (err) {
        var msg = err.message || 'Неверный логин или пароль';
        if (msg === 'token_rejected') {
          msg = 'Сервер не принял токен. На сервере выполните: cd /opt/eye_w && bash deploy/setup_server.sh';
        }
        errEl.textContent = msg;
        errEl.style.display = 'block';
        btn.disabled = false;
        btn.textContent = 'Войти';
      });
  });
})();
