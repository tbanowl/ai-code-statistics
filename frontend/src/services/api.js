const BASE_URL = '/api/stats'

async function requestJson(url, options = {}) {
  const response = await fetch(url, options)
  return response.json()
}

export async function fetchRepositories(params = {}) {
  const query = new URLSearchParams(params).toString()
  return requestJson(`${BASE_URL}/repositories?${query}`)
}

export async function fetchContributors(params = {}) {
  const query = new URLSearchParams(params).toString()
  return requestJson(`${BASE_URL}/contributors?${query}`)
}

export async function fetchStats(params = {}) {
  const query = new URLSearchParams(params).toString()
  return requestJson(`${BASE_URL}/stats?${query}`)
}

export async function fetchDailyStats(params = {}) {
  const query = new URLSearchParams(params).toString()
  return requestJson(`${BASE_URL}/stats/daily?${query}`)
}

export async function triggerAggregate(data = {}) {
  return requestJson(`${BASE_URL}/stats/aggregate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
}
