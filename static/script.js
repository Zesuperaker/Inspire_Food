// Force scroll to top
if (history.scrollRestoration) { history.scrollRestoration = 'manual'; }
window.scrollTo(0, 0);

const links = document.querySelectorAll('.nav-link');
const pill = document.getElementById('nav-indicator');
const sections = document.querySelectorAll('.snap-section');

function movePill(el) {
    if (!el) return;
    pill.style.width = el.offsetWidth + 'px';
    pill.style.left = el.offsetLeft + 'px';
    links.forEach(l => l.classList.remove('active'));
    el.classList.add('active');
}

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const id = entry.target.getAttribute('id');
            const correspondingLink = document.querySelector(`.nav-link[data-section="${id}"]`);
            if (correspondingLink) movePill(correspondingLink);
        }
    });
}, { threshold: 0.6 });
sections.forEach(section => observer.observe(section));

function togglePortal() {
    document.getElementById('portal-overlay').classList.toggle('active');
}

function openAuth(role) {
    const modal = document.getElementById('auth-modal');
    document.getElementById('auth-title').innerText = `${role} Portal`;
    document.getElementById('auth-subtitle').innerText = `Secure Demo Authentication`;
    modal.classList.add('active');
    document.getElementById('portal-overlay').classList.remove('active');
}

function closeAuth() {
    document.getElementById('auth-modal').classList.remove('active');
}

function portalNavigate(sectionId) {
    togglePortal();
    const targetSection = document.getElementById(sectionId);
    if (targetSection) targetSection.scrollIntoView({ behavior: 'smooth' });
}

window.addEventListener('load', () => setTimeout(() => movePill(document.querySelector('.nav-link.active')), 100));
window.addEventListener('resize', () => movePill(document.querySelector('.nav-link.active')));
window.addEventListener('keydown', (e) => {
    if (e.key === "Escape") {
        closeAuth();
        document.getElementById('portal-overlay').classList.remove('active');
    }
});