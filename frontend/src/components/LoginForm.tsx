import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, login } from "../api/client";

interface LoginFormProps {
  onSuccess?: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const queryClient = useQueryClient();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      await queryClient.invalidateQueries({ queryKey: ["auth-session"] });
      onSuccess?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex max-w-xs flex-col gap-2">
      <div className="form-control">
        <label htmlFor="login-username" className="label">
          <span className="label-text">Username</span>
        </label>
        <input
          id="login-username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="input input-bordered input-sm"
        />
      </div>
      <div className="form-control">
        <label htmlFor="login-password" className="label">
          <span className="label-text">Password</span>
        </label>
        <input
          id="login-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input input-bordered input-sm"
        />
      </div>
      {error && <p className="text-error text-sm">{error}</p>}
      <button type="submit" className="btn btn-primary btn-sm" disabled={submitting}>
        Log in
      </button>
    </form>
  );
}
