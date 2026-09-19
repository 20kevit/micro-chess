// Map backend auth failures to Persian UI strings. The server stays
// generic on purpose (no username enumeration); this only translates
// the machine-readable error.code for display.
import { apiCode, apiStatus } from "../api/client";
import type { FaKey } from "../i18n/fa";

export function authErrorKey(e: unknown): FaKey {
  switch (apiCode(e)) {
    case "INVALID_CREDENTIALS":
      return "auth.error.invalid";
    case "USERNAME_TAKEN":
      return "auth.error.taken";
    case "USERNAME_INVALID":
      return "auth.error.invalidUsername";
    case "PASSWORD_TOO_SHORT":
      return "auth.error.shortPassword";
    case "PASSWORD_TOO_LONG":
      return "auth.error.longPassword";
    case "RATE_LIMITED":
      return "auth.error.rateLimited";
    case "ROLE_SELECTION_REQUIRED":
      return "auth.error.roleRequired";
    case "INVALID_ROLE":
      return "auth.error.invalidRole";
    default:
      return apiStatus(e) === 401 ? "auth.error.invalid" : "common.error";
  }
}
