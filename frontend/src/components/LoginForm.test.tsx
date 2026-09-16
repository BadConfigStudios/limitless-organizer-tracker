import { fireEvent, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import { server } from "../test/server";
import { LoginForm } from "./LoginForm";

describe("LoginForm", () => {
  it("renders username and password fields and a submit button", () => {
    renderWithQueryClient(<LoginForm />);

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log in/i })).toBeInTheDocument();
  });

  it("shows an error message on invalid credentials", async () => {
    server.use(
      http.post("*/api/auth/login", () =>
        HttpResponse.json({ detail: "Invalid username or password" }, { status: 401 }),
      ),
    );

    renderWithQueryClient(<LoginForm />);

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "owner" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    expect(await screen.findByText(/invalid username or password/i)).toBeInTheDocument();
  });

  it("calls onSuccess after a successful login", async () => {
    let called = false;
    renderWithQueryClient(<LoginForm onSuccess={() => (called = true)} />);

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: "owner" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "correct-horse" } });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    await screen.findByRole("button", { name: /log in/i }); // wait a tick for the async submit
    expect(called).toBe(true);
  });
});
