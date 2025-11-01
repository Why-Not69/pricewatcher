// static/main.js
// Минимальный vanilla JS для улучшения UX.
// - на странице добавления продукта показывает только нужное число полей для ссылок,
//   и добавляет кнопку "Добавить ещё" до лимита.
// - на странице product_detail перехватывает "Обновить цены сейчас" и делает POST через fetch,
//   показывает простое сообщение и перезагружает страницу после завершения.

// Ждём, когда DOM загрузится
document.addEventListener("DOMContentLoaded", function() {

  // ---------- Логика для страницы "Добавить продукт" ----------
  (function initAddProduct() {
    // элемент, в котором мы хранем data-max-links
    var root = document.getElementById("add-product-root");
    if (!root) return; // не на этой странице

    // максимальное количество ссылок, которое разрешено по тарифу
    var maxLinks = parseInt(root.dataset.maxLinks) || 5;

    // все поля URL (в шаблоне их 5)
    var inputs = Array.from(document.querySelectorAll(".product-url-input"));

    // Скрываем все поля с индексом > maxLinks
    inputs.forEach(function(inp) {
      var idx = parseInt(inp.dataset.index) || 1;
      if (idx > maxLinks) {
        inp.style.display = "none";
      } else {
        inp.style.display = "block";
      }
    });

    var addBtn = document.getElementById("add-link-btn");
    if (!addBtn) return;

    // Показываем кнопку "Добавить ещё" только если есть скрытые поля
    function updateAddBtn() {
      var hiddenExists = inputs.some(function(inp) {
        return inp.style.display === "none";
      });
      addBtn.style.display = hiddenExists ? "inline-block" : "none";
    }
    updateAddBtn();

    // При клике показываем следующее скрытое поле
    addBtn.addEventListener("click", function() {
      for (var i = 0; i < inputs.length; i++) {
        if (inputs[i].style.display === "none") {
          inputs[i].style.display = "block";
          inputs[i].focus();
          break;
        }
      }
      updateAddBtn();
    });

    // Небольшая защита: перед отправкой формы удаляем пустые скрытые поля
    var form = document.getElementById("add-product-form");
    if (form) {
      form.addEventListener("submit", function() {
        // если поле скрыто — убираем его name, чтобы сервер не получал пустые значения
        inputs.forEach(function(inp) {
          if (inp.style.display === "none") {
            inp.removeAttribute("name");
          }
        });
      });
    }
  })();

  // ---------- Логика для страницы "Детали продукта" (обновление через AJAX) ----------
  (function initProductDetail() {
    var form = document.getElementById("update-now-form");
    if (!form) return; // не на этой странице

    var btn = document.getElementById("update-now-btn");
    var status = document.getElementById("update-status");

    form.addEventListener("submit", function(ev) {
      ev.preventDefault(); // не даём форме сделать обычный POST и редирект — используем fetch
      if (!btn) return;

      btn.disabled = true;
      var oldText = btn.innerText;
      btn.innerText = "Обновление...";

      // Отправляем fetch к тому же URL, методом POST.
      // Передаём credentials: 'same-origin', чтобы cookie-сессия ушла на сервер.
      fetch(form.action, {
        method: 'POST',
        credentials: 'same-origin', // важно: передаём куки для сессии
        headers: {
          'Accept': 'text/html'
        }
      }).then(function(response) {
        if (response.ok) {
          status.innerText = "Готово — обновлено.";
          // Перезагрузим страницу, чтобы показать свежие цены.
          setTimeout(function() {
            location.reload();
          }, 700); // чуть задержим чтобы пользователь увидел сообщение
        } else {
          status.innerText = "Ошибка при обновлении.";
          btn.disabled = false;
          btn.innerText = oldText;
        }
      }).catch(function(err) {
        status.innerText = "Сетевая ошибка.";
        console.error(err);
        btn.disabled = false;
        btn.innerText = oldText;
      });
    });
  })();

}); // DOMContentLoaded end
