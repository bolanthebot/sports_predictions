// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const API_ENDPOINTS = {
  health: '/health',
  ready: '/ready',
  games: {
    today: '/api/nba/games/today',
  },
  teams: {
    games: '/api/nba/teams/',
    players: '/api/nba/teamplayers/',
    injuries: '/api/nba/injuries/',
  },
  players: {
    games: '/api/nba/players/',
  },
  predictions: {
    today: '/api/nba/predictions/today/',
    playerToday: '/api/nba/predictions/player/today/',
    playerBatch: '/api/nba/predictions/players/batch/',
  },
};

/**
 * Build full URL from endpoint and optional query params
 * @param {string} endpoint - The endpoint path
 * @param {object} params - Query parameters
 * @returns {string}
 */
export function buildUrl(endpoint, params = {}) {
  const url = new URL(`${API_BASE_URL}${endpoint}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.append(key, value);
    }
  });
  return url.toString();
}

/**
 * Fetch data from API with error handling
 * @param {string} endpoint - The endpoint path
 * @param {object} options - Fetch options (can include 'params' for query parameters)
 * @returns {Promise}
 */
export async function fetchAPI(endpoint, options = {}) {
  const { params, signal, ...fetchOptions } = options;
  
  try {
    const url = buildUrl(endpoint, params);
    const response = await fetch(url, {
      ...fetchOptions,
      signal,
      headers: {
        'Content-Type': 'application/json',
        ...fetchOptions.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    // Don't log abort errors
    if (error.name !== 'AbortError') {
      console.error('API call failed:', error);
    }
    throw error;
  }
}

/**
 * Check if the API is healthy
 * @returns {Promise<boolean>}
 */
export async function checkHealth() {
  try {
    await fetchAPI(API_ENDPOINTS.health);
    return true;
  } catch {
    return false;
  }
}

export { API_BASE_URL, API_ENDPOINTS };
