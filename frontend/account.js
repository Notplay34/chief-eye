(function () {
  if (!window.requireAuth()) return;

  var user = window.getUser();
  if (!user) return;

  var userInfo = document.getElementById('userInfo');
  if (userInfo) {
    userInfo.textContent = 'Вы вошли как ' + (user.name || user.login || '');
  }

  function show(id) {
    var node = document.getElementById(id);
    if (node) node.style.display = 'block';
  }

  if (['ROLE_OPERATOR', 'ROLE_MANAGER', 'ROLE_ADMIN'].indexOf(user.role) >= 0) {
    show('linkDocsForm');
    show('linkCash');
    show('linkPlateTransfer');
  }
  if (['ROLE_PLATE_OPERATOR', 'ROLE_MANAGER', 'ROLE_ADMIN'].indexOf(user.role) >= 0) {
    show('linkPlate');
    show('linkPlateCash');
    show('linkWarehouse');
  }
  if (user.role === 'ROLE_ADMIN') {
    show('linkAnalyticsDocs');
    show('linkAnalyticsPlates');
    show('linkPlateReport');
    show('linkAdmin');
    show('linkUsers');
  }

  var linkLogout = document.getElementById('linkLogout');
  if (linkLogout) {
    linkLogout.addEventListener('click', function (e) {
      e.preventDefault();
      window.clearAuth();
      window.location.href = 'login.html';
    });
  }

  var modalPwd = document.getElementById('modalChangePassword');
  var linkPwd = document.getElementById('linkChangePassword');
  var btnSubmitPwd = document.getElementById('btnSubmitPassword');
  var btnCancelPwd = document.getElementById('btnCancelPassword');
  var inputOld = document.getElementById('inputOldPassword');
  var inputNew = document.getElementById('inputNewPassword');
  var inputNew2 = document.getElementById('inputNewPassword2');
  var msgPwd = document.getElementById('passwordMsg');
  var api = window.API_BASE_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : '');
  var fetchApi = window.fetchWithAuth || fetch;

  function showModal(show) {
    if (!modalPwd) return;
    modalPwd.style.display = show ? 'flex' : 'none';
    if (!show) {
      inputOld.value = '';
      inputNew.value = '';
      inputNew2.value = '';
      msgPwd.textContent = '';
    }
  }

  if (linkPwd) {
    linkPwd.addEventListener('click', function (e) {
      e.preventDefault();
      showModal(true);
    });
  }
  if (btnCancelPwd) {
    btnCancelPwd.addEventListener('click', function () {
      showModal(false);
    });
  }
  if (modalPwd) {
    modalPwd.addEventListener('click', function (e) {
      if (e.target === modalPwd) showModal(false);
    });
  }

  if (btnSubmitPwd) {
    btnSubmitPwd.addEventListener('click', function () {
      var oldP = inputOld.value;
      var newP = inputNew.value;
      var newP2 = inputNew2.value;
      msgPwd.textContent = '';
      if (!oldP) {
        msgPwd.textContent = 'Введите текущий пароль';
        msgPwd.style.color = '#b91c1c';
        return;
      }
      if (!newP || newP.length < 4) {
        msgPwd.textContent = 'Новый пароль — не менее 4 символов';
        msgPwd.style.color = '#b91c1c';
        return;
      }
      if (newP !== newP2) {
        msgPwd.textContent = 'Пароли не совпадают';
        msgPwd.style.color = '#b91c1c';
        return;
      }
      fetchApi(api + '/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_password: oldP, new_password: newP })
      })
        .then(function (r) {
          if (r.ok) {
            msgPwd.textContent = 'Пароль изменён.';
            msgPwd.style.color = 'var(--income)';
            setTimeout(function () { showModal(false); }, 1500);
            return;
          }
          return r.json().then(function (j) {
            throw new Error(j.detail || r.statusText);
          });
        })
        .catch(function (e) {
          msgPwd.textContent = e.message || 'Ошибка';
          msgPwd.style.color = '#b91c1c';
        });
    });
  }
})();
