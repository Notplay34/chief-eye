/**
 * Авторизация: токен в localStorage, заголовок для API, редирект на логин.
 * App state: user, allowed_pavilions, menu_items, currentPavilion (1|2).
 */
(function () {
  var TOKEN_KEY = 'eye_w_token';
  var USER_KEY = 'eye_w_user';
  var ME_KEY = 'eye_w_me';
  var PAVILION_KEY = 'eye_w_pavilion';

  window.API_BASE_URL = window.API_BASE_URL || (window.location.hostname === 'localhost' ? 'http://localhost:8000' : '');

  window.getToken = function () { return localStorage.getItem(TOKEN_KEY); };
  window.setToken = function (token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  };
  window.clearAuth = function () {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(ME_KEY);
    localStorage.removeItem(PAVILION_KEY);
  };
  window.getUser = function () {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch (_) { return null; }
  };
  /** Полный ответ /auth/me: user, allowed_pavilions, menu_items */
  window.getMe = function () {
    try { return JSON.parse(localStorage.getItem(ME_KEY) || 'null'); } catch (_) { return null; }
  };
  window.setMe = function (me) {
    if (me) {
      localStorage.setItem(ME_KEY, JSON.stringify(me));
      if (me.id != null) localStorage.setItem(USER_KEY, JSON.stringify({ id: me.id, name: me.name, role: me.role, login: me.login }));
    }
  };
  /** Текущий павильон 1 или 2 */
  window.getCurrentPavilion = function () {
    var p = localStorage.getItem(PAVILION_KEY);
    if (p === '1' || p === '2') return parseInt(p, 10);
    var me = window.getMe();
    var allowed = (me && me.allowed_pavilions && me.allowed_pavilions.length) ? me.allowed_pavilions : [1];
    return allowed[0];
  };
  window.setCurrentPavilion = function (pavilion) {
    if (pavilion === 1 || pavilion === 2) localStorage.setItem(PAVILION_KEY, String(pavilion));
  };
  window.getAuthHeaders = function () {
    var h = { 'Content-Type': 'application/json' };
    var t = window.getToken();
    if (t) h['Authorization'] = 'Bearer ' + t;
    return h;
  };
  window.fetchWithAuth = function (url, options) {
    options = options || {};
    options.headers = options.headers || {};
    var t = window.getToken();
    if (t) options.headers['Authorization'] = 'Bearer ' + t;
    if (!options.headers['Content-Type']) options.headers['Content-Type'] = 'application/json';
    return fetch(url, options).then(function (res) {
      if (res.status === 401) { window.clearAuth(); window.location.href = 'login.html'; return Promise.reject(new Error('Требуется авторизация')); }
      return res;
    });
  };
  /** Загрузить /auth/me и сохранить в state; вернуть Promise<me> */
  window.loadMe = function () {
    var api = window.API_BASE_URL || '';
    var t = window.getToken();
    if (!t) return Promise.resolve(null);
    return fetch(api + '/auth/me', { headers: { 'Authorization': 'Bearer ' + t } })
      .then(function (r) {
        if (r.status === 401) { window.clearAuth(); window.location.href = 'login.html'; return Promise.reject(new Error('auth')); }
        if (!r.ok) return null;
        return r.json();
      })
      .then(function (me) {
        if (me) window.setMe(me);
        return me;
      })
      .catch(function (err) { if (err && err.message === 'auth') return; return null; });
  };
  window.requireAuth = function () {
    if (!window.getToken() && !/login\.html$/i.test(window.location.pathname)) {
      window.location.href = 'login.html';
      return false;
    }
    return true;
  };
})();
