(function () {
  if (!window.requireAuth || !window.requireAuth()) return;

  function initStub() {
    var container =
      document.getElementById('kpiPlatesContent') ||
      document.getElementById('dynamicsPlatesContent') ||
      document.getElementById('employeesPlatesContent') ||
      document.querySelector('.admin') ||
      document.body;

    if (!container) return;

    if (container.innerHTML && container.innerHTML.indexOf('временно отключ') !== -1) {
      return;
    }

    container.innerHTML =
      '<p class="text-muted">Аналитика по номерам временно отключена. Раздел в разработке.</p>';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStub);
  } else {
    initStub();
  }
})();

