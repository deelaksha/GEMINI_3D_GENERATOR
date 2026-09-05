/**
 * Universal Toast & Notification Utility
 */
export const Toast = {
  timeoutId: null,

  show(message, icon = '✨', duration = 2600) {
    let container = document.getElementById('global-toast');
    if (!container) {
      container = document.createElement('div');
      container.id = 'global-toast';
      container.className = 'fixed bottom-8 left-1/2 -translate-x-1/2 z-50 pointer-events-none opacity-0 transition-all duration-300 transform translate-y-2 bg-slate-900/95 border border-sky-500/50 text-sky-200 text-xs px-4 py-2.5 rounded-full shadow-2xl backdrop-blur flex items-center gap-2';
      document.body.appendChild(container);
    }

    container.innerHTML = `<span class="text-sm">${icon}</span><span class="font-medium">${message}</span>`;
    container.classList.remove('opacity-0', 'translate-y-2');
    container.classList.add('opacity-100', 'translate-y-0');

    if (this.timeoutId) clearTimeout(this.timeoutId);
    this.timeoutId = setTimeout(() => {
      container.classList.remove('opacity-100', 'translate-y-0');
      container.classList.add('opacity-0', 'translate-y-2');
    }, duration);
  }
};
