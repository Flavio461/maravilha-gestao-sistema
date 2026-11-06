'use strict';
document.addEventListener('DOMContentLoaded', function () {
  const toggle = document.querySelector('.sidebar-toggle');
  const sidebar = document.querySelector('#sidebar');
  const closeSidebar = document.querySelector('.sidebar-close');
  if (toggle && sidebar) {
    if (closeSidebar) closeSidebar.addEventListener('click', function () {
      sidebar.classList.remove('sidebar-open');
      toggle.setAttribute('aria-expanded', 'false');
      toggle.focus();
    });
    toggle.addEventListener('click', function () {
      const open = sidebar.classList.toggle('sidebar-open');
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
    });
  }
  const order = document.querySelector('#has_order');
  const fields = document.querySelector('#order-fields');
  const expected = document.querySelector('#expected_date');
  if (order && fields) {
    function syncOrder() {
      fields.hidden = !order.checked;
      if (expected) expected.required = order.checked;
      order.setAttribute('aria-expanded', String(order.checked));
    }
    order.addEventListener('change', syncOrder);
    syncOrder();
  }
});
