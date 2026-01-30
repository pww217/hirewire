/**
 * API client composable with error handling
 */
import type { ValidationError } from '@/types/api'

interface ApiOptions {
  showErrorToast?: boolean
}

/**
 * API client composable with error handling
 */
export function useApi() {
  
  async function request<T>(
    method: string,
    endpoint: string,
    data?: Record<string, unknown>,
    options: ApiOptions = {}
  ): Promise<T> {
    const { showErrorToast = true } = options
    
    const url = new URL(endpoint, window.location.origin)
    
    const fetchOptions: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    }
    
    // For GET requests, add params to URL
    if (method === 'GET' && data) {
      Object.entries(data).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          if (Array.isArray(value)) {
            value.forEach(v => url.searchParams.append(key, String(v)))
          } else {
            url.searchParams.set(key, String(value))
          }
        }
      })
    }
    
    // For other methods, add body
    if (method !== 'GET' && data) {
      fetchOptions.body = JSON.stringify(data)
    }
    
    try {
      const response = await fetch(url.toString(), fetchOptions)
      
      if (!response.ok) {
        let errorMessage = `Request failed: ${response.status}`
        try {
          const errorData = await response.json()
          if (Array.isArray(errorData.detail)) {
            // Format validation errors (422)
            errorMessage = errorData.detail.map((e: ValidationError) => e.msg).join('; ')
          } else {
            errorMessage = errorData.detail || errorMessage
          }
        } catch {
          // Ignore JSON parse errors
        }
        throw new Error(errorMessage)
      }
      
      // Handle 204 No Content
      if (response.status === 204) {
        return undefined as T
      }
      
      return await response.json() as T
    } catch (error) {
      if (showErrorToast) {
        // We'll import ui store dynamically to avoid circular dependencies
        const { useUIStore } = await import('@/stores/ui')
        const uiStore = useUIStore()
        const message = error instanceof Error ? error.message : 'An error occurred'
        uiStore.showError(message)
      }
      throw error
    }
  }
  
  return {
    get: <T>(endpoint: string, params?: Record<string, unknown>, options?: ApiOptions) =>
      request<T>('GET', endpoint, params, options),
      
    post: <T>(endpoint: string, data?: Record<string, unknown>, options?: ApiOptions) =>
      request<T>('POST', endpoint, data, options),
      
    put: <T>(endpoint: string, data?: Record<string, unknown>, options?: ApiOptions) =>
      request<T>('PUT', endpoint, data, options),
      
    delete: <T>(endpoint: string, options?: ApiOptions) =>
      request<T>('DELETE', endpoint, undefined, options),
  }
}
