type DialogKind = 'info' | 'danger' | 'confirm' | 'prompt'

function openDialog(kind: DialogKind, title: string, message = '', initialValue = ''): Promise<string | boolean> {
  return new Promise(resolve => {
    const overlay = document.createElement('div')
    overlay.className = 'icms-dialog-backdrop'
    const dialog = document.createElement('section')
    dialog.className = `icms-dialog icms-dialog-${kind}`
    dialog.setAttribute('role', 'dialog'); dialog.setAttribute('aria-modal', 'true'); dialog.setAttribute('aria-label', title)
    const heading = document.createElement('h3'); heading.textContent = title
    const copy = document.createElement('p'); copy.textContent = message
    const actions = document.createElement('footer'); actions.className = 'icms-dialog-actions'
    let input: HTMLTextAreaElement | null = null
    if (kind === 'prompt') { input = document.createElement('textarea'); input.className = 'inp'; input.value = initialValue; input.rows = 4; input.placeholder = 'Enter a reason or note'; dialog.append(heading, copy, input) } else dialog.append(heading, copy)
    const close = (value: string | boolean) => { document.removeEventListener('keydown', keydown); overlay.remove(); resolve(value) }
    const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'btn btn-out'; cancel.textContent = kind === 'info' || kind === 'danger' ? 'Close' : 'Cancel'; cancel.onclick = () => close(kind === 'prompt' ? '' : false)
    const proceed = document.createElement('button'); proceed.type = 'button'; proceed.className = `btn ${kind === 'danger' ? 'btn-crimson' : 'btn-brass'}`; proceed.textContent = kind === 'info' || kind === 'danger' ? 'Close' : kind === 'prompt' ? 'Continue' : 'Confirm'; proceed.onclick = () => close(kind === 'prompt' ? (input?.value.trim() || '') : true)
    if (kind === 'info' || kind === 'danger') actions.append(proceed); else actions.append(cancel, proceed)
    dialog.append(actions); overlay.append(dialog); document.body.append(overlay)
    const keydown = (event: KeyboardEvent) => { if (event.key === 'Escape') close(kind === 'prompt' ? '' : false) }
    document.addEventListener('keydown', keydown); overlay.addEventListener('click', event => { if (event.target === overlay) close(kind === 'prompt' ? '' : false) })
    window.setTimeout(() => (input || proceed).focus(), 0)
  })
}

export const appAlert = (message: string, title = 'Update') => openDialog('info', title, message) as Promise<boolean>
export const appError = (message: string, title = 'Unable to complete action') => openDialog('danger', title, message) as Promise<boolean>
export const appConfirm = (message: string, title = 'Confirm action') => openDialog('confirm', title, message) as Promise<boolean>
export const appPrompt = (message: string, title = 'Provide details', initialValue = '') => openDialog('prompt', title, message, initialValue) as Promise<string>
