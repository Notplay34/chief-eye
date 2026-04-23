(function () {
  if (!window.requireAuth || !window.requireAuth()) return;

  function initStub() {
    var container = document.getElementById('todayContent')
      || document.getElementById('monthContent')
      || document.getElementById('empAnalyticsContent')
      || document.querySelector('.admin')
      || document.body;

    if (!container) return;

    if (container.innerHTML && container.innerHTML.indexOf('временно отключ') !== -1) {
      return;
    }

    container.innerHTML =
      '<p class="text-muted">Раздел «Аналитика» временно отключён. Функция в разработке.</p>';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStub);
  } else {
    initStub();
  }
})();

