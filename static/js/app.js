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
  const modes = document.querySelectorAll('input[name="sale_mode"]');
  const stockFields = document.querySelector('#stock-materials');
  const manualFields = document.querySelector('#manual-materials');
  const lines = document.querySelector('#stock-lines');
  const addProduct = document.querySelector('#add-product');
  const lineTemplate = document.querySelector('#stock-line-template');
  const total = document.querySelector('#stock-total');
  const currency = new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'});

  function updateProducts() {
    let cents = 0;
    const rows = lines.querySelectorAll('.stock-line');
    rows.forEach(function (row, index) {
      const select = row.querySelector('.stock-product');
      const quantity = row.querySelector('.stock-quantity');
      const option = select.selectedOptions[0];
      const price = Number(option.dataset.price || 0);
      const available = Number(option.dataset.stock || 0);
      const number = index + 1;
      select.id = 'product-' + number;
      quantity.id = 'quantity-' + number;
      row.querySelectorAll('label')[0].htmlFor = select.id;
      row.querySelectorAll('label')[0].textContent = 'Produto ' + number + ' *';
      row.querySelectorAll('label')[1].htmlFor = quantity.id;
      const remove = row.querySelector('.remove-product');
      remove.disabled = rows.length === 1;
      remove.setAttribute('aria-label', 'Remover produto ' + number);
      quantity.max = select.value ? String(available) : '1000000';
      row.querySelector('.stock-hint').textContent = select.value
        ? currency.format(price / 100) + ' por unidade · ' + available + ' disponíveis'
        : 'Selecione para consultar o preço e o estoque.';
      cents += price * Number(quantity.value || 0);
    });
    total.textContent = currency.format(cents / 100);
    addProduct.disabled = rows.length >= 20;
  }

  function syncSaleMode() {
    const useStock = document.querySelector('input[name="sale_mode"]:checked').value === 'estoque';
    stockFields.hidden = !useStock;
    manualFields.hidden = useStock;
    stockFields.querySelectorAll('select, input').forEach(function (input) {
      input.disabled = !useStock;
    });
    manualFields.querySelectorAll('input, textarea').forEach(function (input) {
      input.disabled = useStock;
    });
    updateProducts();
  }

  if (modes.length && stockFields && manualFields && lines && addProduct && lineTemplate && total) {
    modes.forEach(function (mode) { mode.addEventListener('change', syncSaleMode); });
    lines.addEventListener('input', updateProducts);
    lines.addEventListener('change', updateProducts);
    lines.addEventListener('click', function (event) {
      const remove = event.target.closest('.remove-product');
      if (!remove) return;
      remove.closest('.stock-line').remove();
      updateProducts();
      addProduct.focus();
    });
    addProduct.addEventListener('click', function () {
      lines.appendChild(lineTemplate.content.cloneNode(true));
      syncSaleMode();
      lines.lastElementChild.querySelector('select').focus();
    });
    syncSaleMode();
  }
});
