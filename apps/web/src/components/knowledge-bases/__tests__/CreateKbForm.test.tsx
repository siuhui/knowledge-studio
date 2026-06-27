import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateKbForm } from "@/components/knowledge-bases/CreateKbForm";
import { ToastProvider } from "@/hooks/useToast";

// Mock the api module
vi.mock("@/lib/api", () => ({
  api: vi.fn(),
  apiPaginated: vi.fn(),
}));

import { api } from "@/lib/api";

function Wrapper({ children }: { children: React.ReactNode }) {
  return <ToastProvider>{children}</ToastProvider>;
}

describe("CreateKbForm", () => {
  const onCreated = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the form", () => {
    render(<CreateKbForm onCreated={onCreated} />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText("Knowledge base name")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Description (optional)")).toBeInTheDocument();
    expect(screen.getByText("Create")).toBeInTheDocument();
  });

  it("disables create button when name is empty", () => {
    render(<CreateKbForm onCreated={onCreated} />, { wrapper: Wrapper });
    expect(screen.getByText("Create")).toBeDisabled();
  });

  it("enables button when name is filled", async () => {
    const user = userEvent.setup();
    render(<CreateKbForm onCreated={onCreated} />, { wrapper: Wrapper });
    await user.type(screen.getByPlaceholderText("Knowledge base name"), "Test KB");
    expect(screen.getByText("Create")).not.toBeDisabled();
  });

  it("submits and calls onCreated on success", async () => {
    const user = userEvent.setup();
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce({ data: null, requestId: "test-1" });

    render(<CreateKbForm onCreated={onCreated} />, { wrapper: Wrapper });

    await user.type(screen.getByPlaceholderText("Knowledge base name"), "Test KB");
    await user.type(screen.getByPlaceholderText("Description (optional)"), "A description");
    await user.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(mockApi).toHaveBeenCalledWith("/api/v1/knowledge-bases", {
        method: "POST",
        body: JSON.stringify({ name: "Test KB", description: "A description" }),
      });
    });

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalled();
    });
  });

  it("shows error on failure", async () => {
    const user = userEvent.setup();
    const mockApi = vi.mocked(api);
    mockApi.mockRejectedValueOnce(new Error("Name already exists"));

    render(<CreateKbForm onCreated={onCreated} />, { wrapper: Wrapper });

    await user.type(screen.getByPlaceholderText("Knowledge base name"), "Test KB");
    await user.click(screen.getByText("Create"));

    await waitFor(() => {
      const errors = screen.getAllByText("Name already exists");
      expect(errors.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("clears form after successful creation", async () => {
    const user = userEvent.setup();
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce({ data: null, requestId: "test-1" });

    render(<CreateKbForm onCreated={onCreated} />, { wrapper: Wrapper });

    await user.type(screen.getByPlaceholderText("Knowledge base name"), "Test KB");
    await user.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Knowledge base name")).toHaveValue("");
    });
  });
});
