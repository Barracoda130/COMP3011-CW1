import { beforeEach, describe, expect, it, vi } from "vitest";

function createLocalStorageMock() {
  const store = new Map();
  return {
    getItem: vi.fn((key) => (store.has(key) ? store.get(key) : null)),
    setItem: vi.fn((key, value) => {
      store.set(key, String(value));
    }),
    removeItem: vi.fn((key) => {
      store.delete(key);
    }),
    clear: vi.fn(() => {
      store.clear();
    })
  };
}

describe("stores/auth", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  it("stores, reads, and clears auth token", async () => {
    const localStorageMock = createLocalStorageMock();
    vi.stubGlobal("localStorage", localStorageMock);

    const auth = await import("./auth");

    expect(auth.getToken()).toBe(null);
    expect(auth.isAuthenticated()).toBe(false);

    auth.setToken("token-123");

    expect(localStorageMock.setItem).toHaveBeenCalledWith("meal_api_token", "token-123");
    expect(auth.getToken()).toBe("token-123");
    expect(auth.isAuthenticated()).toBe(true);

    auth.clearToken();

    expect(localStorageMock.removeItem).toHaveBeenCalledWith("meal_api_token");
    expect(auth.getToken()).toBe(null);
    expect(auth.isAuthenticated()).toBe(false);
  });

  it("hydrates token from localStorage on module load", async () => {
    const localStorageMock = createLocalStorageMock();
    localStorageMock.getItem.mockReturnValue("persisted-token");
    vi.stubGlobal("localStorage", localStorageMock);

    const auth = await import("./auth");

    expect(auth.getToken()).toBe("persisted-token");
    expect(auth.isAuthenticated()).toBe(true);
  });
});
