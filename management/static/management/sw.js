// OBATEK Service Worker for Offline Support
const CACHE_NAME = 'obatek-v3';
const OFFLINE_URL = '/offline/';

// Assets to cache immediately on install
const PRECACHE_ASSETS = [
  '/',
  '/dashboard/',
  '/calendar/',
  '/offline/',
  '/pending/',
  '/static/management/manifest.json',
];

// Install event - cache core assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Caching core assets');
        return cache.addAll(PRECACHE_ASSETS);
      })
      .then(() => {
        return self.skipWaiting();
      })
      .catch((error) => {
        console.log('[SW] Cache failed:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      return self.clients.claim();
    })
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests (let POST requests go through normally when online)
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip admin and API requests
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/admin/') ||
      url.pathname.startsWith('/api/') ||
      url.pathname.includes('__debug__')) {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then((cachedResponse) => {
        if (cachedResponse) {
          // Update cache in background
          fetch(event.request)
            .then((response) => {
              if (response && response.status === 200) {
                const responseClone = response.clone();
                caches.open(CACHE_NAME).then((cache) => {
                  cache.put(event.request, responseClone);
                });
              }
            })
            .catch(() => {});

          return cachedResponse;
        }

        return fetch(event.request)
          .then((response) => {
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseClone);
            });

            return response;
          })
          .catch((error) => {
            console.log('[SW] Fetch failed:', error);

            if (event.request.mode === 'navigate') {
              return caches.match(OFFLINE_URL);
            }

            return new Response('Offline', {
              status: 503,
              statusText: 'Service Unavailable',
              headers: new Headers({ 'Content-Type': 'text/plain' }),
            });
          });
      })
  );
});

// ================================
// BACKGROUND SYNC FOR TIMESHEETS
// ================================

self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-timesheets') {
    console.log('[SW] Background sync triggered');
    event.waitUntil(syncPendingTimesheets());
  }
});

async function syncPendingTimesheets() {
  const db = await openDatabase();
  const timesheets = await getAllPending(db);

  console.log('[SW] Found', timesheets.length, 'pending timesheets');

  for (const entry of timesheets) {
    try {
      // Reconstruct FormData
      const formData = new FormData();
      for (const [key, value] of Object.entries(entry.data)) {
        formData.append(key, value);
      }

      const response = await fetch('/dashboard/', {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': entry.csrfToken
        }
      });

      if (response.ok || response.redirected) {
        await deletePending(db, entry.id);
        console.log('[SW] Synced timesheet ID:', entry.id);

        // Notify all clients
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
          client.postMessage({
            type: 'TIMESHEET_SYNCED',
            id: entry.id,
            success: true
          });
        });
      }
    } catch (error) {
      console.log('[SW] Failed to sync timesheet:', error);
    }
  }
}

// ================================
// INDEXED DB HELPERS
// ================================

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('obatek-offline', 2);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('pending-timesheets')) {
        const store = db.createObjectStore('pending-timesheets', { keyPath: 'id', autoIncrement: true });
        store.createIndex('timestamp', 'timestamp', { unique: false });
      }
    };
  });
}

function getAllPending(db) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['pending-timesheets'], 'readonly');
    const store = transaction.objectStore('pending-timesheets');
    const request = store.getAll();

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

function deletePending(db, id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['pending-timesheets'], 'readwrite');
    const store = transaction.objectStore('pending-timesheets');
    const request = store.delete(id);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// Listen for messages from the main app
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  // Manual sync trigger
  if (event.data && event.data.type === 'SYNC_NOW') {
    syncPendingTimesheets();
  }
});
