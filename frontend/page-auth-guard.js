(function () {
  if (/login\.html$/i.test(window.location.pathname)) return;
  if (!localStorage.getItem('eye_w_token')) {
    window.location.replace('login.html');
  }
})();
