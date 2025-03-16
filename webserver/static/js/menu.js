document.addEventListener('DOMContentLoaded', () => {
    const menu = document.getElementById('menu');

    // Only add the event listener if the menu element exists
    if (menu) {
        document.addEventListener('click', function (e) {
            if (!menu.contains(e.target)) {
                menu.classList.add('hidden');
            }
        });
    }
});