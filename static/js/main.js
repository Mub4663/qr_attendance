// ── Modal toggle ─────────────────────────────
function toggleModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.toggle('hidden');
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal')) {
    e.target.classList.add('hidden');
  }
});

// ── Auto-dismiss flash messages after 4s ─────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash').forEach(flash => {
    setTimeout(() => flash.remove(), 4000);
  });
});
