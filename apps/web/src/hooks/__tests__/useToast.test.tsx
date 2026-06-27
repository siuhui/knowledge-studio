import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { ToastProvider, useToast } from "@/hooks/useToast";
import { createElement } from "react";

function wrapper({ children }: { children: React.ReactNode }) {
  return createElement(ToastProvider, null, children);
}

describe("useToast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("throws when used outside ToastProvider", () => {
    expect(() => renderHook(() => useToast())).toThrow(
      "useToast must be used within a ToastProvider",
    );
  });

  it("adds a toast", () => {
    const { result } = renderHook(() => useToast(), { wrapper });

    act(() => {
      result.current.addToast("success", "Test message");
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0]).toMatchObject({
      type: "success",
      message: "Test message",
    });
    expect(result.current.toasts[0].id).toBeTruthy();
  });

  it("adds multiple toasts", () => {
    const { result } = renderHook(() => useToast(), { wrapper });

    act(() => {
      result.current.addToast("success", "First");
      result.current.addToast("error", "Second");
    });

    expect(result.current.toasts).toHaveLength(2);
    expect(result.current.toasts[0].type).toBe("success");
    expect(result.current.toasts[1].type).toBe("error");
  });

  it("removes a toast by id", () => {
    const { result } = renderHook(() => useToast(), { wrapper });

    act(() => {
      result.current.addToast("success", "Test");
    });

    const id = result.current.toasts[0].id;

    act(() => {
      result.current.removeToast(id);
    });

    expect(result.current.toasts).toHaveLength(0);
  });

  it("auto-dismisses toasts after timeout", () => {
    const { result } = renderHook(() => useToast(), { wrapper });

    act(() => {
      result.current.addToast("success", "Will disappear");
    });

    expect(result.current.toasts).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(result.current.toasts).toHaveLength(0);
  });
});
