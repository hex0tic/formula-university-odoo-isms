(() => {
    const top = document.querySelector('.fu-top');
    const picker = document.querySelector('.fu-portal-picker');
    if (!top || !picker) return;
    const scrolled = () => top.classList.toggle('is-scrolled', window.scrollY > 12);
    scrolled();
    window.addEventListener('scroll', scrolled, { passive: true });
    document.addEventListener('pointerdown', (event) => {
        if (picker.open && !picker.contains(event.target)) picker.open = false;
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && picker.open) {
            picker.open = false;
            picker.querySelector('summary').focus();
        }
    });
})();
