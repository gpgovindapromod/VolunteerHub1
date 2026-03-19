/* ── VOLUNTEER HUB — Main JS ── */

document.addEventListener('DOMContentLoaded', () => {

  /* ── THEME ── */
  const html = document.documentElement;
  const themeBtn = document.getElementById('themeToggle');
  const themeIcon = document.getElementById('themeIcon');
  function applyTheme(mode) {
    mode === 'light' ? html.classList.add('light') : html.classList.remove('light');
    if (themeIcon) themeIcon.className = mode === 'light' ? 'ri-moon-line' : 'ri-sun-line';
    localStorage.setItem('vh-theme', mode);
  }
  applyTheme(localStorage.getItem('vh-theme') || 'dark');
  themeBtn?.addEventListener('click', () => applyTheme(html.classList.contains('light') ? 'dark' : 'light'));

  /* ── NAVBAR SCROLL ── */
  const navbar = document.getElementById('navbar');
  const onScroll = () => navbar?.classList.toggle('scrolled', window.scrollY > 30);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ── SCROLL PROGRESS ── */
  const pb = document.getElementById('progressBar');
  if (pb) {
    window.addEventListener('scroll', () => {
      pb.style.width = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight) * 100) + '%';
    }, { passive: true });
  }

  /* ── BACK TO TOP ── */
  const bt = document.getElementById('backTop');
  if (bt) {
    window.addEventListener('scroll', () => bt.classList.toggle('visible', window.scrollY > 500), { passive: true });
    bt.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
  }

  /* ── SCROLL REVEAL ── */
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); io.unobserve(e.target); } });
  }, { threshold: 0.1 });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));

  /* ── CURSOR TRAIL ── */
  (function () {
    if (window.matchMedia('(hover: none)').matches) return;
    const canvas = document.getElementById('cursor-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let W = canvas.width = window.innerWidth, H = canvas.height = window.innerHeight;
    window.addEventListener('resize', () => { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; });
    const pts = [];
    window.addEventListener('mousemove', e => {
      pts.push({ x: e.clientX, y: e.clientY, life: 1.0 });
      if (pts.length > 28) pts.shift();
    }, { passive: true });
    function isLight() { return document.documentElement.classList.contains('light'); }
    (function draw() {
      ctx.clearRect(0, 0, W, H);
      for (let i = 0; i < pts.length; i++) pts[i].life -= 0.035;
      while (pts.length && pts[0].life <= 0) pts.shift();
      for (let i = 1; i < pts.length; i++) {
        const p0 = pts[i - 1], p1 = pts[i], t = i / pts.length;
        const alpha = p1.life * t * (isLight() ? 0.22 : 0.30);
        const g = ctx.createLinearGradient(p0.x, p0.y, p1.x, p1.y);
        g.addColorStop(0, `rgba(106,17,203,${alpha * 0.8})`);
        g.addColorStop(1, `rgba(255,65,108,${alpha})`);
        ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y);
        ctx.strokeStyle = g; ctx.lineWidth = 2.2 * t * p1.life; ctx.lineCap = 'round'; ctx.stroke();
      }
      if (pts.length) {
        const last = pts[pts.length - 1];
        ctx.beginPath(); ctx.arc(last.x, last.y, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,65,108,${last.life * 0.6})`; ctx.fill();
      }
      requestAnimationFrame(draw);
    })();
  })();

  /* ── 3D TILT ── */
  document.querySelectorAll('.feat-card').forEach(card => {
    card.addEventListener('mousemove', e => {
      const r = card.getBoundingClientRect();
      card.style.transform = `translateY(-6px) rotateX(${-(e.clientY - r.top - r.height / 2) / 18}deg) rotateY(${(e.clientX - r.left - r.width / 2) / 18}deg)`;
    });
    card.addEventListener('mouseleave', () => card.style.transform = '');
  });

  /* ── SIDEBAR TOGGLE (desktop) ── */
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      const sp = sidebarToggle.querySelector('span');
      if (sp) sp.textContent = sidebar.classList.contains('collapsed') ? '›' : '‹';
    });
  }

  /* ── SIDEBAR TOGGLE (mobile) ── */
  const hamburger = document.getElementById('hamburger');
  const overlay = document.getElementById('sidebarOverlay');
  if (hamburger && sidebar) {
    hamburger.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
      overlay?.classList.toggle('active');
    });
  }
  overlay?.addEventListener('click', () => {
    sidebar?.classList.remove('mobile-open');
    overlay.classList.remove('active');
  });

  /* ── FLASH AUTO-DISMISS ── */
  document.querySelectorAll('.alert[data-autodismiss]').forEach(a => {
    setTimeout(() => { a.style.opacity = '0'; a.style.transform = 'translateX(24px)'; a.style.transition = 'all 0.4s'; setTimeout(() => a.remove(), 400); }, 4000);
  });

  /* ── MODALS ── */
  document.querySelectorAll('[data-modal-open]').forEach(t => {
    t.addEventListener('click', () => document.getElementById(t.dataset.modalOpen)?.classList.add('active'));
  });
  document.querySelectorAll('[data-modal-close]').forEach(b => {
    b.addEventListener('click', () => b.closest('.modal-overlay')?.classList.remove('active'));
  });
  document.querySelectorAll('.modal-overlay').forEach(o => {
    o.addEventListener('click', e => { if (e.target === o) o.classList.remove('active'); });
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.querySelectorAll('.modal-overlay.active').forEach(o => o.classList.remove('active'));
  });

  /* ── FORM VALIDATION ── */
  document.querySelectorAll('form[data-validate]').forEach(form => {
    form.addEventListener('submit', e => {
      let ok = true;
      form.querySelectorAll('[required]').forEach(f => {
        const err = document.getElementById(f.id + '-error');
        if (!f.value.trim()) {
          ok = false; f.style.borderColor = 'var(--pink)';
          if (err) { err.textContent = 'Required.'; err.classList.add('show'); }
        } else {
          f.style.borderColor = '';
          if (err) err.classList.remove('show');
        }
        if (f.type === 'email' && f.value && !/\S+@\S+\.\S+/.test(f.value)) {
          ok = false; f.style.borderColor = 'var(--pink)';
          if (err) { err.textContent = 'Invalid email.'; err.classList.add('show'); }
        }
        if (f.id === 'confirm_password') {
          const pw = document.getElementById('password');
          if (pw && f.value !== pw.value) {
            ok = false; f.style.borderColor = 'var(--pink)';
            if (err) { err.textContent = "Passwords don't match."; err.classList.add('show'); }
          }
        }
      });
      if (!ok) e.preventDefault();
    });
    form.querySelectorAll('[required]').forEach(f => f.addEventListener('input', () => {
      f.style.borderColor = '';
      document.getElementById(f.id + '-error')?.classList.remove('show');
    }));
  });

  /* ── DYNAMIC ROLE FIELDS ── */
  const rolesContainer = document.getElementById('rolesContainer');
  const addRoleBtn = document.getElementById('addRoleBtn');
  if (addRoleBtn && rolesContainer) {
    function addRemoveListeners(row) {
      row.querySelector('.remove-role')?.addEventListener('click', () => row.remove());
    }
    rolesContainer.querySelectorAll('.role-row').forEach(addRemoveListeners);
    addRoleBtn.addEventListener('click', () => {
      const row = document.createElement('div');
      row.className = 'role-row';
      row.innerHTML = `
        <input type="text" name="role_name[]" class="form-control" placeholder="Role name" required>
        <input type="number" name="role_count[]" class="form-control" placeholder="Count" style="max-width:100px;" min="1" required>
        <button type="button" class="btn btn-danger btn-sm remove-role" style="flex-shrink:0;"><i class="ri-close-line"></i></button>`;
      rolesContainer.appendChild(row);
      addRemoveListeners(row);
    });
  }

  /* ── SKILL TAGS ── */
  const skillInput = document.getElementById('skillInput');
  const skillTagsEl = document.getElementById('skillTags');
  const skillHidden = document.getElementById('skills');
  if (skillInput && skillTagsEl && skillHidden) {
    let skills = skillHidden.value ? skillHidden.value.split(',').map(s => s.trim()).filter(Boolean) : [];
    function renderSkills() {
      skillTagsEl.innerHTML = skills.map(s =>
        `<span class="skill-tag">${s} <span style="cursor:pointer;margin-left:4px;" data-rm="${s}">×</span></span>`
      ).join('');
      skillHidden.value = skills.join(',');
      skillTagsEl.querySelectorAll('[data-rm]').forEach(x =>
        x.addEventListener('click', () => { skills = skills.filter(sk => sk !== x.dataset.rm); renderSkills(); })
      );
    }
    renderSkills();
    skillInput.addEventListener('keydown', e => {
      if ((e.key === 'Enter' || e.key === ',') && skillInput.value.trim()) {
        e.preventDefault();
        const v = skillInput.value.trim().replace(/,/g, '');
        if (v && !skills.includes(v)) { skills.push(v); renderSkills(); }
        skillInput.value = '';
      }
    });
  }

  /* ── TABLE SEARCH ── */
  document.getElementById('tableSearch')?.addEventListener('input', function () {
    const q = this.value.toLowerCase();
    document.querySelectorAll('[data-searchable] tbody tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });

  /* ── MARK ALL PRESENT ── */
  document.getElementById('markAllPresent')?.addEventListener('click', () => {
    document.querySelectorAll('.attendance-check').forEach(cb => cb.checked = true);
  });

  /* ── TOGGLE ORG FIELDS (register) ── */
  const roleSelect = document.getElementById('role');
  if (roleSelect) {
    function toggleFields(role) {
      const org = document.getElementById('orgFields');
      const vol = document.getElementById('volunteerFields');
      const lbl = document.getElementById('name-label');
      if (org) org.style.display = role === 'organization' ? 'block' : 'none';
      if (vol) vol.style.display = role === 'organization' ? 'none' : 'block';
      if (lbl) lbl.textContent = role === 'organization' ? 'Organization Name' : 'Full Name';
    }
    roleSelect.addEventListener('change', () => toggleFields(roleSelect.value));
    if (roleSelect.value) toggleFields(roleSelect.value);
  }

  /* ── SMOOTH SCROLL ── */
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    });
  });

  /* ── STAGGER CARDS ── */
  document.querySelectorAll('.cards-grid .feat-card, .stats-grid .stat-card').forEach((el, i) => {
    el.style.transitionDelay = `${i * 0.07}s`;
  });

  /* ── BUTTON RIPPLE ── */
  document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', function (e) {
      const r = this.getBoundingClientRect(), size = Math.max(r.width, r.height) * 2;
      const ripple = document.createElement('span');
      ripple.style.cssText = `position:absolute;border-radius:50%;pointer-events:none;width:${size}px;height:${size}px;left:${e.clientX - r.left - size / 2}px;top:${e.clientY - r.top - size / 2}px;background:rgba(255,255,255,0.18);transform:scale(0);animation:rippleAnim 0.55s ease forwards;`;
      if (!document.getElementById('ripple-style')) {
        const s = document.createElement('style'); s.id = 'ripple-style';
        s.textContent = '@keyframes rippleAnim{to{transform:scale(1);opacity:0}}'; document.head.appendChild(s);
      }
      this.appendChild(ripple); setTimeout(() => ripple.remove(), 600);
    });
  });

});
function setRole(inputId, role, btn, toggleId) {
  document.getElementById(inputId).value = role;
  document.querySelectorAll('#' + toggleId + ' .role-toggle-btn')
    .forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

function setRegRole(role, btn) {
  document.getElementById('reg-role').value = role;
  document.querySelectorAll('#reg-toggle .role-toggle-btn')
    .forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const isOrg = role === 'organization';
  document.getElementById('orgFields').style.display = isOrg ? 'block' : 'none';
  document.getElementById('volunteerFields').style.display = isOrg ? 'none' : 'block';
  document.getElementById('name-label').textContent = isOrg ? 'Organization Name' : 'Full Name';
}