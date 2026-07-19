import { fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import { server } from "../test/server";
import { ResubmitNowButton } from "./ResubmitNowButton";

describe("ResubmitNowButton", () => {
  it("renders a Resubmit Now button", () => {
    renderWithQueryClient(<ResubmitNowButton />);

    expect(screen.getByRole("button", { name: /resubmit now/i })).toBeInTheDocument();
  });

  it("triggers the resubmit-application task when clicked", async () => {
    renderWithQueryClient(<ResubmitNowButton />);

    fireEvent.click(screen.getByRole("button", { name: /resubmit now/i }));

    await waitFor(() => {
      expect(screen.getByText(/resubmission triggered/i)).toBeInTheDocument();
    });
  });

  it("re-enables the button after the request settles", async () => {
    renderWithQueryClient(<ResubmitNowButton />);

    const button = screen.getByRole("button", { name: /resubmit now/i });
    fireEvent.click(button);

    await waitFor(() => expect(button).not.toBeDisabled());
  });

  it("shows an error message on failure", async () => {
    server.use(
      http.post("*/api/tasks/resubmit-application", () => HttpResponse.json(null, { status: 500 })),
    );
    renderWithQueryClient(<ResubmitNowButton />);

    fireEvent.click(screen.getByRole("button", { name: /resubmit now/i }));

    await waitFor(() => {
      expect(screen.getByText(/failed to trigger resubmission/i)).toBeInTheDocument();
    });
  });
});
