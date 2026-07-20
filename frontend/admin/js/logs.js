    // Theme + logout chrome comes from js/admin-common.js, shared with every admin page.
    const AUDIT_STATE = {
      logs: [],
      filtered: [],
    };

    function escapeText(value) {
      return value == null ? '' : String(value);
    }

    function getSeverity(action, entityType) {
      const text = `${action || ''} ${entityType || ''}`.toLowerCase();
      if (/delete|ban|lock|unlock|password|login|logout/.test(text)) return 'critical';
      if (/create|update|assign|status|approve|reject/.test(text)) return 'warning';
      return 'neutral';
    }

    function getActionLabel(action) {
      return escapeText(action || '-').replace(/_/g, ' ');
    }

    function getDetails(log) {
      const message = log.message || log.msg || '';
      if (message) return message;
      const changes = log.changes;
      if (changes && typeof changes === 'object') {
        const pairs = Object.entries(changes).slice(0, 2).map(([key, value]) => {
          if (value && typeof value === 'object' && 'old' in value && 'new' in value) {
            return `${key}: ${escapeText(value.old)} → ${escapeText(value.new)}`;
          }
          return `${key}: ${escapeText(value)}`;
        });
        if (pairs.length) return pairs.join(' • ');
      }
      return '-';
    }

    async function fetchLogs() {
      // Admin profile is a synchronous, non-sensitive guard; the access token itself lives in
      // memory only and is restored lazily by adminAPI on the request below (see js/admin-api.js).
      const adminData = JSON.parse(localStorage.getItem(STORAGE_KEYS.ADMIN_DATA) || 'null');
      if (!adminData) return window.location.href = './login.html';

      const entity = document.getElementById('filter-entity').value || '';

      const logsBody = document.querySelector('#logs-table tbody');
      if (AUDIT_STATE.logs.length === 0) {
        document.getElementById('empty-state').hidden = true;
        showTableSkeleton(logsBody, 7);
      }

      try {
        const body = await adminAPI.getAuditLogs(entity || null, null, 200);
        if (!body.success) throw new Error(body.detail || 'Failed');
        AUDIT_STATE.logs = body.data || [];
        updateSummary(AUDIT_STATE.logs);
        applyFilters();
        updatePills();
        document.getElementById('last-updated').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } catch (err) {
        console.error('Fetch logs failed', err);
        logsBody.textContent = '';
        document.getElementById('empty-state').hidden = false;
      }
    }

    function updateSummary(logs) {
      const adminNames = new Set();
      let sensitiveCount = 0;

      logs.forEach((log) => {
        if (log.admin_name) adminNames.add(log.admin_name);
        if (getSeverity(log.action, log.entity_type) === 'critical') sensitiveCount += 1;
      });

      document.getElementById('total-count').textContent = String(logs.length);
      document.getElementById('admin-count').textContent = String(adminNames.size);
      document.getElementById('high-count').textContent = String(sensitiveCount);
    }

    function updatePills() {
      const pillRow = document.getElementById('filter-pills');
      const entities = [...new Set(AUDIT_STATE.logs.map((log) => log.entity_type).filter(Boolean))].slice(0, 4);
      pillRow.textContent = '';

      const allPill = document.createElement('button');
      allPill.type = 'button';
      allPill.className = 'audit-pill active';
      allPill.textContent = 'All';
      allPill.addEventListener('click', () => {
        document.getElementById('filter-entity').value = '';
        applyFilters();
      });
      pillRow.appendChild(allPill);

      entities.forEach((entity) => {
        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = 'audit-pill';
        pill.textContent = entity;
        pill.addEventListener('click', () => {
          document.getElementById('filter-entity').value = entity;
          applyFilters();
        });
        pillRow.appendChild(pill);
      });
    }

    function applyFilters() {
      const entity = document.getElementById('filter-entity').value.trim().toLowerCase();
      const search = document.getElementById('filter-search').value.trim().toLowerCase();

      AUDIT_STATE.filtered = AUDIT_STATE.logs.filter((log) => {
        const entityType = escapeText(log.entity_type).toLowerCase();
        const adminName = escapeText(log.admin_name || log.admin_id).toLowerCase();
        const action = escapeText(log.action).toLowerCase();
        const details = getDetails(log).toLowerCase();
        const ip = escapeText(log.ip_address || log.ip).toLowerCase();

        const matchesEntity = !entity || entityType.includes(entity);
        const matchesSearch = !search || [adminName, action, entityType, details, ip].some((field) => field.includes(search));
        return matchesEntity && matchesSearch;
      });

      renderLogs(AUDIT_STATE.filtered);
      document.querySelectorAll('.audit-pill').forEach((pill) => {
        pill.classList.toggle('active', pill.textContent.toLowerCase() === (entity || 'all'));
      });
    }

    function renderLogs(logs) {
      const tbody = document.querySelector('#logs-table tbody');
      tbody.textContent = '';
      const emptyState = document.getElementById('empty-state');

      if (!logs.length) {
        emptyState.hidden = false;
        return;
      }

      emptyState.hidden = true;
      logs.forEach(l => {
        const tr = document.createElement('tr');

        const timeTd = document.createElement('td');
        timeTd.textContent = new Date(l.timestamp || l.time || '').toLocaleString();

        const adminTd = document.createElement('td');
        const adminBadge = document.createElement('span');
        adminBadge.className = 'code-badge';
        adminBadge.textContent = l.admin_name || l.admin || l.admin_id || '-';
        adminTd.appendChild(adminBadge);

        const actionTd = document.createElement('td');
        const actionBadge = document.createElement('span');
        const severityClass = { critical: 'danger', warning: 'warning', neutral: 'neutral' }[getSeverity(l.action, l.entity_type)];
        actionBadge.className = `status-badge status-badge--${severityClass}`;
        actionBadge.textContent = getActionLabel(l.action || l.type);
        actionTd.appendChild(actionBadge);

        const entityTd = document.createElement('td');
        entityTd.textContent = l.entity_type || '-';

        const entityIdTd = document.createElement('td');
        entityIdTd.className = 'audit-mono';
        entityIdTd.textContent = l.entity_id || '-';

        const detailsTd = document.createElement('td');
        detailsTd.textContent = getDetails(l);

        const ipTd = document.createElement('td');
        ipTd.className = 'audit-mono';
        ipTd.textContent = l.ip_address || l.ip || '-';

        [timeTd, adminTd, actionTd, entityTd, entityIdTd, detailsTd, ipTd].forEach((cell) => tr.appendChild(cell));
        tbody.appendChild(tr);
      });
    }

    document.getElementById('refresh').addEventListener('click', fetchLogs);
    document.getElementById('filter-entity').addEventListener('input', applyFilters);
    document.getElementById('filter-search').addEventListener('input', applyFilters);
    document.getElementById('clear-filters').addEventListener('click', () => {
      document.getElementById('filter-entity').value = '';
      document.getElementById('filter-search').value = '';
      applyFilters();
    });
    document.getElementById('export-btn').addEventListener('click', () => {
      const rows = [['Time', 'Admin', 'Action', 'Entity', 'Entity ID', 'Details', 'IP']].concat(
        AUDIT_STATE.filtered.map((log) => [
          new Date(log.timestamp || log.time || '').toLocaleString(),
          log.admin_name || log.admin || log.admin_id || '-',
          log.action || log.type || '-',
          log.entity_type || '-',
          log.entity_id || '-',
          getDetails(log),
          log.ip_address || log.ip || '-',
        ])
      );
      const csv = rows.map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(',')).join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'audit-logs.csv';
      link.click();
      URL.revokeObjectURL(link.href);
    });
    document.addEventListener('DOMContentLoaded', fetchLogs);
