// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const API_ENDPOINTS = {
  games: {
    today: '/api/nba/games/today',
  },
  teams: {
    games: '/api/nba/teams/',
    players: '/api/nba/teamplayers/',
  },
  players: {
    games: '/api/nba/players/',
  },
  predictions: {
    today: '/api/nba/predictions/today/',
    playerToday: '/api/nba/predictions/player/today/',
  },
};

/**
 * Fetch data from API with error handling
 * @param {string} endpoint - The endpoint path
 * @param {object} options - Fetch options
 * @returns {Promise}
 */
export async function fetchAPI(endpoint, options = {}) {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('API call failed:', error);
    throw error;
  }
}

export { API_BASE_URL, API_ENDPOINTS };
