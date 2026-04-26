(function () {
  function detectKind() {
    var path = (window.location.pathname || '').toLowerCase();
    if (path.indexOf('analytics-docs') !== -1) return 'docs';
    if (path.indexOf('analytics-plates') !== -1) return 'plates';
    return 'all';
  }

  function getPageMeta(kind) {
    if (kind === 'docs') {
      return {
        title: 'Аналитика — Документы',
        subtitle: 'Сколько заработали на документах и комиссии госпошлин, отдельно от проходных сумм.',
      };
    }
    if (kind === 'plates') {
      return {
        title: 'Аналитика — Номера',
        subtitle: 'Доход по изготовлению номеров, доплатам и работе павильона 2.',
      };
    }
    return {
      title: 'Аналитика',
      subtitle: 'Главный экран владельца: сколько заработали, откуда пришли деньги и что ушло госпошлиной.',
    };
  }

  function formatMoney(value) {
    var num = Number(value || 0);
    return new Intl.NumberFormat('ru-RU', {
      maximumFractionDigits: 0,
      minimumFractionDigits: 0,
    }).format(num) + ' ₽';
  }

  function formatPercent(value) {
    var num = Number(value || 0);
    return new Intl.NumberFormat('ru-RU', {
      maximumFractionDigits: 1,
      minimumFractionDigits: 0,
    }).format(num) + '%';
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function deltaText(current, previous, mode) {
    var curr = Number(current || 0);
    var prev = Number(previous || 0);
    var diff = curr - prev;
    if (!prev && !curr) return 'без изменений';
    if (!prev) return curr ? 'первый период с данными' : 'без данных в прошлом периоде';
    var ratio = (diff / prev) * 100;
    var sign = diff > 0 ? '+' : '';
    if (mode === 'money') return sign + formatMoney(diff) + ' к прошлому периоду';
    if (mode === 'count') return sign + diff + ' к прошлому периоду';
    return sign + ratio.toFixed(1).replace('.', ',') + '% к прошлому периоду';
  }

  function card(title, value, hint, tone) {
    return [
      '<article class="analytics-card', tone ? ' analytics-card--' + tone : '', '">',
      '  <div class="analytics-card__label">', escapeHtml(title), '</div>',
      '  <div class="analytics-card__value">', escapeHtml(value), '</div>',
      '  <div class="analytics-card__hint">', escapeHtml(hint || ''), '</div>',
      '</article>',
    ].join('');
  }

  function renderOverview(overview, previous, kind) {
    var cards;
    if (kind === 'docs') {
      cards = [
        card('Доход по документам', formatMoney(overview.income_total), deltaText(overview.income_total, previous.income_total, 'money'), 'primary'),
        card('Принято госпошлины', formatMoney(overview.state_duty_cash_total), 'Проходная сумма, не доход павильона', 'turnover'),
        card('Заказы', String(overview.orders_count || 0), deltaText(overview.orders_count, previous.orders_count, 'count')),
        card('Средний чек', formatMoney(overview.average_check), deltaText(overview.average_check, previous.average_check, 'money')),
      ];
    } else if (kind === 'plates') {
      cards = [
        card('Доход по номерам', formatMoney(overview.income_total), deltaText(overview.income_total, previous.income_total, 'money'), 'primary'),
        card('Комплекты', String(overview.numbers_units || 0), deltaText(overview.numbers_units, previous.numbers_units, 'count'), 'turnover'),
        card('Заказы с номерами', String(overview.numbers_orders_count || 0), deltaText(overview.numbers_orders_count, previous.numbers_orders_count, 'count')),
        card('Средний чек номеров', formatMoney(overview.average_check), deltaText(overview.average_check, previous.average_check, 'money')),
      ];
    } else {
      cards = [
        card('Мой доход', formatMoney(overview.income_total), deltaText(overview.income_total, previous.income_total, 'money'), 'primary'),
        card('Оборот в кассе', formatMoney(overview.turnover_total), 'Все принятые деньги, включая госпошлину', 'turnover'),
        card('Заказы', String(overview.orders_count || 0), deltaText(overview.orders_count, previous.orders_count, 'count')),
        card('Средний чек', formatMoney(overview.average_check), deltaText(overview.average_check, previous.average_check, 'money')),
      ];
    }

    return '<section class="analytics-grid analytics-grid--cards">' + cards.join('') + '</section>';
  }

  function moneyRow(label, value, tone) {
    return [
      '<div class="analytics-money-row', tone ? ' analytics-money-row--' + tone : '', '">',
      '  <span>', escapeHtml(label), '</span>',
      '  <strong>', escapeHtml(formatMoney(value)), '</strong>',
      '</div>',
    ].join('');
  }

  function breakdownCopy(kind) {
    if (kind === 'docs') {
      return {
        title: 'Доход по документам',
        subtitle: 'Документы и комиссия госпошлины. Номера в этот раздел не попадают.',
        total: 'Итого по документам',
      };
    }
    if (kind === 'plates') {
      return {
        title: 'Доход по номерам',
        subtitle: 'Изготовление номеров и доплаты. Госпошлина и документы здесь не учитываются.',
        total: 'Итого по номерам',
      };
    }
    return {
      title: 'Из чего собрался доход',
      subtitle: 'Здесь только ваши деньги. Госпошлина ниже показана отдельно как проходная сумма.',
      total: 'Итого мой доход',
    };
  }

  function renderPassThrough(overview, kind) {
    if (kind === 'plates') return '';
    return [
      '  <div class="analytics-pass-through">',
      '    <h3>Проходные деньги</h3>',
      moneyRow('Госпошлина к списанию/перечислению', overview.state_duty_total || 0),
      moneyRow('Принято госпошлины в кассу', overview.state_duty_cash_total || overview.state_duty_total || 0),
      '  </div>',
    ].join('');
  }

  function renderIncomeBreakdown(overview, kind) {
    var plateTotal = Number(overview.plates_income || 0) + Number(overview.plate_extra_income || 0);
    var copy = breakdownCopy(kind);
    var rows = [];
    if (kind !== 'plates' && Number(overview.docs_income || 0) > 0) rows.push(moneyRow('Документы', overview.docs_income));
    if (kind !== 'plates' && Number(overview.state_duty_commission_income || 0) > 0) rows.push(moneyRow('Комиссия госпошлин', overview.state_duty_commission_income));
    if (kind !== 'docs' && Number(overview.plates_income || 0) > 0) rows.push(moneyRow('Изготовление номеров', overview.plates_income));
    if (kind !== 'docs' && Number(overview.plate_extra_income || 0) > 0) rows.push(moneyRow('Доплаты за номера', overview.plate_extra_income));
    if (!rows.length) rows.push('<div class="analytics-empty">Дохода за выбранный период пока нет.</div>');

    return [
      '<section class="analytics-panel analytics-panel--breakdown">',
      '  <div class="analytics-panel__header">',
      '    <h2>', escapeHtml(copy.title), '</h2>',
      '    <p>', escapeHtml(copy.subtitle), '</p>',
      '  </div>',
      '  <div class="analytics-money-list">',
      rows.join(''),
      moneyRow(copy.total, overview.income_total, 'total'),
      '  </div>',
      renderPassThrough(overview, kind),
      kind !== 'docs' && Number(overview.numbers_orders_count || 0) ? '<p class="analytics-panel__note">Номера: заказов ' + escapeHtml(overview.numbers_orders_count) + ', комплектов ' + escapeHtml(overview.numbers_units || 0) + ', сумма ' + escapeHtml(formatMoney(plateTotal)) + '.</p>' : '',
      '</section>',
    ].join('');
  }

  function renderTrend(rows) {
    return [
      '<section class="analytics-panel">',
      '  <div class="analytics-panel__header">',
      '    <h2>Доход по месяцам</h2>',
      '    <p>Последние 12 месяцев: удобно смотреть сезонность и просадки.</p>',
      '  </div>',
      '  <div class="analytics-table-wrap">',
      '    <table class="analytics-table">',
      '      <thead><tr><th>Месяц</th><th>Заказы</th><th>Мой доход</th><th>Оборот</th></tr></thead>',
      '      <tbody>',
      rows.map(function (row) {
        return [
          '<tr>',
          '  <td>', escapeHtml(row.label), '</td>',
          '  <td>', escapeHtml(row.orders_count), '</td>',
          '  <td>', escapeHtml(formatMoney(row.income_total)), '</td>',
          '  <td>', escapeHtml(formatMoney(row.turnover_total)), '</td>',
          '</tr>',
        ].join('');
      }).join(''),
      '      </tbody>',
      '    </table>',
      '  </div>',
      '</section>',
    ].join('');
  }

  function renderEmployees(rows) {
    return [
      '<section class="analytics-panel">',
      '  <div class="analytics-panel__header">',
      '    <h2>Сотрудники</h2>',
      '    <p>Кто приносит деньги в выбранном периоде.</p>',
      '  </div>',
      rows && rows.length ? [
        '  <div class="analytics-table-wrap">',
        '    <table class="analytics-table">',
        '      <thead><tr><th>Сотрудник</th><th>Заказы</th><th>Мой доход</th><th>Средний чек</th><th>Доля</th></tr></thead>',
        '      <tbody>',
        rows.map(function (row) {
          return [
            '<tr>',
            '  <td>', escapeHtml(row.employee_name), '</td>',
            '  <td>', escapeHtml(row.orders_count), '</td>',
            '  <td>', escapeHtml(formatMoney(row.income_total)), '</td>',
            '  <td>', escapeHtml(formatMoney(row.average_check)), '</td>',
            '  <td>', escapeHtml(formatPercent(row.share_percent)), '</td>',
            '</tr>',
          ].join('');
        }).join(''),
        '      </tbody>',
        '    </table>',
        '  </div>',
      ].join('') : '<div class="analytics-empty">Нет данных по сотрудникам за этот период.</div>',
      '</section>',
    ].join('');
  }

  function renderServices(rows, kind) {
    var subtitle = 'Услуги и комиссии, отсортированные по сумме.';
    if (kind === 'docs') subtitle = 'Только документы и комиссия госпошлины, без номеров.';
    if (kind === 'plates') subtitle = 'Только изготовление номеров и доплаты, без госпошлины.';
    return [
      '<section class="analytics-panel">',
      '  <div class="analytics-panel__header">',
      '    <h2>Что приносит деньги</h2>',
      '    <p>', escapeHtml(subtitle), '</p>',
      '  </div>',
      rows && rows.length ? [
        '  <div class="analytics-table-wrap">',
        '    <table class="analytics-table">',
        '      <thead><tr><th>Источник</th><th>Количество</th><th>Сумма</th></tr></thead>',
        '      <tbody>',
        rows.map(function (row) {
          return [
            '<tr>',
            '  <td>', escapeHtml(row.label), '</td>',
            '  <td>', escapeHtml(row.count), '</td>',
            '  <td>', escapeHtml(formatMoney(row.revenue)), '</td>',
            '</tr>',
          ].join('');
        }).join(''),
        '      </tbody>',
        '    </table>',
        '  </div>',
      ].join('') : '<div class="analytics-empty">В выбранном периоде услуги не найдены.</div>',
      '</section>',
    ].join('');
  }

  function buildQuery(state) {
    var params = new URLSearchParams();
    params.set('period', state.period);
    params.set('kind', state.kind);
    if (state.dateFrom) params.set('date_from', state.dateFrom);
    if (state.dateTo) params.set('date_to', state.dateTo);
    return params.toString();
  }

  function renderFilters(state) {
    return [
      '<section class="analytics-toolbar">',
      '  <label class="analytics-filter">',
      '    <span>Период</span>',
      '    <select id="analyticsPeriod">',
      ['day', 'week', 'month', 'quarter', 'year'].map(function (value) {
        var labels = { day: 'День', week: 'Неделя', month: 'Месяц', quarter: 'Квартал', year: 'Год' };
        return '<option value="' + value + '"' + (state.period === value ? ' selected' : '') + '>' + labels[value] + '</option>';
      }).join(''),
      '    </select>',
      '  </label>',
      '  <label class="analytics-filter">',
      '    <span>С</span>',
      '    <input type="date" id="analyticsDateFrom" value="' + escapeHtml(state.dateFrom || '') + '">',
      '  </label>',
      '  <label class="analytics-filter">',
      '    <span>По</span>',
      '    <input type="date" id="analyticsDateTo" value="' + escapeHtml(state.dateTo || '') + '">',
      '  </label>',
      '  <button type="button" class="btn btn--secondary" id="analyticsApply">Обновить</button>',
      '</section>',
    ].join('');
  }

  function setPageMeta(kind) {
    var meta = getPageMeta(kind);
    var title = document.getElementById('analyticsTitle');
    var subtitle = document.getElementById('analyticsSubtitle');
    if (title) title.textContent = meta.title;
    if (subtitle) subtitle.textContent = meta.subtitle;
    document.title = meta.title;
  }

  function attachFilters(root, state, reload) {
    var period = root.querySelector('#analyticsPeriod');
    var dateFrom = root.querySelector('#analyticsDateFrom');
    var dateTo = root.querySelector('#analyticsDateTo');
    var apply = root.querySelector('#analyticsApply');
    if (!period || !dateFrom || !dateTo || !apply) return;

    apply.addEventListener('click', function () {
      state.period = period.value;
      state.dateFrom = dateFrom.value || '';
      state.dateTo = dateTo.value || '';
      reload();
    });
  }

  function renderDashboard(root, state, dashboard) {
    root.innerHTML = [
      renderFilters(state),
      renderOverview(dashboard.overview, dashboard.previous_overview, state.kind),
      '<div class="analytics-grid analytics-grid--main">',
      '  <div class="analytics-stack">',
      renderIncomeBreakdown(dashboard.overview, state.kind),
      renderTrend(dashboard.monthly_trend || []),
      '  </div>',
      '  <div class="analytics-stack">',
      renderServices(dashboard.top_services || [], state.kind),
      renderEmployees(dashboard.employee_stats || []),
      '  </div>',
      '</div>',
    ].join('');
  }

  function renderLoading(root, state) {
    root.innerHTML = renderFilters(state) + '<div class="analytics-empty">Загрузка аналитики…</div>';
  }

  function renderError(root, state, message) {
    root.innerHTML = renderFilters(state) + '<div class="analytics-empty analytics-empty--error">' + escapeHtml(message) + '</div>';
  }

  function init() {
    var root = document.getElementById('analyticsApp');
    if (!root) return;

    var state = {
      kind: detectKind(),
      period: 'month',
      dateFrom: '',
      dateTo: '',
    };

    setPageMeta(state.kind);

    function load() {
      renderLoading(root, state);
      attachFilters(root, state, load);
      var url = (window.API_BASE_URL || '') + '/analytics/dashboard?' + buildQuery(state);
      window.fetchWithAuth(url)
        .then(function (response) {
          if (!response.ok) {
            return response.json().catch(function () { return {}; }).then(function (payload) {
              throw new Error(payload.detail || 'Не удалось загрузить аналитику');
            });
          }
          return response.json();
        })
        .then(function (dashboard) {
          renderDashboard(root, state, dashboard);
          attachFilters(root, state, load);
        })
        .catch(function (error) {
          renderError(root, state, error && error.message ? error.message : 'Не удалось загрузить аналитику');
          attachFilters(root, state, load);
        });
    }

    load();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
