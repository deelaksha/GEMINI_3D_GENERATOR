/**
 * Full-screen toggle for a viewport (3D or 2D). Uses the Fullscreen API where the browser supports it on
 * elements; otherwise (iPhone / iPad Safari) the view is expanded to fill the window with CSS. Esc, the same
 * button, or leaving browser full screen restores it. The viewports resize themselves (ResizeObserver).
 */
const EXPAND = '<svg><use href="#i-expand"/></svg>';
const SHRINK = '<svg><use href="#i-shrink"/></svg>';

export function bindFullscreen(view, button, onChange) {
  const native = !!(view.requestFullscreen || view.webkitRequestFullscreen);
  const isOn = () => document.fullscreenElement === view || document.webkitFullscreenElement === view ||
    view.classList.contains('is-max');

  const sync = () => {
    const on = isOn();
    button.innerHTML = on ? SHRINK : EXPAND;
    button.title = on ? 'Exit full screen (Esc)' : 'Full screen';
    button.setAttribute('aria-label', button.title);
    button.classList.toggle('on', on);
    // any view of the page may be the maximized one (each binding syncs on every fullscreenchange)
    document.body.classList.toggle('view-maximized', !!(document.fullscreenElement || document.webkitFullscreenElement ||
      document.querySelector('.is-max')));
    onChange?.(on);
  };

  const exit = () => {
    if (document.fullscreenElement === view) document.exitFullscreen?.();
    else if (document.webkitFullscreenElement === view) document.webkitExitFullscreen?.();
    view.classList.remove('is-max');
    sync();
  };

  const enter = async () => {
    if (isOn()) return;
    if (native) {
      try {
        await (view.requestFullscreen ? view.requestFullscreen() : view.webkitRequestFullscreen());
        return sync();
      } catch (e) { /* refused (e.g. iframe policy): fall back to filling the window */ }
    }
    view.classList.add('is-max');
    sync();
  };

  button.onclick = () => (isOn() ? exit() : enter());
  document.addEventListener('fullscreenchange', sync);
  document.addEventListener('webkitfullscreenchange', sync);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && view.classList.contains('is-max')) exit(); });
  sync();
  return { enter, exit, isOn };
}
