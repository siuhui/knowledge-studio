import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Pagination } from "@/components/knowledge-bases/Pagination";
import type { PaginatedMeta } from "@/lib/types";

const baseMeta: PaginatedMeta = {
  page: 1,
  page_size: 10,
  total: 25,
  total_pages: 3,
};

describe("Pagination", () => {
  it("renders page info", () => {
    render(<Pagination meta={baseMeta} onPageChange={() => {}} />);
    expect(screen.getByText(/25 knowledge bases/)).toBeInTheDocument();
  });

  it("returns null when only one page", () => {
    const { container } = render(
      <Pagination meta={{ ...baseMeta, total_pages: 1, total: 3 }} onPageChange={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("disables Previous on first page", () => {
    render(<Pagination meta={baseMeta} onPageChange={() => {}} />);
    expect(screen.getByText("Previous")).toBeDisabled();
    expect(screen.getByText("Next")).not.toBeDisabled();
  });

  it("disables Next on last page", () => {
    render(<Pagination meta={{ ...baseMeta, page: 3 }} onPageChange={() => {}} />);
    expect(screen.getByText("Next")).toBeDisabled();
    expect(screen.getByText("Previous")).not.toBeDisabled();
  });

  it("disables both when loading", () => {
    render(<Pagination meta={baseMeta} onPageChange={() => {}} loading />);
    expect(screen.getByText("Previous")).toBeDisabled();
    expect(screen.getByText("Next")).toBeDisabled();
  });

  it("calls onPageChange when clicking Next", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination meta={baseMeta} onPageChange={onPageChange} />);
    await user.click(screen.getByText("Next"));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("calls onPageChange when clicking Previous", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination meta={{ ...baseMeta, page: 2 }} onPageChange={onPageChange} />);
    await user.click(screen.getByText("Previous"));
    expect(onPageChange).toHaveBeenCalledWith(1);
  });
});
