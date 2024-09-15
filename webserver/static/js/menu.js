document.addEventListener('DOMContentLoaded', () => {
    const menu = document.getElementById('menu');

    document.addEventListener('click', function(e) {
        if (!menu.contains(e.target)) {
            menu.classList.add('hidden');
        }
    });
});