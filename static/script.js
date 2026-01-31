// Force scroll to top
if (history.scrollRestoration) { history.scrollRestoration = 'manual'; }
window.scrollTo(0, 0);

const links = document.querySelectorAll('.nav-link');
const pill = document.getElementById('nav-indicator');
const sections = document.querySelectorAll('.snap-section');

// Auth state
let currentUser = null;
let isRegistering = false;

// Navigation Pill Movement
function movePill(el) {
    if (!el) return;
    pill.style.width = el.offsetWidth + 'px';
    pill.style.left = el.offsetLeft + 'px';
    links.forEach(l => l.classList.remove('active'));
    el.classList.add('active');
}

// Link Click Handlers
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

// Sign In Portal Toggle
function togglePortal() {
    document.getElementById('portal-overlay').classList.toggle('active');
}

function openAuth(role) {
    if (currentUser) {
        // User already logged in, navigate to dashboard
        window.location.href = '/dashboard';
        return;
    }

    isRegistering = false;
    const modal = document.getElementById('auth-modal');
    document.getElementById('auth-title').innerText = `${role} Portal`;
    document.getElementById('auth-subtitle').innerText = `Sign In to Continue`;
    document.getElementById('auth-form').dataset.role = role;
    modal.classList.add('active');
    document.getElementById('portal-overlay').classList.remove('active');
    document.getElementById('form-toggle').innerText = "Don't have an account? Sign Up";
    updateFormUI();
}

// Close Auth Modal
function closeAuth() {
    document.getElementById('auth-modal').classList.remove('active');
    document.getElementById('auth-form').reset();
    isRegistering = false;
    updateFormUI();
}

// Navigate to Section from Portal
function portalNavigate(sectionId) {
    togglePortal();
    const targetSection = document.getElementById(sectionId);
    if (targetSection) targetSection.scrollIntoView({ behavior: 'smooth' });
}

// Update Auth Form UI
function updateFormUI() {
    const usernameField = document.getElementById('username-field');
    const submitBtn = document.getElementById('auth-submit');
    const toggleBtn = document.getElementById('form-toggle');
    const toggleText = document.getElementById('toggle-text');

    if (isRegistering) {
        usernameField.style.display = 'block';
        submitBtn.innerText = 'Create Account';
        toggleBtn.innerText = 'Already have an account? Sign In';
        toggleText.innerText = 'Already have an account?';
        document.getElementById('auth-subtitle').innerText = 'Create New Account';
    } else {
        usernameField.style.display = 'none';
        submitBtn.innerText = 'Sign In';
        toggleBtn.innerText = 'Sign Up';
        toggleText.innerText = "Don't have an account?";
        document.getElementById('auth-subtitle').innerText = 'Sign In to Continue';
    }
}

// Toggle between Sign In and Register
function toggleAuthMode() {
    isRegistering = !isRegistering;
    document.getElementById('auth-form').reset();
    updateFormUI();
}

// Handle Auth Form Submission
async function handleAuth(e) {
    e.preventDefault();

    const email = document.getElementById('auth-email').value;
    const password = document.getElementById('auth-password').value;
    const username = document.getElementById('auth-username').value;

    if (!email || !password) {
        alert('Please fill in all fields');
        return;
    }

    const submitBtn = document.getElementById('auth-submit');
    submitBtn.disabled = true;
    submitBtn.innerText = isRegistering ? 'Creating...' : 'Signing in...';

    try {
        let response;

        if (isRegistering) {
            if (!username) {
                alert('Username is required for registration');
                return;
            }

            response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password, username })
            });

            if (response.ok) {
                const data = await response.json();
                // Auto-login after registration
                const loginResponse = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });

                if (loginResponse.ok) {
                    const loginData = await loginResponse.json();
                    currentUser = {
                        id: loginData.user_id,
                        email: loginData.email,
                        username: loginData.username
                    };
                    closeAuth();
                    // Redirect to dashboard immediately after successful registration and login
                    window.location.href = '/dashboard';
                    return;
                }
            } else {
                const error = await response.json();
                alert('Registration failed: ' + error.error);
            }
        } else {
            response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            if (response.ok) {
                const data = await response.json();
                currentUser = {
                    id: data.user_id,
                    email: data.email,
                    username: data.username
                };
                closeAuth();
                // Redirect to dashboard immediately after successful login
                window.location.href = '/dashboard';
                return;
            } else {
                const error = await response.json();
                alert('Sign in failed: ' + error.error);
            }
        }
    } catch (error) {
        alert('Error: ' + error.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = isRegistering ? 'Create Account' : 'Sign In';
    }
}

// Logout Function
async function logout() {
    try {
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        currentUser = null;
        updateSignInButton();
        alert('Signed out successfully');
    } catch (error) {
        alert('Logout error: ' + error.message);
    }
}

// Update Sign In Button UI
function updateSignInButton() {
    const signInBtn = document.getElementById('sign-in-btn');

    if (currentUser) {
        signInBtn.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="text-sm">${currentUser.username || currentUser.email}</span>
                <button onclick="logout()" class="bg-red-500/20 text-red-400 px-3 py-1 rounded-full text-xs font-bold hover:bg-red-500 hover:text-white transition-all">Logout</button>
            </div>
        `;
    } else {
        signInBtn.innerHTML = `<span onclick="togglePortal()" class="cursor-pointer">Sign In</span>`;
    }
}

// Initialize
window.addEventListener('load', () => {
    setTimeout(() => movePill(document.querySelector('.nav-link.active')), 100);
    updateSignInButton();

    // Setup auth form handler
    const authForm = document.getElementById('auth-form');
    if (authForm) {
        authForm.addEventListener('submit', handleAuth);
    }

    // Setup form toggle
    const formToggle = document.getElementById('form-toggle');
    if (formToggle) {
        formToggle.addEventListener('click', (e) => {
            e.preventDefault();
            toggleAuthMode();
        });
    }
});

// Handle window resize to adjust pill
window.addEventListener('resize', () => movePill(document.querySelector('.nav-link.active')));
window.addEventListener('keydown', (e) => {
    if (e.key === "Escape") {
        closeAuth();
        document.getElementById('portal-overlay').classList.remove('active');
    }
});