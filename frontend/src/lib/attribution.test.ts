import { beforeEach, describe, expect, it } from "vitest";
import {
  buildRegisterAttribution,
  captureAttribution,
  getStoredAttribution,
  parseAttributionSearch,
} from "./attribution";

beforeEach(() => {
  localStorage.clear();
});

describe("parseAttributionSearch", () => {
  it("reads campaign and coupon params", () => {
    expect(parseAttributionSearch("?campaign=abadeh-chess-group&coupon=ABADEH1405")).toEqual({
      campaign_slug: "abadeh-chess-group",
      coupon_code: "ABADEH1405",
      landing_path: null,
    });
  });

  it("treats ref as a campaign alias", () => {
    expect(parseAttributionSearch("?ref=shiraz1405")).toEqual({
      campaign_slug: "shiraz1405",
      coupon_code: "SHIRAZ1405",
      landing_path: null,
    });
  });

  it("returns null when no marketing params exist", () => {
    expect(parseAttributionSearch("?page=2")).toBeNull();
    expect(parseAttributionSearch("")).toBeNull();
  });
});

describe("captureAttribution", () => {
  it("persists the first touch with landing path", () => {
    const stored = captureAttribution("?coupon=ABADEH1405", "/?coupon=ABADEH1405");
    expect(stored?.first.coupon_code).toBe("ABADEH1405");
    expect(stored?.first.landing_path).toBe("/?coupon=ABADEH1405");
    expect(getStoredAttribution()).toEqual(stored);
  });

  it("preserves first-touch and refreshes last-touch", () => {
    captureAttribution("?campaign=abadeh-chess-group&coupon=ABADEH1405", "/");
    const second = captureAttribution("?campaign=instagram", "/pricing");
    expect(second?.first.coupon_code).toBe("ABADEH1405");
    expect(second?.first.campaign_slug).toBe("abadeh-chess-group");
    expect(second?.last.campaign_slug).toBe("instagram");
    expect(second?.last.coupon_code).toBeNull();
  });

  it("survives reloads via localStorage, not React memory", () => {
    captureAttribution("?coupon=TELEGRAM1405", "/");
    // Simulate a reload: module-level memory is irrelevant; storage remains.
    expect(getStoredAttribution()?.first.coupon_code).toBe("TELEGRAM1405");
    expect(buildRegisterAttribution()).toEqual({
      coupon_code: "TELEGRAM1405",
      landing_path: "/",
    });
  });

  it("returns stored value when the URL carries nothing", () => {
    captureAttribution("?coupon=GROUP-A", "/");
    const again = captureAttribution("", "/register");
    expect(again?.first.coupon_code).toBe("GROUP-A");
  });
});
