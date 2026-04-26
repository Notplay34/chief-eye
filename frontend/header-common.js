(function () {
  var THEME_KEY = 'eye_w_theme';

  function getStoredTheme() {
    try {
      return localStorage.getItem(THEME_KEY) || 'light';
    } catch (_) {
      return 'light';
    }
  }

  function applyTheme(theme) {
    var next = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (_) {}
    var btn = document.getElementById('btnThemeToggle');
    if (btn) {
      btn.textContent = next === 'dark' ? '☀' : '◐';
      btn.title = next === 'dark' ? 'Светлая тема' : 'Тёмная тема';
      btn.setAttribute('aria-label', btn.title);
    }
  }

  applyTheme(getStoredTheme());

  var APP_HEADER_HTML = [
    '<header class="header header--dashboard">',
    '  <div class="header__row">',
    '    <div class="header__brand">',
    '      <h1 class="header__title">РегДок</h1>',
    '    </div>',
    '    <div class="header__actions">',
    '      <button type="button" class="theme-toggle" id="btnThemeToggle" aria-label="Тёмная тема" title="Тёмная тема">◐</button>',
    '      <div class="header__menu-wrap">',
    '        <span class="header__user-name" id="headerUserName" title="Открыть меню">—</span>',
    '        <button type="button" class="header__menu-btn" id="btnMenu" aria-label="Меню" title="Меню">⋮</button>',
    '        <div class="header__dropdown" id="menuDropdown" aria-hidden="true">',
    '          <div class="header__dropdown-inner" id="menuDropdownInner"></div>',
    '        </div>',
    '      </div>',
    '    </div>',
    '  </div>',
    '</header>'
  ].join('');

  var me = window.getMe();

  function ensureDirectorMenuItems(profile) {
    if (!profile || (profile.role || '').toUpperCase() !== 'ROLE_ADMIN') return profile;
    var items = profile.menu_items || [];
    var hasPlateReport = items.some(function (item) { return item && item.id === 'plate_report'; });
    if (!hasPlateReport) {
      var insertAt = items.findIndex(function (item) { return item && item.id === 'admin'; });
      var reportItem = { id: 'plate_report', label: 'Отчёт по номерам', href: 'plate-report.html', group: 'Управление' };
      if (insertAt >= 0) items.splice(insertAt, 0, reportItem);
      else items.push(reportItem);
      profile.menu_items = items;
    }
    return profile;
  }

  function ensureAppHeader() {
    var mount = document.getElementById('appHeader');
    if (mount) {
      mount.innerHTML = APP_HEADER_HTML;
      return;
    }
    if (document.querySelector('.header--dashboard')) return;
    document.body.insertAdjacentHTML('afterbegin', APP_HEADER_HTML);
  }

  function buildMeFromUser() {
    var user = window.getUser();
    if (!user) return { name: 'Аккаунт', allowed_pavilions: [1], menu_items: [] };
    var role = (user.role || '').toUpperCase();
    var pavilions = [1];
    if (role === 'ROLE_ADMIN' || role === 'ROLE_MANAGER') pavilions = [1, 2];
    else if (role === 'ROLE_PLATE_OPERATOR') pavilions = [2];
    var menu_items = [];
    if (role === 'ROLE_OPERATOR' || role === 'ROLE_MANAGER' || role === 'ROLE_ADMIN') {
      menu_items.push({ id: 'form_p1', label: 'Подготовка документов', href: 'index.html' });
      menu_items.push({ id: 'cash_p1', label: 'Касса', href: 'cash-shifts.html' });
      menu_items.push({ id: 'plate_transfer', label: 'Деньги за номера', href: 'plate-transfer.html' });
    }
    if (role === 'ROLE_PLATE_OPERATOR' || role === 'ROLE_MANAGER' || role === 'ROLE_ADMIN') {
      menu_items.push({ id: 'plates', label: 'Невыданные номера', href: 'plate-operator.html' });
      menu_items.push({ id: 'plate_cash', label: 'Касса номеров', href: 'plate-cash.html' });
      menu_items.push({ id: 'warehouse', label: 'Склад заготовок', href: 'warehouse.html' });
    }
    if (role === 'ROLE_ADMIN') {
      menu_items.push({ id: 'analytics_docs', label: 'Аналитика — Документы', href: 'analytics-docs.html' });
      menu_items.push({ id: 'analytics_plates', label: 'Аналитика — Номера', href: 'analytics-plates.html' });
      menu_items.push({ id: 'plate_report', label: 'Отчёт по номерам', href: 'plate-report.html' });
      menu_items.push({ id: 'admin', label: 'Админка', href: 'admin.html' });
      menu_items.push({ id: 'users', label: 'Управление аккаунтами', href: 'users.html' });
    }
    menu_items.push({ id: '_div', label: '', divider: true });
    menu_items.push({ id: 'password', label: 'Сменить пароль', href: '#', action: 'change_password' });
    menu_items.push({ id: 'logout', label: 'Выйти', href: 'login.html', action: 'logout' });
    return ensureDirectorMenuItems({
      id: user.id,
      name: user.name || user.login || 'Аккаунт',
      role: user.role,
      login: user.login,
      allowed_pavilions: pavilions,
      menu_items: menu_items,
    });
  }

  function getGroupKey(item) {
    var href = item.href || '';
    if (/index\.html|plate-operator\.html|warehouse\.html/i.test(href)) return 'Работа';
    if (/cash-shifts\.html|plate-transfer\.html|plate-cash\.html/i.test(href)) return 'Деньги';
    if (/analytics|admin\.html|users\.html/i.test(href)) return 'Управление';
    return 'Профиль';
  }

  function getMenuMeta(item) {
    var id = item.id || '';
    var map = {
      form_p1: { label: 'Документы', note: 'Оформление заказов' },
      plates: { label: 'Номера', note: 'Выдача и статусы' },
      warehouse: { label: 'Склад', note: 'Заготовки номеров' },
      cash_p1: { label: 'Касса', note: 'Документы и госпошлины' },
      plate_cash: { label: 'Касса номеров', note: 'Деньги за номера' },
      plate_transfer: { label: 'Промежуточная касса', note: 'Деньги за номера' },
      analytics_docs: { label: 'Документы', note: 'Аналитика' },
      analytics_plates: { label: 'Номера', note: 'Аналитика' },
      plate_report: { label: 'Отчёт по номерам', note: 'Делёжка и расходы' },
      admin: { label: 'Админка', note: 'Настройки' },
      users: { label: 'Аккаунты', note: 'Пользователи' },
      password: { label: 'Пароль', note: 'Профиль' },
      logout: { label: 'Выйти', note: 'Завершить сеанс' }
    };
    return map[id] || { label: item.label || 'Раздел', note: '' };
  }

  function renderHeader() {
    var userNameEl = document.getElementById('headerUserName');
    me = ensureDirectorMenuItems(me);
    if (userNameEl && me) userNameEl.textContent = me.name || me.login || 'Аккаунт';

    var inner = document.getElementById('menuDropdownInner');
    if (!inner || !me) return;
    inner.innerHTML = '';

    var groups = {
      'Работа': [],
      'Деньги': [],
      'Управление': [],
      'Профиль': [],
    };

    (me.menu_items || []).forEach(function (item) {
      if (!item || (!item.label && !item.href && !item.action)) return;
      if (item.divider) return;
      var key = getGroupKey(item);
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
    });

    var currentPage = window.location.pathname.split('/').pop() || 'index.html';
    ['Работа', 'Деньги', 'Управление', 'Профиль'].forEach(function (key) {
      var items = groups[key];
      if (!items || !items.length) return;
      var groupEl = document.createElement('div');
      groupEl.className = 'header__dropdown-group';
      groupEl.textContent = key;
      inner.appendChild(groupEl);
      items.forEach(function (item) {
        if (!item.label && !item.href) return;
        var meta = getMenuMeta(item);
        var a = document.createElement('a');
        var labelEl = document.createElement('span');
        var noteEl = document.createElement('span');
        a.href = item.href || '#';
        labelEl.className = 'header__dropdown-link-label';
        labelEl.textContent = meta.label;
        noteEl.className = 'header__dropdown-link-note';
        noteEl.textContent = meta.note;
        a.appendChild(labelEl);
        if (meta.note) a.appendChild(noteEl);
        if (item.href && item.href === currentPage) a.classList.add('header__dropdown-link--active');
        a.setAttribute('data-action', item.action || '');
        a.setAttribute('data-id', item.id || '');
        a.addEventListener('click', function (e) {
          if (item.action === 'logout') {
            e.preventDefault();
            window.clearAuth();
            window.location.href = 'login.html';
            return;
          }
          if (item.action === 'change_password') {
            e.preventDefault();
            window.location.href = 'account.html';
            return;
          }
          var d = document.getElementById('menuDropdown');
          if (d) {
            d.classList.remove('header__dropdown--open');
            d.setAttribute('aria-hidden', 'true');
          }
        });
        inner.appendChild(a);
      });
    });
  }

  function toggleMenu() {
    var dd = document.getElementById('menuDropdown');
    if (!dd) return;
    var isOpen = dd.classList.contains('header__dropdown--open');
    dd.classList.toggle('header__dropdown--open', !isOpen);
    dd.setAttribute('aria-hidden', isOpen ? 'true' : 'false');
  }

  function init() {
    function proceed() {
      ensureAppHeader();
      if (!me) me = buildMeFromUser();
      renderHeader();

      // Клик по «РегДок» ведёт на стартовую страницу роли
      var headerTitle = document.querySelector('.header__title');
      if (headerTitle) {
        headerTitle.textContent = 'РегДок';
        headerTitle.style.cursor = 'pointer';
        headerTitle.onclick = function () {
          var user = window.getUser && window.getUser();
          var role = user && user.role;
          if (role === 'ROLE_PLATE_OPERATOR') {
            window.location.href = 'plate-operator.html';
          } else {
            window.location.href = 'index.html';
          }
        };
      }

      var btnMenu = document.getElementById('btnMenu');
      if (btnMenu) btnMenu.addEventListener('click', function (e) { e.stopPropagation(); toggleMenu(); });
      var userNameEl = document.getElementById('headerUserName');
      if (userNameEl) userNameEl.addEventListener('click', function (e) { e.stopPropagation(); toggleMenu(); });
      var btnTheme = document.getElementById('btnThemeToggle');
      if (btnTheme) {
        applyTheme(getStoredTheme());
        btnTheme.addEventListener('click', function (e) {
          e.stopPropagation();
          var current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
          applyTheme(current === 'dark' ? 'light' : 'dark');
        });
      }
      var logoutLink = document.getElementById('headerLogoutLink');
      if (logoutLink) {
        logoutLink.addEventListener('click', function (e) {
          e.preventDefault();
          window.clearAuth();
          window.location.href = 'login.html';
        });
      }
      document.addEventListener('click', function (e) {
        if (!e.target.closest('.header__menu-wrap')) {
          var dd = document.getElementById('menuDropdown');
          if (dd) {
            dd.classList.remove('header__dropdown--open');
            dd.setAttribute('aria-hidden', 'true');
          }
        }
      });
    }

    if (!me || !me.menu_items) {
      if (window.loadMe) {
        window.loadMe().then(function (m) {
          me = m || buildMeFromUser();
          proceed();
        }).catch(function () {
          me = buildMeFromUser();
          proceed();
        });
      } else {
        me = buildMeFromUser();
        proceed();
      }
    } else {
      proceed();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
