export function csrf() { return decodeURIComponent(document.cookie.split('; ').find(x => x.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '') }
export async function api(path, options = {}) {
  const { body, blob, ...rest } = options
  const form = body instanceof FormData
  const response = await fetch('/api/' + path, {credentials:'same-origin', ...rest, headers:{...(form ? {} : {'Content-Type':'application/json'}), 'X-CSRFToken':csrf(), ...rest.headers}, ...(body !== undefined ? {body:form ? body : JSON.stringify(body)} : {})})
  if (!response.ok) {
    let data
    try { data = await response.json() } catch { data = {detail:'Request failed (' + response.status + ').'} }
    const message = data.detail || Object.entries(data).map(([k,v]) => k.replaceAll('_',' ') + ': ' + (Array.isArray(v) ? v.join(' ') : v)).join('\n')
    throw new Error(Array.isArray(message) ? message.join(' ') : String(message))
  }
  if (blob) return response.blob()
  return response.status === 204 ? null : response.json()
}
export function download(blob, name) { const url = URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(url),10000) }
