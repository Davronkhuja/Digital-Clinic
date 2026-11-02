// Phone mask: +998 XX XXX-XX-XX
export function usePhoneMask() {
  function maskPhone(raw) {
    // Remove everything except digits
    const digits = raw.replace(/\D/g, '')
    // Remove leading 998 if present
    const local = digits.startsWith('998') ? digits.slice(3) : digits
    // Build mask
    let result = '+998'
    if (local.length > 0) result += ' ' + local.slice(0, 2)
    if (local.length > 2) result += ' ' + local.slice(2, 5)
    if (local.length > 5) result += '-' + local.slice(5, 7)
    if (local.length > 7) result += '-' + local.slice(7, 9)
    return result
  }

  function onPhoneInput(event, modelSetter) {
    const raw = event.target.value
    const masked = maskPhone(raw)
    modelSetter(masked)
    // Keep cursor at end
    setTimeout(() => {
      event.target.value = masked
      event.target.setSelectionRange(masked.length, masked.length)
    }, 0)
  }

  function onPhoneKeydown(event) {
    // Allow: backspace, delete, tab, escape, arrows, home, end
    const allowed = ['Backspace', 'Delete', 'Tab', 'Escape', 'ArrowLeft', 'ArrowRight', 'Home', 'End']
    if (allowed.includes(event.key)) return
    // Allow digits only
    if (!/^\d$/.test(event.key)) event.preventDefault()
    // Max 9 local digits = +998 + 9
    const digits = event.target.value.replace(/\D/g, '')
    const local = digits.startsWith('998') ? digits.slice(3) : digits
    if (local.length >= 9 && /^\d$/.test(event.key)) event.preventDefault()
  }

  return { maskPhone, onPhoneInput, onPhoneKeydown }
}