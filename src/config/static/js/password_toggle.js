document.querySelectorAll('.password-toggle').forEach(function(btn) {
    var input = btn.parentElement.querySelector('input');
    var labelShow = 'Показать пароль';
    var labelHide = 'Скрыть пароль';
    function updateLabel(visible) {
        btn.setAttribute('aria-label', visible ? labelHide : labelShow);
        btn.title = visible ? labelHide : labelShow;
    }
    btn.addEventListener('click', function() {
        var visible = input.type === 'text';
        input.type = visible ? 'password' : 'text';
        updateLabel(!visible);
    });
});
