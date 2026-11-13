// A click inserts at the viewport centre. Start LogicFlow drag only after a deliberate mouse movement.
export function beginNodeGesture(down: PointerEvent, startDrag: () => void) {
  if (down.pointerType !== 'mouse' || down.button !== 0) return
  const gesture = new AbortController()
  const options = { signal: gesture.signal }
  const cancel = () => gesture.abort()
  window.addEventListener('pointerup', cancel, options)
  window.addEventListener('pointercancel', cancel, options)
  window.addEventListener('blur', cancel, options)
  window.addEventListener('pointermove', (event) => {
    if (event.pointerId !== down.pointerId) return
    if (Math.hypot(event.clientX - down.clientX, event.clientY - down.clientY) < 6) return
    cancel()
    if (event.buttons === 1) startDrag()
  }, options)
}
