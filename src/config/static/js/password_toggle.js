document.querySelectorAll('.password-toggle').forEach(function(btn) {
    var input = btn.parentElement.querySelector('input');
    function show() { input.type = 'text'; }
    function hide() { input.type = 'password'; }
    btn.addEventListener('mousedown', function(e) { if (e.button === 0) show(); });
    btn.addEventListener('mouseup', hide);
    btn.addEventListener('mouseleave', hide);
});
