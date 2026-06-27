import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Mock next/navigation for components that use useRouter / usePathname / useParams
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/knowledge-bases",
  useParams: () => ({ id: "kb-1" }),
  useSearchParams: () => new URLSearchParams(),
}));
