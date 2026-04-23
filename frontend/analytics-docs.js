(function () {
  if (!window.requireAuth || !window.requireAuth()) return;

  function initStub() {
    var container =
      document.getElementById('kpiDocsContent') ||
      document.getElementById('dynamicsDocsContent') ||
      document.getElementById('employeesDocsContent') ||
      document.querySelector('.admin') ||
      document.body;

    if (!container) return;

    if (container.innerHTML && container.innerHTML.indexOf('временно отключ') !== -1) {
      return;
    }

    container.innerHTML =
      '<p class="text-muted">Аналитика по документам временно отключена. Раздел в разработке.</p>';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStub);
  } else {
    initStub();
  }
})();

