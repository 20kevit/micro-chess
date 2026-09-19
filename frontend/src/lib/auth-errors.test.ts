import { describe, expect, it } from "vitest";
import { authErrorKey } from "./auth-errors";

function coded(code: string, status = 400): Error {
  const err = new Error(`api_error:${status}`) as Error & { code: string; status: number };
  err.code = code;
  err.status = status;
  return err;
}

describe("authErrorKey", () => {
  it("maps short and long passwords to distinct Persian keys", () => {
    expect(authErrorKey(coded("PASSWORD_TOO_SHORT"))).toBe("auth.error.shortPassword");
    expect(authErrorKey(coded("PASSWORD_TOO_LONG"))).toBe("auth.error.longPassword");
  });

  it("maps known auth failures", () => {
    expect(authErrorKey(coded("INVALID_CREDENTIALS", 401))).toBe("auth.error.invalid");
    expect(authErrorKey(coded("USERNAME_TAKEN"))).toBe("auth.error.taken");
    expect(authErrorKey(coded("USERNAME_INVALID"))).toBe("auth.error.invalidUsername");
    expect(authErrorKey(coded("RATE_LIMITED", 429))).toBe("auth.error.rateLimited");
  });

  it("falls back to invalid on bare 401 and generic otherwise", () => {
    const bare401 = new Error("api_error:401") as Error & { status: number };
    bare401.status = 401;
    expect(authErrorKey(bare401)).toBe("auth.error.invalid");
    expect(authErrorKey(new Error("boom"))).toBe("common.error");
  });
});
