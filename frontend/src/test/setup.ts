import "@testing-library/jest-dom/vitest";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

window.requestAnimationFrame = (callback: FrameRequestCallback) =>
  window.setTimeout(() => callback(performance.now()), 0);
window.cancelAnimationFrame = (id: number) => window.clearTimeout(id);

