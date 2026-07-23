async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body.detail) detail = body.detail
    } catch {
      // keep the generic status message
    }
    throw new Error(detail)
  }
  if (response.status === 204) return null
  return response.json()
}

export function getConfig() {
  return request('/api/config')
}

export function startDownload(prompt) {
  return request('/api/download', { method: 'POST', body: JSON.stringify({ prompt }) })
}

export function getDownloadJob(id) {
  return request(`/api/download/${id}`)
}

export function respondToDownloadJob(id, answer) {
  return request(`/api/download/${id}/respond`, {
    method: 'POST',
    body: JSON.stringify({ answer }),
  })
}

export function cancelDownloadJob(id) {
  return request(`/api/download/${id}/cancel`, { method: 'POST' })
}

export function startIndex() {
  return request('/api/index', { method: 'POST' })
}

export function getIndexJob(id) {
  return request(`/api/index/${id}`)
}

export function cancelIndexJob(id) {
  return request(`/api/index/${id}/cancel`, { method: 'POST' })
}

export function ask(question, filters = null) {
  const body = filters ? { question, filters } : { question }
  return request('/api/ask', { method: 'POST', body: JSON.stringify(body) })
}

export function clear(confirmed) {
  return request('/api/clear', { method: 'POST', body: JSON.stringify({ confirmed }) })
}

export function getStatus() {
  return request('/api/status')
}

export function deleteFile(pdfPath) {
  return request('/api/files/delete', {
    method: 'POST',
    body: JSON.stringify({ pdf_path: pdfPath, confirmed: true }),
  })
}
