import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../stores/auth", () => ({
  getToken: vi.fn()
}));

describe("services/api", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("adds auth + json headers for JSON requests", async () => {
    const { getToken } = await import("../stores/auth");
    getToken.mockReturnValue("abc-token");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: 1 })
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");
    await api.createRecipe({ title: "A", cuisine: "Italian", prep_minutes: 10, calories: 100, tags: [] });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/recipes");
    expect(options.method).toBe("POST");
    expect(options.headers.get("Authorization")).toBe("Bearer abc-token");
    expect(options.headers.get("Content-Type")).toBe("application/json");
  });

  it("returns null for 204 responses", async () => {
    const { getToken } = await import("../stores/auth");
    getToken.mockReturnValue("abc-token");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => ({})
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");
    const result = await api.deleteRecipe(5);

    expect(result).toBe(null);
  });

  it("formats 400 duplicate-email errors with field metadata", async () => {
    const { getToken } = await import("../stores/auth");
    getToken.mockReturnValue(null);

    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: "Email already registered" })
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");

    await expect(api.register({ email: "x@example.com", password: "StrongPass123", full_name: "X" })).rejects.toMatchObject({
      message: "An account with this email already exists. Try logging in instead.",
      fieldErrors: { email: "This email is already registered" },
      status: 400
    });
  });

  it("formats pydantic validation arrays into readable errors", async () => {
    const { getToken } = await import("../stores/auth");
    getToken.mockReturnValue("abc-token");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [
          { loc: ["body", "prep_minutes"], msg: "Input should be greater than or equal to 1" }
        ]
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");

    await expect(api.createRecipe({})).rejects.toMatchObject({
      status: 422,
      fieldErrors: {
        prep_minutes: "Input should be greater than or equal to 1"
      }
    });
  });

  it("builds rated recipes query params correctly", async () => {
    const { getToken } = await import("../stores/auth");
    getToken.mockReturnValue("abc-token");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], local_count: 0, external_count: 0 })
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");
    await api.ratedRecipes({ query: " pasta ", score: 5 });

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/recipes/rated?");
    expect(url).toContain("query=pasta");
    expect(url).toContain("score=5");
  });

  it("sends import URL payload to recipe import endpoint", async () => {
    const { getToken } = await import("../stores/auth");
    getToken.mockReturnValue("abc-token");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ title: "Imported" })
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");
    await api.importRecipeFromUrl("https://example.com/recipe");

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/recipes/import-url");
    expect(options.method).toBe("POST");
    expect(options.body).toBe(JSON.stringify({ url: "https://example.com/recipe" }));
  });

  it("calls generate weekly plan endpoint with POST", async () => {
    const { getToken } = await import("../stores/auth");
    getToken.mockReturnValue("abc-token");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: 1, status: "active", items: [] })
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");
    await api.generateWeeklyPlan();

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/users/me/weekly-plan/generate");
    expect(options.method).toBe("POST");
  });

  it("calls current weekly plan endpoint with GET", async () => {
    const { getToken } = await import("../stores/auth");
    getToken.mockReturnValue("abc-token");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: 1, status: "active", items: [] })
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");
    await api.getCurrentWeeklyPlan();

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/users/me/weekly-plan/current");
    expect(options.method).toBeUndefined();
  });

  it("calls select weekly plan option endpoint with payload", async () => {
    const { getToken } = await import("../stores/auth");
    getToken.mockReturnValue("abc-token");

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: 1, status: "active", items: [] })
    });
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");
    await api.selectWeeklyPlanOption({ dayIndex: 3, recipeSource: "themealdb" });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/users/me/weekly-plan/current/select");
    expect(options.method).toBe("POST");
    expect(options.body).toBe(JSON.stringify({ day_index: 3, recipe_source: "themealdb" }));
  });
});
