import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KbCard } from "@/components/knowledge-bases/KbCard";
import type { KnowledgeBase } from "@/lib/types";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/knowledge-bases",
  useParams: () => ({}),
}));

const mockKb: KnowledgeBase = {
  id: "kb-1",
  user_id: "user-1",
  name: "My Knowledge Base",
  description: "A test knowledge base",
  created_at: "2025-06-01T00:00:00Z",
  updated_at: "2025-06-15T00:00:00Z",
};

const mockKbNoDesc: KnowledgeBase = {
  id: "kb-2",
  user_id: "user-1",
  name: "No Description KB",
  description: null,
  created_at: "2025-06-01T00:00:00Z",
  updated_at: "2025-06-01T00:00:00Z",
};

describe("KbCard", () => {
  const onEdit = vi.fn();
  const onDelete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders knowledge base info", () => {
    render(<KbCard kb={mockKb} onEdit={onEdit} onDelete={onDelete} />);
    expect(screen.getByText("My Knowledge Base")).toBeInTheDocument();
    expect(screen.getByText("A test knowledge base")).toBeInTheDocument();
    expect(screen.getByLabelText("Rename knowledge base")).toBeInTheDocument();
    expect(screen.getByLabelText("Delete knowledge base")).toBeInTheDocument();
    expect(screen.getByText("Jun 1, 2025")).toBeInTheDocument();
  });

  it("renders without description", () => {
    render(<KbCard kb={mockKbNoDesc} onEdit={onEdit} onDelete={onDelete} />);
    expect(screen.getByText("No Description KB")).toBeInTheDocument();
    expect(screen.queryByText("A test knowledge base")).not.toBeInTheDocument();
  });

  it("navigates to workspace on click", async () => {
    const user = userEvent.setup();
    render(<KbCard kb={mockKb} onEdit={onEdit} onDelete={onDelete} />);

    await user.click(screen.getByText("My Knowledge Base"));

    expect(mockPush).toHaveBeenCalledWith("/knowledge-bases/kb-1");
  });

  it("calls onEdit when edit button is clicked", async () => {
    const user = userEvent.setup();
    render(<KbCard kb={mockKb} onEdit={onEdit} onDelete={onDelete} />);

    await user.click(screen.getByLabelText("Rename knowledge base"));

    expect(onEdit).toHaveBeenCalledWith(mockKb);
    // Should not navigate
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("calls onDelete when delete button is clicked", async () => {
    const user = userEvent.setup();
    render(<KbCard kb={mockKb} onEdit={onEdit} onDelete={onDelete} />);

    await user.click(screen.getByLabelText("Delete knowledge base"));

    expect(onDelete).toHaveBeenCalledWith(mockKb);
    // Should not navigate
    expect(mockPush).not.toHaveBeenCalled();
  });
});
